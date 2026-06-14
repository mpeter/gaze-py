"""Tests for quality/assertions.py — A.2 assertion detection."""

from __future__ import annotations

import ast
import textwrap

# CR-004: testing _extract_referenced_names directly because detect_assertions()
# requires a full TestFunc with a parsed AST node; verifying the name-extraction
# logic for Attribute, Subscript, and Call node types requires direct access to
# the helper without constructing elaborate TestFunc fixtures for each case.
from gaze_py.quality.assertions import _extract_referenced_names, detect_assertions
from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.models import AssertionKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_func(src: str, name: str = "test_example") -> TestFunc:
    """Parse src and return a TestFunc for the named function."""
    module = ast.parse(textwrap.dedent(src))
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return TestFunc(
                name=name,
                filename="test_example.py",
                lineno=node.lineno,
                node=node,
            )
    raise ValueError(f"Function {name!r} not found in source")


# ---------------------------------------------------------------------------
# Basic assertion kind detection
# ---------------------------------------------------------------------------


def test_stdlib_equality_simple() -> None:
    """assert x == y → STDLIB_EQUALITY, referenced_names includes x and y."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert x == y
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_EQUALITY
    assert "x" in sites[0].referenced_names
    assert "y" in sites[0].referenced_names


def test_stdlib_equality_function_calls() -> None:
    """assert f() == g() → STDLIB_EQUALITY, referenced_names includes f and g."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert f() == g()
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_EQUALITY
    assert "f" in sites[0].referenced_names
    assert "g" in sites[0].referenced_names


def test_stdlib_equality_subscript() -> None:
    """assert result[0] == expected → STDLIB_EQUALITY, referenced_names includes result."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert result[0] == expected
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_EQUALITY
    assert "result" in sites[0].referenced_names


def test_stdlib_equality_attribute() -> None:
    """assert obj.value == 42 → STDLIB_EQUALITY, referenced_names includes obj."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert obj.value == 42
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_EQUALITY
    assert "obj" in sites[0].referenced_names


def test_stdlib_none_check() -> None:
    """assert x is None → STDLIB_NONE_CHECK."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert x is None
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_NONE_CHECK


def test_stdlib_error_check() -> None:
    """assert err is None → STDLIB_ERROR_CHECK (name contains 'err')."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert err is None
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_ERROR_CHECK


def test_stdlib_truth() -> None:
    """assert x → STDLIB_TRUTH."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert x
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_TRUTH


def test_stdlib_raises() -> None:
    """with pytest.raises(ValueError): → STDLIB_RAISES."""
    tf = _make_test_func("""
    def test_example() -> None:
        with pytest.raises(ValueError):
            do_something()
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.STDLIB_RAISES


def test_unittest_equal() -> None:
    """self.assertEqual(a, b) → UNITTEST_EQUAL."""
    tf = _make_test_func("""
    def test_example(self) -> None:
        self.assertEqual(a, b)
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.UNITTEST_EQUAL


def test_unittest_none() -> None:
    """self.assertIsNone(x) → UNITTEST_NONE."""
    tf = _make_test_func("""
    def test_example(self) -> None:
        self.assertIsNone(x)
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.UNITTEST_NONE


def test_unittest_raises() -> None:
    """self.assertRaises(Err, fn) → UNITTEST_RAISES."""
    tf = _make_test_func("""
    def test_example(self) -> None:
        self.assertRaises(ValueError, fn)
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    assert sites[0].kind == AssertionKind.UNITTEST_RAISES


def test_no_assertions() -> None:
    """Function with no assertions → empty list."""
    tf = _make_test_func("""
    def test_example() -> None:
        x = compute(1, 2)
    """)
    sites = detect_assertions(tf)
    assert sites == []


# ---------------------------------------------------------------------------
# Location format
# ---------------------------------------------------------------------------


def test_location_three_part_format() -> None:
    """Location uses three-part 'file:line:col' format."""
    tf = _make_test_func("""
    def test_example() -> None:
        assert x == y
    """)
    sites = detect_assertions(tf)
    assert len(sites) == 1
    parts = sites[0].location.split(":")
    assert len(parts) == 3, f"Expected 3 parts in location, got: {sites[0].location!r}"
    assert parts[0] == "test_example.py"
    assert parts[1].isdigit()
    assert parts[2].isdigit()


# ---------------------------------------------------------------------------
# Helper recursion
# ---------------------------------------------------------------------------


def test_helper_recursion() -> None:
    """assert_helper called from test body → assertions inside helper detected at depth=1."""
    helper_src = textwrap.dedent("""
    def assert_helper(x: int) -> None:
        assert x == 42
    """)
    helper_module = ast.parse(helper_src)

    tf = _make_test_func("""
    def test_example() -> None:
        result = compute()
        assert_helper(result)
    """)
    pkg_ast = {"helper.py": helper_module}
    sites = detect_assertions(tf, pkg_ast=pkg_ast)
    # Should find the assertion inside the helper at depth=1.
    assert any(s.depth == 1 for s in sites)
    assert any(s.kind == AssertionKind.STDLIB_EQUALITY for s in sites)


def test_helper_depth_limit() -> None:
    """assert_* at depth=max_depth not recursed into further."""
    # Build a chain: test → assert_a (depth=1) → assert_b (depth=2) → assert_c (depth=3)
    # With max_depth=2, assert_c should NOT be recursed into.
    helper_src = textwrap.dedent("""
    def assert_a(x: int) -> None:
        assert_b(x)

    def assert_b(x: int) -> None:
        assert_c(x)

    def assert_c(x: int) -> None:
        assert x == 99
    """)
    helper_module = ast.parse(helper_src)
    tf = _make_test_func("""
    def test_example() -> None:
        assert_a(result)
    """)
    pkg_ast = {"helper.py": helper_module}
    # With max_depth=2: test(0) → assert_a(1) → assert_b(2) → assert_c would be depth=3
    # but max_depth=2 stops recursion at depth==max_depth.
    sites = detect_assertions(tf, pkg_ast=pkg_ast, max_depth=2)
    # assert_c at depth=3 should NOT be found.
    assert not any(s.kind == AssertionKind.STDLIB_EQUALITY and s.depth == 3 for s in sites)


# ---------------------------------------------------------------------------
# _extract_referenced_names tests
# ---------------------------------------------------------------------------


def test_extract_names_simple_name() -> None:
    """ast.Name → adds the name id."""
    expr = ast.parse("x", mode="eval").body
    assert isinstance(expr, ast.Name)
    names = _extract_referenced_names(expr)
    assert "x" in names


def test_extract_names_attribute() -> None:
    """ast.Attribute → adds attr and base name."""
    expr = ast.parse("obj.value", mode="eval").body
    assert isinstance(expr, ast.Attribute)
    names = _extract_referenced_names(expr)
    assert "obj" in names
    assert "value" in names


def test_extract_names_subscript() -> None:
    """ast.Subscript → adds base name."""
    expr = ast.parse("result[0]", mode="eval").body
    assert isinstance(expr, ast.Subscript)
    names = _extract_referenced_names(expr)
    assert "result" in names


def test_extract_names_call() -> None:
    """ast.Call → adds function name."""
    expr = ast.parse("f()", mode="eval").body
    assert isinstance(expr, ast.Call)
    names = _extract_referenced_names(expr)
    assert "f" in names
