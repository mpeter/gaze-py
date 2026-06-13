"""Side-effect type taxonomy and core domain dataclasses for GazeCRAP."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SideEffectType(StrEnum):
    """All 37 side-effect types across 5 tiers."""

    # P0 - Direct return / receiver mutations
    ReturnValue = "ReturnValue"
    ErrorReturn = "ErrorReturn"
    SentinelError = "SentinelError"
    ReceiverMutation = "ReceiverMutation"
    PointerArgMutation = "PointerArgMutation"

    # P1 - Collection / channel / deferred mutations
    SliceMutation = "SliceMutation"
    MapMutation = "MapMutation"
    GlobalMutation = "GlobalMutation"
    WriterOutput = "WriterOutput"
    HTTPResponseWrite = "HTTPResponseWrite"
    ChannelSend = "ChannelSend"
    ChannelClose = "ChannelClose"
    DeferredReturnMutation = "DeferredReturnMutation"

    # P2 - I/O, concurrency, callbacks
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

    # P3 - Stdio, env, sync primitives
    StdoutWrite = "StdoutWrite"
    StderrWrite = "StderrWrite"
    EnvVarMutation = "EnvVarMutation"
    MutexOp = "MutexOp"
    WaitGroupOp = "WaitGroupOp"
    AtomicOp = "AtomicOp"
    TimeDependency = "TimeDependency"
    ProcessExit = "ProcessExit"
    RecoverBehavior = "RecoverBehavior"

    # P4 - Unsafe / exotic
    ReflectionMutation = "ReflectionMutation"
    UnsafeMutation = "UnsafeMutation"
    CgoCall = "CgoCall"
    FinalizerRegistration = "FinalizerRegistration"
    SyncPoolOp = "SyncPoolOp"
    ClosureCaptureMutation = "ClosureCaptureMutation"


class Tier(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ClassificationLabel(StrEnum):
    contractual = "contractual"
    incidental = "incidental"
    ambiguous = "ambiguous"


class Quadrant(StrEnum):
    Q1_Safe = "Q1_Safe"
    Q2_ComplexButTested = "Q2_ComplexButTested"
    Q3_SimpleButUnderspecified = "Q3_SimpleButUnderspecified"
    Q4_Dangerous = "Q4_Dangerous"


class FixStrategy(StrEnum):
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


@dataclass
class FunctionTarget:
    package: str
    function: str
    receiver: str | None = None
    signature: str | None = None
    location: str | None = None

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
    source_file: str | None = None
    excerpt: str | None = None
    reasoning: str | None = None

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
    reasoning: str | None = None

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
    target: FunctionTarget | None = None
    classification: Classification | None = None

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
    gaze_py_version: str
    python_version: str
    duration_ms: int
    timestamp: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "gaze_version": self.gaze_version,
            "gaze_py_version": self.gaze_py_version,
            "python_version": self.python_version,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "warnings": self.warnings,
        }


@dataclass
class AnalysisResult:
    """Complete analysis result for one function under test."""

    target: FunctionTarget
    side_effects: list[SideEffect] = field(default_factory=list)
    metadata: Metadata | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict representation."""
        return {
            "target": self.target.to_dict(),
            "side_effects": [se.to_dict() for se in self.side_effects],
            "metadata": self.metadata.to_dict() if self.metadata else None,
        }


# ---------------------------------------------------------------------------
# Quality / assertion mapper domain types (S2)
# ---------------------------------------------------------------------------


@dataclass
class AssertionMapping:
    """Mapping of one test assertion to a side effect.

    Attributes:
        assertion_text: Source text of the assert statement.
        location: File and line reference in ``file.py:line`` format.
        confidence: Mapping confidence score in the range 0-100.
        mapped_effect: The matched ``SideEffectType``, or ``None`` if
            the assertion could not be mapped to any known effect.
        unmapped_reason: Short token explaining why the assertion was
            not mapped.  One of ``"helper_param"``, ``"inline_call"``,
            or ``"no_effect_match"``.  ``None`` when ``mapped_effect``
            is set.
    """

    assertion_text: str
    location: str
    confidence: int
    mapped_effect: SideEffectType | None = None
    unmapped_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict representation."""
        d: dict[str, object] = {
            "assertion_text": self.assertion_text,
            "location": self.location,
            "confidence": self.confidence,
        }
        if self.mapped_effect is not None:
            d["mapped_effect"] = self.mapped_effect.value
        if self.unmapped_reason is not None:
            d["unmapped_reason"] = self.unmapped_reason
        return d


@dataclass
class ContractCoverage:
    """Contract coverage metrics for one test function.

    Attributes:
        percentage: Fraction of contractual effects covered, expressed
            as a value in the range 0.0-100.0.
        covered_count: Number of contractual effects that have at least
            one mapped assertion.
        total_contractual: Total number of contractual effects detected
            in the function under test.
        gaps: Contractual ``SideEffect`` instances that have no
            corresponding assertion in the test.
        gap_hints: Suggested assert snippets, one per entry in
            ``gaps``, to guide the developer toward full coverage.
    """

    percentage: float
    covered_count: int
    total_contractual: int
    gaps: list[SideEffect] = field(default_factory=list)
    gap_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict representation."""
        return {
            "percentage": self.percentage,
            "covered_count": self.covered_count,
            "total_contractual": self.total_contractual,
            "gaps": [e.to_dict() for e in self.gaps],
            "gap_hints": self.gap_hints,
        }


@dataclass
class OverSpecificationScore:
    """Over-specification metrics for one test function.

    Attributes:
        count: Number of assertions that target incidental effects.
        ratio: Fraction of all assertions that are over-specified,
            in the range 0.0-1.0.
        incidental_assertions: ``AssertionMapping`` entries whose
            ``mapped_effect`` is classified as incidental.
        suggestions: One plain-English suggestion per entry in
            ``incidental_assertions`` explaining how to remove the
            over-specification.
    """

    count: int
    ratio: float
    incidental_assertions: list[AssertionMapping] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict representation."""
        return {
            "count": self.count,
            "ratio": self.ratio,
            "incidental_assertions": [a.to_dict() for a in self.incidental_assertions],
            "suggestions": self.suggestions,
        }


@dataclass
class QualityReport:
    """Quality analysis result for one test function.

    Attributes:
        test_function: Fully-qualified name of the test function.
        test_location: File and line reference for the test function.
        target_function: Identity and location of the function under
            test.
        contract_coverage: Coverage metrics for contractual effects.
        over_specification: Over-specification metrics.
        ambiguous_effects: ``SideEffect`` instances whose
            classification could not be determined with confidence.
        unmapped_assertions: Assertions that could not be mapped to
            any detected side effect.
        assertion_count: Total number of assert statements found in
            the test function.
        assertion_detection_confidence: Overall confidence (0-100)
            that all assertions in the test were detected correctly.
    """

    test_function: str
    test_location: str
    target_function: FunctionTarget
    contract_coverage: ContractCoverage
    over_specification: OverSpecificationScore
    ambiguous_effects: list[SideEffect] = field(default_factory=list)
    unmapped_assertions: list[AssertionMapping] = field(default_factory=list)
    assertion_count: int = 0
    assertion_detection_confidence: int = 0
    # Note: plan.md specifies a metadata: Metadata field. It is deliberately
    # omitted in v1 — metadata is a reporting concern, not a domain concern.
    # The JSON formatter (report/json.py) attaches metadata at serialisation
    # time via build_metadata(), keeping it out of the domain model.
    # See ADR-002 and plan.md "Modified files" section.

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict representation."""
        return {
            "test_function": self.test_function,
            "test_location": self.test_location,
            "target_function": self.target_function.to_dict(),
            "contract_coverage": self.contract_coverage.to_dict(),
            "over_specification": self.over_specification.to_dict(),
            "ambiguous_effects": [e.to_dict() for e in self.ambiguous_effects],
            "unmapped_assertions": [a.to_dict() for a in self.unmapped_assertions],
            "assertion_count": self.assertion_count,
            "assertion_detection_confidence": self.assertion_detection_confidence,
        }


@dataclass
class PackageSummary:
    """Summary metrics across all test functions in a package.

    Attributes:
        total_tests: Total number of test functions analysed.
        average_contract_coverage: Mean contract coverage percentage
            across all test functions (0.0-100.0).
        total_over_specifications: Sum of over-specification counts
            across all test functions.
        assertion_detection_confidence: Mean assertion-detection
            confidence across all test functions (0-100).
        worst_coverage_tests: ``QualityReport`` entries for the test
            functions with the lowest contract coverage, sorted
            ascending by ``contract_coverage.percentage``.
    """

    total_tests: int
    average_contract_coverage: float
    total_over_specifications: int
    assertion_detection_confidence: int
    worst_coverage_tests: list[QualityReport] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict representation."""
        return {
            "total_tests": self.total_tests,
            "average_contract_coverage": self.average_contract_coverage,
            "total_over_specifications": self.total_over_specifications,
            "assertion_detection_confidence": self.assertion_detection_confidence,
            "worst_coverage_tests": [r.to_dict() for r in self.worst_coverage_tests],
        }


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

# Contractual effect types: P0 and P1 effects that are expected
# observable outputs of a function.  Used by the assertion mapper (S2).
# Design note: frozenset chosen over a set literal so that membership
# tests are O(1) and the constant cannot be mutated at runtime
# (SOLID Open/Closed — extend by adding new types, not by modifying
# this set directly; callers should use ``is_contractual()``).
_CONTRACTUAL_TYPES: frozenset[SideEffectType] = frozenset(
    {
        SideEffectType.ReturnValue,
        SideEffectType.ErrorReturn,
        SideEffectType.SentinelError,
        SideEffectType.ReceiverMutation,
        SideEffectType.PointerArgMutation,
        SideEffectType.GlobalMutation,
    }
)


def is_contractual(effect_type: SideEffectType) -> bool:
    """Return ``True`` if the side effect type is contractual (P0-P1).

    Contractual effects are expected observable outputs that tests
    should assert on.  Incidental effects are implementation details
    that tests should not over-specify.

    Args:
        effect_type: The ``SideEffectType`` to classify.

    Returns:
        ``True`` when *effect_type* is in the contractual set,
        ``False`` otherwise.
    """
    return effect_type in _CONTRACTUAL_TYPES
