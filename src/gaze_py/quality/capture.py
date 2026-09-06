"""Bounded AST provenance for pytest captured stdout and stderr assertions."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from gaze_py.quality.capture_identity import TargetCallIdentity
from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.effects import SideEffectType

_CAPTURE_FIXTURES = frozenset({"capsys", "capfd"})
_STREAM_TYPES = {
    "out": SideEffectType.StdoutWrite,
    "err": SideEffectType.StderrWrite,
}


@dataclass
class _CaptureState:
    """Mutable state for one straight-line test-function scan."""

    fixtures: set[str]
    target_identity: TargetCallIdentity
    pending_target: bool = False
    pending_ambiguous: bool = False
    capture_results: dict[str, bool] = field(default_factory=dict)
    values: dict[str, SideEffectType | None] = field(default_factory=dict)
    capture_related_names: set[str] = field(default_factory=set)


def map_capture_assertions(
    test_func: TestFunc,
    target_name: str,
    *,
    target_path: Path | None = None,
) -> dict[tuple[int, int], SideEffectType | None]:
    """Find capture-related assertions and their attributable stream effects.

    The analysis intentionally supports straight-line statements plus ``with``
    bodies. Other control flow is treated as ambiguous, and nested definition
    bodies are never inspected.

    Args:
        test_func: Test function whose AST supplies execution order.
        target_name: Production function name whose output is being mapped.
        target_path: Exact production module path for qualified-call identity.

    Returns:
        Assertion source positions mapped to a stream effect, or ``None`` when
        the assertion is capture-related but cannot be safely attributed.

    Raises:
        None.
    """
    parameter_names = {
        arg.arg
        for arg in (
            *test_func.node.args.posonlyargs,
            *test_func.node.args.args,
            *test_func.node.args.kwonlyargs,
        )
    }
    state = _CaptureState(
        fixtures=parameter_names & _CAPTURE_FIXTURES,
        target_identity=TargetCallIdentity(
            target_name=target_name,
            module_aliases={
                alias.name: alias.module
                for alias in test_func.module_aliases
                if alias.name not in parameter_names
            },
            target_path=target_path,
        ),
    )
    result: dict[tuple[int, int], SideEffectType | None] = {}
    _scan_statements(
        test_func.node.body,
        state=state,
        result=result,
    )
    return result


def _scan_statements(
    statements: list[ast.stmt],
    *,
    state: _CaptureState,
    result: dict[tuple[int, int], SideEffectType | None],
) -> None:
    """Scan a sequence of statements in lexical order."""
    for statement in statements:
        _scan_statement(statement, state=state, result=result)


def _scan_statement(
    statement: ast.stmt,
    *,
    state: _CaptureState,
    result: dict[tuple[int, int], SideEffectType | None],
) -> None:
    """Apply one statement's bounded provenance transition."""
    if _handle_rebinding_statement(statement, state):
        return
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        _scan_definition(statement, state)
        return
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        _scan_with(statement, state=state, result=result)
        return
    if isinstance(statement, ast.Assert):
        _scan_assertion(statement, state, result)
        return
    if isinstance(statement, (ast.Assign, ast.AnnAssign)):
        _scan_assignment(statement, state)
        return
    if isinstance(statement, ast.Expr):
        related, _ = _expression_streams(statement.value, state)
        if not related:
            _update_pending_from_calls(statement.value, state)
        return

    # Branches and loops need path-sensitive execution to establish order.
    state.pending_ambiguous = state.pending_target or state.pending_ambiguous
    for node in _iter_without_nested_definitions(statement):
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Store):
            _invalidate_target(node, state)


def _handle_rebinding_statement(statement: ast.stmt, state: _CaptureState) -> bool:
    """Invalidate aliases rebound by uncommon straight-line syntax."""
    for node in _iter_without_nested_definitions(statement):
        if isinstance(node, ast.NamedExpr):
            _invalidate_target(node.target, state)
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        _shadow_import_bindings(statement, state)
        state.pending_ambiguous = True
        return True
    if isinstance(statement, ast.Delete):
        for target in statement.targets:
            _invalidate_target(target, state)
        state.pending_ambiguous = True
        return True
    return False


def _scan_assertion(
    statement: ast.Assert,
    state: _CaptureState,
    result: dict[tuple[int, int], SideEffectType | None],
) -> None:
    """Record one capture assertion or update pending producer state."""
    related, streams = _expression_streams(statement.test, state)
    if related:
        effect_type = (
            None if _has_unrelated_call(statement.test, state) else _single_stream(streams)
        )
        result[(statement.lineno, statement.col_offset)] = effect_type
    else:
        _update_pending_from_calls(statement.test, state)


def _scan_definition(
    statement: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    state: _CaptureState,
) -> None:
    """Account for executable definition headers without entering their bodies."""
    if isinstance(statement, ast.ClassDef) or _definition_header_has_effect(statement):
        state.pending_ambiguous = True


def _scan_with(
    statement: ast.With | ast.AsyncWith,
    *,
    state: _CaptureState,
    result: dict[tuple[int, int], SideEffectType | None],
) -> None:
    """Scan a context body while conservatively accounting for enter and exit."""
    state.pending_ambiguous = True
    for item in statement.items:
        if item.optional_vars is not None:
            _invalidate_target(item.optional_vars, state)
    _scan_statements(
        statement.body,
        state=state,
        result=result,
    )
    state.pending_ambiguous = True


def _scan_assignment(
    statement: ast.Assign | ast.AnnAssign,
    state: _CaptureState,
) -> None:
    """Update capture provenance and pending-output state for an assignment."""
    value = statement.value
    if value is None:
        return
    targets: list[ast.expr]
    if isinstance(statement, ast.Assign):
        targets = list(statement.targets)
    else:
        targets = [statement.target]
    for target in targets:
        _invalidate_target(target, state)

    capture_call = _capture_call(value, state.fixtures)
    if capture_call is not None:
        attributable = state.pending_target and not state.pending_ambiguous
        _bind_capture_value(targets, value, attributable=attributable, state=state)
        state.pending_target = False
        state.pending_ambiguous = False
        return

    related, streams = _expression_streams(value, state)
    if related:
        stream = _single_stream(streams)
        for target in targets:
            if isinstance(target, ast.Name):
                state.values[target.id] = stream
                state.capture_related_names.add(target.id)
        return

    _update_pending_from_calls(value, state)


def _bind_capture_value(
    targets: list[ast.expr],
    value: ast.expr,
    *,
    attributable: bool,
    state: _CaptureState,
) -> None:
    """Bind the supported tuple, result-object, and direct-attribute forms."""
    if len(targets) != 1:
        return
    target = targets[0]
    stream_type = _capture_attribute_type(value)
    if isinstance(target, ast.Name) and stream_type is None:
        state.capture_results[target.id] = attributable
        state.capture_related_names.add(target.id)
        return
    if isinstance(target, ast.Name):
        state.values[target.id] = stream_type if attributable else None
        state.capture_related_names.add(target.id)
        return
    if isinstance(target, (ast.Tuple, ast.List)):
        for index, element in enumerate(target.elts[:2]):
            if isinstance(element, ast.Name):
                effect_type = (
                    SideEffectType.StdoutWrite if index == 0 else SideEffectType.StderrWrite
                )
                state.values[element.id] = effect_type if attributable else None
                state.capture_related_names.add(element.id)


def _expression_streams(
    expression: ast.AST,
    state: _CaptureState,
) -> tuple[bool, set[SideEffectType]]:
    """Resolve capture provenance used by an expression."""
    direct = _direct_expression_streams(expression, state)
    if direct is not None:
        return direct
    if isinstance(expression, ast.Call) and _is_json_loads(expression, state):
        return _expression_streams(expression.args[0], state)
    if isinstance(expression, ast.Call):
        related = False
        for child in (*expression.args, *(keyword.value for keyword in expression.keywords)):
            child_related, _ = _expression_streams(child, state)
            related = related or child_related
        if related:
            return True, set()

    related = False
    streams: set[SideEffectType] = set()
    for descendant in ast.iter_child_nodes(expression):
        child_related, child_streams = _expression_streams(descendant, state)
        related = related or child_related
        streams.update(child_streams)
    return related, streams


def _direct_expression_streams(
    expression: ast.AST,
    state: _CaptureState,
) -> tuple[bool, set[SideEffectType]] | None:
    """Resolve direct names, attributes, and consuming capture calls."""
    if isinstance(expression, ast.Name) and expression.id in state.capture_related_names:
        effect_type = state.values.get(expression.id)
        return True, {effect_type} if effect_type is not None else set()
    if isinstance(expression, ast.Attribute):
        attribute_result = _attribute_streams(expression, state)
        if attribute_result is not None:
            return attribute_result
    if isinstance(expression, ast.Call) and _capture_call(expression, state.fixtures) is not None:
        state.pending_target = False
        state.pending_ambiguous = False
        return True, set()
    return None


def _attribute_streams(
    expression: ast.Attribute,
    state: _CaptureState,
) -> tuple[bool, set[SideEffectType]] | None:
    """Resolve capture-result and inline capture stream attributes."""
    if isinstance(expression.value, ast.Name) and expression.value.id in state.capture_results:
        effect_type = _STREAM_TYPES.get(expression.attr)
        if effect_type is None or not state.capture_results[expression.value.id]:
            return True, set()
        return True, {effect_type}
    capture_call = _capture_call(expression.value, state.fixtures)
    if capture_call is not None and expression.attr in _STREAM_TYPES:
        attributable = state.pending_target and not state.pending_ambiguous
        state.pending_target = False
        state.pending_ambiguous = False
        return True, {_STREAM_TYPES[expression.attr]} if attributable else set()
    if _is_readouterr_call(expression.value) and expression.attr in _STREAM_TYPES:
        return True, set()
    return None


def _capture_call(node: ast.AST, fixtures: set[str]) -> ast.Call | None:
    """Return a recognized fixture ``readouterr`` call within node."""
    candidate = node.value if isinstance(node, ast.Attribute) else node
    if not isinstance(candidate, ast.Call) or candidate.args or candidate.keywords:
        return None
    function = candidate.func
    if not isinstance(function, ast.Attribute) or function.attr != "readouterr":
        return None
    if isinstance(function.value, ast.Name) and function.value.id in fixtures:
        return candidate
    return None


def _is_readouterr_call(node: ast.AST) -> bool:
    """Return whether node structurally calls any object's ``readouterr``."""
    candidate = node.value if isinstance(node, ast.Attribute) else node
    return (
        isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Attribute)
        and candidate.func.attr == "readouterr"
    )


def _capture_attribute_type(node: ast.expr) -> SideEffectType | None:
    """Return the stream type for a direct capture-call attribute."""
    if isinstance(node, ast.Attribute):
        return _STREAM_TYPES.get(node.attr)
    return None


def _single_stream(streams: set[SideEffectType]) -> SideEffectType | None:
    """Return one unambiguous stream, rejecting absent or mixed provenance."""
    if len(streams) == 1:
        return next(iter(streams))
    return None


def _is_json_loads(node: ast.Call, state: _CaptureState) -> bool:
    """Return whether node is the bounded value-preserving ``json.loads`` call."""
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        and node.func.attr == "loads"
        and len(node.args) == 1
        and not node.keywords
        and state.target_identity.is_module_alias("json", "json")
    )


def _has_unrelated_call(node: ast.AST, state: _CaptureState) -> bool:
    """Return whether a capture assertion also invokes an unsupported call."""
    return any(
        not _is_json_loads(descendant, state) and _capture_call(descendant, state.fixtures) is None
        for descendant in _iter_without_nested_definitions(node)
        if isinstance(descendant, ast.Call)
    )


def _definition_header_has_effect(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether a nested function header can invoke user code."""
    if node.decorator_list:
        return True
    header_nodes: list[ast.AST] = [*node.args.defaults]
    header_nodes.extend(default for default in node.args.kw_defaults if default is not None)
    header_nodes.extend(arg.annotation for arg in node.args.args if arg.annotation is not None)
    header_nodes.extend(
        arg.annotation for arg in node.args.kwonlyargs if arg.annotation is not None
    )
    if node.returns is not None:
        header_nodes.append(node.returns)
    return any(
        isinstance(descendant, ast.Call)
        for header in header_nodes
        for descendant in _iter_without_nested_definitions(header)
    )


def _update_pending_from_calls(node: ast.AST, state: _CaptureState) -> None:
    """Open or taint the pending capture window based on calls in one expression."""
    calls = [item for item in _iter_without_nested_definitions(node) if isinstance(item, ast.Call)]
    target_calls = [call for call in calls if state.target_identity.matches(call)]
    unrelated_calls = [
        call
        for call in calls
        if not state.target_identity.matches(call)
        and _capture_call(call, state.fixtures) is None
        and not _is_json_loads(call, state)
    ]
    if target_calls:
        state.pending_target = True
        state.pending_ambiguous = state.pending_ambiguous or bool(unrelated_calls)
    elif unrelated_calls:
        state.pending_ambiguous = True


def _invalidate_target(target: ast.expr, state: _CaptureState) -> None:
    """Remove saved provenance for names overwritten by an assignment."""
    for node in ast.walk(target):
        if isinstance(node, ast.Name):
            if node.id in state.values or node.id in state.capture_results:
                state.capture_related_names.add(node.id)
            state.values.pop(node.id, None)
            state.capture_results.pop(node.id, None)
            state.fixtures.discard(node.id)
            state.target_identity.shadow(node.id)


def _shadow_import_bindings(
    statement: ast.Import | ast.ImportFrom,
    state: _CaptureState,
) -> None:
    """Invalidate local names rebound by imports inside the test function."""
    for imported in statement.names:
        if imported.name == "*":
            state.target_identity.module_aliases.clear()
            continue
        local_name = imported.asname or imported.name.split(".", maxsplit=1)[0]
        state.target_identity.shadow(local_name)


def _iter_without_nested_definitions(node: ast.AST) -> list[ast.AST]:
    """Return descendants while excluding nested executable definition bodies."""
    result: list[ast.AST] = []
    stack = [node]
    while stack:
        current = stack.pop()
        result.append(current)
        if isinstance(
            current,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            continue
        stack.extend(ast.iter_child_nodes(current))
    return result
