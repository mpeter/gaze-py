"""Canonical static identities used by quality analysis internals."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path

from gaze_py.quality.models import _ImportBinding


@dataclass(frozen=True)
class _TargetIdentity:
    """Exact canonical identity for one production callable."""

    module: str | None
    function: str
    receiver: str | None

    def matches(self, call: ast.Call, bindings: dict[str, _ImportBinding]) -> bool:
        """Return whether a call resolves exactly to this module-level target."""
        if self.module is None or self.receiver is not None:
            return False
        if isinstance(call.func, ast.Name):
            binding = bindings.get(call.func.id)
            return (
                binding is not None
                and binding.module == self.module
                and binding.symbol == self.function
                and self.function not in binding.blocked_members
            )
        if not isinstance(call.func, ast.Attribute) or call.func.attr != self.function:
            return False
        if not isinstance(call.func.value, ast.Name):
            return False
        binding = bindings.get(call.func.value.id)
        return (
            binding is not None
            and binding.module == self.module
            and binding.symbol is None
            and self.function not in binding.blocked_members
        )


def _target_identity(
    target_path: Path | None,
    import_root: Path | None,
    *,
    function: str,
    receiver: str | None,
) -> _TargetIdentity:
    """Build an exact target identity from an authoritative import root."""
    module = None
    if target_path is not None and import_root is not None:
        module = _module_name(target_path.resolve(), import_root.resolve())
    return _TargetIdentity(module=module, function=function, receiver=receiver)


def _module_name(file_path: Path, import_root: Path) -> str | None:
    """Return a dotted module only when file_path is beneath import_root."""
    try:
        relative = file_path.relative_to(import_root)
    except ValueError:
        return None
    parts = list(relative.parts)
    if not parts or not parts[-1].endswith(".py"):
        return None
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts) or None


def _import_root(file_path: Path) -> Path:
    """Return the canonical package import root for a resolved Python file."""
    current = file_path.parent
    while (current / "__init__.py").exists():
        parent = current.parent
        if parent == current:
            break
        current = parent
    return current


def _collect_module_aliases(module: ast.Module) -> tuple[_ImportBinding, ...]:
    """Collect ordered module-level imports that remain unshadowed."""
    aliases: dict[str, _ImportBinding] = {}
    blocked_by_module: dict[str, frozenset[str]] = {}
    for statement in module.body:
        if isinstance(statement, ast.Import):
            for imported in statement.names:
                local_name = imported.asname or imported.name.split(".", maxsplit=1)[0]
                bound_module = imported.name if imported.asname is not None else local_name
                aliases[local_name] = _ImportBinding(
                    local_name,
                    bound_module,
                    blocked_members=blocked_by_module.get(bound_module, frozenset()),
                )
        elif isinstance(statement, ast.ImportFrom):
            for imported in statement.names:
                if imported.name == "*":
                    aliases.clear()
                    continue
                local_name = imported.asname or imported.name
                aliases.pop(local_name, None)
                if statement.level == 0 and statement.module is not None:
                    aliases[local_name] = _ImportBinding(
                        local_name,
                        statement.module,
                        imported.name,
                        blocked_by_module.get(statement.module, frozenset()),
                    )
        else:
            if any(
                isinstance(node, ast.ImportFrom)
                and any(imported.name == "*" for imported in node.names)
                for node in ast.walk(statement)
            ):
                aliases.clear()
            for name in _module_bound_names(statement):
                aliases.pop(name, None)
            _record_stored_members(statement, aliases, blocked_by_module)
    return tuple(aliases.values())


def _record_stored_members(
    statement: ast.stmt,
    aliases: dict[str, _ImportBinding],
    blocked_by_module: dict[str, frozenset[str]],
) -> None:
    """Propagate module member replacement facts across every live alias."""
    for name, member in _stored_members(statement):
        binding = aliases.get(name)
        if binding is None or binding.symbol is not None:
            continue
        blocked = blocked_by_module.get(binding.module, frozenset()) | {member}
        blocked_by_module[binding.module] = blocked
        for alias_name, alias in tuple(aliases.items()):
            if alias.module == binding.module and alias.symbol is None:
                aliases[alias_name] = replace(alias, blocked_members=blocked)


def _module_bound_names(statement: ast.stmt) -> set[str]:
    """Collect names rebound by one module statement without entering definitions."""
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {statement.name}
    names: set[str] = set()
    stack: list[ast.AST] = [statement]
    while stack:
        node = stack.pop()
        if node is not statement and isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.alias) and node.name != "*":
            names.add(node.asname or node.name.split(".", maxsplit=1)[0])
        stack.extend(ast.iter_child_nodes(node))
    return names


def _stored_members(node: ast.AST) -> set[tuple[str, str]]:
    """Return direct ``name.member`` stores without entering deferred bodies."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return set()
    members: set[tuple[str, str]] = set()
    for item in _walk_binding_scope(node):
        if (
            isinstance(item, ast.Attribute)
            and isinstance(item.ctx, (ast.Store, ast.Del))
            and isinstance(item.value, ast.Name)
        ):
            members.add((item.value.id, item.attr))
    return members


def _walk_binding_scope(node: ast.AST) -> list[ast.AST]:
    """Walk binding syntax while excluding nested deferred bodies."""
    result: list[ast.AST] = []
    stack = [node]
    while stack:
        current = stack.pop()
        result.append(current)
        if current is not node and isinstance(
            current,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            continue
        stack.extend(ast.iter_child_nodes(current))
    return result
