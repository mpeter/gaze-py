"""Tests for quality/pairing.py — A.1 test-target pairing."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from gaze_py.quality.models import TestFunc

# CR-004: testing _extract_call_name directly because pair_to_targets() requires a
# full source_functions list and a TestFunc; the method/qualified-name distinction
# is cleaner to assert at the unit level without constructing elaborate fixtures.
from gaze_py.quality.pairing import _extract_call_name, find_test_functions, pair_to_targets
from gaze_py.taxonomy.models import FunctionTarget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_func(src: str, name: str = "test_foo") -> TestFunc:
    """Parse src and return a TestFunc for the named function."""
    module = ast.parse(textwrap.dedent(src))
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return TestFunc(name=name, filename="test_example.py", lineno=node.lineno, node=node)
    raise ValueError(f"Function {name!r} not found in source")


def _make_target(name: str) -> FunctionTarget:
    """Create a minimal FunctionTarget with the given name."""
    return FunctionTarget(
        name=name,
        file_path="src/example.py",
        line=1,
        complexity=1,
    )


# ---------------------------------------------------------------------------
# pair_to_targets tests
# ---------------------------------------------------------------------------


def test_pair_empty_source_functions() -> None:
    """Empty source_functions → unmatched immediately."""
    tf = _make_test_func("def test_foo() -> None: pass")
    result = pair_to_targets(tf, [])
    assert result.target_name is None
    assert result.inference_method == "unmatched"
    assert result.confidence == 0.0


def test_pair_name_convention_exact() -> None:
    """test_foo → foo → confidence 0.9 exact match."""
    tf = _make_test_func("def test_foo() -> None: pass")
    targets = [_make_target("foo"), _make_target("bar")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "foo"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.9


def test_pair_name_convention_case_insensitive() -> None:
    """test_foo → Foo (case-insensitive) → confidence 0.7."""
    tf = _make_test_func("def test_foo() -> None: pass")
    targets = [_make_target("Foo")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "Foo"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.7


def test_pair_call_graph_no_name_match() -> None:
    """No name match but call to source function found → confidence 0.8."""
    src = """
    def test_something() -> None:
        result = process_data(1, 2)
        assert result == 3
    """
    tf = _make_test_func(src, "test_something")
    targets = [_make_target("process_data"), _make_target("other_fn")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "process_data"
    assert result.inference_method == "call_graph"
    assert result.confidence == 0.8


def test_pair_unmatched() -> None:
    """No name match and no call found → None target."""
    tf = _make_test_func("def test_xyz() -> None: pass", "test_xyz")
    targets = [_make_target("alpha"), _make_target("beta")]
    result = pair_to_targets(tf, targets)
    assert result.target_name is None
    assert result.inference_method == "unmatched"
    assert result.confidence == 0.0


def test_pair_class_method() -> None:
    """Method of a Test* class is paired correctly."""
    src = """
    class TestMyClass:
        def test_process(self) -> None:
            process(1)
    """
    module = ast.parse(textwrap.dedent(src))
    class_node = module.body[0]
    assert isinstance(class_node, ast.ClassDef)
    method_node = class_node.body[0]
    assert isinstance(method_node, ast.FunctionDef)
    tf = TestFunc(
        name="test_process",
        filename="test_myclass.py",
        lineno=method_node.lineno,
        node=method_node,
    )
    targets = [_make_target("process")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "process"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.9


def test_pair_underscore_name() -> None:
    """test_process_items → process_items (exact match with underscores)."""
    tf = _make_test_func("def test_process_items() -> None: pass", "test_process_items")
    targets = [_make_target("process_items")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "process_items"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# find_test_functions tests
# ---------------------------------------------------------------------------


def test_find_test_functions(tmp_path: Path) -> None:
    """Returns only test_* prefixed functions, not helpers."""
    src = textwrap.dedent("""
    def test_alpha() -> None:
        pass

    def helper_setup() -> None:
        pass

    def test_beta() -> None:
        pass

    class TestSuite:
        def test_gamma(self) -> None:
            pass

        def setup_method(self) -> None:
            pass
    """)
    test_file = tmp_path / "test_example.py"
    test_file.write_text(src)
    results = find_test_functions(test_file)
    names = [tf.name for tf in results]
    assert "test_alpha" in names
    assert "test_beta" in names
    assert "test_gamma" in names
    assert "helper_setup" not in names
    assert "setup_method" not in names


def test_find_test_functions_empty_file(tmp_path: Path) -> None:
    """Empty file returns empty list."""
    test_file = tmp_path / "test_empty.py"
    test_file.write_text("")
    assert find_test_functions(test_file) == []


def test_find_test_functions_nonexistent(tmp_path: Path) -> None:
    """Non-existent file returns empty list (graceful degradation)."""
    assert find_test_functions(tmp_path / "missing.py") == []


# ---------------------------------------------------------------------------
# _extract_call_name tests
# ---------------------------------------------------------------------------


def test_extract_call_name_simple() -> None:
    """Simple name call → returns the name."""
    stmt = ast.parse("foo()").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    assert _extract_call_name(stmt.value) == "foo"


def test_extract_call_name_method() -> None:
    """Method call → returns None."""
    stmt = ast.parse("obj.method()").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    assert _extract_call_name(stmt.value) is None


def test_extract_call_name_qualified() -> None:
    """Qualified name call → returns None."""
    stmt = ast.parse("mod.fn()").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    assert _extract_call_name(stmt.value) is None
