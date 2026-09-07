"""Ordered assertion-time analysis for return and captured-stream evidence."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from gaze_py.quality._identity import _ImportBinding, _target_identity, _TargetIdentity
from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.effects import SideEffectType

_CAPTURE_FIXTURES = frozenset({"capsys", "capfd"})
_STREAM_TYPES = {"out": SideEffectType.StdoutWrite, "err": SideEffectType.StderrWrite}


@dataclass(frozen=True)
class _Value:
    """Provenance held by one live local value."""

    streams: frozenset[SideEffectType] = frozenset()
    role: SideEffectType | None = None
    blocked: bool = False
    capture_result: bool = False
    family: int | None = None


@dataclass
class _State:
    """Mutable state for one ordered test-function scan."""

    fixtures: set[str]
    identity: _TargetIdentity
    imports: dict[str, _ImportBinding]
    lexical_locals: set[str]
    values: dict[str, _Value] = field(default_factory=dict)
    related_names: set[str] = field(default_factory=set)
    pending_target: bool = False
    tainted: bool = False
    next_family: int = 1


def _map_assertion_evidence(
    test_func: TestFunc,
    target_name: str,
    *,
    target_path: Path | None,
    import_root: Path | None,
    receiver: str | None,
) -> dict[tuple[int, int], SideEffectType | None]:
    """Return ordered assertion evidence, including explicit blocked entries."""
    parameters = _parameter_names(test_func.node)
    local_names = _function_local_names(test_func.node)
    imports = {
        alias.name: _ImportBinding(alias.module, alias.symbol)
        for alias in test_func.module_aliases
        if alias.name not in local_names
    }
    state = _State(
        fixtures=parameters & _CAPTURE_FIXTURES,
        identity=_target_identity(
            target_path, import_root, function=target_name, receiver=receiver
        ),
        imports=imports,
        lexical_locals=local_names,
    )
    result: dict[tuple[int, int], SideEffectType | None] = {}
    _scan_statements(test_func.node.body, state, result)
    return result


def _scan_statements(
    statements: list[ast.stmt],
    state: _State,
    result: dict[tuple[int, int], SideEffectType | None],
) -> bool:
    """Scan statements in execution order until unconditional termination."""
    for index, statement in enumerate(statements):
        if isinstance(statement, (ast.Return, ast.Raise)):
            value = statement.value if isinstance(statement, ast.Return) else statement.exc
            if value is not None:
                _observe_expression(value, state)
            for unreachable in statements[index + 1 :]:
                _block_contained_assertions(unreachable, state, result)
            return True
        if _scan_statement(statement, state, result):
            for unreachable in statements[index + 1 :]:
                _block_contained_assertions(unreachable, state, result)
            return True
    return False


def _scan_statement(
    statement: ast.stmt,
    state: _State,
    result: dict[tuple[int, int], SideEffectType | None],
) -> bool:
    """Apply one supported transition or quarantine unsupported control flow."""
    if isinstance(statement, ast.Assert):
        _scan_assertion(statement, state, result)
    elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
        _scan_assignment(statement, state)
    elif isinstance(statement, ast.Expr):
        _observe_expression(statement.value, state)
    elif isinstance(statement, (ast.Import, ast.ImportFrom)):
        _apply_import(statement, state)
    elif isinstance(statement, ast.Delete):
        for target in statement.targets:
            _invalidate_storage(target, state)
        state.tainted = True
    elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        _scan_definition(statement, state)
    elif isinstance(statement, ast.With):
        return _scan_with(statement, state, result)
    elif not isinstance(statement, ast.Pass):
        _scan_unsupported(statement, state, result)
    return False


def _scan_assertion(
    statement: ast.Assert,
    state: _State,
    result: dict[tuple[int, int], SideEffectType | None],
) -> None:
    """Record the live value role used by one assertion."""
    value = _evaluate(statement.test, state)
    position = (statement.lineno, statement.col_offset)
    if value is not None:
        if value.blocked:
            result[position] = None
        elif value.role is not None:
            result[position] = value.role
        elif len(value.streams) == 1:
            result[position] = next(iter(value.streams))
        else:
            result[position] = None
    _observe_calls(statement.test, state, expression_value=value)


def _scan_assignment(statement: ast.Assign | ast.AnnAssign, state: _State) -> None:
    """Evaluate assignment RHS before invalidating and replacing destinations."""
    value = statement.value
    if value is None:
        return
    evaluated = _evaluate(value, state)
    _observe_calls(value, state, expression_value=evaluated)
    targets = list(statement.targets) if isinstance(statement, ast.Assign) else [statement.target]
    if len(targets) != 1:
        blocked = _blocked_value(evaluated)
        for target in targets:
            _bind_unsupported_storage(target, blocked, state)
        return
    target = targets[0]
    if isinstance(value, ast.Call) and _is_legacy_target_call(value, state):
        evaluated = _Value(role=SideEffectType.ReturnValue)
    elif isinstance(value, ast.Call) and _has_target_name(value, state):
        evaluated = _Value(blocked=True)
    if isinstance(target, ast.Tuple) and _is_capture_read(value, state):
        _bind_capture_tuple(target, evaluated, state)
    elif isinstance(target, ast.Name):
        was_related = target.id in state.related_names
        _invalidate_name(target.id, state)
        if evaluated is not None:
            state.values[target.id] = evaluated
            state.related_names.add(target.id)
        elif was_related:
            state.values[target.id] = _Value(blocked=True)
    else:
        _bind_unsupported_storage(target, _blocked_value(evaluated), state)
        state.tainted = True


def _scan_definition(
    statement: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    state: _State,
) -> None:
    """Taint for executable headers without entering deferred bodies."""
    state.imports.pop(statement.name, None)
    state.values.pop(statement.name, None)
    if isinstance(statement, ast.ClassDef):
        state.tainted = True
    elif statement.decorator_list or any(
        isinstance(node, ast.Call) for node in _definition_header_nodes(statement)
    ):
        state.tainted = True


def _scan_with(
    statement: ast.With,
    state: _State,
    result: dict[tuple[int, int], SideEffectType | None],
) -> bool:
    """Scan a context body while treating entry and exit as possible producers."""
    state.tainted = True
    for item in statement.items:
        if item.optional_vars is not None:
            _invalidate_storage(item.optional_vars, state)
    if _scan_statements(statement.body, state, result):
        return True
    state.tainted = True
    return False


def _scan_unsupported(
    statement: ast.stmt,
    state: _State,
    result: dict[tuple[int, int], SideEffectType | None],
) -> None:
    """Quarantine branch-dependent calls, drains, stores, and assertions."""
    nodes = _walk_without_nested_bodies(statement)
    if any(isinstance(node, ast.Call) and _is_capture_read(node, state) for node in nodes):
        state.pending_target = False
    if any(isinstance(node, ast.Call) for node in nodes):
        state.tainted = True
    for node in nodes:
        if isinstance(node, ast.Call):
            _invalidate_referenced_families(node, state)
        elif isinstance(node, ast.Assert):
            result[(node.lineno, node.col_offset)] = None
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            existing = state.values.get(node.id)
            if existing is not None:
                _invalidate_families(existing, state)
            _invalidate_name(node.id, state)
        elif isinstance(node, ast.ImportFrom) and any(
            imported.name == "*" for imported in node.names
        ):
            state.imports.clear()


def _block_contained_assertions(
    statement: ast.stmt,
    state: _State,
    result: dict[tuple[int, int], SideEffectType | None],
) -> None:
    """Block capture-shaped assertions in unreachable syntax."""
    for node in _walk_without_nested_bodies(statement):
        if isinstance(node, ast.Assert):
            result[(node.lineno, node.col_offset)] = None


def _evaluate(node: ast.AST, state: _State) -> _Value | None:
    """Evaluate bounded value provenance without executing analyzed code."""
    if isinstance(node, ast.Name):
        return state.values.get(node.id)
    if isinstance(node, ast.Attribute):
        return _evaluate_attribute(node, state)
    if isinstance(node, ast.Subscript):
        return _evaluate_subscript(node, state)
    if isinstance(node, ast.Call):
        return _evaluate_call(node, state)
    if isinstance(node, ast.Lambda):
        return _Value(blocked=True) if _capture_related_syntax(node.body, state) else None
    return _evaluate_children(node, state)


def _evaluate_attribute(node: ast.Attribute, state: _State) -> _Value | None:
    """Resolve capture-result attributes and ordinary derived attributes."""
    base = _evaluate(node.value, state)
    if base is None:
        return None
    if base.capture_result and node.attr in _STREAM_TYPES:
        if base.blocked:
            return _Value(blocked=True)
        return _Value(streams=frozenset({_STREAM_TYPES[node.attr]}))
    return _Value(streams=base.streams, blocked=base.blocked, family=base.family)


def _evaluate_subscript(node: ast.Subscript, state: _State) -> _Value | None:
    """Preserve one JSON family's provenance through read-only indexing."""
    base = _evaluate(node.value, state)
    if base is not None and base.family is not None:
        if any(isinstance(item, ast.Call) for item in _walk_without_nested_bodies(node.slice)):
            return _blocked_value(base)
        index = _evaluate(node.slice, state)
        if index is not None:
            return _combine_values((base, index))
        return base
    return _combine_values(_evaluate(child, state) for child in ast.iter_child_nodes(node))


def _evaluate_call(node: ast.Call, state: _State) -> _Value | None:
    """Resolve supported calls and block arbitrary capture transformations."""
    if _is_capture_read(node, state):
        attributable = state.pending_target and not state.tainted
        state.pending_target = False
        state.tainted = False
        return _Value(capture_result=True, blocked=not attributable)
    if isinstance(node.func, ast.Attribute) and node.func.attr == "readouterr":
        return _Value(blocked=True)
    evaluated_inputs = tuple(_evaluate(child, state) for child in _call_value_inputs(node))
    if _is_json_loads(node, state):
        source = evaluated_inputs[1]
        if source is not None and not source.blocked and len(source.streams) == 1:
            family = state.next_family
            state.next_family += 1
            return _Value(streams=source.streams, family=family)
    related = _combine_values(evaluated_inputs)
    if related is not None:
        _invalidate_families(related, state)
        return _blocked_value(related)
    return None


def _evaluate_children(node: ast.AST, state: _State) -> _Value | None:
    """Combine child provenance and block expressions with unknown calls."""
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) or (
        isinstance(node, (ast.BoolOp, ast.IfExp))
        and any(isinstance(item, ast.Call) for item in _walk_without_nested_bodies(node))
    ):
        return _evaluate_uncertain_expression(node, state)
    combined = _combine_values(_evaluate(child, state) for child in ast.iter_child_nodes(node))
    if combined is not None and any(
        isinstance(item, ast.Call)
        and not _is_capture_read(item, state)
        and not (isinstance(item, ast.Call) and _is_json_loads(item, state))
        for item in _walk_without_nested_bodies(node)
    ):
        return _blocked_value(combined)
    return combined


def _evaluate_uncertain_expression(node: ast.AST, state: _State) -> _Value | None:
    """Quarantine calls whose execution depends on expression control flow."""
    nodes = _walk_without_nested_bodies(node)
    if any(isinstance(item, ast.Call) and _is_capture_read(item, state) for item in nodes):
        state.pending_target = False
    if any(isinstance(item, ast.Call) for item in nodes):
        state.tainted = True
    _invalidate_referenced_families(node, state)
    related = _combine_values(
        state.values.get(item.id) for item in nodes if isinstance(item, ast.Name)
    )
    if related is not None or _capture_related_syntax(node, state):
        return _blocked_value(related)
    return None


def _observe_expression(node: ast.expr, state: _State) -> None:
    """Apply call and capture-window effects for an expression statement."""
    value = _evaluate(node, state)
    _observe_calls(node, state, expression_value=value)


def _observe_calls(node: ast.AST, state: _State, *, expression_value: _Value | None) -> None:
    """Update the pending output window from definitely evaluated calls."""
    if isinstance(node, ast.Call) and _is_capture_read(node, state):
        return
    if isinstance(node, ast.Call) and _matches_target(node, state):
        nested = [
            call for call in _direct_calls_in_arguments(node) if not _is_json_loads(call, state)
        ]
        state.pending_target = True
        state.tainted = state.tainted or bool(nested)
        return
    calls = [item for item in _walk_without_nested_bodies(node) if isinstance(item, ast.Call)]
    unknown_calls = [
        call
        for call in calls
        if not _is_capture_read(call, state) and not _is_json_loads(call, state)
    ]
    if unknown_calls and (expression_value is None or not expression_value.capture_result):
        state.tainted = True


def _matches_target(call: ast.Call, state: _State) -> bool:
    """Resolve a call against immutable target identity and live imports."""
    return state.identity.matches(call, state.imports)


def _is_legacy_target_call(call: ast.Call, state: _State) -> bool:
    """Preserve bare-name return binding compatibility without capture credit."""
    if _matches_target(call, state):
        return True
    if not isinstance(call.func, ast.Name) or call.func.id != state.identity.function:
        return False
    return call.func.id not in state.imports and call.func.id not in state.lexical_locals


def _has_target_name(call: ast.Call, state: _State) -> bool:
    """Return whether a conflicting call still uses the target's bare name."""
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == state.identity.function
        or isinstance(call.func, ast.Attribute)
        and call.func.attr == state.identity.function
    )


def _is_capture_read(node: ast.AST, state: _State) -> bool:
    """Return whether node is an exact zero-argument fixture read."""
    return (
        isinstance(node, ast.Call)
        and not node.args
        and not node.keywords
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "readouterr"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in state.fixtures
    )


def _is_json_loads(node: ast.Call, state: _State) -> bool:
    """Return whether node is the supported unshadowed json.loads form."""
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        and node.func.attr == "loads"
        and len(node.args) == 1
        and not node.keywords
        and state.imports.get(node.func.value.id) == _ImportBinding("json")
    )


def _apply_import(statement: ast.Import | ast.ImportFrom, state: _State) -> None:
    """Apply a definite local import in execution order."""
    state.tainted = True
    if isinstance(statement, ast.Import):
        for imported in statement.names:
            local = imported.asname or imported.name.split(".", maxsplit=1)[0]
            module = imported.name if imported.asname is not None else local
            state.imports[local] = _ImportBinding(module)
            state.values.pop(local, None)
        return
    if statement.level != 0 or statement.module is None:
        state.imports.clear()
        return
    for imported in statement.names:
        if imported.name == "*":
            state.imports.clear()
        else:
            local = imported.asname or imported.name
            state.imports[local] = _ImportBinding(statement.module, imported.name)
            state.values.pop(local, None)


def _bind_capture_tuple(target: ast.Tuple, value: _Value | None, state: _State) -> None:
    """Bind exact two-name tuple capture unpacking."""
    if len(target.elts) != 2 or not all(isinstance(item, ast.Name) for item in target.elts):
        _bind_unsupported_storage(target, _blocked_value(value), state)
        return
    blocked = value is None or value.blocked
    for item, stream in zip(target.elts, _STREAM_TYPES.values(), strict=True):
        assert isinstance(item, ast.Name)
        _invalidate_name(item.id, state)
        state.values[item.id] = _Value(
            streams=frozenset() if blocked else frozenset({stream}), blocked=blocked
        )
        state.related_names.add(item.id)


def _bind_unsupported_storage(target: ast.expr, value: _Value, state: _State) -> None:
    """Retain blocked provenance across unsupported assignment storage."""
    if isinstance(target, ast.Name):
        existing = state.values.get(target.id)
        if existing is not None:
            _invalidate_families(existing, state)
        _invalidate_name(target.id, state)
        state.values[target.id] = value
        state.related_names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            _bind_unsupported_storage(item, value, state)
    else:
        _invalidate_referenced_families(target, state)
        for node in ast.walk(target):
            if isinstance(node, ast.Name):
                state.values[node.id] = value
                state.related_names.add(node.id)
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        if target.attr == state.identity.function:
            state.imports.pop(target.value.id, None)


def _invalidate_storage(target: ast.expr, state: _State) -> None:
    """Invalidate direct names without treating attribute bases as rebound."""
    if isinstance(target, ast.Name):
        _invalidate_name(target.id, state)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            _invalidate_storage(item, state)
    elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        if target.attr == state.identity.function:
            state.imports.pop(target.value.id, None)


def _invalidate_name(name: str, state: _State) -> None:
    """Remove all trusted roles for one rebound local name."""
    state.values.pop(name, None)
    state.imports.pop(name, None)
    state.fixtures.discard(name)


def _invalidate_families(value: _Value, state: _State) -> None:
    """Block every alias and descendant in an escaped JSON family."""
    if value.family is not None:
        for name, existing in tuple(state.values.items()):
            if existing.family == value.family:
                state.values[name] = _Value(blocked=True, family=value.family)


def _invalidate_referenced_families(node: ast.AST, state: _State) -> None:
    """Invalidate provenance families referenced by uncertain or escaping syntax."""
    families = {
        value.family
        for item in _walk_without_nested_bodies(node)
        if isinstance(item, ast.Name)
        if (value := state.values.get(item.id)) is not None and value.family is not None
    }
    for family in families:
        _invalidate_families(_Value(family=family), state)


def _blocked_value(value: _Value | None) -> _Value:
    """Return blocked provenance while retaining its family identity."""
    return _Value(blocked=True, family=value.family if value is not None else None)


def _combine_values(values: Iterable[_Value | None]) -> _Value | None:
    """Combine child provenance, preserving roles and rejecting mixed streams."""
    present = [value for value in values if isinstance(value, _Value)]
    if not present:
        return None
    streams = frozenset(stream for value in present for stream in value.streams)
    roles = {value.role for value in present if value.role is not None}
    families = {value.family for value in present if value.family is not None}
    return _Value(
        streams=streams,
        role=next(iter(roles)) if len(roles) == 1 else None,
        blocked=any(value.blocked for value in present) or len(streams) > 1,
        family=next(iter(families)) if len(families) == 1 else None,
    )


def _parameter_names(node: ast.FunctionDef) -> set[str]:
    """Return all parameter names, including variadic parameters."""
    names = {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    if node.args.vararg is not None:
        names.add(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.add(node.args.kwarg.arg)
    return names


def _function_local_names(node: ast.FunctionDef) -> set[str]:
    """Precompute lexical locals so later assignments shadow module imports."""
    names = _parameter_names(node)
    for item in _walk_without_nested_bodies(node):
        if item is node:
            continue
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(item.name)
        elif isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
            names.add(item.id)
        elif isinstance(item, ast.alias):
            names.add(item.asname or item.name.split(".", maxsplit=1)[0])
    return names


def _definition_header_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Return decorators, defaults, and all annotation descendants."""
    result: list[ast.AST] = [*node.decorator_list, *node.args.defaults]
    result.extend(default for default in node.args.kw_defaults if default is not None)
    args = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    result.extend(arg.annotation for arg in args if arg.annotation is not None)
    if node.args.vararg is not None and node.args.vararg.annotation is not None:
        result.append(node.args.vararg.annotation)
    if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
        result.append(node.args.kwarg.annotation)
    if node.returns is not None:
        result.append(node.returns)
    return [descendant for item in result for descendant in ast.walk(item)]


def _call_value_inputs(node: ast.Call) -> tuple[ast.AST, ...]:
    """Return receiver, positional, and keyword values used by a call."""
    callable_value: tuple[ast.AST, ...] = ()
    if isinstance(node.func, ast.Attribute):
        callable_value = (node.func.value,)
    elif isinstance(node.func, ast.Name):
        callable_value = (node.func,)
    return (*callable_value, *node.args, *(keyword.value for keyword in node.keywords))


def _direct_calls_in_arguments(node: ast.Call) -> list[ast.Call]:
    """Return calls in target arguments without entering deferred bodies."""
    return [
        item
        for argument in (*node.args, *(keyword.value for keyword in node.keywords))
        for item in _walk_without_nested_bodies(argument)
        if isinstance(item, ast.Call)
    ]


def _capture_related_syntax(node: ast.AST, state: _State) -> bool:
    """Return whether syntax uses known or structural capture provenance."""
    for item in _walk_without_nested_bodies(node):
        if isinstance(item, ast.Name) and item.id in state.values:
            return True
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
            if item.func.attr == "readouterr":
                return True
    return False


def _walk_without_nested_bodies(node: ast.AST) -> list[ast.AST]:
    """Walk syntax while excluding nested function, class, and lambda bodies."""
    result: list[ast.AST] = []
    stack = [node]
    while stack:
        current = stack.pop()
        result.append(current)
        if current is not node and isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        stack.extend(ast.iter_child_nodes(current))
    return result
