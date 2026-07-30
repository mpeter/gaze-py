"""O1 quality assessment pipeline entry point.

Orchestrates the full pipeline:
  1. Detect and classify side effects in the source path.
  2. Discover test functions in the tests path.
  3. For each test function: pair → detect assertions → build bindings →
     map assertions → compute coverage → build QualityReport.
"""

from __future__ import annotations

import collections
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gaze_py.analysis.files import collect_py_files
from gaze_py.analysis.runner import detect_and_classify, project_docs_text
from gaze_py.config.loader import GazeConfig
from gaze_py.quality.assertions import detect_assertions
from gaze_py.quality.coverage import compute_contract_coverage
from gaze_py.quality.mapper import build_call_bindings, map_assertions_to_effects
from gaze_py.quality.models import TestFunc
from gaze_py.quality.pairing import _build_astroid_graph, find_test_functions, pair_to_targets
from gaze_py.taxonomy.models import (
    AssertionKind,
    ContractCoverageResult,
    FunctionTarget,
    OverSpecification,
    QualityReport,
    TestTargetPair,
)


@dataclass(frozen=True)
class AssessResult:
    """Result of a full O1 quality assessment pipeline run.

    Separates test-function-keyed reports from production functions that have
    no paired test, so callers can distinguish "tested but low coverage" from
    "never tested at all" (D6 in design.md).

    Attributes:
        reports: One QualityReport per discovered test function (paired).
            Every entry has a non-empty test_function name.
        untested: One QualityReport per production function with detected
            effects that was never the target_function of any test-keyed
            report. Every entry uses test_function="" as a sentinel.
            Populated only on unfiltered assess() calls (target_func=None).
    """

    reports: tuple[QualityReport, ...]
    untested: tuple[QualityReport, ...]


def assess(
    src_path: Path,
    tests_path: Path,
    *,
    config: GazeConfig,
    target_func: str | None = None,
    include_unexported: bool = True,
) -> AssessResult:
    """Run the full O1 quality assessment pipeline.

    Detects and classifies side effects in src_path, discovers test functions
    in tests_path, pairs each test with its production target, detects
    assertions, maps them to effects, and computes contract coverage.

    Args:
        src_path: Source directory or file to analyze for side effects.
        tests_path: Test directory or file containing test functions to assess.
        config: GazeConfig with classification thresholds.
        target_func: If provided, restrict output to test functions that pair
            to this production function name. Filtering is applied after pairing.
            When set, AssessResult.untested is always empty (filtering would
            incorrectly mark tested-but-filtered functions as untested).
        include_unexported: When True (default), include underscore-prefixed
            (private) functions in the source analysis. When False, restrict
            to public functions only. Defaults to True because Python's ``_``
            prefix is a convention, not an access boundary — private helpers
            are often the most complex and least directly tested parts of a
            codebase. Pass ``include_unexported=False`` to restore the old
            public-only behaviour.

    Returns:
        AssessResult with .reports (one per test function) and .untested
        (one per unmatched production function with effects). Returns an
        AssessResult with empty tuples if no test functions are discovered
        in tests_path — this is not an error.
    """
    # Step 1: detect and classify source functions (uses shared runner, M1 fixed).
    # include_unexported=True by default so private helpers are included (D1 in design.md).
    # Project docs text augments Signal 5 (O3) — Go's quality path consumes
    # classifications attached by the docs-aware analysis pipeline, so the
    # quality command must classify with the same docs augmentation as
    # analyze/crap or the same effect gets a different label per command.
    source_targets = detect_and_classify(
        src_path.resolve(),
        config=config,
        include_unexported=include_unexported,
        docs_text=project_docs_text(src_path.resolve(), config),
    )

    # Build a lookup map: function name → all FunctionTargets with that name.
    # A list, not a single value — multiple production functions can share a
    # bare name across different files/classes (e.g. a method and an
    # unrelated top-level function both named "add_note"). Resolved via
    # _resolve_target() using TestTargetPair.target_file to disambiguate.
    target_map: dict[str, list[FunctionTarget]] = collections.defaultdict(list)
    for t in source_targets:
        target_map[t.function].append(t)

    # Step 2: discover test functions.
    test_funcs = _collect_test_functions(tests_path)
    if not test_funcs:
        return AssessResult(reports=(), untested=())

    # Step 3: prepare a LAZY Astroid call graph for Strategy 3 pairing (D2).
    # The graph is expensive (astroid inference over every file, preceded by
    # a global MANAGER.clear_cache()) and is only consulted for tests that
    # Strategies 1–2 fail to pair. The provider builds it at most once per
    # assess() call, and not at all when name/call-site pairing succeeds
    # for every test — the common case (audit P3, docs/audit-2026-07-12.md).
    test_files: list[Path] = list(dict.fromkeys(Path(tf.filename) for tf in test_funcs))
    src_files: list[Path] = list(collect_py_files(src_path))
    graph_cache: dict[str, set[str]] | None = None

    def graph_provider() -> dict[str, set[str]]:
        nonlocal graph_cache
        if graph_cache is None:
            graph_cache = _build_astroid_graph(test_files, src_files)
        return graph_cache

    # Step 4: process each test function through the pipeline.
    reports: list[QualityReport] = []

    for test_func in test_funcs:
        report = _process_test_func(
            test_func,
            source_targets=source_targets,
            target_map=target_map,
            config=config,
            target_func=target_func,
            astroid_graph_provider=graph_provider,
        )
        if report is not None:
            reports.append(report)

    # Step 5: collect untested production functions (D6 in design.md).
    # seen is (function, file_path) pairs, not bare names — a bare-name set
    # would incorrectly mark an untested function as "seen" whenever an
    # unrelated same-named function elsewhere was tested (e.g. testing
    # GHIssueStore.add_note must not suppress the untested-function entry
    # for an unrelated top-level add_note in a different file).
    seen: set[tuple[str, str]] = {
        (r.target_function.function, r.target_function.file_path)
        for r in reports
        if r.target_function is not None
    }

    if target_func is None:
        # Unfiltered run: compute untested reports for all unpaired source functions.
        untested = _untested_reports(tuple(source_targets), seen, config)
    else:
        # Filtered run: seen_names is filtered, so we cannot reliably determine
        # which functions are truly untested. Set untested to empty (B-03).
        untested = ()

    return AssessResult(reports=tuple(reports), untested=untested)


def _resolve_target(
    pair: TestTargetPair,
    target_map: dict[str, list[FunctionTarget]],
) -> FunctionTarget | None:
    """Resolve a TestTargetPair to its concrete FunctionTarget.

    target_name alone is not a unique key when multiple production
    functions share a bare name (e.g. a method and an unrelated top-level
    function both named "add_note"). When target_map has more than one
    candidate for pair.target_name, disambiguates via pair.target_file —
    refusing (returning None) rather than guessing when target_file does
    not resolve it to exactly one candidate. A refused resolution surfaces
    as "Inferred target not found" in the caller, which is honest: better
    than silently misattributing contract coverage to the wrong function.

    Args:
        pair: The TestTargetPair to resolve. pair.target_name must not be None.
        target_map: Function name → all FunctionTargets sharing that name.

    Returns:
        The matched FunctionTarget, or None when target_name has no
        candidates or is ambiguous and unresolved.
    """
    assert pair.target_name is not None, "caller must check pair.target_name before resolving"
    candidates = target_map.get(pair.target_name, [])
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1 and pair.target_file is not None:
        matches = [c for c in candidates if c.file_path == pair.target_file]
        if len(matches) == 1:
            return matches[0]
    return None


def _process_test_func(
    test_func: TestFunc,
    *,
    source_targets: list[FunctionTarget],
    target_map: dict[str, list[FunctionTarget]],
    config: GazeConfig,
    target_func: str | None,
    astroid_graph_provider: Callable[[], dict[str, set[str]]] | None = None,
) -> QualityReport | None:
    """Process a single test function through the full pipeline.

    Args:
        test_func: The test function to process.
        source_targets: All production FunctionTargets from the source analysis.
        target_map: Lookup map from function name to FunctionTarget.
        config: GazeConfig with classification thresholds.
        target_func: Optional filter — skip if pair doesn't match this name.
        astroid_graph_provider: Optional zero-arg callable returning the
            caller→callees adjacency dict for Strategy 3 transitive pairing.
            Invoked only when Strategies 1–2 fail. When None, Strategy 3 is
            skipped.

    Returns:
        A QualityReport, or None when the test function is filtered out.
    """
    # Pair the test function with a production target.
    pair = pair_to_targets(
        test_func,
        source_targets,
        astroid_graph_provider=astroid_graph_provider,
    )

    # If target_func filter is set, skip non-matching pairs.
    if target_func is not None and pair.target_name != target_func:
        return None

    # Detect assertions in the test function.
    assertions = detect_assertions(test_func)

    # If no target was found, emit a report with no coverage.
    if pair.target_name is None:
        return QualityReport(
            test_function=test_func.name,
            target_function=None,
            assertions=tuple(assertions),
            contract_coverage=None,
            warnings=("No production target found for this test function.",),
            test_location=f"{test_func.filename}:{test_func.lineno}",
        )

    production_target = _resolve_target(pair, target_map)
    if production_target is None:
        # Target name was inferred but not found in the source map.
        return QualityReport(
            test_function=test_func.name,
            target_function=None,
            assertions=tuple(assertions),
            contract_coverage=None,
            warnings=(f"Inferred target '{pair.target_name}' not found in source analysis.",),
            test_location=f"{test_func.filename}:{test_func.lineno}",
        )

    # Build call bindings (which variable holds the return value).
    bindings = build_call_bindings(test_func, pair.target_name)

    # Map assertions to effects.
    mapped = map_assertions_to_effects(assertions, production_target, bindings)

    # Compute contract coverage.
    coverage = compute_contract_coverage(production_target, mapped, config=config)

    # Compute over-specification score.
    total_assertions = len(assertions)
    over_spec_count = coverage.over_specification_count if coverage is not None else 0
    over_spec_ratio = over_spec_count / total_assertions if total_assertions > 0 else 0.0

    # Compute assertion detection confidence per T113:
    # mapped / total * 100, where "mapped" = assertions with a known kind
    # (kind != AssertionKind.UNKNOWN). When total == 0, confidence is 100
    # (no assertions means nothing was missed).
    if total_assertions == 0:
        assertion_confidence = 100
    else:
        mapped_count = sum(1 for a in assertions if a.kind != AssertionKind.UNKNOWN)
        assertion_confidence = round(mapped_count / total_assertions * 100)

    return QualityReport(
        test_function=test_func.name,
        target_function=production_target,
        assertions=tuple(assertions),
        contract_coverage=coverage,
        warnings=(),
        complexity=production_target.complexity,
        test_location=f"{test_func.filename}:{test_func.lineno}",
        over_specification=OverSpecification(count=over_spec_count, ratio=over_spec_ratio),
        assertion_count=total_assertions,
        assertion_detection_confidence=assertion_confidence,
    )


def _untested_reports(
    source_targets: tuple[FunctionTarget, ...],
    seen: set[tuple[str, str]],
    config: GazeConfig,
) -> tuple[QualityReport, ...]:
    """Build QualityReport entries for production functions with no paired test.

    For each FunctionTarget whose (function, file_path) is not in seen, calls
    compute_contract_coverage() with no_test_coverage=True and emits a
    QualityReport with test_function="" as a sentinel (D6 in design.md).

    Args:
        source_targets: All production FunctionTargets from source analysis.
        seen: Set of (function, file_path) pairs already covered by paired
            test-keyed reports. Functions matching an entry are skipped.
            Keyed on the pair, not bare function name — a bare-name key
            would incorrectly suppress an untested entry whenever an
            unrelated same-named function elsewhere was tested.
        config: GazeConfig with classification thresholds.

    Returns:
        Tuple of QualityReport entries for unpaired production functions.
        Empty tuple when all production functions are paired.
    """
    results: list[QualityReport] = []
    for target in source_targets:
        if (target.function, target.file_path) in seen:
            continue
        coverage = compute_contract_coverage(target, [], config=config, no_test_coverage=True)
        results.append(
            QualityReport(
                test_function="",
                target_function=target,
                assertions=(),
                contract_coverage=coverage,
                warnings=("No test targets this function.",),
                complexity=target.complexity,
            )
        )
    return tuple(results)


def _collect_test_functions(tests_path: Path) -> list[TestFunc]:
    """Collect all test functions from a file or directory.

    Delegates to `collect_py_files()` which applies the standard skip-dir
    filter (cache, venv, node_modules, etc.).

    Args:
        tests_path: A single .py file or a directory to scan recursively.

    Returns:
        List of TestFunc objects from all discovered test files.
    """
    results: list[TestFunc] = []
    for py_file in collect_py_files(tests_path):
        results.extend(find_test_functions(py_file))
    return results


def build_contract_coverage_map(
    src_path: Path,
    tests_path: Path,
    config: GazeConfig,
    *,
    include_unexported: bool = True,
) -> dict[tuple[str, str], ContractCoverageResult]:
    """Build a mapping from (function, file_path) to its best ContractCoverageResult.

    Runs the full O1 quality assessment pipeline via ``assess()`` and
    consolidates the results into a flat dict keyed by (function, file_path)
    — not bare function name. A bare-name key would misattribute contract
    coverage across same-named functions in different files/classes: e.g.
    an untested top-level ``add_note`` would silently inherit a fully-tested
    ``SomeClass.add_note``'s 100% coverage (the exact false-positive class
    that led fieldkit-cmd to disable the CRAP/contract-coverage gate,
    reproduced deterministically via this field: 100% -> 50% on an
    unmodified function). When multiple test functions target the SAME
    (function, file_path), the entry with the highest ``percentage`` is
    kept (or the first entry when both percentages are ``None``).

    On any exception from ``assess()``, a warning is emitted to stderr and
    an empty dict is returned so callers can degrade gracefully (OC-003).

    Args:
        src_path: Source directory or file to analyze for side effects.
        tests_path: Test directory or file containing test functions to assess.
        config: GazeConfig with classification thresholds.
        include_unexported: When True (default), include underscore-prefixed
            (private) functions. Forwarded to ``assess()``.

    Returns:
        Dict mapping (function, file_path) → ContractCoverageResult.  Empty
        when the pipeline fails or no reports are produced.
    """
    try:
        result = assess(src_path, tests_path, config=config, include_unexported=include_unexported)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"warning: quality pipeline failed: {exc}\n")
        return {}

    coverage_map: dict[tuple[str, str], ContractCoverageResult] = {}
    for report in result.reports + result.untested:
        if report.target_function is None or report.contract_coverage is None:
            continue
        # target_function is FunctionTarget | None; already checked None above.
        key = (report.target_function.function, report.target_function.file_path)
        ccr = report.contract_coverage
        if key not in coverage_map:
            coverage_map[key] = ccr
        else:
            existing = coverage_map[key]
            # Keep the entry with the higher percentage; when both are None,
            # the first entry wins (insertion order preserved).
            if ccr.percentage is not None and (
                existing.percentage is None or ccr.percentage > existing.percentage
            ):
                coverage_map[key] = ccr
    return coverage_map
