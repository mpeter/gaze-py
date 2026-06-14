"""A.4 — Contract coverage computation for the O1 quality assessment pipeline.

Classifies each side effect on the target function individually using
ClassificationEngine, then computes what fraction of contractual effects
have at least one mapped assertion.

Per OC-003 (null-not-zero): when there are no contractual effects,
percentage is None — NOT 0.0.
"""

from __future__ import annotations

from gaze_py.classify.engine import ClassificationEngine
from gaze_py.config.loader import GazeConfig
from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.models import (
    AssertionSite,
    ContractCoverageResult,
    FunctionTarget,
    SideEffect,
)


def compute_contract_coverage(
    target: FunctionTarget,
    mapped: list[tuple[AssertionSite, SideEffectType | None]],
    *,
    config: GazeConfig,
) -> ContractCoverageResult:
    """Compute contract coverage for a test-target pair.

    Classifies each side effect on the target individually using
    ClassificationEngine. Contractual effects are those with label="contractual".
    Coverage is the fraction of distinct contractual effect types that have
    at least one mapped assertion.

    Per OC-003: when there are no contractual effects, percentage is None.
    This distinguishes "no contractual effects" from "0% coverage".

    Args:
        target: The production FunctionTarget with detected side effects.
        mapped: List of (AssertionSite, SideEffectType | None) from
            map_assertions_to_effects(). Length must equal the assertion count.
        config: GazeConfig providing contractual_threshold and
            incidental_threshold for the classification engine.

    Returns:
        ContractCoverageResult with coverage metrics.
    """
    engine = ClassificationEngine(
        config.contractual_threshold,
        config.incidental_threshold,
    )

    contractual: list[SideEffect] = []
    incidental_types: set[SideEffectType] = set()
    ambiguous_scores: list[int] = []

    for effect in target.effects:
        classification = engine.classify(effect, target)
        if classification.label == "contractual":
            contractual.append(effect)
        elif classification.label == "incidental":
            incidental_types.add(effect.type)  # .type, not .effect_type
        else:
            # ambiguous — collect confidence score for effect_confidence_range
            ambiguous_scores.append(classification.score)

    # Null-not-zero: no contractual effects → percentage is None.
    if not contractual:
        if not target.effects:
            reason = "no_effects_detected"
        elif ambiguous_scores and not incidental_types:
            # All effects are ambiguous — surface confidence range for diagnostics.
            reason = "all_effects_ambiguous"
        else:
            reason = "no_contractual_effects"
        return ContractCoverageResult(
            percentage=None,
            covered_effects=0,
            total_contractual=0,
            over_specification_count=0,
            unmapped_assertions=0,
            reason=reason,
            min_confidence=min(ambiguous_scores) if reason == "all_effects_ambiguous" else None,
            max_confidence=max(ambiguous_scores) if reason == "all_effects_ambiguous" else None,
        )

    # Use distinct effect types (not raw count) — one ReturnValue counts once.
    contractual_types: set[SideEffectType] = {e.type for e in contractual}  # .type
    covered_types: set[SideEffectType] = {et for _, et in mapped if et is not None}
    covered_count = len(contractual_types & covered_types)
    over_spec = sum(1 for _, et in mapped if et in incidental_types)
    unmapped = sum(1 for _, et in mapped if et is None)

    return ContractCoverageResult(
        percentage=covered_count / len(contractual_types) * 100.0,
        covered_effects=covered_count,
        total_contractual=len(contractual_types),
        over_specification_count=over_spec,
        unmapped_assertions=unmapped,
        reason=None,
    )
