"""Side-effect type taxonomy and core domain dataclasses for GazeCRAP."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SideEffectType(str, Enum):
    """All 37 side-effect types across 5 tiers."""

    # P0 — Direct return / receiver mutations
    ReturnValue = "ReturnValue"
    ErrorReturn = "ErrorReturn"
    SentinelError = "SentinelError"
    ReceiverMutation = "ReceiverMutation"
    PointerArgMutation = "PointerArgMutation"

    # P1 — Collection / channel / deferred mutations
    SliceMutation = "SliceMutation"
    MapMutation = "MapMutation"
    GlobalMutation = "GlobalMutation"
    WriterOutput = "WriterOutput"
    HTTPResponseWrite = "HTTPResponseWrite"
    ChannelSend = "ChannelSend"
    ChannelClose = "ChannelClose"
    DeferredReturnMutation = "DeferredReturnMutation"

    # P2 — I/O, concurrency, callbacks
    FileSystemWrite = "FileSystemWrite"
    FileSystemDelete = "FileSystemDelete"
    FileSystemMeta = "FileSystemMeta"
    DatabaseWrite = "DatabaseWrite"
    DatabaseTransaction = "DatabaseTransaction"
    GoroutineSpawn = "GoroutineSpawn"
    Panic = "Panic"
    CallbackInvocation = "CallbackInvocation"
    LogWrite = "LogWrite"
    ContextCancellation = "ContextCancellation"

    # P3 — Stdio, env, sync primitives
    StdoutWrite = "StdoutWrite"
    StderrWrite = "StderrWrite"
    EnvVarMutation = "EnvVarMutation"
    MutexOp = "MutexOp"
    WaitGroupOp = "WaitGroupOp"
    AtomicOp = "AtomicOp"
    TimeDependency = "TimeDependency"
    ProcessExit = "ProcessExit"
    RecoverBehavior = "RecoverBehavior"

    # P4 — Unsafe / exotic
    ReflectionMutation = "ReflectionMutation"
    UnsafeMutation = "UnsafeMutation"
    CgoCall = "CgoCall"
    FinalizerRegistration = "FinalizerRegistration"
    SyncPoolOp = "SyncPoolOp"
    ClosureCaptureMutation = "ClosureCaptureMutation"


class Tier(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ClassificationLabel(str, Enum):
    contractual = "contractual"
    incidental = "incidental"
    ambiguous = "ambiguous"


class Quadrant(str, Enum):
    Q1_Safe = "Q1_Safe"
    Q2_ComplexButTested = "Q2_ComplexButTested"
    Q3_SimpleButUnderspecified = "Q3_SimpleButUnderspecified"
    Q4_Dangerous = "Q4_Dangerous"


class FixStrategy(str, Enum):
    decompose = "decompose"
    add_tests = "add_tests"
    add_assertions = "add_assertions"
    decompose_and_test = "decompose_and_test"


# ---------------------------------------------------------------------------
# Tier mapping
# ---------------------------------------------------------------------------

TIER_MAP: dict[SideEffectType, Tier] = {
    # P0
    SideEffectType.ReturnValue: Tier.P0,
    SideEffectType.ErrorReturn: Tier.P0,
    SideEffectType.SentinelError: Tier.P0,
    SideEffectType.ReceiverMutation: Tier.P0,
    SideEffectType.PointerArgMutation: Tier.P0,
    # P1
    SideEffectType.SliceMutation: Tier.P1,
    SideEffectType.MapMutation: Tier.P1,
    SideEffectType.GlobalMutation: Tier.P1,
    SideEffectType.WriterOutput: Tier.P1,
    SideEffectType.HTTPResponseWrite: Tier.P1,
    SideEffectType.ChannelSend: Tier.P1,
    SideEffectType.ChannelClose: Tier.P1,
    SideEffectType.DeferredReturnMutation: Tier.P1,
    # P2
    SideEffectType.FileSystemWrite: Tier.P2,
    SideEffectType.FileSystemDelete: Tier.P2,
    SideEffectType.FileSystemMeta: Tier.P2,
    SideEffectType.DatabaseWrite: Tier.P2,
    SideEffectType.DatabaseTransaction: Tier.P2,
    SideEffectType.GoroutineSpawn: Tier.P2,
    SideEffectType.Panic: Tier.P2,
    SideEffectType.CallbackInvocation: Tier.P2,
    SideEffectType.LogWrite: Tier.P2,
    SideEffectType.ContextCancellation: Tier.P2,
    # P3
    SideEffectType.StdoutWrite: Tier.P3,
    SideEffectType.StderrWrite: Tier.P3,
    SideEffectType.EnvVarMutation: Tier.P3,
    SideEffectType.MutexOp: Tier.P3,
    SideEffectType.WaitGroupOp: Tier.P3,
    SideEffectType.AtomicOp: Tier.P3,
    SideEffectType.TimeDependency: Tier.P3,
    SideEffectType.ProcessExit: Tier.P3,
    SideEffectType.RecoverBehavior: Tier.P3,
    # P4
    SideEffectType.ReflectionMutation: Tier.P4,
    SideEffectType.UnsafeMutation: Tier.P4,
    SideEffectType.CgoCall: Tier.P4,
    SideEffectType.FinalizerRegistration: Tier.P4,
    SideEffectType.SyncPoolOp: Tier.P4,
    SideEffectType.ClosureCaptureMutation: Tier.P4,
}


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------


def _generate_side_effect_id() -> str:
    """Generate a unique side-effect ID in the format ``se-XXXXXXXX``."""
    raw = hashlib.sha256(f"{time.time_ns()}".encode()).hexdigest()[:8]
    return f"se-{raw}"


@dataclass
class FunctionTarget:
    package: str
    function: str
    receiver: Optional[str] = None
    signature: Optional[str] = None
    location: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "package": self.package,
            "function": self.function,
            "receiver": self.receiver,
            "signature": self.signature,
            "location": self.location,
        }


@dataclass
class Signal:
    source: str
    weight: float
    source_file: Optional[str] = None
    excerpt: Optional[str] = None
    reasoning: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "weight": self.weight,
            "source_file": self.source_file,
            "excerpt": self.excerpt,
            "reasoning": self.reasoning,
        }


@dataclass
class Classification:
    label: ClassificationLabel
    confidence: int
    signals: list[Signal] = field(default_factory=list)
    reasoning: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label.value,
            "confidence": self.confidence,
            "signals": [s.to_dict() for s in self.signals],
            "reasoning": self.reasoning,
        }


@dataclass
class SideEffect:
    id: str
    type: SideEffectType
    tier: Tier
    location: str
    description: str
    target: Optional[FunctionTarget] = None
    classification: Optional[Classification] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type.value,
            "tier": self.tier.value,
            "location": self.location,
            "description": self.description,
            "target": self.target.to_dict() if self.target else None,
            "classification": self.classification.to_dict() if self.classification else None,
        }


@dataclass
class Metadata:
    gaze_version: str
    python_version: str
    duration_ms: int
    timestamp: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "gaze_version": self.gaze_version,
            "python_version": self.python_version,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "warnings": self.warnings,
        }


@dataclass
class AnalysisResult:
    target: FunctionTarget
    side_effects: list[SideEffect] = field(default_factory=list)
    metadata: Optional[Metadata] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target.to_dict(),
            "side_effects": [se.to_dict() for se in self.side_effects],
            "metadata": self.metadata.to_dict() if self.metadata else None,
        }
