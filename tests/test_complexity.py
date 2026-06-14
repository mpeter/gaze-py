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


def test_high_complexity_function_exact_value() -> None:
    """high_complexity.py fixture: exact cyclomatic complexity is 9.

    Breakdown (1 base + 8 decision points):
      Line 3:  if x > 0        → +1
      Line 4:  if y > 0        → +1
      Line 6:  elif z > 0      → +1 (ast.If in orelse)
      Line 10: elif flag        → +1 (ast.If in orelse)
      Line 11: for i in range   → +1
      Line 12: if i % 2 == 0   → +1
      Line 17: while z > 0     → +1
      Line 19: if z == 5       → +1
    Total: 1 + 8 = 9
    """
    targets_file = FIXTURES / "high_complexity.py"
    module = ast.parse(targets_file.read_text(encoding="utf-8"))
    fn_nodes = [n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert fn_nodes, "Expected at least one function in high_complexity.py"
    result = cyclomatic_complexity(fn_nodes[0])
    assert result == 9, f"Expected complexity 9, got {result}"  # noqa: PLR2004


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


# ---------------------------------------------------------------------------
# CX-002: Additional round-trip tests with exact known values
# ---------------------------------------------------------------------------


def test_assert_statement_increments_complexity() -> None:
    """CX-002: assert statement adds one branch point (base 1 + 1 assert = 2)."""
    source = "def f(x):\n    assert x > 0\n    return x\n"
    fn = _parse_first_fn(source)
    result = cyclomatic_complexity(fn)
    assert result == 2, f"Expected 2 (1 base + 1 assert), got {result}"  # noqa: PLR2004


def test_with_multi_item_increments_per_item() -> None:
    """CX-002: 'with a, b:' adds 2 (one per item); base + 2 = 3."""
    source = "def f():\n    with open('a') as x, open('b') as y:\n        pass\n"
    fn = _parse_first_fn(source)
    result = cyclomatic_complexity(fn)
    assert result == 3, f"Expected 3 (1 base + 2 with-items), got {result}"  # noqa: PLR2004


def test_multiple_except_handlers() -> None:
    """CX-002: two except clauses → +2; base + 2 = 3."""
    source = (
        "def f():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError:\n"
        "        pass\n"
        "    except TypeError:\n"
        "        pass\n"
    )
    fn = _parse_first_fn(source)
    result = cyclomatic_complexity(fn)
    assert result == 3, f"Expected 3 (1 base + 2 except handlers), got {result}"  # noqa: PLR2004


def test_chained_bool_op() -> None:
    """CX-002: 'a and b and c' is ONE BoolOp with 3 values → +2; base + 2 = 3."""
    source = "def f(a, b, c):\n    return a and b and c\n"
    fn = _parse_first_fn(source)
    result = cyclomatic_complexity(fn)
    # One BoolOp node: values=[a, b, c], len(values)-1 = 2 → +2. Base 1 + 2 = 3.
    assert result == 3, f"Expected 3 (1 base + BoolOp len-1=2), got {result}"  # noqa: PLR2004


def test_comprehension_multiple_if_filters() -> None:
    """CX-002: two if-filters in a comprehension → +2; base + 2 = 3."""
    source = "def f(items):\n    return [x for x in items if x > 0 if x < 10]\n"
    fn = _parse_first_fn(source)
    result = cyclomatic_complexity(fn)
    assert result == 3, f"Expected 3 (1 base + 2 comprehension ifs), got {result}"  # noqa: PLR2004


def test_nested_inner_function_scored_independently() -> None:
    """CX-002: inner function's complexity is scored independently of outer."""
    source = """\
def outer():
    x = 1
    def inner(a, b, c):
        if a:
            return a
        if b:
            return b
        return c
    return inner(x, x, x)
"""
    module = ast.parse(source)
    outer_node = next(n for n in module.body if isinstance(n, ast.FunctionDef))
    inner_node = next(
        n for n in ast.walk(outer_node) if isinstance(n, ast.FunctionDef) and n.name == "inner"
    )

    # Outer: no decision points of its own (nested function not counted)
    assert cyclomatic_complexity(outer_node) == 1, (
        f"Expected outer complexity 1, got {cyclomatic_complexity(outer_node)}"
    )
    # Inner: 2 if-statements → 1 base + 2 = 3
    assert cyclomatic_complexity(inner_node) == 3, (  # noqa: PLR2004
        f"Expected inner complexity 3, got {cyclomatic_complexity(inner_node)}"
    )
