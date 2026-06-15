"""O1 quality assessment pipeline entry point.

Orchestrates the full pipeline:
  1. Detect and classify side effects in the source path.
  2. Discover test functions in the tests path.
  3. For each test function: pair → detect assertions → build bindings →
     map assertions → compute coverage → build QualityReport.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gaze_py.analysis.files import collect_py_files
from gaze_py.analysis.runner import detect_and_classify
from gaze_py.config.loader import GazeConfig
from gaze_py.quality.assertions import detect_assertions
from gaze_py.quality.coverage import compute_contract_coverage
from gaze_py.quality.mapper import build_call_bindings, map_assertions_to_effects
from gaze_py.quality.models import TestFunc
from gaze_py.quality.pairing import _build_astroid_graph, find_test_functions, pair_to_targets
from gaze_py.taxonomy.models import FunctionTarget, QualityReport


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

    Returns:
        AssessResult with .reports (one per test function) and .untested
        (one per unmatched production function with effects). Returns an
        AssessResult with empty tuples if no test functions are discovered
        in tests_path — this is not an error.
    """
    # Step 1: detect and classify source functions (uses shared runner, M1 fixed).
    source_targets = detect_and_classify(src_path.resolve(), config=config)

    # Build a lookup map: function name → FunctionTarget.
    target_map: dict[str, FunctionTarget] = {t.name: t for t in source_targets}

    # Step 2: discover test functions.
    test_funcs = _collect_test_functions(tests_path)
    if not test_funcs:
        return AssessResult(reports=(), untested=())

    # Step 3: build Astroid call graph once for Strategy 3 pairing (D2).
    # Deduplicate file paths — one path per file, not one per test function.
    test_files: list[Path] = list(dict.fromkeys(Path(tf.filename) for tf in test_funcs))
    src_files: list[Path] = list(collect_py_files(src_path))
    graph = _build_astroid_graph(test_files, src_files)

    # Step 4: process each test function through the pipeline.
    reports: list[QualityReport] = []

    for test_func in test_funcs:
        report = _process_test_func(
            test_func,
            source_targets=source_targets,
            target_map=target_map,
            config=config,
            target_func=target_func,
            astroid_graph=graph,
        )
        if report is not None:
            reports.append(report)

    # Step 5: collect untested production functions (D6 in design.md).
    # seen_names is the set of non-None target_function values from paired reports.
    seen_names: set[str] = {r.target_function for r in reports if r.target_function is not None}

    if target_func is None:
        # Unfiltered run: compute untested reports for all unpaired source functions.
        untested = _untested_reports(tuple(source_targets), seen_names, config)
    else:
        # Filtered run: seen_names is filtered, so we cannot reliably determine
        # which functions are truly untested. Set untested to empty (B-03).
        untested = ()

    return AssessResult(reports=tuple(reports), untested=untested)


def _process_test_func(
    test_func: TestFunc,
    *,
    source_targets: list[FunctionTarget],
    target_map: dict[str, FunctionTarget],
    config: GazeConfig,
    target_func: str | None,
    astroid_graph: dict[str, set[str]] | None = None,
) -> QualityReport | None:
    """Process a single test function through the full pipeline.

    Args:
        test_func: The test function to process.
        source_targets: All production FunctionTargets from the source analysis.
        target_map: Lookup map from function name to FunctionTarget.
        config: GazeConfig with classification thresholds.
        target_func: Optional filter — skip if pair doesn't match this name.
        astroid_graph: Optional caller→callees adjacency dict for Strategy 3
            transitive call graph pairing. When None, Strategy 3 is skipped.

    Returns:
        A QualityReport, or None when the test function is filtered out.
    """
    # Pair the test function with a production target.
    pair = pair_to_targets(test_func, source_targets, astroid_graph=astroid_graph)

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
        )

    production_target = target_map.get(pair.target_name)
    if production_target is None:
        # Target name was inferred but not found in the source map.
        return QualityReport(
            test_function=test_func.name,
            target_function=pair.target_name,
            assertions=tuple(assertions),
            contract_coverage=None,
            warnings=(f"Inferred target '{pair.target_name}' not found in source analysis.",),
        )

    # Build call bindings (which variable holds the return value).
    bindings = build_call_bindings(test_func, pair.target_name)

    # Map assertions to effects.
    mapped = map_assertions_to_effects(assertions, production_target, bindings)

    # Compute contract coverage.
    coverage = compute_contract_coverage(production_target, mapped, config=config)

    return QualityReport(
        test_function=test_func.name,
        target_function=pair.target_name,
        assertions=tuple(assertions),
        contract_coverage=coverage,
        warnings=(),
        complexity=production_target.complexity,
    )


def _untested_reports(
    source_targets: tuple[FunctionTarget, ...],
    seen_names: set[str],
    config: GazeConfig,
) -> tuple[QualityReport, ...]:
    """Build QualityReport entries for production functions with no paired test.

    For each FunctionTarget whose name is not in seen_names, calls
    compute_contract_coverage() with no_test_coverage=True and emits a
    QualityReport with test_function="" as a sentinel (D6 in design.md).

    Args:
        source_targets: All production FunctionTargets from source analysis.
        seen_names: Set of target_function values already covered by paired
            test-keyed reports. Functions in this set are skipped.
        config: GazeConfig with classification thresholds.

    Returns:
        Tuple of QualityReport entries for unpaired production functions.
        Empty tuple when all production functions are paired.
    """
    results: list[QualityReport] = []
    for target in source_targets:
        if target.name in seen_names:
            continue
        coverage = compute_contract_coverage(target, [], config=config, no_test_coverage=True)
        results.append(
            QualityReport(
                test_function="",
                target_function=target.name,
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
