"""Tests for quality/coverage.py — A.4 contract coverage computation."""

from __future__ import annotations

from gaze_py.classify.engine import ClassificationEngine
from gaze_py.config.loader import GazeConfig
from gaze_py.quality.coverage import compute_contract_coverage
from gaze_py.taxonomy.effects import SideEffectType, Tier
from gaze_py.taxonomy.models import AssertionKind, AssertionSite, FunctionTarget, SideEffect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    contractual_threshold: int = 80,
    incidental_threshold: int = 50,
) -> GazeConfig:
    """Create a GazeConfig with given thresholds."""
    cfg = GazeConfig()
    cfg.contractual_threshold = contractual_threshold
    cfg.incidental_threshold = incidental_threshold
    return cfg


def _make_assertion(
    kind: AssertionKind = AssertionKind.STDLIB_EQUALITY,
    names: frozenset[str] | None = None,
) -> AssertionSite:
    """Create a minimal AssertionSite."""
    return AssertionSite(
        location="test_example.py:1:0",
        kind=kind,
        depth=0,
        referenced_names=names or frozenset(),
    )


def _make_effect(
    effect_type: SideEffectType,
    target: str = "example_fn",
) -> SideEffect:
    """Create a minimal SideEffect."""
    return SideEffect(
        id="se-00000000",
        type=effect_type,
        tier=Tier.P0,
        location="src/example.py:1:0",
        description="test effect",
        target=target,
    )


def _make_target(effects: list[SideEffect]) -> FunctionTarget:
    """Create a FunctionTarget with given effects.

    Uses caller_count=10 to push ReturnValue (P0 tier) into contractual range.
    """
    return FunctionTarget(
        name="example_fn",
        file_path="src/example.py",
        line=1,
        complexity=1,
        caller_count=10,  # caller signal pushes toward contractual
        effects=effects,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_contractual_effects_covered() -> None:
    """All contractual effects covered → percentage=100.0, over_spec=0, reason=None."""
    # ReturnValue (P0) with caller_count=10 → contractual.
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target([effect])
    # Assertion mapped to ReturnValue.
    mapped = [(_make_assertion(), SideEffectType.ReturnValue)]
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config)
    assert result.percentage == 100.0
    assert result.covered_effects == 1
    assert result.total_contractual == 1
    assert result.over_specification_count == 0
    assert result.reason is None


def test_zero_assertions_contractual_effects_exist() -> None:
    """Zero assertions, contractual effects exist → percentage=0.0, covered=0."""
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target([effect])
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config)
    assert result.percentage == 0.0
    assert result.covered_effects == 0
    assert result.total_contractual == 1
    assert result.unmapped_assertions == 0


def test_partial_coverage() -> None:
    """1 of 2 contractual effects covered → percentage=50.0."""
    # ReturnValue (P0, contractual) and ErrorReturn (P0, contractual).
    effects = [
        _make_effect(SideEffectType.ReturnValue),
        _make_effect(SideEffectType.ErrorReturn),
    ]
    target = _make_target(effects)
    # Only ReturnValue is covered.
    mapped = [
        (_make_assertion(), SideEffectType.ReturnValue),
        (_make_assertion(), None),  # unmapped
    ]
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config)
    assert result.percentage == 50.0
    assert result.covered_effects == 1
    assert result.total_contractual == 2


def test_no_contractual_effects_all_incidental() -> None:
    """No contractual effects (all incidental) → percentage is None, reason set.

    LogWrite (P2) with caller_count=0: base=50, tier_boost=0, no signals → score=50.
    With incidental_threshold=60: score=50 < 60 → incidental.
    With contractual_threshold=80: score=50 < 80 → not contractual.
    """
    effect = _make_effect(SideEffectType.LogWrite)
    target = FunctionTarget(
        name="example_fn",
        file_path="src/example.py",
        line=1,
        complexity=1,
        caller_count=0,  # no caller signal → score stays at base
        effects=[effect],
    )
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    # LogWrite score=50 (base only, no signals) → incidental (50 < 60).
    config = _make_config(contractual_threshold=80, incidental_threshold=60)
    result = compute_contract_coverage(target, mapped, config=config)
    assert result.percentage is None
    assert result.reason == "no_contractual_effects"
    assert result.total_contractual == 0


def test_no_effects_at_all() -> None:
    """No effects at all → percentage is None, reason='no_effects_detected'."""
    target = _make_target([])
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config)
    assert result.percentage is None
    assert result.reason == "no_effects_detected"
    assert result.total_contractual == 0
    assert result.covered_effects == 0


def test_over_specification() -> None:
    """Assertion maps to incidental effect → over_specification_count=1.

    With caller_count=0:
    - ReturnValue (P0): base=50, tier_boost=25 → score=75 → contractual (>=70).
    - LogWrite (P2): base=50, tier_boost=0 → score=50 → incidental (<60).
    """
    effects = [
        _make_effect(SideEffectType.ReturnValue),
        _make_effect(SideEffectType.LogWrite),
    ]
    target = FunctionTarget(
        name="example_fn",
        file_path="src/example.py",
        line=1,
        complexity=1,
        caller_count=0,  # no caller signal → scores stay at base+tier_boost
        effects=effects,
    )
    # ReturnValue score=75 → contractual (>=70).
    # LogWrite score=50 → incidental (<60).
    mapped = [
        (_make_assertion(), SideEffectType.ReturnValue),
        (_make_assertion(), SideEffectType.LogWrite),
    ]
    config = _make_config(contractual_threshold=70, incidental_threshold=60)
    result = compute_contract_coverage(target, mapped, config=config)
    assert result.over_specification_count == 1


def test_unmapped_assertion() -> None:
    """Assertion maps to None → unmapped_assertions=1."""
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target([effect])
    mapped = [
        (_make_assertion(), SideEffectType.ReturnValue),
        (_make_assertion(), None),  # unmapped
    ]
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config)
    assert result.unmapped_assertions == 1


def test_percentage_is_none_not_zero_for_no_contractual() -> None:
    """Null-not-zero: no contractual effects → percentage is None, NOT 0.0."""
    target = _make_target([])
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config)
    # Must be None, not 0.0 — this is the OC-003 null-not-zero requirement.
    assert result.percentage is None
    assert result.percentage != 0.0


def test_all_effects_ambiguous_populates_confidence_range() -> None:
    """ECR-001 (coverage.py path): all_effects_ambiguous reason fires when all effects
    are classified ambiguous and min_confidence/max_confidence are populated.

    Uses real ClassificationEngine with a LogWrite effect on a private function
    with no callers — reliably produces ambiguous classification (score=50).
    """
    effect = _make_effect(SideEffectType.LogWrite)
    # Private name + 0 callers → ambiguous classification from ClassificationEngine
    target = FunctionTarget(
        name="_private_fn",
        file_path="src/example.py",
        line=1,
        complexity=1,
        caller_count=0,
        effects=[effect],
    )
    # Pre-condition probe: verify this fixture is reliably ambiguous before
    # relying on it in the coverage assertion. compute_contract_coverage()
    # creates its own ClassificationEngine internally; this probe confirms the
    # input would be classified ambiguous by any standard engine instance.
    engine = ClassificationEngine()
    classification = engine.classify(effect, target)
    assert classification.label == "ambiguous", (
        f"Pre-condition failed: expected ambiguous, got {classification.label} "
        f"(score={classification.score})"
    )

    # compute_contract_coverage uses the engine internally to classify effects
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config(contractual_threshold=80, incidental_threshold=50)
    result = compute_contract_coverage(target, mapped, config=config)

    assert result.reason == "all_effects_ambiguous"
    assert result.min_confidence is not None
    assert result.max_confidence is not None
    assert result.min_confidence == result.max_confidence  # single effect → same score
    assert 0 <= result.min_confidence <= 100  # noqa: PLR2004
    assert result.percentage is None  # OC-003: null-not-zero


# ---------------------------------------------------------------------------
# Task 3.3 — no_test_coverage reason code (Go porting contract D5 / OC-003)
# ---------------------------------------------------------------------------


def test_no_test_coverage_emits_none_percentage() -> None:
    """no_test_coverage=True with ReturnValue effect → percentage is None, reason set."""
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target([effect])
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config, no_test_coverage=True)
    assert result.percentage is None
    assert result.reason == "no_test_coverage"


def test_no_test_coverage_total_contractual_populated() -> None:
    """no_test_coverage=True → total_contractual >= 1, covered_effects == 0.

    ReturnValue (P0) with caller_count=10 classifies as contractual, so
    total_contractual must be at least 1. No assertions are mapped, so
    covered_effects must be 0.
    """
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target([effect])
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config, no_test_coverage=True)
    assert result.total_contractual >= 1
    assert result.covered_effects == 0


def test_no_test_coverage_oc003_null_not_zero() -> None:
    """OC-003: no_test_coverage=True → percentage is None, NOT 0.0.

    "no test = no coverage data, not 0% coverage" — Go porting contract
    (contract.go:148). Conflating "not measured" with "measured as zero"
    is the exact violation OC-003 prohibits.
    """
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target([effect])
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config, no_test_coverage=True)
    assert result.percentage is None
    assert result.percentage != 0.0


def test_no_test_coverage_empty_effects_falls_through() -> None:
    """no_test_coverage=True with no effects → falls through to 'no_effects_detected'.

    When the target has no detected side effects, no_test_coverage is irrelevant —
    the function falls through to normal computation and returns the standard
    'no_effects_detected' reason (not 'no_test_coverage').
    """
    target = _make_target([])
    mapped: list[tuple[AssertionSite, SideEffectType | None]] = []
    config = _make_config()
    result = compute_contract_coverage(target, mapped, config=config, no_test_coverage=True)
    assert result.reason == "no_effects_detected"
    assert result.percentage is None
