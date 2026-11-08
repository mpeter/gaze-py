"""Bounded recorded-invocation evidence consumed by the ordered test scanner."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from gaze_py.quality._identity import _collect_module_aliases, _TargetIdentity
from gaze_py.quality.models import _ImportBinding


@dataclass
class _InvocationEvidence:
    """One straight-line dictionary, fake, patch and selected-target exercise.

    Unsupported transitions permanently close this evidence window. No alias,
    branch, arbitrary mutation, or interprocedural value propagation is inferred.
    """

    record: str
    fake: ast.FunctionDef
    subprocess_name: str
    phase: int = 0

    def observe(
        self,
        statement: ast.stmt,
        *,
        identity: _TargetIdentity,
        imports: dict[str, _ImportBinding],
        monkeypatch_live: bool,
    ) -> bool:
        """Advance one definite statement; return whether it asserts the record."""
        if isinstance(statement, ast.Assert):
            if any(
                isinstance(node, (ast.Call, ast.NamedExpr)) for node in ast.walk(statement.test)
            ):
                self.phase = -1
            comparison = statement.test
            return (
                self.phase == 4
                and isinstance(comparison, ast.Compare)
                and isinstance(comparison.left, ast.Name)
                and comparison.left.id == self.record
                and len(comparison.ops) == 1
                and isinstance(comparison.ops[0], ast.Eq)
                and isinstance(comparison.comparators[0], ast.Dict)
                and all(
                    isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Constant, ast.Load))
                    for node in ast.walk(comparison.comparators[0])
                )
            )
        value = (
            statement.value
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Expr))
            else None
        )
        if self.phase == 0 and _empty_record(statement, self.record):
            self.phase = 1
        elif self.phase == 1 and statement is self.fake:
            self.phase = 2
        elif self.phase == 2 and monkeypatch_live and self._is_patch(value, identity, imports):
            self.phase = 3
        elif (
            self.phase == 3
            and isinstance(value, ast.Call)
            and identity.matches(value, imports)
            and _supported_exercise_storage(statement, self.record)
            and not any(
                isinstance(node, (ast.Call, ast.NamedExpr))
                for arg in (*value.args, *value.keywords)
                for node in ast.walk(arg)
            )
        ):
            self.phase = 4
        else:
            self.phase = -1
        return False

    def _is_patch(
        self,
        value: ast.expr | None,
        identity: _TargetIdentity,
        imports: dict[str, _ImportBinding],
    ) -> bool:
        """Require the live module-object form of pytest monkeypatch.setattr."""
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "monkeypatch"
            and value.func.attr == "setattr"
            and len(value.args) == 3
            and not value.keywords
        ):
            return False
        owner, member, replacement = value.args
        if not (
            isinstance(owner, ast.Attribute)
            and isinstance(owner.value, ast.Name)
            and owner.attr == self.subprocess_name
            and isinstance(member, ast.Constant)
            and member.value == "run"
            and isinstance(replacement, ast.Name)
            and replacement.id == self.fake.name
        ):
            return False
        binding = imports.get(owner.value.id)
        return (
            binding is not None
            and owner.attr not in binding.blocked_members
            and (
                (binding.module == identity.module and binding.symbol is None)
                or (
                    binding.symbol is not None
                    and f"{binding.module}.{binding.symbol}" == identity.module
                )
            )
        )


def _supported_exercise_storage(statement: ast.stmt, record: str) -> bool:
    """Reject a target-result store that overwrites the record or escapes."""
    if isinstance(statement, ast.Expr):
        return True
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
    elif isinstance(statement, ast.AnnAssign):
        target = statement.target
    else:
        return False
    return isinstance(target, ast.Name) and target.id != record


def _empty_record(statement: ast.stmt, name: str) -> bool:
    """Recognize a single fresh local dictionary, without aliases."""
    value: ast.expr | None
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target, value = statement.targets[0], statement.value
    elif isinstance(statement, ast.AnnAssign):
        target, value = statement.target, statement.value
    else:
        return False
    return (
        isinstance(target, ast.Name)
        and target.id == name
        and isinstance(value, ast.Dict)
        and not value.keys
    )


def _recorded_fake(node: ast.FunctionDef, imports: dict[str, _ImportBinding]) -> str | None:
    """Recognize a received-parameter update followed by a completed-process stub."""
    args = node.args
    imports = {
        name: binding
        for name, binding in imports.items()
        if name not in {arg.arg for arg in (*args.args, *args.posonlyargs, *args.kwonlyargs)}
        and (args.kwarg is None or name != args.kwarg.arg)
    }
    if (
        node.decorator_list
        or args.defaults
        or args.kwonlyargs
        or args.posonlyargs
        or len(args.args) != 1
        or args.kwarg is None
        or args.vararg is not None
        or len(node.body) != 2
        or any(
            isinstance(item, ast.Call)
            for arg in (*args.args, args.kwarg)
            if arg is not None and arg.annotation is not None
            for item in ast.walk(arg.annotation)
        )
        or (
            node.returns is not None
            and any(isinstance(item, ast.Call) for item in ast.walk(node.returns))
        )
    ):
        return None
    update, returned = node.body
    if not (
        isinstance(update, ast.Expr)
        and isinstance(update.value, ast.Call)
        and isinstance(update.value.func, ast.Attribute)
        and isinstance(update.value.func.value, ast.Name)
        and update.value.func.attr == "update"
        and not update.value.args
        and len(update.value.keywords) == 2
        and isinstance(returned, ast.Return)
        and isinstance(returned.value, ast.Call)
        and _TargetIdentity("subprocess", "CompletedProcess", None).matches(returned.value, imports)
    ):
        return None
    positional, keywords = update.value.keywords
    record = update.value.func.value.id
    if not (
        positional.arg is not None
        and isinstance(positional.value, ast.Name)
        and positional.value.id == args.args[0].arg
        and keywords.arg is None
        and isinstance(keywords.value, ast.Name)
        and keywords.value.id == args.kwarg.arg
        and record not in {args.args[0].arg, args.kwarg.arg, node.name}
    ):
        return None
    inputs = [*returned.value.args, *(kw.value for kw in returned.value.keywords)]
    if any(
        not isinstance(item, (ast.Name, ast.Constant))
        or (isinstance(item, ast.Name) and item.id != args.args[0].arg)
        for item in inputs
    ):
        return None
    return record


def _invocation_evidence(
    test_node: ast.FunctionDef,
    *,
    target_path: Path | None,
    identity: _TargetIdentity,
    imports: dict[str, _ImportBinding],
    test_path: Path,
) -> _InvocationEvidence | None:
    """Prepare a narrow candidate; the existing scanner owns live ordering."""
    fakes = [
        (node, record)
        for node in test_node.body
        if isinstance(node, ast.FunctionDef)
        if (record := _recorded_fake(node, imports)) is not None
    ]
    if (
        len(fakes) != 1
        or target_path is None
        or not target_path.is_file()
        or identity.module is None
        or not test_path.is_file()
        or not _imports_and_definitions_only(ast.parse(test_path.read_text(encoding="utf-8")))
    ):
        return None
    module = ast.parse(target_path.read_text(encoding="utf-8"))
    bindings = {binding.name: binding for binding in _collect_module_aliases(module)}
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == identity.function
    ]
    if (
        len(functions) != 1
        or functions[0].decorator_list
        or identity.receiver is not None
        or not _imports_and_definitions_only(module)
    ):
        return None
    function = functions[0]
    # No local shadowing of a module binding, including deferred assignments.
    local_names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    local_names.update(arg.arg for arg in ast.walk(function.args) if isinstance(arg, ast.arg))
    bindings = {name: binding for name, binding in bindings.items() if name not in local_names}
    boundary = _TargetIdentity("subprocess", "run", None)
    calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and boundary.matches(node, bindings)
    ]
    if len(calls) != 1 or not isinstance(calls[0].func, ast.Attribute):
        return None
    # Require an unconditional direct boundary call, not a branch/helper call.
    body = function.body[1:] if ast.get_docstring(function) is not None else function.body
    if not (
        body and isinstance(body[0], (ast.Assign, ast.AnnAssign)) and body[0].value is calls[0]
    ) or any(
        isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Lambda,
                ast.Import,
                ast.ImportFrom,
                ast.Global,
                ast.Nonlocal,
            ),
        )
        for stmt in function.body
        for node in ast.walk(stmt)
    ):
        return None
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and node is not calls[0]:
            if not (
                isinstance(node.func, ast.Name)
                and node.func.id == "RuntimeError"
                and "RuntimeError" not in bindings
                and "RuntimeError" not in local_names
                and not any(
                    isinstance(stmt, ast.FunctionDef) and stmt.name == "RuntimeError"
                    for stmt in module.body
                )
                and any(
                    isinstance(stmt, ast.Raise) and stmt.exc is node for stmt in ast.walk(function)
                )
            ):
                return None
    fake, record = fakes[0]
    assert isinstance(calls[0].func.value, ast.Name)
    return _InvocationEvidence(record, fake, calls[0].func.value.id)


def _imports_and_definitions_only(module: ast.Module) -> bool:
    """Reject untracked module-object mutations for from-package imports."""
    return all(
        isinstance(statement, (ast.Import, ast.ImportFrom))
        or (
            isinstance(statement, ast.FunctionDef)
            and not statement.decorator_list
            and not any(isinstance(node, ast.Call) for node in ast.walk(statement.args))
            and (
                statement.returns is None
                or not any(isinstance(node, ast.Call) for node in ast.walk(statement.returns))
            )
        )
        or (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
        for statement in module.body
    )
