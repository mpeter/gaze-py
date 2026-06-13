"""Tests for gaze_py.quality — assertion mapper and contract coverage.

Each test maps to a spec acceptance scenario (SC-NNN) from
``specs/001-gaze-py-engine/spec.md`` User Story 2.  Tests are written
BEFORE the implementation exists (TDD) and MUST fail with
``ModuleNotFoundError`` until ``src/gaze_py/quality.py`` is created.

Convention pack compliance:
- TC-001: pytest only, no unittest.TestCase
- TC-002: direct assert statements
- TC-003: descriptive test names matching SC-NNN identifiers
- TC-007: acceptance tests named after spec success criteria
- TC-008: assert specific values, not just truthiness
- TC-009: each test is independently runnable
- TC-012: error paths and edge cases covered

S2 isolation requirement (plan.md):
    ``SideEffect`` objects are constructed directly — ``analyze_function()``
    is NOT called.  This keeps S2 tests isolated from S1 correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gaze_py.quality import map_assertions
from gaze_py.taxonomy import (
    SideEffect,
    SideEffectType,
    Tier,
)

TESTDATA = Path(__file__).parent / "testdata" / "quality"

# ---------------------------------------------------------------------------
# Shared SideEffect factories (S2 isolation: no analyze_function() calls)
# ---------------------------------------------------------------------------


def _make_return_effect() -> SideEffect:
    """Construct a ReturnValue SideEffect directly (no analysis.py).

    Returns:
        A ``SideEffect`` with type ``ReturnValue`` and tier ``P0``.
    """
    return SideEffect(
        id="se-00000001",
        type=SideEffectType.ReturnValue,
        tier=Tier.P0,
        location="src.py:1",
        description="Return value",
        target="int",  # type: ignore[arg-type]
    )


def _make_error_effect() -> SideEffect:
    """Construct an ErrorReturn SideEffect directly (no analysis.py).

    Returns:
        A ``SideEffect`` with type ``ErrorReturn`` and tier ``P0``.
    """
    return SideEffect(
        id="se-00000002",
        type=SideEffectType.ErrorReturn,
        tier=Tier.P0,
        location="src.py:3",
        description="Raises ZeroDivisionError",
        target="ZeroDivisionError",  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# SC-014 — ReturnValue covered via assignment + assert
# ---------------------------------------------------------------------------


def test_sc014_return_value_covered() -> None:
    """SC-014: assert result == 3 after result = compute(...) covers ReturnValue.

    Given a test that assigns the return value and asserts on it,
    When mapped against a ReturnValue effect,
    Then ContractCoverage.percentage == 100.0 and covered_count == 1.
    """
    test_source = (TESTDATA / "test_basic.py").read_text()
    target_effects = [_make_return_effect()]
    report = map_assertions(test_source, target_effects, "compute")

    assert report.contract_coverage.percentage == 100.0, f"Expected 100.0%, got {report.contract_coverage.percentage}"
    assert report.contract_coverage.covered_count == 1, (
        f"Expected covered_count=1, got {report.contract_coverage.covered_count}"
    )


# ---------------------------------------------------------------------------
# SC-015 — ErrorReturn covered via pytest.raises context manager
# ---------------------------------------------------------------------------


def test_sc015_error_return_covered() -> None:
    """SC-015: pytest.raises(ZeroDivisionError) covers ErrorReturn.

    Given a test using ``with pytest.raises(ZeroDivisionError): divide(...)``,
    When mapped against an ErrorReturn effect,
    Then ContractCoverage.percentage == 100.0.
    """
    test_source = (TESTDATA / "test_raises.py").read_text()
    target_effects = [_make_error_effect()]
    report = map_assertions(test_source, target_effects, "divide")

    assert report.contract_coverage.percentage == 100.0, f"Expected 100.0%, got {report.contract_coverage.percentage}"


# ---------------------------------------------------------------------------
# SC-016 — No assertions → 0% coverage with gap_hints
# ---------------------------------------------------------------------------


def test_sc016_no_assertions_zero_coverage() -> None:
    """SC-016: test with no assert statements produces 0% coverage and gap_hints.

    Given a test that calls the function but has no assert statements,
    When mapped against a ReturnValue effect,
    Then ContractCoverage.percentage == 0.0 and gap_hints contains one hint.
    """
    test_source = (TESTDATA / "test_no_assert.py").read_text()
    target_effects = [_make_return_effect()]
    report = map_assertions(test_source, target_effects, "multiply")

    assert report.contract_coverage.percentage == 0.0, f"Expected 0.0%, got {report.contract_coverage.percentage}"
    assert isinstance(report.contract_coverage.gap_hints, list), "gap_hints must be a list"
    assert len(report.contract_coverage.gap_hints) == 1, (
        f"Expected 1 gap hint (one per uncovered effect), got {len(report.contract_coverage.gap_hints)}"
    )


# ---------------------------------------------------------------------------
# SC-017 — Over-specification: isinstance assert on return value
# ---------------------------------------------------------------------------


def test_sc017_over_specification() -> None:
    """SC-017: isinstance(result, int) is an over-specified assertion.

    Given a test with both a value assertion (assert result == 16) and
    a type assertion (assert isinstance(result, int)),
    When mapped against a ReturnValue effect,
    Then:
    - contract_coverage.percentage == 100.0 (value assertion covers ReturnValue)
    - over_specification.count == 1 (isinstance flagged as incidental after value assert)
    - over_specification.suggestions has exactly one entry
    """
    test_source = (TESTDATA / "test_incidental.py").read_text()
    target_effects = [_make_return_effect()]
    report = map_assertions(test_source, target_effects, "square")

    assert report.contract_coverage.percentage == 100.0, (
        f"Expected 100.0% (result==16 covers ReturnValue), got {report.contract_coverage.percentage}"
    )
    assert report.over_specification.count == 1, (
        f"Expected exactly 1 incidental assertion (isinstance check), got {report.over_specification.count}"
    )
    assert len(report.over_specification.suggestions) == 1


# ---------------------------------------------------------------------------
# SC-018 — Partial coverage: 50% (ReturnValue covered, ErrorReturn not)
# ---------------------------------------------------------------------------


def test_sc018_partial_coverage_50_percent() -> None:
    """SC-018: test covering only ReturnValue out of two contractual effects.

    Given a function with ReturnValue and ErrorReturn effects, and a test
    that only asserts on the return value (not the exception),
    When mapped,
    Then ContractCoverage.percentage == 50.0 and gaps contains ErrorReturn.
    """
    test_source = (TESTDATA / "test_partial.py").read_text()
    target_effects = [_make_return_effect(), _make_error_effect()]
    report = map_assertions(test_source, target_effects, "process")

    assert report.contract_coverage.percentage == 50.0, f"Expected 50.0%, got {report.contract_coverage.percentage}"
    assert len(report.contract_coverage.gaps) == 1, (
        f"Expected 1 gap (ErrorReturn uncovered), "
        f"got {len(report.contract_coverage.gaps)}: {report.contract_coverage.gaps}"
    )


# ---------------------------------------------------------------------------
# SC-019 — Inline call assertion: assert negate(5) == -5
# ---------------------------------------------------------------------------


def test_sc019_inline_call_covered() -> None:
    """SC-019: inline assert f() == x pattern covers ReturnValue.

    Given a test with ``assert negate(5) == -5`` (no intermediate assignment),
    When mapped against a ReturnValue effect,
    Then ContractCoverage.percentage == 100.0 (inline call pattern recognised).
    """
    test_source = (TESTDATA / "test_inline.py").read_text()
    target_effects = [_make_return_effect()]
    report = map_assertions(test_source, target_effects, "negate")

    assert report.contract_coverage.percentage == 100.0, (
        f"Expected 100.0% (inline assert negate(5)==-5 covers ReturnValue), got {report.contract_coverage.percentage}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_test_source_zero_coverage() -> None:
    """Empty test source produces 0% coverage without raising an error.

    Given an empty string as test source,
    When mapped against a ReturnValue effect,
    Then ContractCoverage.percentage == 0.0 and no exception is raised.
    """
    target_effects = [_make_return_effect()]
    report = map_assertions("", target_effects, "compute")

    assert report.contract_coverage.percentage == 0.0
    assert isinstance(report.contract_coverage.gap_hints, list)


def test_malformed_test_source_raises_parse_error() -> None:
    """Malformed test source raises GazeParseError.

    Given a test source with a SyntaxError,
    When map_assertions is called,
    Then GazeParseError is raised (not a bare SyntaxError).
    """
    from gaze_py.analysis import GazeParseError

    target_effects = [_make_return_effect()]
    with pytest.raises(GazeParseError):
        map_assertions("def broken(:\n    pass\n", target_effects, "broken")


def test_no_contractual_effects_full_coverage() -> None:
    """Zero contractual effects → 100% coverage (vacuously true).

    Given an empty target_effects list,
    When mapped,
    Then ContractCoverage.percentage == 100.0 (no effects to cover).
    """
    test_source = (TESTDATA / "test_basic.py").read_text()
    report = map_assertions(test_source, [], "compute")

    assert report.contract_coverage.percentage == 100.0
    assert report.contract_coverage.covered_count == 0
    assert report.contract_coverage.total_contractual == 0


# ---------------------------------------------------------------------------
# Tests for quality-call-scanning change (opsx/quality-call-scanning)
# ---------------------------------------------------------------------------


def test_iter_test_functions_finds_top_level() -> None:
    """_iter_test_functions returns top-level def test_* functions."""
    import ast

    from gaze_py.quality import _iter_test_functions

    source = "def test_foo():\n    assert 1 == 1\ndef helper():\n    pass\n"
    tree = ast.parse(source)
    results = _iter_test_functions(tree)
    assert len(results) == 1
    assert results[0][0] == "test_foo"


def test_iter_test_functions_finds_class_methods() -> None:
    """_iter_test_functions returns class-based test methods."""
    import ast

    from gaze_py.quality import _iter_test_functions

    source = "class TestFoo:\n    def test_bar(self):\n        assert True\n    def helper(self):\n        pass\n"
    tree = ast.parse(source)
    results = _iter_test_functions(tree)
    assert len(results) == 1
    assert results[0][0] == "TestFoo.test_bar"


def test_iter_test_functions_finds_both() -> None:
    """_iter_test_functions finds both top-level and class-based tests."""
    import ast

    from gaze_py.quality import _iter_test_functions

    source = (
        "def test_standalone():\n    pass\n\n"
        "class TestGroup:\n"
        "    def test_one(self):\n        pass\n"
        "    def test_two(self):\n        pass\n"
    )
    tree = ast.parse(source)
    results = _iter_test_functions(tree)
    names = [n for n, _ in results]
    assert "test_standalone" in names
    assert "TestGroup.test_one" in names
    assert "TestGroup.test_two" in names
    assert len(results) == 3


def test_extract_called_names_simple() -> None:
    """_extract_called_names finds bare function calls."""
    import ast

    from gaze_py.quality import _extract_called_names

    source = "foo(1, 2)\nbar()\n"
    tree = ast.parse(source)
    body = tree.body
    names = _extract_called_names(body)
    assert "foo" in names
    assert "bar" in names


def test_extract_called_names_attribute() -> None:
    """_extract_called_names extracts the method name from attr calls."""
    import ast

    from gaze_py.quality import _extract_called_names

    source = "module.foo()\nobj.bar(x)\n"
    tree = ast.parse(source)
    names = _extract_called_names(tree.body)
    assert "foo" in names
    assert "bar" in names


def test_extract_called_names_ignores_nested_def() -> None:
    """_extract_called_names does not descend into nested function defs."""
    import ast

    from gaze_py.quality import _extract_called_names

    source = "def helper():\n    secret()\nvisible()\n"
    tree = ast.parse(source)
    names = _extract_called_names(tree.body)
    assert "visible" in names
    assert "secret" not in names


def test_map_assertions_finds_class_method_tests() -> None:
    """map_assertions finds coverage from class-based test methods."""
    test_source = (
        "from mymod import compute\n\n"
        "class TestCompute:\n"
        "    def test_basic(self):\n"
        "        result = compute(1, 2)\n"
        "        assert result == 3\n"
    )
    report = map_assertions(test_source, [_make_return_effect()], "compute")
    assert report.contract_coverage.percentage == 100.0, (
        f"Expected 100% coverage from class-based test, got {report.contract_coverage.percentage}%"
    )


def test_map_assertions_test_function_name_populated() -> None:
    """map_assertions populates test_function with real test method names."""
    test_source = "class TestFoo:\n    def test_bar(self):\n        result = fn()\n        assert result == 1\n"
    report = map_assertions(test_source, [_make_return_effect()], "fn")
    assert report.test_function != "<test_function>", (
        "test_function should be populated with real name, not placeholder"
    )
    assert "test_bar" in report.test_function


def test_map_assertions_multi_test_merged() -> None:
    """map_assertions merges bodies from multiple tests that call the target."""
    test_source = (
        "class TestFoo:\n"
        "    def test_returns(self):\n"
        "        result = fn(1)\n"
        "        assert result == 1\n"
        "    def test_raises(self):\n"
        "        import pytest\n"
        "        with pytest.raises(ValueError):\n"
        "            fn(-1)\n"
    )
    effects = [
        _make_return_effect(),
        _make_error_effect(),
    ]
    report = map_assertions(test_source, effects, "fn")
    assert report.contract_coverage.percentage == 100.0, (
        f"Both effects should be covered by merged test bodies, got {report.contract_coverage.percentage}%"
    )


def test_map_assertions_fallback_when_no_call_detected() -> None:
    """map_assertions falls back to all test bodies when target_func not called by name.

    When no test function explicitly calls the target, map_assertions uses all
    test bodies and sets assertion_detection_confidence = 0.
    """
    # test_helper calls 'helper', not 'compute' — fallback should activate
    test_source = "def test_helper():\n    result = helper(1, 2)\n    assert result == 3\n"
    report = map_assertions(test_source, [_make_return_effect()], "compute")
    # Fallback activated — confidence must be 0
    assert report.assertion_detection_confidence == 0, (
        f"Expected confidence=0 for fallback path, got {report.assertion_detection_confidence}"
    )
    # The report must be a well-formed QualityReport (no exception raised)
    assert isinstance(report.contract_coverage.percentage, float)
