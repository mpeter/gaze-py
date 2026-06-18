"""Side effect type taxonomy for gaze-py.

Defines the canonical 38-value SideEffectType enum, the 5-tier Tier enum,
and the TIER_MAP mapping each effect type to its tier.

Per EC-001: tier assignments are fixed by the porting contracts and MUST NOT
be configurable.
"""

from __future__ import annotations

import enum

# NOTE: porting contracts say "37 types" in their headers but enumeration yields
# 38 (P0=5+P1=8+P2=10+P3=9+P4=6). Tests assert 38.


class Tier(enum.Enum):
    """Priority tier for a side effect type.

    Tiers determine the base confidence boost applied during classification
    and the detection requirement level (P0 = zero false negatives).
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class SideEffectType(enum.StrEnum):
    """Canonical 38-value side effect type taxonomy.

    Values are retained verbatim from the Go gaze taxonomy to preserve JSON
    schema compatibility per OC-002 and EC-001. Python-specific detection
    uses language-appropriate patterns (e.g., GoroutineSpawn detects
    threading.Thread) but the type string remains unchanged.
    """

    # --- P0: Must Detect (5) ---
    ReturnValue = "ReturnValue"
    ErrorReturn = "ErrorReturn"
    SentinelError = "SentinelError"
    ReceiverMutation = "ReceiverMutation"
    PointerArgMutation = "PointerArgMutation"

    # --- P1: High Value (8) ---
    SliceMutation = "SliceMutation"
    MapMutation = "MapMutation"
    GlobalMutation = "GlobalMutation"
    WriterOutput = "WriterOutput"
    HTTPResponseWrite = "HTTPResponseWrite"
    ChannelSend = "ChannelSend"
    ChannelClose = "ChannelClose"
    DeferredReturnMutation = "DeferredReturnMutation"

    # --- P2: Important (10) ---
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

    # --- P3: Nice to Have (9) ---
    StdoutWrite = "StdoutWrite"
    StderrWrite = "StderrWrite"
    EnvVarMutation = "EnvVarMutation"
    MutexOp = "MutexOp"
    WaitGroupOp = "WaitGroupOp"
    # PERMANENTLY CLOSED — no Python equivalent.
    # Python has no atomic primitive. threading.local is thread-local
    # storage, not an atomic read-modify-write. ctypes atomics are
    # indistinguishable from general ctypes calls (already CgoCall).
    # Remains in taxonomy for porting contract compatibility (EC-001).
    AtomicOp = "AtomicOp"
    TimeDependency = "TimeDependency"
    ProcessExit = "ProcessExit"
    RecoverBehavior = "RecoverBehavior"

    # --- P4: Exotic (6) ---
    ReflectionMutation = "ReflectionMutation"
    UnsafeMutation = "UnsafeMutation"
    CgoCall = "CgoCall"
    FinalizerRegistration = "FinalizerRegistration"
    # PERMANENTLY CLOSED — no Python equivalent.
    # Go's sync.Pool has no Python equivalent. Object reuse pools
    # in Python are application-level; no stdlib type matches the
    # semantics. Remains in taxonomy for porting contract compatibility.
    SyncPoolOp = "SyncPoolOp"
    ClosureCaptureMutation = "ClosureCaptureMutation"


# Mapping from each SideEffectType to its Tier.
# This is the authoritative source for tier lookups — do not duplicate inline.
TIER_MAP: dict[SideEffectType, Tier] = {
    # P0 — 5 types
    SideEffectType.ReturnValue: Tier.P0,
    SideEffectType.ErrorReturn: Tier.P0,
    SideEffectType.SentinelError: Tier.P0,
    SideEffectType.ReceiverMutation: Tier.P0,
    SideEffectType.PointerArgMutation: Tier.P0,
    # P1 — 8 types
    SideEffectType.SliceMutation: Tier.P1,
    SideEffectType.MapMutation: Tier.P1,
    SideEffectType.GlobalMutation: Tier.P1,
    SideEffectType.WriterOutput: Tier.P1,
    SideEffectType.HTTPResponseWrite: Tier.P1,
    SideEffectType.ChannelSend: Tier.P1,
    SideEffectType.ChannelClose: Tier.P1,
    SideEffectType.DeferredReturnMutation: Tier.P1,
    # P2 — 10 types
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
    # P3 — 9 types
    SideEffectType.StdoutWrite: Tier.P3,
    SideEffectType.StderrWrite: Tier.P3,
    SideEffectType.EnvVarMutation: Tier.P3,
    SideEffectType.MutexOp: Tier.P3,
    SideEffectType.WaitGroupOp: Tier.P3,
    SideEffectType.AtomicOp: Tier.P3,
    SideEffectType.TimeDependency: Tier.P3,
    SideEffectType.ProcessExit: Tier.P3,
    SideEffectType.RecoverBehavior: Tier.P3,
    # P4 — 6 types
    SideEffectType.ReflectionMutation: Tier.P4,
    SideEffectType.UnsafeMutation: Tier.P4,
    SideEffectType.CgoCall: Tier.P4,
    SideEffectType.FinalizerRegistration: Tier.P4,
    SideEffectType.SyncPoolOp: Tier.P4,
    SideEffectType.ClosureCaptureMutation: Tier.P4,
}
