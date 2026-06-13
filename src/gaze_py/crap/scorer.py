"""CRAP and GazeCRAP scoring functions.

Implements the CRAP formula, GazeCRAP extension, quadrant assignment,
fix strategy selection, CRAPload counting, and recommended action generation.

All functions are pure — they accept numeric inputs and return numeric outputs
or None when inputs are unavailable (OC-003: null-not-zero).

Per SC-001 through SC-006 (contracts.md and tasks.md).
"""

from __future__ import annotations

from gaze_py.taxonomy.models import FunctionTarget

# ---------------------------------------------------------------------------
# Strategy sort order — lower index = higher priority in output (SC-006).
# add_tests < add_assertions < decompose_and_test < decompose
# ---------------------------------------------------------------------------
_STRATEGY_ORDER: dict[str, int] = {
    "add_tests": 0,
    "add_assertions": 1,
    "decompose_and_test": 2,
    "decompose": 3,
}

# Default complexity threshold for fix_strategy Rule 1 and Rule 2 (SC-005).
_DEFAULT_COMPLEXITY_THRESHOLD: int = 15

# Maximum number of recommended actions returned (SC-006).
_MAX_RECOMMENDED_ACTIONS: int = 20


def crap(complexity: int, line_coverage: float | None) -> float | None:
    """Compute the CRAP score for a function.

    Formula: complexity^2 * (1 - line_coverage)^3 + complexity

    Returns None when line_coverage is None (capability not run), per OC-003.

    Args:
        complexity: McCabe cyclomatic complexity (>= 1).
        line_coverage: Line coverage fraction in [0.0, 1.0], or None when
            coverage data was not provided.

    Returns:
        CRAP score as a float, or None when line_coverage is None.
    """
    if line_coverage is None:
        return None
    return complexity**2 * (1 - line_coverage) ** 3 + complexity


def gaze_crap(complexity: int, contract_coverage: float | None) -> float | None:
    """Compute the GazeCRAP score for a function.

    Uses the same formula as crap() but with contract coverage instead of
    line coverage. Returns None when contract_coverage is None (O1 not run).

    Formula: complexity^2 * (1 - contract_coverage)^3 + complexity

    Args:
        complexity: McCabe cyclomatic complexity (>= 1).
        contract_coverage: Contract coverage fraction in [0.0, 1.0], or None
            when O1 (contract coverage analysis) has not run.

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
        threshold: CRAP score threshold. Functions with CRAP >= threshold
            are included in the result. Default: 15.0.

    Returns:
        List of FunctionTargets with CRAP >= threshold, in the order they
        appear in targets.
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
    """Assign a quadrant label based on line and contract coverage.

    Quadrant definitions (per SC-004):
    - Q1: line_coverage >= 0.5 AND contract_coverage >= 0.5 (high/high — safe)
    - Q2: line_coverage >= 0.5 AND contract_coverage < 0.5 (high/low)
    - Q3: line_coverage < 0.5 AND contract_coverage >= 0.5 (low/high)
    - Q4: line_coverage < 0.5 AND contract_coverage < 0.5 (low/low — risky)

    Returns None when either coverage value is None.

    Args:
        line_coverage: Line coverage fraction in [0.0, 1.0], or None.
        contract_coverage: Contract coverage fraction in [0.0, 1.0], or None.

    Returns:
        Quadrant label ("Q1", "Q2", "Q3", or "Q4"), or None when either
        coverage value is None.
    """
    if line_coverage is None or contract_coverage is None:
        return None

    _HIGH_THRESHOLD = 0.5
    high_line = line_coverage >= _HIGH_THRESHOLD
    high_contract = contract_coverage >= _HIGH_THRESHOLD

    if high_line and high_contract:
        return "Q1"
    if high_line and not high_contract:
        return "Q2"
    if not high_line and high_contract:
        return "Q3"
    return "Q4"


def fix_strategy(
    *,
    crap_score: float | None,
    complexity: int,
    line_coverage: float | None,
    quadrant_label: str | None,
    threshold: float = 15.0,
    complexity_threshold: int = _DEFAULT_COMPLEXITY_THRESHOLD,
) -> str | None:
    """Determine the recommended fix strategy for a function.

    Evaluation order per SC-005:
    - Returns None when CRAP is None or CRAP < threshold.
    - Rule 1: complexity >= complexity_threshold AND line_coverage == 0.0
              → "decompose_and_test"
    - Rule 2: complexity >= complexity_threshold AND line_coverage > 0.0
              AND quadrant == "Q3" → "decompose"
    - Rule 3 (default): → "add_tests"

    Args:
        crap_score: Computed CRAP score, or None when coverage not provided.
        complexity: McCabe cyclomatic complexity.
        line_coverage: Line coverage fraction in [0.0, 1.0], or None.
        quadrant_label: Quadrant label from quadrant(), or None.
        threshold: CRAP threshold for CRAPload membership. Default: 15.0.
        complexity_threshold: Complexity threshold for Rules 1 and 2.
            Default: 15.

    Returns:
        Fix strategy string, or None when CRAP is null or below threshold.
    """
    # Guard: no strategy when CRAP is unavailable or below threshold.
    if crap_score is None or crap_score < threshold:
        return None

    # Rule 1: high complexity + zero coverage → must decompose AND add tests.
    if complexity >= complexity_threshold and line_coverage == 0.0:
        return "decompose_and_test"

    # Rule 2: high complexity + some coverage + Q3 → decompose (tests exist but
    # contract coverage is low, meaning the structure is the problem).
    if (
        complexity >= complexity_threshold
        and line_coverage is not None
        and line_coverage > 0.0
        and quadrant_label == "Q3"
    ):
        return "decompose"

    # Rule 3 (default): CRAP is high but complexity is manageable → add tests.
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
        targets: All analyzed FunctionTargets. Only those with a non-null
            fix_strategy in their Score are included.

    Returns:
        List of action dicts, each with keys: "function", "file", "strategy",
        "crap". Capped at 20 entries.
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
                "function": target.name,
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

    # Sort: strategy priority ascending, then CRAP score descending.
    actions.sort(key=_sort_key)

    return actions[:_MAX_RECOMMENDED_ACTIONS]
