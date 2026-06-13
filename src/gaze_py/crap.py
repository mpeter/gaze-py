"""CRAP and GazeCRAP score computation with quadrant classification."""

from __future__ import annotations

from gaze_py.taxonomy import FixStrategy, Quadrant


def crap_score(complexity: int, coverage_pct: float) -> float:
    """Compute the CRAP (Change Risk Anti-Pattern) score.

    Formula: complexity² × (1 - coverage/100)³ + complexity
    """
    return complexity**2 * (1 - coverage_pct / 100) ** 3 + complexity


def gaze_crap_score(complexity: int, contract_coverage_pct: float) -> float:
    """Compute the GazeCRAP score using contract-aware coverage.

    Same formula as CRAP but substitutes line coverage with
    contract coverage — the percentage of *contractual* side effects
    that are verified by tests.
    """
    return crap_score(complexity, contract_coverage_pct)


def classify_quadrant(
    crap: float,
    gaze_crap: float | None,
    crap_threshold: float,
    gaze_crap_threshold: float,
) -> Quadrant | None:
    """Classify a function into a quality quadrant (Q1–Q4).

    Uses a 2×2 matrix of (CRAP vs threshold) × (GazeCRAP vs threshold):

    * **Q1_Safe** — both scores below thresholds.
    * **Q2_ComplexButTested** — CRAP above threshold, GazeCRAP below.
    * **Q3_SimpleButUnderspecified** — CRAP below threshold, GazeCRAP above.
    * **Q4_Dangerous** — both scores above thresholds.

    Returns ``None`` when *gaze_crap* is not available.
    """
    if gaze_crap is None:
        return None

    crap_over = crap > crap_threshold
    gaze_over = gaze_crap > gaze_crap_threshold

    if not crap_over and not gaze_over:
        return Quadrant.Q1_Safe
    if crap_over and not gaze_over:
        return Quadrant.Q2_ComplexButTested
    if not crap_over and gaze_over:
        return Quadrant.Q3_SimpleButUnderspecified
    return Quadrant.Q4_Dangerous


def assign_fix_strategy(
    complexity: int,
    line_coverage: float,
    quadrant: Quadrant | None,
    crap_threshold: float,
) -> FixStrategy | None:
    """Determine the recommended fix strategy based on quadrant and metrics.

    * **Q1_Safe** — no action needed → ``None``
    * **Q2_ComplexButTested** — function is complex but well-tested →
      ``decompose`` to reduce complexity.
    * **Q3_SimpleButUnderspecified** — simple but missing contract tests →
      ``add_tests`` if low line coverage, ``add_assertions`` if line
      coverage is adequate but contract coverage is missing.
    * **Q4_Dangerous** — complex *and* under-specified →
      ``decompose_and_test``.
    """
    if quadrant is None:
        return None

    if quadrant == Quadrant.Q1_Safe:
        return None

    if quadrant == Quadrant.Q2_ComplexButTested:
        return FixStrategy.decompose

    if quadrant == Quadrant.Q3_SimpleButUnderspecified:
        if line_coverage < 50:
            return FixStrategy.add_tests
        return FixStrategy.add_assertions

    # Q4_Dangerous
    return FixStrategy.decompose_and_test
