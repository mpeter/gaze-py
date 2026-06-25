"""Tests for the classification engine — CC-001 through CC-006.

All tests use synthetic SideEffect and FunctionTarget objects. The detector
is NOT invoked here; this isolates classification logic from detection logic.
"""

from __future__ import annotations

import pytest

from gaze_py.classify.engine import ClassificationEngine
from gaze_py.taxonomy.effects import TIER_MAP, SideEffectType
from gaze_py.taxonomy.models import FunctionTarget, SideEffect

# ---------------------------------------------------------------------------
# Expected weight constants (mirrors signal module constants for readability)
# ---------------------------------------------------------------------------

_P0_SCORE = 75  # base 50 + P0 boost 25
_P1_SCORE = 60  # base 50 + P1 boost 10
_P2_SCORE = 50  # base 50 + P2 boost 0

_INTERFACE_WEIGHT = 30
_VISIBILITY_FUNC_WEIGHT = 8
_VISIBILITY_MAX_WEIGHT = 20
_CALLER_ONE_WEIGHT = 5
_CALLER_MULTI_WEIGHT = 10
_CALLER_MANY_WEIGHT = 15
_NAMING_CONTRACTUAL_WEIGHT = 10
_NAMING_SENTINEL_WEIGHT = 30
_NAMING_INCIDENTAL_WEIGHT = -10
_DOCSTRING_DIRECT_WEIGHT = 15
_DOCSTRING_INDIRECT_WEIGHT = 5
_DOCSTRING_INCIDENTAL_WEIGHT = -15
_CONTRADICTION_WEIGHT = -20
_SCORE_MAX = 100
_SCORE_MIN = 0
_DEFAULT_CONTRACTUAL_THRESHOLD = 80
_DEFAULT_INCIDENTAL_THRESHOLD = 50

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_effect(
    effect_type: SideEffectType,
    *,
    name: str = "test_func",
) -> SideEffect:
    """Build a minimal synthetic SideEffect for testing."""
    tier = TIER_MAP[effect_type]
    return SideEffect(
        id="se-00000000",
        type=effect_type,
        tier=tier,
        location="test.py:1:0",
        description="synthetic effect for testing",
        target=name,
    )


def _make_target(
    *,
    name: str = "_test_func",
    caller_count: int = 0,
) -> FunctionTarget:
    """Build a minimal synthetic FunctionTarget for testing.

    Defaults to a private name (_test_func) so that baseline tests (no signals)
    are not contaminated by the visibility signal. Tests that need a public name
    must pass name= explicitly.
    """
    return FunctionTarget(
        function=name,
        file_path="test.py",
        line=1,
        complexity=1,
        package="test.py",
        receiver=None,
        signature=f"def {name}()",
        caller_count=caller_count,
    )


def _engine(
    *,
    contractual_threshold: int = _DEFAULT_CONTRACTUAL_THRESHOLD,
    incidental_threshold: int = _DEFAULT_INCIDENTAL_THRESHOLD,
) -> ClassificationEngine:
    """Build a ClassificationEngine with the given thresholds."""
    return ClassificationEngine(contractual_threshold, incidental_threshold)


# ---------------------------------------------------------------------------
# CC-001: Confidence scoring formula — tier boosts
# ---------------------------------------------------------------------------


def test_cc001_p0_baseline_score() -> None:
    """CC-001: P0 effect with no signals → score = 75 (50 + 25)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.score == _P0_SCORE


def test_cc001_p1_baseline_score() -> None:
    """CC-001: P1 effect with no signals → score = 60 (50 + 10)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.SliceMutation)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.score == _P1_SCORE


def test_cc001_p2_baseline_score() -> None:
    """CC-001: P2 effect with no signals → score = 50 (50 + 0)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.FileSystemWrite)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.score == _P2_SCORE


def test_cc001_p3_baseline_score() -> None:
    """CC-001: P3 effect with no signals → score = 50 (50 + 0)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.StdoutWrite)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.score == _P2_SCORE


def test_cc001_p4_baseline_score() -> None:
    """CC-001: P4 effect with no signals → score = 50 (50 + 0)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ClosureCaptureMutation)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.score == _P2_SCORE


# ---------------------------------------------------------------------------
# CC-001: Contradiction penalty
# ---------------------------------------------------------------------------


def test_cc001_contradiction_penalty_applied() -> None:
    """CC-001: Positive + negative signals → contradiction penalty of -20."""
    engine = _engine()
    # naming "GetUser" → +10 (contractual prefix for ReturnValue, positive signal)
    # docstring "logs the request" → -15 (incidental keyword, negative signal)
    # Both polarities present → contradiction penalty -20 appended.
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser")
    result = engine.classify(
        effect,
        target,
        docstring="logs the request for debugging",
    )
    contradiction_signals = [s for s in result.signals if s.source == "contradiction"]
    assert len(contradiction_signals) == 1
    assert contradiction_signals[0].weight == _CONTRADICTION_WEIGHT


def test_cc001_no_contradiction_with_only_positive_signals() -> None:
    """CC-004: No contradiction signal when only positive signals present."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser")
    # Docstring with contractual keyword only — no incidental keywords.
    result = engine.classify(
        effect,
        target,
        docstring="Returns the user object.",
    )
    contradiction_signals = [s for s in result.signals if s.source == "contradiction"]
    assert len(contradiction_signals) == 0


# ---------------------------------------------------------------------------
# CC-002: Score clamping
# ---------------------------------------------------------------------------


def test_cc002_score_clamped_at_lower_bound() -> None:
    """CC-002: Raw score below 0 → clamped to 0.

    With the current signal set, the minimum achievable raw score is:
    P4 base (50) + incidental naming (-10) + incidental docstring (-15)
    + contradiction (-20) = 5. The engine still clamps to >= 0.
    We verify the engine never returns a negative score.
    """
    engine = _engine()
    effect = _make_effect(SideEffectType.ClosureCaptureMutation, name="logRequest")
    target = _make_target(name="logRequest")
    result = engine.classify(
        effect,
        target,
        docstring="logs the request for debugging purposes",
    )
    assert result.score >= _SCORE_MIN


def test_cc002_score_clamped_at_upper_bound() -> None:
    """CC-002: Raw score above 100 → clamped to 100.

    P0 (75) + interface (+30) + visibility (+20) + caller 4+ (+15)
    + naming contractual (+10) + docstring direct (+15) = 165 → clamped to 100.
    """
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser", caller_count=5)
    result = engine.classify(
        effect,
        target,
        class_bases=["ABC"],
        docstring="Returns the user object.",
    )
    assert result.score == _SCORE_MAX


# ---------------------------------------------------------------------------
# CC-003: Label thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score_target", "expected_label"),
    [
        (85, "contractual"),
        (65, "ambiguous"),
        (40, "incidental"),
    ],
)
def test_cc003_label_thresholds(score_target: int, expected_label: str) -> None:
    """CC-003: Labels assigned based on score vs thresholds (contractual=80, incidental=50)."""
    engine = _engine(
        contractual_threshold=_DEFAULT_CONTRACTUAL_THRESHOLD,
        incidental_threshold=_DEFAULT_INCIDENTAL_THRESHOLD,
    )
    if expected_label == "contractual":
        # P0 (75) + caller 4+ (+15) = 90 → contractual
        effect = _make_effect(SideEffectType.ReturnValue)
        target = _make_target(caller_count=5)
        result = engine.classify(effect, target)
        assert result.label == "contractual"
    elif expected_label == "ambiguous":
        # P2 (50) + caller 2-3 (+10) = 60 → ambiguous
        effect = _make_effect(SideEffectType.FileSystemWrite)
        target = _make_target(caller_count=2)
        result = engine.classify(effect, target)
        assert result.label == "ambiguous"
    else:
        # P2 (50) + incidental name (-10) + visibility (+8) + contradiction (-20) = 28
        # → incidental (28 < 50)
        effect = _make_effect(SideEffectType.LogWrite, name="logRequest")
        target = _make_target(name="logRequest")
        result = engine.classify(effect, target)
        assert result.label == "incidental"


def test_cc003_boundary_exactly_at_contractual_threshold() -> None:
    """CC-003: score=80 exactly at contractual_threshold → 'contractual' (>= inclusive)."""
    engine = _engine(
        contractual_threshold=_DEFAULT_CONTRACTUAL_THRESHOLD,
        incidental_threshold=_DEFAULT_INCIDENTAL_THRESHOLD,
    )
    # P0 (75) + caller 1 (+5) = 80 → contractual (private name, no visibility signal)
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target(caller_count=1)
    result = engine.classify(effect, target)
    assert result.score == _DEFAULT_CONTRACTUAL_THRESHOLD
    assert result.label == "contractual"


def test_cc003_boundary_exactly_at_incidental_threshold() -> None:
    """CC-003: score=50 exactly at incidental_threshold → 'ambiguous' (not 'incidental')."""
    engine = _engine(
        contractual_threshold=_DEFAULT_CONTRACTUAL_THRESHOLD,
        incidental_threshold=_DEFAULT_INCIDENTAL_THRESHOLD,
    )
    # P2 (50) + no signals = 50 → ambiguous (>= incidental_threshold)
    effect = _make_effect(SideEffectType.FileSystemWrite)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.score == _DEFAULT_INCIDENTAL_THRESHOLD
    assert result.label == "ambiguous"


# ---------------------------------------------------------------------------
# CC-004: Contradiction detection
# ---------------------------------------------------------------------------


def test_cc004_contradiction_signal_recorded() -> None:
    """CC-004: Contradiction signal has source='contradiction' and weight=-20."""
    engine = _engine()
    # naming contractual (+10) + docstring incidental (-15) → contradiction
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser")
    result = engine.classify(
        effect,
        target,
        docstring="logs the result for debugging",
    )
    contradiction = next((s for s in result.signals if s.source == "contradiction"), None)
    assert contradiction is not None
    assert contradiction.source == "contradiction"
    assert contradiction.weight == _CONTRADICTION_WEIGHT


def test_cc004_no_contradiction_without_both_polarities() -> None:
    """CC-004: No contradiction when only positive signals exist."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser", caller_count=2)
    result = engine.classify(
        effect,
        target,
        docstring="Returns the user object.",
    )
    contradiction = next((s for s in result.signals if s.source == "contradiction"), None)
    assert contradiction is None


# ---------------------------------------------------------------------------
# CC-005: Interface signal
# ---------------------------------------------------------------------------


def test_cc005_interface_signal_abc_subclass() -> None:
    """CC-005: Method on ABC subclass → interface signal weight=+30."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target, class_bases=["ABC"])
    interface_signals = [s for s in result.signals if s.source == "interface"]
    assert len(interface_signals) == 1
    assert interface_signals[0].weight == _INTERFACE_WEIGHT


def test_cc005_interface_signal_protocol_subclass() -> None:
    """CC-005: Method on Protocol subclass → interface signal weight=+30."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target, class_bases=["Protocol"])
    interface_signals = [s for s in result.signals if s.source == "interface"]
    assert len(interface_signals) == 1
    assert interface_signals[0].weight == _INTERFACE_WEIGHT


def test_cc005_no_interface_signal_for_plain_class() -> None:
    """CC-005: Method on plain class (no ABC/Protocol) → no interface signal."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target, class_bases=["SomeBaseClass"])
    interface_signals = [s for s in result.signals if s.source == "interface"]
    assert len(interface_signals) == 0


def test_cc005_no_interface_signal_for_standalone_function() -> None:
    """CC-005: Standalone function (no class_bases) → no interface signal."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target)
    interface_signals = [s for s in result.signals if s.source == "interface"]
    assert len(interface_signals) == 0


# ---------------------------------------------------------------------------
# CC-005: Visibility signal
# ---------------------------------------------------------------------------


def test_cc005_visibility_fully_public_function() -> None:
    """CC-005: Public function name (no receiver, no return type) → visibility +8."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target(name="GetUser")
    result = engine.classify(effect, target)
    visibility_signals = [s for s in result.signals if s.source == "visibility"]
    assert len(visibility_signals) == 1
    assert visibility_signals[0].weight == _VISIBILITY_FUNC_WEIGHT


def test_cc005_visibility_fully_public_with_return_and_receiver() -> None:
    """CC-005: Public function + public return type + public receiver → +20 (clamped)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target(name="GetUser")
    result = engine.classify(
        effect,
        target,
        return_type_hint="User",
        receiver_name="UserService",
    )
    visibility_signals = [s for s in result.signals if s.source == "visibility"]
    assert len(visibility_signals) == 1
    # +8 (func) + +6 (return type) + +6 (receiver) = +20 (clamped to 20)
    assert visibility_signals[0].weight == _VISIBILITY_MAX_WEIGHT


def test_cc005_visibility_private_function_no_signal() -> None:
    """CC-005: Private function (underscore prefix) → no visibility signal."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target(name="_private_func")
    result = engine.classify(effect, target)
    visibility_signals = [s for s in result.signals if s.source == "visibility"]
    assert len(visibility_signals) == 0


# ---------------------------------------------------------------------------
# CC-005: Caller dependency signal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("caller_count", "expected_weight"),
    [
        (0, 0),
        (1, _CALLER_ONE_WEIGHT),
        (2, _CALLER_MULTI_WEIGHT),
        (3, _CALLER_MULTI_WEIGHT),
        (4, _CALLER_MANY_WEIGHT),
        (10, _CALLER_MANY_WEIGHT),
    ],
)
def test_cc005_caller_signal_weights(caller_count: int, expected_weight: int) -> None:
    """CC-005: Caller count → expected weight per the weight table."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target(caller_count=caller_count)
    result = engine.classify(effect, target)
    caller_signals = [s for s in result.signals if s.source == "caller"]
    if expected_weight == 0:
        # No signal emitted for 0 callers
        assert len(caller_signals) == 0
    else:
        assert len(caller_signals) == 1
        assert caller_signals[0].weight == expected_weight


# ---------------------------------------------------------------------------
# CC-005: Naming signal — contractual prefix
# ---------------------------------------------------------------------------


def test_cc005_naming_contractual_prefix_fires_for_implied_effect() -> None:
    """CC-005: 'GetUser' with ReturnValue effect → naming signal weight=+10."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser")
    result = engine.classify(effect, target)
    naming_signals = [s for s in result.signals if s.source == "naming"]
    assert len(naming_signals) == 1
    assert naming_signals[0].weight == _NAMING_CONTRACTUAL_WEIGHT


def test_cc005_naming_contractual_prefix_does_not_fire_for_non_implied_effect() -> None:
    """CC-005: 'GetUser' with LogWrite effect → no naming signal weight=+10.

    The 'Get*' prefix implies ReturnValue, not LogWrite. The naming signal
    MUST NOT fire for non-implied effect types.
    """
    engine = _engine()
    effect = _make_effect(SideEffectType.LogWrite, name="GetUser")
    target = _make_target(name="GetUser")
    result = engine.classify(effect, target)
    # No contractual naming signal should fire for LogWrite with Get* prefix
    contractual_naming = [
        s for s in result.signals if s.source == "naming" and s.weight == _NAMING_CONTRACTUAL_WEIGHT
    ]
    assert len(contractual_naming) == 0


def test_cc005_naming_sentinel_special_case() -> None:
    """CC-005: SentinelError effect with 'Err*' name → naming signal weight=+30."""
    engine = _engine()
    effect = _make_effect(SideEffectType.SentinelError, name="ErrNotFound")
    target = _make_target(name="ErrNotFound")
    result = engine.classify(effect, target)
    naming_signals = [s for s in result.signals if s.source == "naming"]
    assert len(naming_signals) == 1
    assert naming_signals[0].weight == _NAMING_SENTINEL_WEIGHT


def test_cc005_naming_incidental_prefix() -> None:
    """CC-005: 'logRequest' → naming signal weight=-10."""
    engine = _engine()
    effect = _make_effect(SideEffectType.LogWrite, name="logRequest")
    target = _make_target(name="logRequest")
    result = engine.classify(effect, target)
    naming_signals = [s for s in result.signals if s.source == "naming"]
    assert len(naming_signals) == 1
    assert naming_signals[0].weight == _NAMING_INCIDENTAL_WEIGHT


# ---------------------------------------------------------------------------
# CC-005: Docstring signal
# ---------------------------------------------------------------------------


def test_cc005_docstring_direct_match() -> None:
    """CC-005: Docstring 'returns' + ReturnValue effect → source='godoc', weight=+15."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(
        effect,
        target,
        docstring="Returns the user object from the database.",
    )
    godoc_signals = [s for s in result.signals if s.source == "godoc" and s.weight > 0]
    assert len(godoc_signals) >= 1
    assert any(s.weight == _DOCSTRING_DIRECT_WEIGHT for s in godoc_signals)


def test_cc005_docstring_indirect_match() -> None:
    """CC-005: Docstring 'modifies' + ReturnValue → source='godoc_keyword_indirect', weight=+5.

    'modifies' implies ReceiverMutation/PointerArgMutation/etc., NOT ReturnValue.
    So for a ReturnValue effect, 'modifies' is an indirect match (+5).
    """
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(
        effect,
        target,
        docstring="Modifies the user record in the database.",
    )
    indirect_signals = [s for s in result.signals if s.source == "godoc_keyword_indirect"]
    assert len(indirect_signals) >= 1
    assert any(s.weight == _DOCSTRING_INDIRECT_WEIGHT for s in indirect_signals)


def test_cc005_docstring_incidental_keyword() -> None:
    """CC-005: Docstring 'logs' → source='godoc', weight=-15."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(
        effect,
        target,
        docstring="Logs the request for debugging purposes.",
    )
    incidental_godoc = [s for s in result.signals if s.source == "godoc" and s.weight < 0]
    assert len(incidental_godoc) >= 1
    assert any(s.weight == _DOCSTRING_INCIDENTAL_WEIGHT for s in incidental_godoc)


def test_cc005_no_docstring_no_signal() -> None:
    """CC-005: No docstring → no godoc signals."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target, docstring=None)
    godoc_signals = [s for s in result.signals if s.source in ("godoc", "godoc_keyword_indirect")]
    assert len(godoc_signals) == 0


# ---------------------------------------------------------------------------
# CC-006: Signal recording — source and weight fields
# ---------------------------------------------------------------------------


def test_cc006_signal_has_source_and_weight_fields() -> None:
    """CC-006: Every signal has a non-empty source (str) and non-zero weight (int)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser", caller_count=2)
    result = engine.classify(
        effect,
        target,
        class_bases=["ABC"],
        docstring="Returns the user.",
    )
    assert len(result.signals) > 0
    for signal in result.signals:
        assert isinstance(signal.source, str) and len(signal.source) > 0, f"Bad source in {signal}"
        assert isinstance(signal.weight, int) and signal.weight != 0, (
            f"Zero weight in signal {signal.source!r}"
        )


def test_cc006_canonical_source_identifiers() -> None:
    """CC-006: Signal sources use canonical identifiers from contracts.md."""
    allowed_sources = {
        "interface",
        "visibility",
        "caller",
        "naming",
        "godoc",
        "godoc_keyword_indirect",
        "contradiction",
    }
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue, name="GetUser")
    target = _make_target(name="GetUser", caller_count=2)
    result = engine.classify(
        effect,
        target,
        class_bases=["ABC"],
        docstring="Returns the user object.",
    )
    for signal in result.signals:
        assert signal.source in allowed_sources, (
            f"Unexpected signal source: {signal.source!r} — expected one of {allowed_sources}"
        )


# ---------------------------------------------------------------------------
# Integration: full classification result structure
# ---------------------------------------------------------------------------


def test_classification_result_has_label_score_signals() -> None:
    """ClassificationResult has label, score, and signals fields."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target)
    assert isinstance(result.label, str)
    assert result.label in ("contractual", "ambiguous", "incidental")
    assert isinstance(result.score, int)
    assert _SCORE_MIN <= result.score <= _SCORE_MAX
    assert isinstance(result.signals, tuple)


def test_classification_result_is_frozen() -> None:
    """ClassificationResult is immutable (frozen dataclass)."""
    engine = _engine()
    effect = _make_effect(SideEffectType.ReturnValue)
    target = _make_target()
    result = engine.classify(effect, target)
    with pytest.raises((AttributeError, TypeError)):
        result.label = "contractual"  # type: ignore[misc]


@pytest.mark.parametrize("effect_type", list(SideEffectType))
def test_classify_all_effect_types_without_error(effect_type: SideEffectType) -> None:
    """Engine classifies every SideEffectType without raising."""
    engine = _engine()
    effect = _make_effect(effect_type)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.label in ("contractual", "ambiguous", "incidental")
    assert _SCORE_MIN <= result.score <= _SCORE_MAX


# ---------------------------------------------------------------------------
# Tier boost verification across all tiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("effect_type", "expected_base_score"),
    [
        (SideEffectType.ReturnValue, _P0_SCORE),  # P0: 50 + 25
        (SideEffectType.ErrorReturn, _P0_SCORE),  # P0
        (SideEffectType.SentinelError, _P0_SCORE),  # P0
        (SideEffectType.ReceiverMutation, _P0_SCORE),  # P0
        (SideEffectType.PointerArgMutation, _P0_SCORE),  # P0
        (SideEffectType.SliceMutation, _P1_SCORE),  # P1: 50 + 10
        (SideEffectType.MapMutation, _P1_SCORE),  # P1
        (SideEffectType.GlobalMutation, _P1_SCORE),  # P1
        (SideEffectType.WriterOutput, _P1_SCORE),  # P1
        (SideEffectType.FileSystemWrite, _P2_SCORE),  # P2: 50 + 0
        (SideEffectType.StdoutWrite, _P2_SCORE),  # P3: 50 + 0
        (SideEffectType.ClosureCaptureMutation, _P2_SCORE),  # P4: 50 + 0
    ],
)
def test_tier_boost_produces_correct_baseline(
    effect_type: SideEffectType, expected_base_score: int
) -> None:
    """CC-001: Each tier produces the correct baseline score with no signals."""
    engine = _engine()
    effect = _make_effect(effect_type)
    target = _make_target()
    result = engine.classify(effect, target)
    assert result.score == expected_base_score, (
        f"Expected score {expected_base_score} for {effect_type}, got {result.score}"
    )
