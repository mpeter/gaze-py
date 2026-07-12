"""Tests for taxonomy layer — EC-001 compliance.

Verifies:
- Exactly 48 SideEffectType members per the EC-001 tier table
  ("Total: 48 effect types" — contracts.md), including the 10 types
  taxonomy-reference.md marks "Defined" (specified but not yet detected
  by the reference Go implementation)
- Tier counts: P0=6, P1=11, P2=16, P3=9, P4=6
- All named types present by their string value
- TIER_MAP covers all 48 types
- Score dataclass has required nullable fields
- FunctionTarget has caller_count field
- Summary has crap_threshold and gaze_crap_threshold fields
- Exception hierarchy is correct
"""

from __future__ import annotations

import dataclasses

import pytest

from gaze_py.taxonomy.effects import TIER_MAP, SideEffectType, Tier
from gaze_py.taxonomy.exceptions import GazeConfigError, GazeParseError
from gaze_py.taxonomy.models import (
    AnalysisResult,
    ClassificationResult,
    FunctionTarget,
    Score,
    SideEffect,
    Signal,
    Summary,
)

# ---------------------------------------------------------------------------
# Named constants for tier counts — satisfies PLR2004 (no magic values).
# These are the canonical counts from EC-001 / taxonomy-reference.md.
# ---------------------------------------------------------------------------
_TOTAL_EFFECT_TYPES = 48  # EC-001 tier table: "Total: 48 effect types"
_P0_COUNT = 6
_P1_COUNT = 11
_P2_COUNT = 16
_P3_COUNT = 9
_P4_COUNT = 6
_TIER_COUNT = 5

_DEFAULT_CRAP_THRESHOLD = 15.0

# ---------------------------------------------------------------------------
# EC-001: Type count and tier membership
# ---------------------------------------------------------------------------


class TestSideEffectTypeCount:
    """EC-001: Exactly 48 SideEffectType members."""

    def test_total_count_is_48(self) -> None:
        """EC-001: Total member count is 48.

        The EC-001 tier table totals 48 (P0=6 + P1=11 + P2=16 + P3=9 +
        P4=6). Ten of these are "Defined" in taxonomy-reference.md —
        present in the taxonomy but not yet detected by the reference Go
        implementation. Definitions are contract-mandated regardless of
        detection status.
        """
        assert len(SideEffectType) == _TOTAL_EFFECT_TYPES

    def test_tier_map_covers_all_48_types(self) -> None:
        """TIER_MAP has an entry for every SideEffectType member."""
        assert len(TIER_MAP) == _TOTAL_EFFECT_TYPES
        for effect_type in SideEffectType:
            assert effect_type in TIER_MAP, f"TIER_MAP missing entry for {effect_type}"


@pytest.mark.parametrize(
    "tier,expected_count",
    [
        (Tier.P0, _P0_COUNT),
        (Tier.P1, _P1_COUNT),
        (Tier.P2, _P2_COUNT),
        (Tier.P3, _P3_COUNT),
        (Tier.P4, _P4_COUNT),
    ],
)
def test_tier_member_count(tier: Tier, expected_count: int) -> None:
    """EC-001: Each tier has the correct member count per the porting contract.

    Counts follow the EC-001 tier table: P0=6, P1=11, P2=16, P3=9, P4=6.
    """
    tier_types = [t for t, t_tier in TIER_MAP.items() if t_tier == tier]
    assert len(tier_types) == expected_count, (
        f"Expected {expected_count} {tier.value} types, got {len(tier_types)}: {tier_types}"
    )


# ---------------------------------------------------------------------------
# EC-001: All named types present by string value
# ---------------------------------------------------------------------------

# P0 types
_P0_NAMES = [
    "ReturnValue",
    "ErrorReturn",
    "SentinelError",
    "ReceiverMutation",
    "PointerArgMutation",
    "ErrorSignal",
]
# P1 types
_P1_NAMES = [
    "SliceMutation",
    "MapMutation",
    "GlobalMutation",
    "WriterOutput",
    "HTTPResponseWrite",
    "ChannelSend",
    "ChannelClose",
    "DeferredReturnMutation",
    "GeneratorYield",
    "ContainerMutation",
    "StreamOutput",
]
# P2 types
_P2_NAMES = [
    "FileSystemWrite",
    "FileSystemDelete",
    "FileSystemMeta",
    "DatabaseWrite",
    "DatabaseTransaction",
    "GoroutineSpawn",
    "Panic",
    "CallbackInvocation",
    "LogWrite",
    "ContextCancellation",
    "AsyncGeneratorYield",
    "MetaprogrammingMutation",
    "DescriptorEffect",
    "ResourceManagement",
    "ImportSideEffect",
    "MonkeyPatch",
]
# P3 types
_P3_NAMES = [
    "StdoutWrite",
    "StderrWrite",
    "EnvVarMutation",
    "MutexOp",
    "WaitGroupOp",
    "AtomicOp",
    "TimeDependency",
    "ProcessExit",
    "RecoverBehavior",
]
# P4 types
_P4_NAMES = [
    "ReflectionMutation",
    "UnsafeMutation",
    "CgoCall",
    "FinalizerRegistration",
    "SyncPoolOp",
    "ClosureCaptureMutation",
]

_ALL_NAMES = _P0_NAMES + _P1_NAMES + _P2_NAMES + _P3_NAMES + _P4_NAMES


@pytest.mark.parametrize("name", _ALL_NAMES)
def test_effect_type_present_by_name(name: str) -> None:
    """EC-001: Each named type is accessible as a SideEffectType member."""
    assert name in SideEffectType.__members__, f"SideEffectType missing member: {name}"


@pytest.mark.parametrize("name", _P0_NAMES)
def test_p0_type_has_correct_tier(name: str) -> None:
    """EC-001: Each P0 type maps to Tier.P0 in TIER_MAP."""
    effect_type = SideEffectType[name]
    assert TIER_MAP[effect_type] == Tier.P0


@pytest.mark.parametrize("name", _P1_NAMES)
def test_p1_type_has_correct_tier(name: str) -> None:
    """EC-001: Each P1 type maps to Tier.P1 in TIER_MAP."""
    effect_type = SideEffectType[name]
    assert TIER_MAP[effect_type] == Tier.P1


@pytest.mark.parametrize("name", _P2_NAMES)
def test_p2_type_has_correct_tier(name: str) -> None:
    """EC-001: Each P2 type maps to Tier.P2 in TIER_MAP."""
    effect_type = SideEffectType[name]
    assert TIER_MAP[effect_type] == Tier.P2


@pytest.mark.parametrize("name", _P3_NAMES)
def test_p3_type_has_correct_tier(name: str) -> None:
    """EC-001: Each P3 type maps to Tier.P3 in TIER_MAP."""
    effect_type = SideEffectType[name]
    assert TIER_MAP[effect_type] == Tier.P3


@pytest.mark.parametrize("name", _P4_NAMES)
def test_p4_type_has_correct_tier(name: str) -> None:
    """EC-001: Each P4 type maps to Tier.P4 in TIER_MAP."""
    effect_type = SideEffectType[name]
    assert TIER_MAP[effect_type] == Tier.P4


# ---------------------------------------------------------------------------
# StrEnum behaviour
# ---------------------------------------------------------------------------


class TestStrEnumBehaviour:
    """SideEffectType is a StrEnum — values equal their names."""

    def test_str_enum_value_equals_name(self) -> None:
        """SideEffectType members compare equal to their string name."""
        assert SideEffectType.ReturnValue == "ReturnValue"
        assert SideEffectType.ClosureCaptureMutation == "ClosureCaptureMutation"

    def test_tier_enum_values(self) -> None:
        """Tier enum has exactly 5 members."""
        assert len(Tier) == _TIER_COUNT
        assert {t.value for t in Tier} == {"P0", "P1", "P2", "P3", "P4"}


# ---------------------------------------------------------------------------
# Score dataclass field assertions
# ---------------------------------------------------------------------------


class TestScoreFields:
    """Score dataclass has all required nullable fields per OC-002/OC-003."""

    def test_score_has_contract_coverage_reason(self) -> None:
        """Score has contract_coverage_reason field."""
        field_names = {f.name for f in dataclasses.fields(Score)}
        assert "contract_coverage_reason" in field_names

    def test_score_contract_coverage_reason_defaults_none(self) -> None:
        """contract_coverage_reason defaults to None."""
        score = Score()
        assert score.contract_coverage_reason is None

    def test_score_has_effect_confidence_range(self) -> None:
        """Score has effect_confidence_range field."""
        field_names = {f.name for f in dataclasses.fields(Score)}
        assert "effect_confidence_range" in field_names

    def test_score_effect_confidence_range_defaults_none(self) -> None:
        """effect_confidence_range defaults to None."""
        score = Score()
        assert score.effect_confidence_range is None

    def test_score_effect_confidence_range_accepts_tuple(self) -> None:
        """effect_confidence_range accepts a tuple[int, int]."""
        score = Score(effect_confidence_range=(10, 90))  # noqa: PLR2004
        assert score.effect_confidence_range == (10, 90)  # noqa: PLR2004

    def test_score_all_fields_default_none(self) -> None:
        """All Score fields default to None (null-not-zero per OC-003)."""
        score = Score()
        assert score.line_coverage is None
        assert score.crap is None
        assert score.gaze_crap is None
        assert score.contract_coverage is None
        assert score.contract_coverage_reason is None
        assert score.fix_strategy is None
        assert score.quadrant is None
        assert score.effect_confidence_range is None

    def test_score_is_frozen(self) -> None:
        """Score is a frozen dataclass (value object)."""
        score = Score(line_coverage=75.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            score.line_coverage = 80.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FunctionTarget dataclass field assertions
# ---------------------------------------------------------------------------


class TestFunctionTargetFields:
    """FunctionTarget dataclass has all required fields."""

    def test_function_target_has_caller_count(self) -> None:
        """FunctionTarget has caller_count field."""
        field_names = {f.name for f in dataclasses.fields(FunctionTarget)}
        assert "caller_count" in field_names

    def test_function_target_caller_count_defaults_zero(self) -> None:
        """caller_count defaults to 0."""
        ft = FunctionTarget(
            function="fn",
            file_path="a.py",
            line=1,
            complexity=1,
            package="a.py",
            receiver=None,
            signature="def fn()",
        )
        assert ft.caller_count == 0

    def test_function_target_effects_defaults_empty_list(self) -> None:
        """effects defaults to an empty list."""
        ft = FunctionTarget(
            function="fn",
            file_path="a.py",
            line=1,
            complexity=1,
            package="a.py",
            receiver=None,
            signature="def fn()",
        )
        assert ft.effects == []

    def test_function_target_classification_defaults_none(self) -> None:
        """classification defaults to None."""
        ft = FunctionTarget(
            function="fn",
            file_path="a.py",
            line=1,
            complexity=1,
            package="a.py",
            receiver=None,
            signature="def fn()",
        )
        assert ft.classification is None

    def test_function_target_score_defaults_none(self) -> None:
        """score defaults to None."""
        ft = FunctionTarget(
            function="fn",
            file_path="a.py",
            line=1,
            complexity=1,
            package="a.py",
            receiver=None,
            signature="def fn()",
        )
        assert ft.score is None

    def test_function_target_is_mutable(self) -> None:
        """FunctionTarget is mutable (not frozen) so the pipeline can build it."""
        _caller_count = 5
        ft = FunctionTarget(
            function="fn",
            file_path="a.py",
            line=1,
            complexity=1,
            package="a.py",
            receiver=None,
            signature="def fn()",
        )
        ft.caller_count = _caller_count
        assert ft.caller_count == _caller_count


# ---------------------------------------------------------------------------
# Summary dataclass field assertions
# ---------------------------------------------------------------------------


class TestSummaryFields:
    """Summary dataclass has crap_threshold and gaze_crap_threshold fields."""

    def test_summary_has_crap_threshold(self) -> None:
        """Summary has crap_threshold field."""
        field_names = {f.name for f in dataclasses.fields(Summary)}
        assert "crap_threshold" in field_names

    def test_summary_has_gaze_crap_threshold(self) -> None:
        """Summary has gaze_crap_threshold field."""
        field_names = {f.name for f in dataclasses.fields(Summary)}
        assert "gaze_crap_threshold" in field_names

    def test_summary_crap_threshold_defaults(self) -> None:
        """crap_threshold and gaze_crap_threshold default to 15.0."""
        summary = Summary(function_count=0, crapload=0)
        assert summary.crap_threshold == _DEFAULT_CRAP_THRESHOLD
        assert summary.gaze_crap_threshold == _DEFAULT_CRAP_THRESHOLD

    def test_summary_nullable_fields_default_none(self) -> None:
        """Optional Summary fields default to None."""
        summary = Summary(function_count=0, crapload=0)
        assert summary.gaze_crapload is None
        assert summary.avg_line_coverage is None
        assert summary.avg_contract_coverage is None
        assert summary.quadrant_counts is None
        assert summary.fix_strategy_counts is None
        assert summary.recommended_actions is None


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Exception classes have the correct base classes."""

    def test_gaze_parse_error_is_runtime_error(self) -> None:
        """GazeParseError is a subclass of RuntimeError."""
        assert issubclass(GazeParseError, RuntimeError)

    def test_gaze_config_error_is_value_error(self) -> None:
        """GazeConfigError is a subclass of ValueError."""
        assert issubclass(GazeConfigError, ValueError)

    def test_gaze_parse_error_can_be_raised(self) -> None:
        """GazeParseError can be raised and caught as RuntimeError."""
        with pytest.raises(RuntimeError):
            raise GazeParseError("test error")

    def test_gaze_config_error_can_be_raised(self) -> None:
        """GazeConfigError can be raised and caught as ValueError."""
        with pytest.raises(ValueError):
            raise GazeConfigError("test error")


# ---------------------------------------------------------------------------
# Model instantiation smoke tests
# ---------------------------------------------------------------------------


class TestModelInstantiation:
    """Smoke tests: all domain models can be instantiated."""

    def test_signal_instantiation(self) -> None:
        """Signal can be instantiated with source and weight."""
        _weight = 10
        sig = Signal(source="naming", weight=_weight)
        assert sig.source == "naming"
        assert sig.weight == _weight

    def test_classification_result_instantiation(self) -> None:
        """ClassificationResult can be instantiated."""
        _weight = 10
        _score = 85
        sig = Signal(source="naming", weight=_weight)
        result = ClassificationResult(label="contractual", score=_score, signals=(sig,))
        assert result.label == "contractual"
        assert result.score == _score
        assert len(result.signals) == 1

    def test_side_effect_instantiation(self) -> None:
        """SideEffect can be instantiated with all required fields."""
        effect = SideEffect(
            id="se-abc12345",
            type=SideEffectType.ReturnValue,
            tier=Tier.P0,
            location="src/foo.py:10:4",
            description="Returns a non-None value",
            target="foo.bar",
        )
        assert effect.type == SideEffectType.ReturnValue
        assert effect.tier == Tier.P0

    def test_analysis_result_instantiation(self) -> None:
        """AnalysisResult can be instantiated with results and summary."""
        summary = Summary(function_count=0, crapload=0)
        result = AnalysisResult(results=[], summary=summary)
        assert result.results == []
        assert result.summary.function_count == 0
