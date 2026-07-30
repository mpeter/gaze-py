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


@pytest.mark.parametrize(
    "complexity,line_coverage,expected",
    [
        (1, 1.0, 1.0),
        (1, 0.0, 2.0),
        (1, 0.5, 1.125),
        (5, 1.0, 5.0),
        (5, 0.5, 8.125),
        (5, 0.0, 30.0),
        (10, 1.0, 10.0),
        (10, 0.5, 22.5),
        (10, 0.0, 110.0),
        (15, 1.0, 15.0),
        (15, 0.0, 240.0),
        (20, 1.0, 20.0),
        (20, 0.5, 70.0),
    ],
)
def test_sc001_crap_reference_values(
    complexity: int, line_coverage: float, expected: float
) -> None:
    """SC-001: CRAP reference values — formula: complexity² × (1 - coverage)³ + complexity.

    Coverage inputs are fractions in [0.0, 1.0].
    """
    result = crap(complexity, line_coverage)
    assert result == pytest.approx(expected, rel=1e-6)


def test_sc001_crap_returns_none_when_coverage_is_none() -> None:
    """SC-001: crap(complexity=5, line_coverage=None) → None (OC-003)."""
    result = crap(5, None)
    assert result is None


# ---------------------------------------------------------------------------
# SC-002: gaze_crap() formula
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "complexity,contract_coverage,expected",
    [
        (1, 1.0, 1.0),
        (5, 0.5, 8.125),
        (10, 0.0, 110.0),
    ],
)
def test_sc002_gaze_crap_reference_values(
    complexity: int, contract_coverage: float, expected: float
) -> None:
    """SC-002: GazeCRAP reference values — same formula as CRAP over contract coverage.

    Coverage inputs are fractions in [0.0, 1.0].
    """
    result = gaze_crap(complexity, contract_coverage)
    assert result == pytest.approx(expected, rel=1e-6)


def test_sc002_gaze_crap_returns_none_when_coverage_is_none() -> None:
    """SC-002: gaze_crap(complexity=5, contract_coverage=None) → None (OC-003)."""
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
        function=name,
        file_path="test.py",
        line=1,
        complexity=5,
        package="test.py",
        receiver=None,
        signature=f"def {name}()",
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
    assert len(result) == 2
    names = [t.function for t in result]
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
    assert result[0].function == "boundary"


# ---------------------------------------------------------------------------
# SC-004: quadrant() — truth table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line_cov,contract_cov,expected",
    [
        (0.8, 0.9, "Q1_Safe"),
        (0.8, 0.3, "Q2_ComplexButTested"),
        (0.3, 0.8, "Q3_SimpleButUnderspecified"),
        (0.3, 0.2, "Q4_Dangerous"),
    ],
)
def test_sc004_quadrant_truth_table(line_cov: float, contract_cov: float, expected: str) -> None:
    """SC-004: Quadrant truth table — all four quadrant labels."""
    assert quadrant(line_cov, contract_cov) == expected


def test_sc004_quadrant_boundary_exactly_half() -> None:
    """SC-004: 0.5 is 'high' (>= 0.5) → Q1_Safe."""
    result = quadrant(0.5, 0.5)
    assert result == "Q1_Safe"


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
    """SC-005 Rule 2: complexity >= threshold AND coverage > 0 AND Q3_SimpleButUnderspecified.

    Expected strategy: 'decompose'.
    """
    result = fix_strategy(
        crap_score=30.0,
        complexity=15,
        line_coverage=0.6,
        quadrant_label="Q3_SimpleButUnderspecified",
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


def test_sc005_rule3_add_assertions() -> None:
    """SC-005 Rule 3: Q3_SimpleButUnderspecified with complexity < threshold → add_assertions."""
    result = fix_strategy(
        crap_score=20.0,
        complexity=5,  # below complexity_threshold=15 so Rules 1+2 don't fire
        line_coverage=0.3,
        quadrant_label="Q3_SimpleButUnderspecified",
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "add_assertions"


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


def test_sc005_rule4_decompose_when_coverage_already_adequate() -> None:
    """SC-005 Rule 4: line_coverage >= 0.5 and no rule above fired -> 'decompose'.

    Regression fixture: fieldkit-cmd's commands/skill/eval_runner.py:
    _parse_eval_argv had CRAP=15.18, complexity=15, line_coverage=0.908,
    quadrant=Q1_Safe (both line and contract coverage already high). Before
    this guard, fix_strategy fell through to 'add_tests' unconditionally —
    recommending more tests for a function already at 90.8% line coverage
    and 100% contract coverage, when the actual CRAP driver was complexity.
    """
    result = fix_strategy(
        crap_score=15.18,
        complexity=15,
        line_coverage=0.908,
        quadrant_label="Q1_Safe",
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "decompose"


def test_sc005_rule4_boundary_exactly_at_coverage_floor() -> None:
    """SC-005 Rule 4: line_coverage == 0.5 (inclusive floor) -> 'decompose'."""
    result = fix_strategy(
        crap_score=20.0,
        complexity=5,
        line_coverage=0.5,
        quadrant_label="Q4",
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "decompose"


def test_sc005_rule4_does_not_fire_just_below_coverage_floor() -> None:
    """SC-005: line_coverage just below 0.5 still falls through to 'add_tests'.

    Regression guard for test_sc005_rule3_add_tests_default's boundary.
    """
    result = fix_strategy(
        crap_score=20.0,
        complexity=5,
        line_coverage=0.49,
        quadrant_label="Q4",
        threshold=15.0,
        complexity_threshold=15,
    )
    assert result == "add_tests"


def test_sc005_rule3_suppressed_when_no_assertion_gaps() -> None:
    """SC-005 Rule 3: has_assertion_gaps=False suppresses 'add_assertions'.

    Regression fixture: fieldkit-cmd's commands/driver/cli.py:run had
    CRAP=16.37, quadrant=Q3_SimpleButUnderspecified, contract_coverage=100.0
    (Gaps == []). Before this guard, Rule 3 fired 'add_assertions' purely
    from the quadrant label — recommending assertions for a function with
    zero assertion gaps. With has_assertion_gaps=False known, Rule 3 is
    skipped and (since line_coverage 0.34 < 0.5, per Q3's own low-line-
    coverage definition) falls through to 'add_tests' — the strategy that
    actually addresses what's missing.
    """
    result = fix_strategy(
        crap_score=16.37,
        complexity=6,
        line_coverage=0.34,
        quadrant_label="Q3_SimpleButUnderspecified",
        threshold=15.0,
        complexity_threshold=15,
        has_assertion_gaps=False,
    )
    assert result == "add_tests"


def test_sc005_rule3_fires_when_assertion_gaps_present() -> None:
    """SC-005 Rule 3: has_assertion_gaps=True still yields 'add_assertions'."""
    result = fix_strategy(
        crap_score=20.0,
        complexity=5,
        line_coverage=0.3,
        quadrant_label="Q3_SimpleButUnderspecified",
        threshold=15.0,
        complexity_threshold=15,
        has_assertion_gaps=True,
    )
    assert result == "add_assertions"


def test_sc005_rule3_fires_when_gap_visibility_unknown() -> None:
    """SC-005 Rule 3: has_assertion_gaps=None (unset, O1 not run) preserves prior behavior."""
    result = fix_strategy(
        crap_score=20.0,
        complexity=5,
        line_coverage=0.3,
        quadrant_label="Q3_SimpleButUnderspecified",
        threshold=15.0,
        complexity_threshold=15,
        has_assertion_gaps=None,
    )
    assert result == "add_assertions"


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
        function=name,
        file_path=file_path,
        line=1,
        complexity=5,
        package=file_path,
        receiver=None,
        signature=f"def {name}()",
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
    assert len(result) == 3
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
    assert len(result) == 1
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


# ---------------------------------------------------------------------------
# Phase 7 — Scorer edge-case tests (unscored targets)
# ---------------------------------------------------------------------------


def test_sc003_crapload_skips_unscored_targets() -> None:
    """SC-003: crapload skips FunctionTargets where score is None (not score.crap=None).

    score is None (unset) — distinct from Score(crap=None) which is a different
    branch covered by test_sc003_crapload_excludes_null_crap.
    """
    # Construct target WITHOUT assigning .score (score stays as default None).
    # This is distinct from Score(crap=None) which is a different branch.
    target = FunctionTarget(
        function="f",
        file_path="f.py",
        line=1,
        complexity=5,
        package="f.py",
        receiver=None,
        signature="def f()",
    )
    # target.score is None (unset), NOT Score(crap=None)
    result = crapload([target], threshold=0.5)
    assert result == []


def test_sc006_recommended_actions_skips_unscored_targets() -> None:
    """SC-006: recommended_actions skips FunctionTargets where score is None.

    score is None (unset) — distinct from Score(fix_strategy=None) which is a
    different branch covered by test_sc006_recommended_actions_excludes_null_strategy.
    """
    target = FunctionTarget(
        function="f",
        file_path="f.py",
        line=1,
        complexity=5,
        package="f.py",
        receiver=None,
        signature="def f()",
    )
    # score is None (unset), not Score(fix_strategy=None)
    result = recommended_actions([target])
    assert result == []
