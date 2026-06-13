"""Tests for CRAP and GazeCRAP scoring — SC-001 through SC-006.

All tests use synthetic inputs. No file I/O or AST analysis is performed here.
"""

from __future__ import annotations

import pytest

from gaze_py.crap.scorer import (
    crap,
    crapload,
    fix_strategy,
    gaze_crap,
    quadrant,
    recommended_actions,
)
from gaze_py.taxonomy.models import FunctionTarget, Score

# ---------------------------------------------------------------------------
# SC-001: crap() formula
# ---------------------------------------------------------------------------


def test_sc001_crap_formula_basic() -> None:
    """SC-001: crap(complexity=1, line_coverage=1.0) → 1.0."""
    # complexity^2 * (1 - 1.0)^3 + complexity = 1 * 0 + 1 = 1.0
    result = crap(1, 1.0)
    assert result == pytest.approx(1.0)


def test_sc001_crap_formula_zero_coverage() -> None:
    """SC-001: crap(complexity=5, line_coverage=0.0) → 30.0."""
    # 5^2 * (1 - 0)^3 + 5 = 25 + 5 = 30.0
    result = crap(5, 0.0)
    assert result == pytest.approx(30.0)


def test_sc001_crap_formula_partial_coverage() -> None:
    """SC-001: crap(complexity=3, line_coverage=0.5) → 4.125."""
    # 3^2 * (1 - 0.5)^3 + 3 = 9 * 0.125 + 3 = 1.125 + 3 = 4.125
    result = crap(3, 0.5)
    assert result == pytest.approx(4.125)


def test_sc001_crap_returns_none_when_coverage_is_none() -> None:
    """SC-001: crap(complexity=5, line_coverage=None) → None."""
    result = crap(5, None)
    assert result is None


def test_sc001_crap_complexity_1_full_coverage() -> None:
    """SC-001: crap(1, 1.0) → 1.0 (perfect function)."""
    assert crap(1, 1.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# SC-002: gaze_crap() formula
# ---------------------------------------------------------------------------


def test_sc002_gaze_crap_formula_basic() -> None:
    """SC-002: gaze_crap(complexity=1, contract_coverage=1.0) → 1.0."""
    result = gaze_crap(1, 1.0)
    assert result == pytest.approx(1.0)


def test_sc002_gaze_crap_formula_zero_coverage() -> None:
    """SC-002: gaze_crap(complexity=5, contract_coverage=0.0) → 30.0."""
    result = gaze_crap(5, 0.0)
    assert result == pytest.approx(30.0)


def test_sc002_gaze_crap_returns_none_when_coverage_is_none() -> None:
    """SC-002: gaze_crap(complexity=5, contract_coverage=None) → None."""
    result = gaze_crap(5, None)
    assert result is None


def test_sc002_gaze_crap_same_formula_as_crap() -> None:
    """SC-002: gaze_crap uses the same formula as crap (different input dimension)."""
    # Both use: complexity^2 * (1 - coverage)^3 + complexity
    assert gaze_crap(4, 0.75) == pytest.approx(crap(4, 0.75))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SC-003: crapload()
# ---------------------------------------------------------------------------


def _make_target(name: str, crap_score: float | None) -> FunctionTarget:
    """Build a FunctionTarget with a given CRAP score."""
    score = Score(crap=crap_score)
    target = FunctionTarget(
        name=name,
        file_path="test.py",
        line=1,
        complexity=5,
    )
    target.score = score
    return target


def test_sc003_crapload_returns_targets_above_threshold() -> None:
    """SC-003: crapload returns FunctionTargets with CRAP >= threshold."""
    targets = [
        _make_target("high", 30.0),
        _make_target("medium", 15.0),
        _make_target("low", 5.0),
        _make_target("null_crap", None),
    ]
    result = crapload(targets, threshold=15.0)
    names = [t.name for t in result]
    assert "high" in names
    assert "medium" in names  # >= 15.0 is included
    assert "low" not in names
    assert "null_crap" not in names


def test_sc003_crapload_empty_when_all_below_threshold() -> None:
    """SC-003: crapload returns empty list when no function meets threshold."""
    targets = [_make_target("low", 5.0), _make_target("medium", 10.0)]
    result = crapload(targets, threshold=15.0)
    assert result == []


def test_sc003_crapload_excludes_null_crap() -> None:
    """SC-003: crapload excludes functions with null CRAP score."""
    targets = [_make_target("null_crap", None)]
    result = crapload(targets, threshold=15.0)
    assert result == []


def test_sc003_crapload_boundary_inclusive() -> None:
    """SC-003: crapload includes functions with CRAP exactly equal to threshold."""
    targets = [_make_target("boundary", 15.0)]
    result = crapload(targets, threshold=15.0)
    assert len(result) == 1
    assert result[0].name == "boundary"


# ---------------------------------------------------------------------------
# SC-004: quadrant()
# ---------------------------------------------------------------------------


def test_sc004_quadrant_q1_high_line_high_contract() -> None:
    """SC-004: Q1 — both coverages >= 0.5."""
    result = quadrant(0.8, 0.9)
    assert result == "Q1"


def test_sc004_quadrant_q2_high_line_low_contract() -> None:
    """SC-004: Q2 — line_coverage >= 0.5, contract_coverage < 0.5."""
    result = quadrant(0.8, 0.3)
    assert result == "Q2"


def test_sc004_quadrant_q3_low_line_high_contract() -> None:
    """SC-004: Q3 — line_coverage < 0.5, contract_coverage >= 0.5."""
    result = quadrant(0.3, 0.8)
    assert result == "Q3"


def test_sc004_quadrant_q4_low_line_low_contract() -> None:
    """SC-004: Q4 — both coverages < 0.5."""
    result = quadrant(0.3, 0.2)
    assert result == "Q4"


def test_sc004_quadrant_boundary_exactly_half() -> None:
    """SC-004: 0.5 is 'high' (>= 0.5)."""
    result = quadrant(0.5, 0.5)
    assert result == "Q1"


def test_sc004_quadrant_returns_none_when_line_coverage_is_none() -> None:
    """SC-004: None when line_coverage is None."""
    result = quadrant(None, 0.8)
    assert result is None


def test_sc004_quadrant_returns_none_when_contract_coverage_is_none() -> None:
    """SC-004: None when contract_coverage is None."""
    result = quadrant(0.8, None)
    assert result is None


def test_sc004_quadrant_returns_none_when_both_none() -> None:
    """SC-004: None when both coverages are None."""
    result = quadrant(None, None)
    assert result is None


# ---------------------------------------------------------------------------
# SC-005: fix_strategy()
# ---------------------------------------------------------------------------


def test_sc005_fix_strategy_none_when_crap_is_none() -> None:
    """SC-005: fix_strategy returns None when CRAP is None."""
    result = fix_strategy(crap_score=None, complexity=10, line_coverage=0.0, quadrant_label=None)
    assert result is None


def test_sc005_fix_strategy_none_when_crap_below_threshold() -> None:
    """SC-005: fix_strategy returns None when CRAP < threshold."""
    result = fix_strategy(
        crap_score=5.0,
        complexity=10,
        line_coverage=0.0,
        quadrant_label=None,
        threshold=15.0,
    )
    assert result is None


def test_sc005_rule1_decompose_and_test() -> None:
    """SC-005 Rule 1: complexity >= threshold AND coverage = 0 → 'decompose_and_test'."""
    result = fix_strategy(
        crap_score=30.0,
        complexity=15,
        line_coverage=0.0,
        quadrant_label="Q4",
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "decompose_and_test"


def test_sc005_rule2_decompose() -> None:
    """SC-005 Rule 2: complexity >= threshold AND coverage > 0 AND Q3 → 'decompose'."""
    result = fix_strategy(
        crap_score=30.0,
        complexity=15,
        line_coverage=0.6,
        quadrant_label="Q3",
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "decompose"


def test_sc005_rule3_add_tests_default() -> None:
    """SC-005 Rule 3 (default): CRAP >= threshold, no other rule → 'add_tests'."""
    result = fix_strategy(
        crap_score=20.0,
        complexity=5,
        line_coverage=0.3,
        quadrant_label="Q4",
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "add_tests"


def test_sc005_rule1_takes_priority_over_rule3() -> None:
    """SC-005: Rule 1 fires before Rule 3 when complexity >= threshold AND coverage = 0."""
    result = fix_strategy(
        crap_score=30.0,
        complexity=20,
        line_coverage=0.0,
        quadrant_label=None,
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "decompose_and_test"


def test_sc005_fix_strategy_none_when_crap_exactly_below_threshold() -> None:
    """SC-005: fix_strategy returns None when CRAP is just below threshold."""
    result = fix_strategy(
        crap_score=14.99,
        complexity=10,
        line_coverage=0.0,
        quadrant_label=None,
        threshold=15.0,
    )
    assert result is None


# ---------------------------------------------------------------------------
# SC-006: recommended_actions()
# ---------------------------------------------------------------------------


def _make_target_with_strategy(
    name: str,
    crap_score: float | None,
    strategy: str | None,
    file_path: str = "test.py",
) -> FunctionTarget:
    """Build a FunctionTarget with a given CRAP score and fix strategy."""
    score = Score(crap=crap_score, fix_strategy=strategy)
    target = FunctionTarget(
        name=name,
        file_path=file_path,
        line=1,
        complexity=5,
    )
    target.score = score
    return target


def test_sc006_recommended_actions_sort_order() -> None:
    """SC-006: recommended_actions sorted by strategy priority, then CRAP desc."""
    targets = [
        _make_target_with_strategy("fn_decompose", 30.0, "decompose"),
        _make_target_with_strategy("fn_add_tests", 20.0, "add_tests"),
        _make_target_with_strategy("fn_decompose_and_test", 25.0, "decompose_and_test"),
    ]
    result = recommended_actions(targets)
    strategies = [r["strategy"] for r in result]
    # add_tests < add_assertions < decompose_and_test < decompose
    assert strategies.index("add_tests") < strategies.index("decompose_and_test")
    assert strategies.index("decompose_and_test") < strategies.index("decompose")


def test_sc006_recommended_actions_capped_at_20() -> None:
    """SC-006: recommended_actions caps output at 20 entries."""
    targets = [_make_target_with_strategy(f"fn_{i}", float(20 + i), "add_tests") for i in range(30)]
    result = recommended_actions(targets)
    _max_actions = 20
    assert len(result) <= _max_actions


def test_sc006_recommended_actions_required_keys() -> None:
    """SC-006: Each action dict has 'function', 'file', 'strategy', 'crap' keys."""
    targets = [_make_target_with_strategy("my_func", 30.0, "decompose")]
    result = recommended_actions(targets)
    assert len(result) == 1
    action = result[0]
    assert "function" in action
    assert "file" in action
    assert "strategy" in action
    assert "crap" in action


def test_sc006_recommended_actions_excludes_null_strategy() -> None:
    """SC-006: Functions with null fix_strategy are excluded from actions."""
    targets = [
        _make_target_with_strategy("fn_with_strategy", 30.0, "add_tests"),
        _make_target_with_strategy("fn_no_strategy", 5.0, None),
    ]
    result = recommended_actions(targets)
    names = [r["function"] for r in result]
    assert "fn_with_strategy" in names
    assert "fn_no_strategy" not in names


def test_sc006_recommended_actions_empty_list_when_no_targets() -> None:
    """SC-006: recommended_actions returns empty list when no targets have strategies."""
    targets = [_make_target_with_strategy("fn", 5.0, None)]
    result = recommended_actions(targets)
    assert result == []


def test_sc006_recommended_actions_correct_values() -> None:
    """SC-006: Action dict values match the FunctionTarget fields."""
    targets = [_make_target_with_strategy("my_func", 30.0, "decompose", file_path="src/foo.py")]
    result = recommended_actions(targets)
    assert len(result) == 1
    action = result[0]
    assert action["function"] == "my_func"
    assert action["file"] == "src/foo.py"
    assert action["strategy"] == "decompose"
    assert action["crap"] == pytest.approx(30.0)
