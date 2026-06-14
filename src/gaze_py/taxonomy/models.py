"""Domain model dataclasses for gaze-py.

All value objects use @dataclass(frozen=True) to prevent accidental mutation
after construction. Mutable container/builder objects (FunctionTarget,
AnalysisResult, Summary) use plain @dataclass so the pipeline can build
them incrementally.

Per CR-005: JSON serialization uses dataclasses.asdict() + a custom encoder
in report/json_formatter.py. No to_dict() methods are defined here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from gaze_py.taxonomy.effects import SideEffectType, Tier


@dataclass(frozen=True)
class Signal:
    """A single classification signal with its source and weight.

    Attributes:
        source: Canonical signal source ID (e.g., "naming", "godoc",
            "visibility"). MUST match the identifiers in taxonomy-reference.md.
        weight: Signal weight as a signed integer. Positive weights push
            toward contractual; negative weights push toward incidental.
    """

    source: str
    weight: int


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying a single side effect.

    Attributes:
        label: Classification label — one of "contractual", "ambiguous",
            or "incidental".
        score: Final clamped confidence score in the range [0, 100].
        signals: All signals that contributed to the score, including the
            contradiction signal when both positive and negative signals exist.
    """

    label: str  # "contractual" | "ambiguous" | "incidental"
    score: int
    signals: tuple[Signal, ...]


@dataclass(frozen=True)
class SideEffect:
    """A single detected side effect on a function.

    Attributes:
        id: Deterministic 8-character hex ID prefixed with "se-". Computed
            from sha256(rel_path + ":" + function_name + ":" + effect_type
            + ":" + location).
        type: The SideEffectType enum value for this effect.
        tier: The Tier enum value for this effect (derived from TIER_MAP).
        location: Source location in "file:line:col" format (two colons).
        description: Human-readable description of the detected effect.
        target: Qualified function name that contains this effect.
    """

    id: str
    type: SideEffectType
    tier: Tier
    location: str  # "file:line:col"
    description: str
    target: str  # function qualified name


@dataclass(frozen=True)
class Score:
    """Scoring metrics for a single function.

    All fields that depend on optional capabilities are typed X | None and
    default to None per OC-003 (null-not-zero). Fields are null when the
    corresponding capability has not run.

    Attributes:
        line_coverage: Line coverage fraction [0.0, 1.0] from coverage.py,
            or None when --coverprofile was not provided to gazepy crap.
        crap: CRAP score, or None when line_coverage is None.
        gaze_crap: GazeCRAP score, or None when O1 (contract coverage) has
            not run.
        contract_coverage: Contract coverage percentage [0, 100] from O1,
            or None when O1 has not run.
        contract_coverage_reason: Reason code when contract coverage is 0%
            or diagnostic. Set to "no_effects_detected" for pure functions
            even without O1. All other reason codes require O1.
        fix_strategy: Recommended fix strategy for CRAPload functions, or
            None when CRAP is null or CRAP < crap_threshold.
        quadrant: Quadrant classification (e.g., "Q1_Safe"), or None when
            GazeCRAP is not available.
        effect_confidence_range: Reserved for a future change. Always None
            in this implementation. The field MUST be present and serialize
            as null per OC-003.
    """

    line_coverage: float | None = None
    crap: float | None = None
    gaze_crap: float | None = None
    contract_coverage: float | None = None
    contract_coverage_reason: str | None = None
    fix_strategy: str | None = None
    quadrant: str | None = None
    effect_confidence_range: tuple[int, int] | None = None


@dataclass
class FunctionTarget:
    """A single analyzed function with its detected effects and scores.

    Mutable so the pipeline can populate fields incrementally (detect →
    classify → score).

    Attributes:
        name: Simple function name (not qualified).
        file_path: Project-relative path to the source file.
        line: Line number where the function is defined (1-indexed).
        complexity: McCabe cyclomatic complexity computed by
            analysis/complexity.py.
        caller_count: Number of distinct caller modules (from the pre-pass
            caller map). Defaults to 0 when no caller map is provided.
        effects: All detected side effects for this function.
        classification: Classification result for the primary effect, or
            None before classification runs.
        score: Scoring metrics, or None before scoring runs.
    """

    name: str
    file_path: str
    line: int
    complexity: int
    caller_count: int = 0
    effects: list[SideEffect] = field(default_factory=list)
    classification: ClassificationResult | None = None
    score: Score | None = None


@dataclass
class Summary:
    """Aggregate statistics for an analysis run.

    Attributes:
        function_count: Total number of analyzed functions.
        crapload: Count of functions where CRAP >= crap_threshold.
        gaze_crapload: Count of functions where GazeCRAP >= gaze_crap_threshold,
            or None when O1 has not run.
        avg_line_coverage: Average line coverage across all functions, or
            None when coverage data was not provided.
        avg_contract_coverage: Average contract coverage across all functions,
            or None when O1 has not run.
        quadrant_counts: Count of functions per quadrant, or None when O1
            has not run.
        fix_strategy_counts: Count of functions per fix strategy, or None
            when no CRAP scores are available. Populated whenever CRAP scores
            are computed (does NOT require O1 quality assessment).
        recommended_actions: Prioritized list of recommended actions for
            CRAPload functions. None when CRAP is null (coverage not provided);
            empty list when CRAP is computed but no functions are in CRAPload.
        crap_threshold: CRAP threshold used for CRAPload computation.
            Always non-null — sourced from GazeConfig.
        gaze_crap_threshold: GazeCRAP threshold used for GazeCRAPload
            computation. Always non-null — sourced from GazeConfig.
    """

    function_count: int
    crapload: int | None
    gaze_crapload: int | None = None
    avg_line_coverage: float | None = None
    avg_contract_coverage: float | None = None
    quadrant_counts: dict[str, int] | None = None
    fix_strategy_counts: dict[str, int] | None = None
    recommended_actions: list[dict[str, object]] | None = None
    crap_threshold: float = 15.0
    gaze_crap_threshold: float = 15.0


@dataclass
class AnalysisResult:
    """Top-level result of a gaze-py analysis run.

    Attributes:
        functions: One FunctionTarget per analyzed function, in file order.
        summary: Aggregate statistics for the run.
    """

    functions: list[FunctionTarget]
    summary: Summary


# ---------------------------------------------------------------------------
# O1 quality assessment types
# ---------------------------------------------------------------------------


class AssertionKind(enum.StrEnum):
    """Classification of an assertion pattern found in a test function.

    Values match the canonical assertion taxonomy for the O1 quality pipeline.
    Per EC-001: StrEnum so values serialize as strings automatically.
    """

    STDLIB_EQUALITY = "stdlib_equality"
    STDLIB_NONE_CHECK = "stdlib_none_check"
    STDLIB_ERROR_CHECK = "stdlib_error_check"
    STDLIB_TRUTH = "stdlib_truth"
    STDLIB_RAISES = "stdlib_raises"
    UNITTEST_EQUAL = "unittest_equal"
    UNITTEST_NONE = "unittest_none"
    UNITTEST_RAISES = "unittest_raises"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AssertionSite:
    """Detected assertion location in a test function.

    Attributes:
        location: Source position as "file:line:col" (three-part, matching
            SideEffect.location format). When column is unavailable from
            the AST node, use col=0: "file:line:0".
        kind: Assertion pattern type.
        depth: 0=direct in test body, 1–3=inside helper function.
        referenced_names: Variable names referenced in the assertion expression.
            For calls (e.g., assert f() == g()), collect the function name strings.
            For subscripts (assert result[0] == 1), collect "result".
            For attribute access (assert obj.value == 42), collect "obj".
    """

    location: str
    kind: AssertionKind
    depth: int
    referenced_names: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class TestTargetPair:
    """Pairing between a test function and its inferred target.

    Attributes:
        test_name: Name of the test function.
        target_name: Name of the production function (None if unmatched).
        inference_method: "name_convention" | "call_graph" | "unmatched".
        confidence: 0.0–1.0.
    """

    test_name: str
    target_name: str | None
    inference_method: str
    confidence: float


@dataclass(frozen=True)
class ContractCoverageResult:
    """Contract coverage for one test-target pair.

    Attributes:
        percentage: Contract coverage as percentage [0.0, 100.0], or None
            when there are no contractual effects (null-not-zero per OC-003).
            Callers passing this to gaze_crap() or quadrant() MUST divide by 100.
        covered_effects: Count of contractual effects with ≥1 mapped assertion.
        total_contractual: Total contractual effects on the target function.
        over_specification_count: Assertions that map to incidental effects.
        unmapped_assertions: Assertions that did not map to any effect.
        reason: "no_contractual_effects" | "no_effects_detected" | None.
            Set when percentage is None.
    """

    percentage: float | None
    covered_effects: int
    total_contractual: int
    over_specification_count: int
    unmapped_assertions: int
    reason: str | None = None


@dataclass(frozen=True)
class QualityReport:
    """Quality assessment result for one test-target pair.

    Attributes:
        test_function: Name of the test function.
        target_function: Name of the target function (None if unmatched).
        assertions: Detected assertion sites in the test function.
        contract_coverage: Coverage result (None if no target found).
        warnings: Non-fatal warnings from pairing or mapping.
    """

    test_function: str
    target_function: str | None
    assertions: tuple[AssertionSite, ...]
    contract_coverage: ContractCoverageResult | None
    warnings: tuple[str, ...]
