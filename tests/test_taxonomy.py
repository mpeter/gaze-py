"""Tests for the side-effect taxonomy and domain dataclasses."""

from __future__ import annotations

import re

from gaze_py.taxonomy import (
    TIER_MAP,
    AnalysisResult,
    Classification,
    ClassificationLabel,
    FunctionTarget,
    Metadata,
    SideEffect,
    SideEffectType,
    Signal,
    Tier,
    _generate_side_effect_id,
)


class TestSideEffectTypes:
    """Ensure all 37 types exist and are properly enumerated."""

    def test_total_count(self) -> None:
        assert len(SideEffectType) == 38

    def test_p0_types(self) -> None:
        p0 = {"ReturnValue", "ErrorReturn", "SentinelError", "ReceiverMutation", "PointerArgMutation"}
        for name in p0:
            assert hasattr(SideEffectType, name), f"Missing P0 type: {name}"

    def test_p1_types(self) -> None:
        p1 = {
            "SliceMutation",
            "MapMutation",
            "GlobalMutation",
            "WriterOutput",
            "HTTPResponseWrite",
            "ChannelSend",
            "ChannelClose",
            "DeferredReturnMutation",
        }
        for name in p1:
            assert hasattr(SideEffectType, name), f"Missing P1 type: {name}"

    def test_p4_types(self) -> None:
        p4 = {
            "ReflectionMutation",
            "UnsafeMutation",
            "CgoCall",
            "FinalizerRegistration",
            "SyncPoolOp",
            "ClosureCaptureMutation",
        }
        for name in p4:
            assert hasattr(SideEffectType, name), f"Missing P4 type: {name}"


class TestTierMap:
    """Verify the tier mapping is complete and consistent."""

    def test_covers_all_types(self) -> None:
        mapped = set(TIER_MAP.keys())
        all_types = set(SideEffectType)
        assert mapped == all_types, f"Unmapped types: {all_types - mapped}"

    def test_p0_mapping(self) -> None:
        assert TIER_MAP[SideEffectType.ReturnValue] == Tier.P0
        assert TIER_MAP[SideEffectType.ErrorReturn] == Tier.P0

    def test_p2_mapping(self) -> None:
        assert TIER_MAP[SideEffectType.FileSystemWrite] == Tier.P2
        assert TIER_MAP[SideEffectType.DatabaseWrite] == Tier.P2
        assert TIER_MAP[SideEffectType.GoroutineSpawn] == Tier.P2

    def test_p4_mapping(self) -> None:
        assert TIER_MAP[SideEffectType.ReflectionMutation] == Tier.P4
        assert TIER_MAP[SideEffectType.CgoCall] == Tier.P4


class TestSideEffectId:
    """Test the ``se-XXXXXXXX`` ID generation format."""

    def test_format(self) -> None:
        sid = _generate_side_effect_id()
        assert re.match(r"^se-[0-9a-f]{8}$", sid), f"Bad ID format: {sid}"

    def test_unique(self) -> None:
        ids = {_generate_side_effect_id() for _ in range(100)}
        assert len(ids) == 100, "Generated duplicate IDs"


class TestToDict:
    """Verify JSON-serialisable dict output from domain objects."""

    def test_side_effect_to_dict(self) -> None:
        se = SideEffect(
            id="se-aabbccdd",
            type=SideEffectType.ReturnValue,
            tier=Tier.P0,
            location="main.go:42",
            description="returns int",
        )
        d = se.to_dict()
        assert d["id"] == "se-aabbccdd"
        assert d["type"] == "ReturnValue"
        assert d["tier"] == "P0"
        assert d["location"] == "main.go:42"
        assert d["description"] == "returns int"
        assert d["target"] is None
        assert d["classification"] is None

    def test_side_effect_with_classification(self) -> None:
        sig = Signal(source="tier_boost", weight=25.0, reasoning="P0 tier")
        cls_ = Classification(
            label=ClassificationLabel.contractual,
            confidence=90,
            signals=[sig],
            reasoning="High confidence P0",
        )
        se = SideEffect(
            id="se-11223344",
            type=SideEffectType.ErrorReturn,
            tier=Tier.P0,
            location="pkg.go:10",
            description="error return",
            classification=cls_,
        )
        d = se.to_dict()
        assert d["classification"]["label"] == "contractual"
        assert d["classification"]["confidence"] == 90
        assert len(d["classification"]["signals"]) == 1
        assert d["classification"]["signals"][0]["source"] == "tier_boost"

    def test_analysis_result_to_dict(self) -> None:
        target = FunctionTarget(package="main", function="Run")
        meta = Metadata(
            gaze_version="0.1.0",
            python_version="3.11.0",
            duration_ms=123,
            timestamp="2025-01-01T00:00:00Z",
        )
        result = AnalysisResult(target=target, metadata=meta)
        d = result.to_dict()
        assert d["target"]["package"] == "main"
        assert d["target"]["function"] == "Run"
        assert d["target"]["receiver"] is None
        assert d["metadata"]["gaze_version"] == "0.1.0"
        assert d["side_effects"] == []

    def test_function_target_optional_fields(self) -> None:
        ft = FunctionTarget(package="pkg", function="Fn", receiver="*T", signature="func()", location="f.go:1")
        d = ft.to_dict()
        assert d["receiver"] == "*T"
        assert d["signature"] == "func()"
        assert d["location"] == "f.go:1"
