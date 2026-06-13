"""CLI entry point for gaze-py.

Provides two subcommands:
- analyze <path>: Detect side effects and compute CRAP scores for a path.
- report <src> <tests>: Like analyze, but accepts a tests directory argument
  (O1 quality assessment deferred — tests directory is ignored with a warning).

Per CS-008: all output via click.echo(), never print(). Errors to stderr with
err=True. Exit non-zero on fatal errors via raise SystemExit(1).

Per design.md: GazeParseError from the detector is caught, a warning is emitted
to stderr, and analysis continues with other files.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from gaze_py.analysis.detector import FileDetector
from gaze_py.classify.engine import ClassificationEngine
from gaze_py.config.loader import GazeConfig, load_config
from gaze_py.crap.scorer import (
    crap,
    crapload,
    fix_strategy,
    recommended_actions,
)
from gaze_py.report.json_formatter import to_json
from gaze_py.report.text_formatter import to_text
from gaze_py.taxonomy.exceptions import GazeConfigError, GazeParseError
from gaze_py.taxonomy.models import AnalysisResult, FunctionTarget, Score, Summary


@click.group()
def cli() -> None:
    """gaze-py — Python side-effect detector and CRAP scorer."""


@cli.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--coverage-json",
    "coverage_json",
    type=click.Path(exists=False),
    default=None,
    help="Path to coverage.py JSON report (coverage json output).",
)
def analyze(path: str, output_format: str, coverage_json: str | None) -> None:
    """Detect side effects and compute CRAP scores for PATH.

    PATH may be a single .py file or a directory. Directories are scanned
    recursively for all .py files.

    When --coverage-json is provided, line coverage is read from the
    coverage.py JSON report and used to compute CRAP scores.
    """
    src_path = Path(path)
    if not src_path.exists():
        click.echo(f"Error: path does not exist: {path}", err=True)
        raise SystemExit(1)

    config = load_config(src_path)
    try:
        coverage_data = _load_coverage_json(coverage_json)
    except GazeConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e

    result = _run_pipeline(src_path, config, coverage_data)
    _emit(result, output_format)


@cli.command()
@click.argument("src", type=click.Path(exists=False))
@click.argument("tests", type=click.Path(exists=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--coverage-json",
    "coverage_json",
    type=click.Path(exists=False),
    default=None,
    help="Path to coverage.py JSON report (coverage json output).",
)
def report(src: str, tests: str, output_format: str, coverage_json: str | None) -> None:
    """Detect side effects and compute CRAP scores for SRC.

    TESTS is accepted but ignored in this release — O1 quality assessment
    (assertion mapping) is deferred to a future change.

    SRC may be a single .py file or a directory. Directories are scanned
    recursively for all .py files.
    """
    # Emit the O1 deferral warning to stderr (per design.md Report command behavior).
    click.echo(
        "Warning: report --tests: quality assessment (O1) deferred — ignoring tests directory",
        err=True,
    )

    src_path = Path(src)
    if not src_path.exists():
        click.echo(f"Error: path does not exist: {src}", err=True)
        raise SystemExit(1)

    config = load_config(src_path)
    try:
        coverage_data = _load_coverage_json(coverage_json)
    except GazeConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e

    result = _run_pipeline(src_path, config, coverage_data)
    _emit(result, output_format)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _load_coverage_json(coverage_json: str | None) -> dict[str, float] | None:
    """Load coverage data from a coverage.py JSON report.

    Args:
        coverage_json: Path to the coverage.py JSON report, or None when
            --coverage-json was not provided.

    Returns:
        Dict mapping relative file path → percent_covered (float [0, 100]),
        or None when coverage_json is None.

    Raises:
        SystemExit: When the coverage file does not exist, is not valid JSON,
            or lacks the required 'files' key.
    """
    if coverage_json is None:
        return None

    cov_path = Path(coverage_json).resolve()

    if not cov_path.exists():
        click.echo(
            f"Error: coverage-json file does not exist: {cov_path}",
            err=True,
        )
        raise SystemExit(1)

    try:
        raw_text = cov_path.read_text(encoding="utf-8")
    except OSError as e:
        raise GazeConfigError(f"Cannot read coverage JSON {cov_path}: {e}") from e
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise GazeConfigError(f"Failed to parse coverage JSON {cov_path}: {e}") from e

    if not isinstance(raw, dict) or "files" not in raw:
        click.echo(
            f"Error: coverage JSON {cov_path} lacks required 'files' key. "
            'Expected format: {"files": {"<path>": {"summary": {"percent_covered": N}}}}',
            err=True,
        )
        raise SystemExit(1)

    # Build a flat map: relative_path → percent_covered
    coverage_map: dict[str, float] = {}
    files_section = raw["files"]
    if isinstance(files_section, dict):
        for file_path, file_data in files_section.items():
            if (
                isinstance(file_data, dict)
                and isinstance(file_data.get("summary"), dict)
                and "percent_covered" in file_data["summary"]
            ):
                pct = file_data["summary"]["percent_covered"]
                if isinstance(pct, (int, float)):
                    coverage_map[str(file_path)] = float(pct)

    return coverage_map


_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".ruff_cache", "dist"}
)


def _collect_py_files(path: Path) -> list[Path]:
    """Collect all .py files under path (recursively for directories).

    Skips common non-source directories (.git, __pycache__, .venv, etc.)
    to avoid analyzing virtual-environment or cache files.

    Args:
        path: A .py file or a directory to scan recursively.

    Returns:
        Sorted list of .py file paths.
    """
    if path.is_file():
        return [path] if path.suffix == ".py" else []
    return sorted(p for p in path.rglob("*.py") if not any(part in _SKIP_DIRS for part in p.parts))


def _resolve_line_coverage(
    py_file: Path,
    root: Path,
    coverage_data: dict[str, float] | None,
) -> float | None:
    """Resolve line coverage fraction for a single file.

    Tries the project-relative path first, then falls back to the filename.
    Converts percent_covered (0-100) from coverage_data to a fraction (0.0-1.0).

    Args:
        py_file: Absolute path to the Python source file.
        root: Project root directory.
        coverage_data: Dict mapping relative path → percent_covered (0-100), or None.

    Returns:
        Line coverage fraction in [0.0, 1.0], or None when not available.
    """
    if coverage_data is None:
        return None
    if py_file.is_relative_to(root):
        rel = str(py_file.relative_to(root))
    else:
        rel = py_file.name
    pct = coverage_data.get(rel) or coverage_data.get(py_file.name)
    if pct is None:
        return None
    # Convert percentage (0-100) to fraction (0.0-1.0) for the scorer.
    return pct / 100.0


def _score_target(
    target: FunctionTarget,
    *,
    line_coverage_frac: float | None,
    config: GazeConfig,
) -> None:
    """Compute and attach a Score to a FunctionTarget in-place.

    Args:
        target: The FunctionTarget to score.
        line_coverage_frac: Line coverage fraction in [0.0, 1.0], or None.
        config: GazeConfig providing CRAP threshold values.
    """
    crap_score = crap(target.complexity, line_coverage_frac)
    strategy = fix_strategy(
        crap_score=crap_score,
        complexity=target.complexity,
        line_coverage=line_coverage_frac,
        quadrant_label=None,  # O1 deferred — quadrant always None
        threshold=config.crap_threshold,
        complexity_threshold=int(config.crap_threshold),
    )
    # "no_effects_detected" for pure functions (zero effects), per OC-003.
    contract_coverage_reason: str | None = None
    if not target.effects:
        contract_coverage_reason = "no_effects_detected"

    target.score = Score(
        line_coverage=line_coverage_frac,
        crap=crap_score,
        gaze_crap=None,  # O1 deferred
        contract_coverage=None,  # O1 deferred
        contract_coverage_reason=contract_coverage_reason,
        fix_strategy=strategy,
        quadrant=None,  # O1 deferred
        effect_confidence_range=None,  # deferred to future change
    )


def _build_summary(
    all_targets: list[FunctionTarget],
    *,
    config: GazeConfig,
    coverage_data: dict[str, float] | None,
) -> Summary:
    """Build the Summary aggregate from all analyzed targets.

    Args:
        all_targets: All FunctionTargets from the analysis run.
        config: GazeConfig providing threshold values.
        coverage_data: Coverage data dict, or None when not provided.

    Returns:
        Summary with aggregate statistics.
    """
    crapload_count = len(crapload(all_targets, threshold=config.crap_threshold))

    # recommended_actions: None when coverage not provided; [] when coverage
    # provided but no functions in CRAPload (OC-003).
    rec_actions: list[dict[str, object]] | None
    if coverage_data is None:
        rec_actions = None
    else:
        rec_actions = recommended_actions(all_targets)

    # avg_line_coverage: None when coverage not provided
    avg_line_coverage: float | None = None
    if coverage_data is not None:
        coverages = [
            t.score.line_coverage
            for t in all_targets
            if t.score is not None and t.score.line_coverage is not None
        ]
        avg_line_coverage = sum(coverages) / len(coverages) if coverages else None

    return Summary(
        function_count=len(all_targets),
        crapload=crapload_count,
        gaze_crapload=None,  # O1 deferred
        avg_line_coverage=avg_line_coverage,
        avg_contract_coverage=None,  # O1 deferred
        quadrant_counts=None,  # O1 deferred
        fix_strategy_counts=None,  # O1 deferred
        recommended_actions=rec_actions,
        crap_threshold=config.crap_threshold,
        gaze_crap_threshold=config.gaze_crap_threshold,
    )


def _run_pipeline(
    src_path: Path,
    config: GazeConfig,
    coverage_data: dict[str, float] | None,
) -> AnalysisResult:
    """Run the full detect → classify → score pipeline.

    Args:
        src_path: Source path (file or directory) to analyze.
        config: GazeConfig with threshold values.
        coverage_data: Dict mapping relative path → percent_covered, or None.

    Returns:
        AnalysisResult with all functions, scores, and summary.
    """
    root = src_path.resolve() if src_path.is_dir() else src_path.resolve().parent
    py_files = _collect_py_files(src_path.resolve())

    engine = ClassificationEngine(config.contractual_threshold, config.incidental_threshold)
    all_targets: list[FunctionTarget] = []

    for py_file in py_files:
        try:
            targets = FileDetector.detect(py_file, root=root, callers=None)
        except GazeParseError as e:
            click.echo(f"Warning: {e}", err=True)
            continue

        line_coverage_frac = _resolve_line_coverage(py_file, root, coverage_data)

        for target in targets:
            # Classify each effect (last effect wins for primary classification).
            for effect in target.effects:
                target.classification = engine.classify(effect, target)
            _score_target(target, line_coverage_frac=line_coverage_frac, config=config)

        all_targets.extend(targets)

    summary = _build_summary(all_targets, config=config, coverage_data=coverage_data)
    return AnalysisResult(functions=all_targets, summary=summary)


def _emit(result: AnalysisResult, output_format: str) -> None:
    """Emit the analysis result in the requested format.

    Args:
        result: The AnalysisResult to emit.
        output_format: One of "json" or "text".
    """
    if output_format == "json":
        click.echo(to_json(result))
    else:
        click.echo(to_text(result))
