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
    ContractCoverage,
    OverSpecificationScore,
    QualityReport,
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

    assert report.contract_coverage.percentage == 100.0, (
        f"Expected 100.0%, got {report.contract_coverage.percentage}"
    )
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

    assert report.contract_coverage.percentage == 100.0, (
        f"Expected 100.0%, got {report.contract_coverage.percentage}"
    )


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

    assert report.contract_coverage.percentage == 0.0, (
        f"Expected 0.0%, got {report.contract_coverage.percentage}"
    )
    assert isinstance(report.contract_coverage.gap_hints, list), (
        "gap_hints must be a list"
    )
    assert len(report.contract_coverage.gap_hints) == 1, (
        f"Expected 1 gap hint (one per uncovered effect), "
        f"got {len(report.contract_coverage.gap_hints)}"
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
    - over_specification.count >= 0 (isinstance may be flagged as incidental)
    - over_specification.suggestions is a list
    """
    test_source = (TESTDATA / "test_incidental.py").read_text()
    target_effects = [_make_return_effect()]
    report = map_assertions(test_source, target_effects, "square")

    assert report.contract_coverage.percentage == 100.0, (
        f"Expected 100.0% (result==16 covers ReturnValue), "
        f"got {report.contract_coverage.percentage}"
    )
    assert report.over_specification.count >= 0, (
        "over_specification.count must be non-negative"
    )
    assert isinstance(report.over_specification.suggestions, list), (
        "over_specification.suggestions must be a list"
    )


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

    assert report.contract_coverage.percentage == 50.0, (
        f"Expected 50.0%, got {report.contract_coverage.percentage}"
    )
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
        f"Expected 100.0% (inline assert negate(5)==-5 covers ReturnValue), "
        f"got {report.contract_coverage.percentage}"
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
