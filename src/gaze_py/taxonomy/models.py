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
        classification: Per-effect classification result, or None before
            classification runs. Mirrors Go's SideEffect.Classification
            (types.go) — each effect carries its own classification, and
            JSON serialization emits it per effect (omitted when None,
            matching Go's omitempty). Attached via dataclasses.replace()
            in the runner since SideEffect is frozen.
    """

    id: str
    type: SideEffectType
    tier: Tier
    location: str  # "file:line:col"
    description: str
    target: str  # function qualified name
    classification: ClassificationResult | None = None


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
        effect_confidence_range: ``(min_confidence, max_confidence)`` as a
            tuple of two ints in [0, 100] when all detected effects on the
            function are classified as ambiguous (``reason == "all_effects_ambiguous"``
            in the O1 quality pipeline). ``None`` in all other cases, including
            when O1 has not run. Per OC-003, the field MUST be present in JSON
            output and serializes as a two-element array or null.
    """

    line_coverage: float | None = None
    crap: float | None = None
    gaze_crap: float | None = None
    contract_coverage: float | None = None
    contract_coverage_reason: str | None = None
    fix_strategy: str | None = None
    quadrant: str | None = None
    effect_confidence_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class Metadata:
    """Analysis run metadata injected at serialization time.

    Populated by the JSON formatter — not stored in the model pipeline.
    This avoids circular imports and keeps models pure.

    Attributes:
        gaze_version: gaze-py version string (from gaze_py.__version__).
        warnings: Non-fatal warnings from the analysis run. Reserved for future
            use — always an empty tuple in this version. Analysis warnings are
            currently emitted to stderr only and are not threaded into the pipeline.
        duration_ms: Wall-clock milliseconds from run start to serialization.
        timestamp: ISO 8601 UTC timestamp in YYYY-MM-DDTHH:mm:SSZ format,
            matching Go's time.RFC3339 (seconds precision, Z suffix).
    """

    gaze_version: str
    warnings: tuple[str, ...]
    duration_ms: int
    timestamp: str


@dataclass
class FunctionTarget:
    """A single analyzed function with its detected effects and scores.

    Mutable so the pipeline can populate fields incrementally (detect →
    classify → score).

    Attributes:
        function: Simple function name (not qualified). Named ``function``
            (not ``name``) so dataclasses.asdict() serializes as ``"function"``
            per FR-002 / OC-002.
        file_path: Project-relative path to the source file.
        line: Line number where the function is defined (1-indexed).
        complexity: McCabe cyclomatic complexity computed by
            analysis/complexity.py.
        package: Project-relative file path (Python equivalent of Go's
            import path). Populated at construction time in detector.py.
        receiver: Class name for methods (e.g., ``"FileDetector"``), or
            ``None`` for module-level functions. Populated at construction.
        signature: Full function signature reconstructed from the AST
            ``arguments`` node (e.g., ``"def parse(text: str) -> int"``).
            Falls back to ``"def <name>(...)"`` only when annotation
            reconstruction raises. Populated at construction.
        caller_count: Number of distinct caller modules (from the pre-pass
            caller map). Defaults to 0 when no caller map is provided.
        effects: All detected side effects for this function.
        classification: Legacy per-function classification slot. No longer
            populated by the pipeline — classification is per effect
            (SideEffect.classification), matching the Go schema. Retained
            for API compatibility; always None after detect_and_classify().
        score: Scoring metrics, or None before scoring runs.
        docstring: The function's docstring text, or None when absent.
            Analysis context for the classification engine (Signal 5);
            not serialized into JSON output.
        class_bases: Base class names of the enclosing class for methods
            (e.g., ["ABC", "Protocol"]), or None for module-level functions
            and methods of base-less classes. Analysis context for the
            interface signal (Signal 1); not serialized.
        return_type_hint: String form of the return annotation (e.g.,
            "int", "None"), or None when unannotated. Analysis context for
            the visibility signal (Signal 2); not serialized.
    """

    function: str
    file_path: str
    line: int
    complexity: int
    package: str
    receiver: str | None
    signature: str
    caller_count: int = 0
    effects: list[SideEffect] = field(default_factory=list)
    classification: ClassificationResult | None = None
    score: Score | None = None
    docstring: str | None = None
    class_bases: list[str] | None = None
    return_type_hint: str | None = None


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
        results: One FunctionTarget per analyzed function, in file order.
            Named ``results`` (not ``functions``) per FR-001 / OC-002 to
            match the Go gaze reference implementation's JSON field name.
        summary: Aggregate statistics for the run.
    """

    results: list[FunctionTarget]
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
        target_file: file_path of the matched FunctionTarget, or None. Set
            whenever target_name is set. Disambiguates same-named functions
            across different files/classes — target_name alone is not a
            unique key when multiple production functions share a bare
            name (e.g. a method and an unrelated top-level function both
            named "add_note"). Consumers that look up the FunctionTarget
            by name MUST also match on target_file when more than one
            candidate shares target_name.
        inference_method: "name_convention" | "call_graph" |
            "call_graph_transitive" | "unmatched".
        confidence: 0.0–1.0.
    """

    test_name: str
    target_name: str | None
    inference_method: str
    confidence: float
    target_file: str | None = None


@dataclass(frozen=True)
class ContractCoverageResult:
    """Contract coverage for one test-target pair.

    Attributes:
        percentage: Contract coverage as percentage [0.0, 100.0], or None
            when there are no contractual effects (null-not-zero per OC-003).
            Callers passing this to gaze_crap() or quadrant() MUST divide by 100.
        covered_effects: Count of contractual effects with ≥1 mapped assertion.
        total_contractual: Total contractual effects on the target function.
        covered_count: Alias for covered_effects — serialized as
            ``covered_count`` in JSON per FR-006 / OC-002.
        over_specification_count: Assertions that map to incidental effects.
        unmapped_assertions: Assertions that did not map to any effect.
        reason: Reason code when percentage is None:
            ``"no_effects_detected"`` — function has no detected side effects;
            ``"no_contractual_effects"`` — effects exist but all are incidental;
            ``"all_effects_ambiguous"`` — effects exist but all are ambiguous
            (none contractual, none incidental). ``None`` when coverage is
            computed normally.
            ``"no_test_coverage"`` — effects were detected but no test targets
            this function; percentage is None (null per OC-003 and Go
            porting contract — "no test = no coverage data, not 0%").
        min_confidence: Minimum ``ClassificationResult.score`` across all
            ambiguous effects. Set only when ``reason == "all_effects_ambiguous"``.
        max_confidence: Maximum ``ClassificationResult.score`` across all
            ambiguous effects. Set only when ``reason == "all_effects_ambiguous"``.
        gaps: Contractual effects with no mapped assertion, in the order
            they appear in the target function's effects. Parallel to
            gap_hints. Empty when coverage is 100% or when percentage
            is None (no contractual effects, no_test_coverage, etc.).
        gap_hints: Python assertion snippets, one per gap. Parallel to
            gaps — len(gaps) == len(gap_hints) is an enforced
            postcondition. Empty when gaps is empty.
        discarded_returns: Contractual return/error effects whose values
            were explicitly discarded. Empty tuple — gaze-py does not yet
            detect explicit discard patterns (OC-003 compliant).
        discarded_return_hints: Assertion snippets for discarded returns.
            Parallel to discarded_returns. Empty tuple (OC-003 compliant).
    """

    percentage: float | None
    covered_effects: int
    total_contractual: int
    over_specification_count: int
    unmapped_assertions: int
    reason: str | None = None
    min_confidence: int | None = None
    max_confidence: int | None = None
    gaps: tuple[SideEffect, ...] = ()
    gap_hints: tuple[str, ...] = ()
    discarded_returns: tuple[SideEffect, ...] = ()
    discarded_return_hints: tuple[str, ...] = ()

    @property
    def covered_count(self) -> int:
        """Alias for covered_effects — serialized as covered_count per FR-006."""
        return self.covered_effects


@dataclass(frozen=True)
class OverSpecification:
    """Over-specification score for a test-target pair.

    Measures how many incidental side effects the test asserts on,
    indicating refactoring fragility.

    Attributes:
        count: Number of incidental side effects asserted on.
        ratio: Incidental assertions / total assertions (0.0–1.0).
            0.0 when total assertions is 0.
        incidental_assertions: Mappings to incidental effects.
            Empty tuple — gaze-py does not yet populate this field (OC-003).
        suggestions: Actionable advice per incidental assertion.
            Empty tuple — Go generates these from AI; gaze-py emits [] (OC-003).
    """

    count: int
    ratio: float
    incidental_assertions: tuple[object, ...] = ()
    suggestions: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualityReport:
    """Quality assessment result for one test-target pair.

    Attributes:
        test_function: Name of the test function. Empty string ("") when
            this report represents an unmatched production function with
            no paired test (part of AssessResult.untested). Only appears
            in quality output via AssessResult.untested, never in the
            quality CLI command output.
        target_function: The FunctionTarget being tested, or None if
            unmatched. Type changed from str|None to FunctionTarget|None
            per FR-005 / OC-002 to match Go gaze reference output.
        assertions: Detected assertion sites in the test function.
        contract_coverage: Coverage result (None if no target found).
        warnings: Non-fatal warnings from pairing or mapping.
        complexity: McCabe cyclomatic complexity of the production target,
            or None when no target was found. Used to compute GazeCRAP in
            text output.
        test_location: Source location of the test function (file:line),
            or empty string when not available.
        over_specification: Over-specification score for this pair.
        ambiguous_effects: Side effects excluded from metrics due to
            ambiguous classification.
        assertion_count: Total detected assertion sites in the test function.
        assertion_detection_confidence: Fraction of assertions successfully
            pattern-matched (0–100). 100 when assertion_count is 0.
    """

    test_function: str
    target_function: FunctionTarget | None
    assertions: tuple[AssertionSite, ...]
    contract_coverage: ContractCoverageResult | None
    warnings: tuple[str, ...]
    complexity: int | None = None
    test_location: str = ""
    over_specification: OverSpecification = field(
        default_factory=lambda: OverSpecification(count=0, ratio=0.0)
    )
    ambiguous_effects: tuple[SideEffect, ...] = ()
    assertion_count: int = 0
    assertion_detection_confidence: int = 100


@dataclass
class QualitySummary:
    """Aggregate quality metrics for a quality assessment run.

    Attributes:
        total_tests: Number of test functions analyzed.
        average_contract_coverage: Mean coverage across all paired tests,
            or None when no paired tests exist.
        total_over_specifications: Sum of over_specification.count across
            all paired tests.
        worst_coverage_tests: Test function names with the lowest contract
            coverage (bottom 5). Empty when no paired tests exist.
        assertion_detection_confidence: Mean of per-report
            assertion_detection_confidence values, rounded to nearest int.
    """

    total_tests: int
    average_contract_coverage: float | None
    total_over_specifications: int
    worst_coverage_tests: list[str]
    assertion_detection_confidence: int
