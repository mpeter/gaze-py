"""Smoke tests for text report formatters.

Maps to spec acceptance scenario SC-025 from
``specs/001-gaze-py-engine/spec.md`` User Story 3.

Tests are written BEFORE the implementation exists (TDD) and MUST fail
with ``ImportError`` until ``src/gaze_py/report/text.py`` is created.

Convention pack compliance:
- TC-001: pytest only, no unittest.TestCase
- TC-002: direct assert statements
- TC-003: descriptive test names
- TC-008: assert specific values, not just truthiness
- TC-009: each test is independently runnable
"""

from __future__ import annotations

import io

import pytest

from gaze_py.report.text import write_analysis_text, write_quality_text
from gaze_py.taxonomy import (
    AnalysisResult,
    ContractCoverage,
    FunctionTarget,
    OverSpecificationScore,
    QualityReport,
    SideEffect,
    SideEffectType,
    Tier,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def p0_target() -> FunctionTarget:
    """A FunctionTarget for a function that returns a value.

    Returns:
        A ``FunctionTarget`` with package, function, signature, and location set.
    """
    return FunctionTarget(
        package="mypackage",
        function="compute",
        signature="compute(x: int) -> int",
        location="mypackage/compute.py:5",
    )


@pytest.fixture()
def p0_effect(p0_target: FunctionTarget) -> SideEffect:
    """A P0 ReturnValue SideEffect.

    Args:
        p0_target: The function target for the side effect.

    Returns:
        A ``SideEffect`` with type ``ReturnValue`` and tier ``P0``.
    """
    return SideEffect(
        id="se-00000001",
        type=SideEffectType.ReturnValue,
        tier=Tier.P0,
        location="mypackage/compute.py:8",
        description="Returns computed integer result",
        target=p0_target,
    )


@pytest.fixture()
def p1_effect(p0_target: FunctionTarget) -> SideEffect:
    """A P1 GlobalMutation SideEffect.

    Args:
        p0_target: The function target for the side effect.

    Returns:
        A ``SideEffect`` with type ``GlobalMutation`` and tier ``P1``.
    """
    return SideEffect(
        id="se-00000002",
        type=SideEffectType.GlobalMutation,
        tier=Tier.P1,
        location="mypackage/compute.py:9",
        description="Mutates global counter",
        target=p0_target,
    )


@pytest.fixture()
def analysis_result_with_effects(
    p0_target: FunctionTarget,
    p0_effect: SideEffect,
    p1_effect: SideEffect,
) -> AnalysisResult:
    """An AnalysisResult with two side effects (P0 and P1).

    Args:
        p0_target: The function target.
        p0_effect: A P0 ReturnValue effect.
        p1_effect: A P1 GlobalMutation effect.

    Returns:
        An ``AnalysisResult`` with two side effects.
    """
    return AnalysisResult(
        target=p0_target,
        side_effects=[p0_effect, p1_effect],
    )


@pytest.fixture()
def quality_report(p0_target: FunctionTarget) -> QualityReport:
    """A minimal QualityReport for text formatter smoke tests.

    Args:
        p0_target: The function under test.

    Returns:
        A ``QualityReport`` with 50% contract coverage.
    """
    coverage = ContractCoverage(
        percentage=50.0,
        covered_count=1,
        total_contractual=2,
        gaps=[],
        gap_hints=["assert result == expected"],
    )
    over_spec = OverSpecificationScore(
        count=1,
        ratio=0.5,
        incidental_assertions=[],
        suggestions=["Remove assertion on internal state"],
    )
    return QualityReport(
        test_function="test_compute",
        test_location="tests/test_compute.py:10",
        target_function=p0_target,
        contract_coverage=coverage,
        over_specification=over_spec,
        ambiguous_effects=[],
        unmapped_assertions=[],
        assertion_count=2,
        assertion_detection_confidence=75,
    )


# ---------------------------------------------------------------------------
# SC-025: Text output is non-empty for a result with side effects
# ---------------------------------------------------------------------------


def test_analysis_text_nonempty(analysis_result_with_effects: AnalysisResult) -> None:
    """SC-025: write_analysis_text produces non-empty output for a result with effects.

    Given an AnalysisResult with one or more side effects,
    When write_analysis_text is called,
    Then the output is a non-empty string.
    """
    out = io.StringIO()
    write_analysis_text([analysis_result_with_effects], out)
    content = out.getvalue()
    assert len(content) > 0


def test_analysis_text_contains_tier(analysis_result_with_effects: AnalysisResult) -> None:
    """SC-025: Text output contains tier labels (P0, P1, etc.).

    Given an AnalysisResult with P0 and P1 side effects,
    When write_analysis_text is called,
    Then the output contains at least one tier label string.
    """
    out = io.StringIO()
    write_analysis_text([analysis_result_with_effects], out)
    content = out.getvalue()
    # At least one of the tier labels must appear in the output
    tier_labels = {"P0", "P1", "P2", "P3", "P4"}
    assert any(label in content for label in tier_labels), (
        f"Expected at least one tier label in output, got: {content!r}"
    )


def test_analysis_text_empty_results() -> None:
    """Edge case: write_analysis_text with empty list produces a message.

    Given an empty results list,
    When write_analysis_text is called,
    Then the output is non-empty (e.g., 'No functions analyzed.').
    """
    out = io.StringIO()
    write_analysis_text([], out)
    content = out.getvalue()
    assert len(content) > 0


# ---------------------------------------------------------------------------
# Quality text formatter smoke tests
# ---------------------------------------------------------------------------


def test_quality_text_nonempty(quality_report: QualityReport) -> None:
    """SC-025: write_quality_text produces non-empty output for a quality report.

    Given a QualityReport with coverage and over-specification data,
    When write_quality_text is called,
    Then the output is a non-empty string.
    """
    out = io.StringIO()
    write_quality_text([quality_report], out)
    content = out.getvalue()
    assert len(content) > 0


def test_quality_text_empty_reports() -> None:
    """Edge case: write_quality_text with empty list produces a message.

    Given an empty reports list,
    When write_quality_text is called,
    Then the output is non-empty (e.g., 'No quality reports.').
    """
    out = io.StringIO()
    write_quality_text([], out)
    content = out.getvalue()
    assert len(content) > 0


# ---------------------------------------------------------------------------
# Fallback path: monkeypatch _HAS_RICH = False
# ---------------------------------------------------------------------------


def test_analysis_text_fallback_no_rich(
    analysis_result_with_effects: AnalysisResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback path: write_analysis_text uses plain text when rich is absent.

    Given _HAS_RICH is patched to False,
    When write_analysis_text is called,
    Then output contains the function name and tier labels.
    """
    import gaze_py.report.text as text_mod

    monkeypatch.setattr(text_mod, "_HAS_RICH", False)
    out = io.StringIO()
    write_analysis_text([analysis_result_with_effects], out)
    content = out.getvalue()
    assert "compute" in content
    assert any(label in content for label in {"P0", "P1", "P2", "P3", "P4"})


def test_quality_text_fallback_no_rich(
    quality_report: QualityReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback path: write_quality_text uses plain text when rich is absent.

    Given _HAS_RICH is patched to False,
    When write_quality_text is called,
    Then output contains coverage percentage.
    """
    import gaze_py.report.text as text_mod

    monkeypatch.setattr(text_mod, "_HAS_RICH", False)
    out = io.StringIO()
    write_quality_text([quality_report], out)
    content = out.getvalue()
    assert "50%" in content
