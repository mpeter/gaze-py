"""Shared file-collection utilities for the analysis pipeline."""

from __future__ import annotations

from pathlib import Path

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
    }
)


def collect_py_files(path: Path) -> list[Path]:
    """Collect all .py files under path (recursively for directories).

    Skips common non-source directories per _SKIP_DIRS.

    Args:
        path: A .py file or a directory to scan recursively.

    Returns:
        Sorted list of .py file paths.
    """
    if path.is_file():
        return [path] if path.suffix == ".py" else []
    return sorted(p for p in path.rglob("*.py") if not any(part in _SKIP_DIRS for part in p.parts))
