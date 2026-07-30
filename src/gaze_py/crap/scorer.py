"""CRAP and GazeCRAP scoring functions.

Implements the CRAP formula, GazeCRAP extension, quadrant assignment,
fix strategy selection, CRAPload filtering, and recommended action generation.

All functions are pure — they accept numeric inputs and return numeric outputs
or None when inputs are unavailable (OC-003: null-not-zero).

Coverage inputs are fractions in [0.0, 1.0].

Per SC-001 through SC-006 (contracts.md and tasks.md).
"""

from __future__ import annotations

from gaze_py.taxonomy.models import FunctionTarget

_STRATEGY_ORDER: dict[str, int] = {
    "add_tests": 0,
    "add_assertions": 1,
    "decompose_and_test": 2,
    "decompose": 3,
}

_DEFAULT_COMPLEXITY_THRESHOLD: int = 15
_MAX_RECOMMENDED_ACTIONS: int = 20
_QUADRANT_HIGH_THRESHOLD: float = 0.5


def crap(complexity: int, line_coverage: float | None) -> float | None:
    """Compute the CRAP score for a function.

    Formula: complexity^2 * (1 - line_coverage)^3 + complexity

    Returns None when line_coverage is None (capability not run), per OC-003.

    Args:
        complexity: McCabe cyclomatic complexity (>= 1).
        line_coverage: Line coverage fraction in [0.0, 1.0], or None.

    Returns:
        CRAP score as a float, or None when line_coverage is None.
    """
    if line_coverage is None:
        return None
    return complexity**2 * (1 - line_coverage) ** 3 + complexity


def gaze_crap(complexity: int, contract_coverage: float | None) -> float | None:
    """Compute the GazeCRAP score for a function.

    Formula: complexity^2 * (1 - contract_coverage)^3 + complexity

    Args:
        complexity: McCabe cyclomatic complexity (>= 1).
        contract_coverage: Contract coverage fraction in [0.0, 1.0], or None.

    Returns:
        GazeCRAP score as a float, or None when contract_coverage is None.
    """
    if contract_coverage is None:
        return None
    return complexity**2 * (1 - contract_coverage) ** 3 + complexity


def crapload(
    targets: list[FunctionTarget],
    *,
    threshold: float = 15.0,
) -> list[FunctionTarget]:
    """Return functions whose CRAP score meets or exceeds the threshold.

    Functions with a null CRAP score (coverage not provided) are excluded.

    Args:
        targets: All analyzed FunctionTargets.
        threshold: CRAP score threshold. Default: 15.0.

    Returns:
        List of FunctionTargets with CRAP >= threshold.
    """
    result: list[FunctionTarget] = []
    for target in targets:
        if target.score is None:
            continue
        crap_score = target.score.crap
        if crap_score is not None and crap_score >= threshold:
            result.append(target)
    return result


def quadrant(
    line_coverage: float | None,
    contract_coverage: float | None,
) -> str | None:
    """Assign a quadrant label based on line and contract coverage fractions.

    Quadrant definitions (per SC-004):
    - Q1_Safe: line_coverage >= 0.5 AND contract_coverage >= 0.5
    - Q2_ComplexButTested: line_coverage >= 0.5 AND contract_coverage < 0.5
    - Q3_SimpleButUnderspecified: line_coverage < 0.5 AND contract_coverage >= 0.5
    - Q4_Dangerous: line_coverage < 0.5 AND contract_coverage < 0.5

    Returns None when either coverage value is None.

    Args:
        line_coverage: Line coverage fraction in [0.0, 1.0], or None.
        contract_coverage: Contract coverage fraction in [0.0, 1.0], or None.

    Returns:
        Quadrant label ("Q1_Safe", "Q2_ComplexButTested",
        "Q3_SimpleButUnderspecified", or "Q4_Dangerous"), or None.
    """
    if line_coverage is None or contract_coverage is None:
        return None

    high_line = line_coverage >= _QUADRANT_HIGH_THRESHOLD
    high_contract = contract_coverage >= _QUADRANT_HIGH_THRESHOLD

    if high_line and high_contract:
        return "Q1_Safe"
    if high_line and not high_contract:
        return "Q2_ComplexButTested"
    if not high_line and high_contract:
        return "Q3_SimpleButUnderspecified"
    return "Q4_Dangerous"


def fix_strategy(
    *,
    crap_score: float | None,
    complexity: int,
    line_coverage: float | None,
    quadrant_label: str | None,
    threshold: float = 15.0,
    complexity_threshold: int = _DEFAULT_COMPLEXITY_THRESHOLD,
    has_assertion_gaps: bool | None = None,
) -> str | None:
    """Determine the recommended fix strategy for a function.

    Evaluation order per SC-005:
    - Returns None when CRAP is None or CRAP < threshold.
    - Rule 1: complexity >= complexity_threshold AND line_coverage == 0.0
              -> "decompose_and_test"
    - Rule 2: complexity >= complexity_threshold AND line_coverage > 0.0
              AND quadrant == "Q3_SimpleButUnderspecified" -> "decompose"
    - Rule 3: quadrant == "Q3_SimpleButUnderspecified" AND has_assertion_gaps
              is not False -> "add_assertions". Suppressed when the caller
              affirmatively knows there are no assertion gaps
              (has_assertion_gaps=False) — recommending more assertions when
              contract coverage is already 100% is not actionable.
    - Rule 4: line_coverage >= 0.5 and no rule above fired -> "decompose".
              CRAP staying at/above threshold despite already-adequate line
              coverage means complexity is the dominant term; recommending
              more tests would be low-value. This also makes "add_tests"
              unreachable once coverage is already adequate, closing the
              gap where Rule 5 previously fired regardless of how much
              coverage already existed.
    - Rule 5 (default): -> "add_tests"

    Args:
        crap_score: Computed CRAP score, or None.
        complexity: McCabe cyclomatic complexity.
        line_coverage: Line coverage fraction in [0.0, 1.0], or None.
        quadrant_label: Quadrant label from quadrant(), or None.
        threshold: CRAP threshold. Default: 15.0.
        complexity_threshold: Complexity threshold for Rules 1 and 2. Default: 15.
        has_assertion_gaps: Whether the O1 quality pipeline found unasserted
            contractual effects for this function. None when O1 has not run
            (unknown — Rule 3 behaves as before). True/False when known.

    Returns:
        Fix strategy string, or None when CRAP is null or below threshold.
    """
    if crap_score is None or crap_score < threshold:
        return None

    if complexity >= complexity_threshold and line_coverage == 0.0:
        return "decompose_and_test"

    if (
        complexity >= complexity_threshold
        and line_coverage is not None
        and line_coverage > 0.0
        and quadrant_label == "Q3_SimpleButUnderspecified"
    ):
        return "decompose"

    if quadrant_label == "Q3_SimpleButUnderspecified" and has_assertion_gaps is not False:
        return "add_assertions"

    if line_coverage is not None and line_coverage >= _QUADRANT_HIGH_THRESHOLD:
        return "decompose"

    return "add_tests"


def recommended_actions(
    targets: list[FunctionTarget],
) -> list[dict[str, object]]:
    """Generate a prioritized list of recommended actions for CRAPload functions.

    Includes only functions that have a non-null fix_strategy. Sorted by
    strategy priority (add_tests < add_assertions < decompose_and_test <
    decompose), then by CRAP score descending within each strategy group.
    Capped at 20 entries per SC-006.

    Args:
        targets: All analyzed FunctionTargets.

    Returns:
        List of action dicts with keys: "function", "file", "strategy", "crap".
        Capped at 20 entries.
    """
    actions: list[dict[str, object]] = []

    for target in targets:
        if target.score is None:
            continue
        strategy = target.score.fix_strategy
        if strategy is None:
            continue
        actions.append(
            {
                "function": target.function,
                "file": target.file_path,
                "strategy": strategy,
                "crap": target.score.crap,
            }
        )

    def _sort_key(a: dict[str, object]) -> tuple[int, float]:
        strategy_rank = _STRATEGY_ORDER.get(str(a["strategy"]), 99)
        crap_val = a["crap"]
        crap_rank = -(float(crap_val) if isinstance(crap_val, (int, float)) else 0.0)
        return (strategy_rank, crap_rank)

    actions.sort(key=_sort_key)

    return actions[:_MAX_RECOMMENDED_ACTIONS]
