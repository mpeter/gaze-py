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
    no_test_coverage: bool = False,
) -> ContractCoverageResult:
    """Compute contract coverage for a test-target pair.

    Classifies each side effect on the target individually using
    ClassificationEngine. Contractual effects are those with label="contractual".
    Coverage is the fraction of distinct contractual effect types that have
    at least one mapped assertion.

    Per OC-003: when there are no contractual effects, percentage is None.
    This distinguishes "no contractual effects" from "0% coverage".

    When ``no_test_coverage=True`` and the target has detected effects, the
    function returns ``percentage=None`` with ``reason="no_test_coverage"``.
    This matches the Go porting contract (contract.go:148): "no test = no
    coverage data, not 0%". The ``"no_test_coverage"`` reason supersedes
    ``"all_effects_ambiguous"`` — any non-empty effects set triggers it.
    When ``no_test_coverage=True`` but the target has no effects, the call
    falls through to normal computation (returns ``"no_effects_detected"``).

    Args:
        target: The production FunctionTarget with detected side effects.
        mapped: List of (AssertionSite, SideEffectType | None) from
            map_assertions_to_effects(). Length must equal the assertion count.
        config: GazeConfig providing contractual_threshold and
            incidental_threshold for the classification engine.
        no_test_coverage: When True and target has effects, return
            percentage=None with reason="no_test_coverage" (Go contract D5).
            Defaults to False, preserving all existing caller behaviour.

    Returns:
        ContractCoverageResult with coverage metrics.
    """
    engine = ClassificationEngine(
        config.contractual_threshold,
        config.incidental_threshold,
    )

    # no_test_coverage fast-path: effects exist but no test targets this function.
    # "no_test_coverage" supersedes "all_effects_ambiguous" — any non-empty effects
    # set triggers this path regardless of classification state (matches Go behaviour
    # where effectsSet membership drives the check, not classification outcome).
    if no_test_coverage and target.effects:
        contractual_count = sum(
            1 for effect in target.effects if engine.classify(effect, target).label == "contractual"
        )
        return ContractCoverageResult(
            percentage=None,
            covered_effects=0,
            total_contractual=contractual_count,
            over_specification_count=0,
            unmapped_assertions=0,
            reason="no_test_coverage",
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
