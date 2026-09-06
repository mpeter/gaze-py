"""Static import and target-call identity for capture provenance."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from gaze_py.quality.models import ModuleAlias


@dataclass
class TargetCallIdentity:
    """Resolve plain and statically imported qualified target calls.

    Attributes:
        target_name: Production function's bare name.
        module_aliases: Unshadowed local alias to absolute dotted module.
        target_path: Exact analyzed production module path, when available.
    """

    target_name: str
    module_aliases: dict[str, str]
    target_path: Path | None

    def matches(self, node: ast.Call) -> bool:
        """Return whether a call has plain or exact imported target identity."""
        if isinstance(node.func, ast.Name):
            return node.func.id == self.target_name
        if not isinstance(node.func, ast.Attribute) or node.func.attr != self.target_name:
            return False
        if not isinstance(node.func.value, ast.Name) or self.target_path is None:
            return False
        module = self.module_aliases.get(node.func.value.id)
        return module is not None and _module_matches_target(module, self.target_path)

    def shadow(self, name: str) -> None:
        """Remove an import alias overwritten within the test function."""
        self.module_aliases.pop(name, None)

    def is_module_alias(self, name: str, module: str) -> bool:
        """Return whether an unshadowed local name imports the exact module."""
        return self.module_aliases.get(name) == module


def collect_module_aliases(module: ast.Module) -> tuple[ModuleAlias, ...]:
    """Collect bounded absolute module imports from a parsed test module.

    Args:
        module: Parsed test module whose top-level imports are inspected.

    Returns:
        Immutable aliases for direct imports and absolute from-imports.

    Raises:
        None.
    """
    aliases: dict[str, str] = {}
    for statement in module.body:
        if isinstance(statement, ast.Import):
            for imported in statement.names:
                if imported.asname is not None or "." not in imported.name:
                    aliases[imported.asname or imported.name] = imported.name
        elif isinstance(statement, ast.ImportFrom):
            for imported in statement.names:
                local_name = imported.asname or imported.name
                aliases.pop(local_name, None)
                if statement.level == 0 and statement.module is not None and imported.name != "*":
                    aliases[local_name] = f"{statement.module}.{imported.name}"
        else:
            for name in _module_bound_names(statement):
                aliases.pop(name, None)
    return tuple(ModuleAlias(name, imported) for name, imported in aliases.items())


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
        stack.extend(ast.iter_child_nodes(node))
    return names


def _module_matches_target(module: str, target_path: Path) -> bool:
    """Match a complete dotted import to one concrete target module path."""
    module_parts = tuple(module.split("."))
    file_suffix = (*module_parts[:-1], f"{module_parts[-1]}.py")
    package_suffix = (*module_parts, "__init__.py")
    target_parts = target_path.resolve().parts
    return target_parts[-len(file_suffix) :] == file_suffix or (
        target_parts[-len(package_suffix) :] == package_suffix
    )
