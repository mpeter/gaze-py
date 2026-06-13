"""Tests for cyclomatic_complexity() — McCabe algorithm correctness.

All tests use inline source strings parsed via ast.parse(). No file I/O.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from gaze_py.analysis.complexity import cyclomatic_complexity

FIXTURES = Path(__file__).parent / "testdata" / "analysis"


def _parse_first_fn(source: str) -> ast.FunctionDef:
    """Parse source and return the first top-level FunctionDef."""
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node  # type: ignore[return-value]
    raise ValueError("No function found in source")


# ---------------------------------------------------------------------------
# Baseline: pure function → complexity 1
# ---------------------------------------------------------------------------


def test_pure_function_complexity_is_1() -> None:
    """Pure function with body 'pass' → complexity 1 (base)."""
    targets_file = FIXTURES / "pure_function.py"
    module = ast.parse(targets_file.read_text(encoding="utf-8"))
    fn_nodes = [n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert fn_nodes, "Expected at least one function in pure_function.py"
    result = cyclomatic_complexity(fn_nodes[0])
    assert result == 1


# ---------------------------------------------------------------------------
# High complexity fixture → complexity > 1
# ---------------------------------------------------------------------------


def test_high_complexity_function_greater_than_1() -> None:
    """high_complexity.py fixture has complexity > 1."""
    targets_file = FIXTURES / "high_complexity.py"
    module = ast.parse(targets_file.read_text(encoding="utf-8"))
    fn_nodes = [n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert fn_nodes, "Expected at least one function in high_complexity.py"
    result = cyclomatic_complexity(fn_nodes[0])
    assert result > 1, f"Expected complexity > 1 for high_complexity.py, got {result}"


# ---------------------------------------------------------------------------
# Nested function isolation — outer and inner scored independently
# ---------------------------------------------------------------------------


def test_nested_function_complexity_is_independent() -> None:
    """Outer function complexity does not include inner function's decision points."""
    source = """\
def outer():
    x = 1
    def inner(a, b, c):
        if a:
            return a
        elif b:
            return b
        else:
            return c
    return inner
"""
    module = ast.parse(source)
    outer = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "outer")
    # outer has no decision points of its own → complexity 1
    assert cyclomatic_complexity(outer) == 1


# ---------------------------------------------------------------------------
# Boolean operator: `if a and b:` → complexity 2 (1 base + 1 for BoolOp)
# ---------------------------------------------------------------------------


def test_bool_op_increments_complexity() -> None:
    """'if a and b:' → complexity 2 (1 base + 1 for the BoolOp)."""
    source = """\
def f(a, b):
    if a and b:
        return 1
    return 0
"""
    fn = _parse_first_fn(source)
    # if → +1, BoolOp (and, 2 values) → +1, base = 1 → total 3
    result = cyclomatic_complexity(fn)
    # if adds 1, BoolOp(and) with 2 values adds 1 → 1 + 1 + 1 = 3
    assert result == 3  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Comprehension if-filter → increments complexity
# ---------------------------------------------------------------------------


def test_comprehension_if_increments_complexity() -> None:
    """List comprehension with if-filter → complexity 2 (1 base + 1 for filter)."""
    source = """\
def f(items):
    return [x for x in items if x > 0]
"""
    fn = _parse_first_fn(source)
    result = cyclomatic_complexity(fn)
    # base 1 + comprehension if 1 = 2
    assert result == 2  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Parametrized: known complexity values for simple patterns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source,expected",
    [
        # No decision points → 1
        ("def f(): pass", 1),
        # Single if → 2
        ("def f(x):\n    if x:\n        return x\n    return 0", 2),
        # if + elif → 3
        (
            "def f(x, y):\n    if x:\n        return x"
            "\n    elif y:\n        return y\n    return 0",
            3,
        ),
        # for loop → 2
        ("def f(items):\n    for x in items:\n        pass", 2),
        # while loop → 2
        ("def f(x):\n    while x > 0:\n        x -= 1", 2),
        # try/except → 2
        ("def f():\n    try:\n        pass\n    except Exception:\n        pass", 2),
    ],
)
def test_complexity_known_values(source: str, expected: int) -> None:
    """Parametrized: known complexity values for simple patterns."""
    fn = _parse_first_fn(source)
    result = cyclomatic_complexity(fn)
    assert result == expected, f"Expected complexity {expected}, got {result} for:\n{source}"
