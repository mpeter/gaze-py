"""Tests for the CRAP and GazeCRAP score computation."""

from __future__ import annotations

import pytest

from gaze_py.crap import (
    assign_fix_strategy,
    classify_quadrant,
    compute_crap,
    compute_gazecrap,
    crap_score,
    gaze_crap_score,
)
from gaze_py.taxonomy import FixStrategy, Quadrant


class TestCrapScore:
    """Core CRAP formula tests."""

    def test_zero_coverage(self) -> None:
        """With 0% coverage: CRAP = complexity² + complexity."""
        assert crap_score(10, 0.0) == 10**2 + 10  # 110
        assert crap_score(1, 0.0) == 1 + 1  # 2
        assert crap_score(5, 0.0) == 25 + 5  # 30

    def test_full_coverage(self) -> None:
        """With 100% coverage: CRAP = complexity (cubic term vanishes)."""
        assert crap_score(10, 100.0) == 10
        assert crap_score(1, 100.0) == 1
        assert crap_score(42, 100.0) == 42

    def test_known_value_50_percent(self) -> None:
        """complexity=10, coverage=50% → 10² × 0.5³ + 10 = 100×0.125 + 10 = 22.5."""
        result = crap_score(10, 50.0)
        assert result == pytest.approx(22.5)

    def test_known_value_75_percent(self) -> None:
        """complexity=8, coverage=75% → 64 × 0.25³ + 8 = 64×0.015625 + 8 = 9.0."""
        result = crap_score(8, 75.0)
        assert result == pytest.approx(9.0)

    def test_gaze_crap_mirrors_crap(self) -> None:
        """GazeCRAP uses the same formula with contract coverage."""
        assert gaze_crap_score(10, 50.0) == pytest.approx(crap_score(10, 50.0))
        assert gaze_crap_score(5, 80.0) == pytest.approx(crap_score(5, 80.0))


class TestQuadrantClassification:
    """Tests for Q1–Q4 quadrant assignment."""

    def test_q1_safe(self) -> None:
        assert classify_quadrant(5.0, 5.0, 30.0, 30.0) == Quadrant.Q1_Safe

    def test_q2_complex_but_tested(self) -> None:
        assert classify_quadrant(50.0, 5.0, 30.0, 30.0) == Quadrant.Q2_ComplexButTested

    def test_q3_simple_but_underspecified(self) -> None:
        assert classify_quadrant(5.0, 50.0, 30.0, 30.0) == Quadrant.Q3_SimpleButUnderspecified

    def test_q4_dangerous(self) -> None:
        assert classify_quadrant(50.0, 50.0, 30.0, 30.0) == Quadrant.Q4_Dangerous

    def test_none_when_gaze_crap_missing(self) -> None:
        assert classify_quadrant(50.0, None, 30.0, 30.0) is None

    def test_at_threshold_is_safe(self) -> None:
        """Scores *at* the threshold (not over) → Q1."""
        assert classify_quadrant(30.0, 30.0, 30.0, 30.0) == Quadrant.Q1_Safe


class TestFixStrategy:
    """Tests for fix-strategy assignment."""

    def test_q1_no_action(self) -> None:
        assert assign_fix_strategy(5, 80.0, Quadrant.Q1_Safe, 30.0) is None

    def test_q2_decompose(self) -> None:
        assert assign_fix_strategy(20, 90.0, Quadrant.Q2_ComplexButTested, 30.0) == FixStrategy.decompose

    def test_q3_low_coverage_add_tests(self) -> None:
        assert assign_fix_strategy(3, 30.0, Quadrant.Q3_SimpleButUnderspecified, 30.0) == FixStrategy.add_tests

    def test_q3_high_coverage_add_assertions(self) -> None:
        assert assign_fix_strategy(3, 80.0, Quadrant.Q3_SimpleButUnderspecified, 30.0) == FixStrategy.add_assertions

    def test_q4_decompose_and_test(self) -> None:
        assert assign_fix_strategy(20, 20.0, Quadrant.Q4_Dangerous, 30.0) == FixStrategy.decompose_and_test

    def test_none_quadrant_returns_none(self) -> None:
        assert assign_fix_strategy(10, 50.0, None, 30.0) is None


# ---------------------------------------------------------------------------
# SC-020 / SC-021: GazeCRAP formula verification (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("complexity", "contract_coverage_pct", "expected"),
    [
        # SC-020: complexity=5, coverage=0% → 5² × 1³ + 5 = 30
        (5, 0.0, 30.0),
        # SC-021: complexity=5, coverage=100% → 5² × 0³ + 5 = 5
        (5, 100.0, 5.0),
    ],
)
def test_sc020_sc021_gaze_crap_formula(
    complexity: int,
    contract_coverage_pct: float,
    expected: float,
) -> None:
    """SC-020/SC-021: GazeCRAP formula produces correct values.

    Given complexity and contract_coverage_pct,
    When gaze_crap_score is called,
    Then the result matches the hand-computed expected value.
    """
    assert gaze_crap_score(complexity, contract_coverage_pct) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("complexity", "contract_coverage_pct", "expected"),
    [
        (5, 0.0, 30.0),
        (5, 100.0, 5.0),
    ],
)
def test_compute_gazecrap_alias(
    complexity: int,
    contract_coverage_pct: float,
    expected: float,
) -> None:
    """compute_gazecrap alias produces the same results as gaze_crap_score.

    Given complexity and contract_coverage_pct,
    When compute_gazecrap is called,
    Then the result matches the expected value (alias parity).
    """
    assert compute_gazecrap(complexity, contract_coverage_pct) == pytest.approx(expected)


def test_compute_crap_alias() -> None:
    """compute_crap alias produces the same results as crap_score.

    Given complexity=10 and coverage=50%,
    When compute_crap is called,
    Then the result matches crap_score(10, 50.0).
    """
    assert compute_crap(10, 50.0) == pytest.approx(crap_score(10, 50.0))
