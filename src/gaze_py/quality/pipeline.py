"""O1 quality assessment pipeline entry point.

Orchestrates the full pipeline:
  1. Detect and classify side effects in the source path.
  2. Discover test functions in the tests path.
  3. For each test function: pair → detect assertions → build bindings →
     map assertions → compute coverage → build QualityReport.
"""

from __future__ import annotations

from pathlib import Path

from gaze_py.analysis.detector import FileDetector
from gaze_py.classify.engine import ClassificationEngine
from gaze_py.config.loader import GazeConfig
from gaze_py.quality.assertions import detect_assertions
from gaze_py.quality.coverage import compute_contract_coverage
from gaze_py.quality.mapper import build_call_bindings, map_assertions_to_effects
from gaze_py.quality.models import TestFunc
from gaze_py.quality.pairing import find_test_functions, pair_to_targets
from gaze_py.taxonomy.exceptions import GazeParseError
from gaze_py.taxonomy.models import FunctionTarget, QualityReport

# Directories to skip when collecting Python source files.
_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".ruff_cache", "dist"}
)


def assess(
    src_path: Path,
    tests_path: Path,
    *,
    config: GazeConfig,
    target_func: str | None = None,
) -> list[QualityReport]:
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

    Returns:
        List of QualityReport, one per discovered test function. Returns an
        empty list if no test functions are discovered in tests_path — this
        is not an error.
    """
    # Step 1: detect and classify source functions.
    source_targets = _detect_and_classify(src_path.resolve(), config=config)

    # Build a lookup map: function name → FunctionTarget.
    target_map: dict[str, FunctionTarget] = {t.name: t for t in source_targets}

    # Step 2: discover test functions.
    test_funcs = _collect_test_functions(tests_path)
    if not test_funcs:
        return []

    # Step 3: process each test function through the pipeline.
    reports: list[QualityReport] = []

    for test_func in test_funcs:
        report = _process_test_func(
            test_func,
            source_targets=source_targets,
            target_map=target_map,
            config=config,
            target_func=target_func,
        )
        if report is not None:
            reports.append(report)

    return reports


def _process_test_func(
    test_func: TestFunc,
    *,
    source_targets: list[FunctionTarget],
    target_map: dict[str, FunctionTarget],
    config: GazeConfig,
    target_func: str | None,
) -> QualityReport | None:
    """Process a single test function through the full pipeline.

    Args:
        test_func: The test function to process.
        source_targets: All production FunctionTargets from the source analysis.
        target_map: Lookup map from function name to FunctionTarget.
        config: GazeConfig with classification thresholds.
        target_func: Optional filter — skip if pair doesn't match this name.

    Returns:
        A QualityReport, or None when the test function is filtered out.
    """
    # Pair the test function with a production target.
    pair = pair_to_targets(test_func, source_targets)

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
    )


def _detect_and_classify(
    src_path: Path,
    *,
    config: GazeConfig,
) -> list[FunctionTarget]:
    """Detect side effects and classify them for all functions in src_path.

    Mirrors the logic of cli.main._run_detect_classify() but lives in the
    quality package to avoid a circular import (cli.main imports from quality).

    Args:
        src_path: Resolved source path (file or directory) to analyze.
        config: GazeConfig with classification thresholds.

    Returns:
        List of FunctionTarget with effects and classification results.
        No Score objects are attached.
    """
    root = src_path if src_path.is_dir() else src_path.parent
    py_files = _collect_py_files(src_path)
    engine = ClassificationEngine(config.contractual_threshold, config.incidental_threshold)
    all_targets: list[FunctionTarget] = []

    for py_file in py_files:
        try:
            targets = FileDetector.detect(py_file, root=root, callers=None)
        except GazeParseError:
            continue

        for target in targets:
            for effect in target.effects:
                target.classification = engine.classify(effect, target)
            all_targets.append(target)

    return all_targets


def _collect_py_files(path: Path) -> list[Path]:
    """Collect all .py files under path (recursively for directories).

    Args:
        path: A .py file or a directory to scan recursively.

    Returns:
        Sorted list of .py file paths.
    """
    if path.is_file():
        return [path] if path.suffix == ".py" else []
    return sorted(p for p in path.rglob("*.py") if not any(part in _SKIP_DIRS for part in p.parts))


def _collect_test_functions(tests_path: Path) -> list[TestFunc]:
    """Collect all test functions from a file or directory.

    Args:
        tests_path: A single .py file or a directory to scan recursively.

    Returns:
        List of TestFunc objects from all discovered test files.
    """
    results: list[TestFunc] = []
    if tests_path.is_file():
        results.extend(find_test_functions(tests_path))
    elif tests_path.is_dir():
        for py_file in sorted(tests_path.rglob("*.py")):
            results.extend(find_test_functions(py_file))
    return results
