"""CLI entry point for gaze-py.

Provides subcommands:
- analyze <path>: Detect side effects and optionally classify them. CRAP scoring
  has moved to 'gazepy crap'. All CRAP-derived output fields are null.
- crap <path>: Detect, classify, and compute CRAP/GazeCRAP scores. Optionally
  runs pytest as a subprocess to collect coverage data automatically.
- quality [path]: Stub — requires O1 (change 002/A).
- docscan [path]: Stub — requires O3.
- report [path]: Stub — migration guidance to 'gazepy crap'.
- schema: Emit the JSON schema for AnalysisResult output.
- self-check: Run CRAP analysis on gaze-py's own source.
- init: Scaffold .opencode agent + command assets into the current project.

Per CS-008: all output via click.echo(), never print(). Errors to stderr with
err=True. Exit non-zero on fatal errors via raise SystemExit(N).

Per CR-006: no rich dependency. Use click.echo() only.
Per CS-016: functions with 4+ parameters use keyword-only args after *.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from gaze_py import __version__ as _version
from gaze_py.analysis.detector import FileDetector
from gaze_py.classify.engine import ClassificationEngine
from gaze_py.cli.scaffold import run as _scaffold_run
from gaze_py.config.loader import GazeConfig, load_config, load_config_explicit
from gaze_py.crap.scorer import (
    crap as compute_crap,
)
from gaze_py.crap.scorer import (
    crapload,
    fix_strategy,
    recommended_actions,
)
from gaze_py.report.json_formatter import SCHEMA, to_json
from gaze_py.report.text_formatter import to_text
from gaze_py.taxonomy.exceptions import GazeConfigError, GazeParseError
from gaze_py.taxonomy.models import AnalysisResult, FunctionTarget, Score, Summary


@click.group()
def cli() -> None:
    """gaze-py — Python side-effect detector and CRAP scorer."""


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="json",
    show_default=True,
    help="Output format. (default differs from Go gaze which defaults to text)",
)
@click.option(
    "--classify",
    "-c",
    is_flag=True,
    default=False,
    help="Run the classification engine on detected effects.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Full signal breakdown (implies --classify).",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to .gaze.yaml configuration file (default: walk-up search).",
)
@click.option(
    "--contractual-threshold",
    "contractual_threshold",
    type=int,
    default=None,
    help="Override contractual confidence threshold from config.",
)
@click.option(
    "--incidental-threshold",
    "incidental_threshold",
    type=int,
    default=None,
    help="Override incidental confidence threshold from config.",
)
@click.option(
    "--function",
    "-f",
    "function_name",
    type=str,
    default=None,
    help="Analyze a specific function by name.",
)
@click.option(
    "--include-unexported",
    "include_unexported",
    is_flag=True,
    default=False,
    help="Include underscore-prefixed (unexported) functions.",
)
def analyze(
    path: str,
    output_format: str,
    classify: bool,
    verbose: bool,
    config_path: str | None,
    contractual_threshold: int | None,
    incidental_threshold: int | None,
    function_name: str | None,
    include_unexported: bool,
) -> None:
    """Detect side effects for PATH and optionally classify them.

    PATH may be a single .py file or a directory. Directories are scanned
    recursively for all .py files.

    CRAP scoring has moved to 'gazepy crap'. All CRAP-derived fields
    (line_coverage, crap, fix_strategy, etc.) are null in this command's output.
    Use 'gazepy crap [path]' for CRAP scoring.

    Note: --format defaults to json (differs from Go gaze which defaults to text).
    """
    src_path = Path(path)
    if not src_path.exists():
        click.echo(f"Error: path does not exist: {path}", err=True)
        raise SystemExit(2)

    if config_path is not None:
        try:
            config = load_config_explicit(Path(config_path))
        except GazeConfigError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(2) from e
    else:
        config = load_config(src_path)

    # Apply CLI threshold overrides after config load.
    if contractual_threshold is not None:
        config.contractual_threshold = contractual_threshold
    if incidental_threshold is not None:
        config.incidental_threshold = incidental_threshold

    # --verbose implies --classify
    run_classify = classify or verbose

    targets = _run_detect_classify(
        src_path.resolve(),
        config=config,
        classify=run_classify,
        function_filter=function_name,
        include_unexported=include_unexported,
    )

    # Build summary with all CRAP-derived fields null per OC-003.
    summary = Summary(
        function_count=len(targets),
        crapload=None,
        gaze_crapload=None,
        avg_line_coverage=None,
        avg_contract_coverage=None,
        quadrant_counts=None,
        fix_strategy_counts=None,
        recommended_actions=None,
        crap_threshold=config.crap_threshold,
        gaze_crap_threshold=config.gaze_crap_threshold,
    )
    result = AnalysisResult(functions=targets, summary=summary)
    _emit(result, output_format)


# ---------------------------------------------------------------------------
# crap command
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--coverprofile",
    type=click.Path(exists=False),
    default=None,
    help="Path to a pre-generated coverage.py JSON report. "
    "When omitted, gazepy runs pytest automatically.",
)
@click.option(
    "--crap-threshold",
    "crap_threshold",
    type=float,
    default=15.0,
    show_default=True,
    help="CRAP score threshold for CRAPload computation.",
)
@click.option(
    "--gaze-crap-threshold",
    "gaze_crap_threshold",
    type=float,
    default=15.0,
    show_default=True,
    help="GazeCRAP score threshold (accepted; enforcement requires O1).",
)
@click.option(
    "--max-crapload",
    "max_crapload",
    type=int,
    default=0,
    show_default=True,
    help="CI gate: fail (exit 1) when crapload exceeds this value. 0 = no limit.",
)
@click.option(
    "--max-gaze-crapload",
    "max_gaze_crapload",
    type=int,
    default=0,
    show_default=True,
    help="CI gate: accepted, enforcement deferred until O1. 0 = no limit.",
)
@click.option(
    "--ai-mapper",
    "ai_mapper",
    type=str,
    default=None,
    hidden=True,
    help="AI mapper to use for classification (accepted; ignored until O1).",
)
@click.option(
    "--ai-mapper-model",
    "ai_mapper_model",
    type=str,
    default=None,
    hidden=True,
    help="AI mapper model (accepted; ignored until O1).",
)
@click.option(
    "--baseline",
    type=click.Path(exists=False),
    default=None,
    help="Baseline file for delta reporting (stub: not yet implemented).",
)
def crap(
    path: str,
    output_format: str,
    coverprofile: str | None,
    crap_threshold: float,
    gaze_crap_threshold: float,
    max_crapload: int,
    max_gaze_crapload: int,
    ai_mapper: str | None,
    ai_mapper_model: str | None,
    baseline: str | None,
) -> None:
    """Detect side effects and compute CRAP scores for PATH.

    PATH may be a single .py file or a directory. Directories are scanned
    recursively for all .py files.

    When --coverprofile is not provided, gazepy automatically runs pytest with
    coverage collection. Use --coverprofile to supply a pre-generated report.

    CI gate: --max-crapload exits 1 when the crapload count exceeds the limit.
    """
    # --baseline stub — exit 1 (not 2) with clear message.
    if baseline is not None:
        click.echo(
            "Error: --baseline is not yet implemented in gazepy.",
            err=True,
        )
        raise SystemExit(1)

    # PATH validation — must happen before subprocess or analysis.
    src = Path(path).resolve()
    if not src.exists():
        click.echo(f"Error: path does not exist: {path}", err=True)
        raise SystemExit(2)

    config = load_config(src)
    config.crap_threshold = crap_threshold
    config.gaze_crap_threshold = gaze_crap_threshold

    # Coverage acquisition — two paths.
    coverage_data: dict[str, float] | None

    if coverprofile is not None:
        # Path A: explicit --coverprofile provided.
        try:
            coverage_data = _load_coverage_json(coverprofile)
        except GazeConfigError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(2) from e
    else:
        # Path B: auto-run pytest for coverage.
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_f:
            tmp = tmp_f.name
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    f"--cov={src}",
                    "--cov-report",
                    f"json:{tmp}",
                    "-q",
                    "--tb=no",
                ],
                check=True,
                capture_output=True,
            )
            coverage_data = _load_coverage_json(tmp)
        except (subprocess.CalledProcessError, OSError):
            # pytest not installed, not found, or exited non-zero.
            click.echo(
                "Warning: pytest failed or is not installed — "
                "continuing without coverage data. "
                "Use --coverprofile to provide a pre-generated report.",
                err=True,
            )
            coverage_data = None
        except Exception as exc:  # noqa: BLE001  # _load_coverage_json parse errors
            # GazeConfigError (ValueError) or any other JSON parse failure.
            click.echo(
                f"Warning: coverage JSON could not be parsed — continuing without coverage data. "
                f"({exc})",
                err=True,
            )
            coverage_data = None
        finally:
            Path(tmp).unlink(missing_ok=True)

    result = _run_crap(src, coverage_data, config=config)
    _emit(result, output_format)

    # CI threshold enforcement — after emitting output.
    if max_gaze_crapload > 0:
        click.echo(
            "Warning: --max-gaze-crapload is not enforced until O1 "
            "(quality assessment) is implemented. Threshold check skipped.",
            err=True,
        )

    if (
        max_crapload > 0
        and result.summary.crapload is not None
        and result.summary.crapload > max_crapload
    ):
        click.echo(
            f"CI gate: crapload={result.summary.crapload} exceeds --max-crapload={max_crapload}",
            err=True,
        )
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# quality command (stub — task 3)
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", type=click.Path(exists=False), required=False)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option("--target", type=str, default=None, help="Target package or module.")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Full signal breakdown.",
)
@click.option(
    "--include-unexported",
    "include_unexported",
    is_flag=True,
    default=False,
    help="Include underscore-prefixed functions.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to .gaze.yaml configuration file.",
)
@click.option(
    "--contractual-threshold",
    "contractual_threshold",
    type=int,
    default=None,
    help="Override contractual confidence threshold.",
)
@click.option(
    "--incidental-threshold",
    "incidental_threshold",
    type=int,
    default=None,
    help="Override incidental confidence threshold.",
)
@click.option(
    "--min-contract-coverage",
    "min_contract_coverage",
    type=float,
    default=None,
    help="Minimum contract coverage percentage required.",
)
@click.option(
    "--max-over-specification",
    "max_over_specification",
    type=float,
    default=None,
    help="Maximum allowed over-specification percentage.",
)
@click.option(
    "--ai-mapper",
    "ai_mapper",
    type=str,
    default=None,
    hidden=True,
    help="AI mapper for classification (requires O1).",
)
@click.option(
    "--ai-mapper-model",
    "ai_mapper_model",
    type=str,
    default=None,
    hidden=True,
    help="AI mapper model (requires O1).",
)
def quality(
    path: str | None,
    output_format: str,
    target: str | None,
    verbose: bool,
    include_unexported: bool,
    config_path: str | None,
    contractual_threshold: int | None,
    incidental_threshold: int | None,
    min_contract_coverage: float | None,
    max_over_specification: float | None,
    ai_mapper: str | None,
    ai_mapper_model: str | None,
) -> None:
    """Assess contract coverage and over-specification for PATH (stub).

    Requires O1 quality assessment — tracked in change 002/A.
    Use Go gaze for full capability: gaze quality [packages]
    """
    click.echo(
        "Error: quality is not yet implemented in gazepy.\n"
        "       Requires O1 (quality assessment) — tracked in change 002/A.\n"
        "       Use Go gaze for full capability: gaze quality [packages]",
        err=True,
    )
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# docscan command (stub — task 4)
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", type=click.Path(exists=False), required=False)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to .gaze.yaml configuration file.",
)
def docscan(path: str | None, config_path: str | None) -> None:
    """Scan documentation coverage for PATH (stub).

    Requires O3 — tracked in a future change.
    Use Go gaze for full capability: gaze docscan [packages]
    """
    click.echo(
        "Error: docscan is not yet implemented in gazepy.\n"
        "       Requires O3 — tracked in a future change.\n"
        "       Use Go gaze for full capability: gaze docscan [packages]",
        err=True,
    )
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# report command (stub — task 5, replaces old (src, tests) signature)
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", type=click.Path(exists=False), required=False)
@click.option(
    "--ai",
    "ai_provider",
    type=str,
    default=None,
    help="AI provider for report generation (requires O1+O2).",
)
@click.option(
    "--model",
    type=str,
    default=None,
    help="AI model to use for report generation.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--coverprofile",
    type=click.Path(exists=False),
    default=None,
    help="Path to a pre-generated coverage.py JSON report.",
)
@click.option(
    "--max-crapload",
    "max_crapload",
    type=int,
    default=0,
    show_default=True,
    help="CI gate: fail when crapload exceeds this value. 0 = no limit.",
)
@click.option(
    "--max-gaze-crapload",
    "max_gaze_crapload",
    type=int,
    default=0,
    show_default=True,
    help="CI gate: accepted, enforcement deferred until O1.",
)
@click.option(
    "--min-contract-coverage",
    "min_contract_coverage",
    type=float,
    default=None,
    help="Minimum contract coverage percentage (requires O1).",
)
@click.option(
    "--ai-timeout",
    "ai_timeout",
    type=int,
    default=None,
    help="Timeout in seconds for AI provider calls.",
)
def report(
    path: str | None,
    ai_provider: str | None,
    model: str | None,
    output_format: str,
    coverprofile: str | None,
    max_crapload: int,
    max_gaze_crapload: int,
    min_contract_coverage: float | None,
    ai_timeout: int | None,
) -> None:
    """Generate AI-enhanced analysis report for PATH (stub).

    Requires O1+O2 — use 'gazepy crap [path]' for CRAP scoring previously
    available via 'gazepy report'.
    """
    click.echo(
        "Error: report is not yet implemented in gazepy (requires O1+O2).\n"
        "       Use 'gazepy crap [path]' for CRAP scoring previously available\n"
        "       via 'gazepy report'.\n"
        "       Use Go gaze for full AI reports: gaze report [packages] --ai=claude",
        err=True,
    )
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _load_coverage_json(coverage_json: str | None) -> dict[str, float] | None:
    """Load coverage data from a coverage.py JSON report.

    Raises GazeConfigError for all error conditions so callers can decide
    the appropriate exit code and user-facing message.

    Args:
        coverage_json: Path string to the coverage.py JSON report, or None
            when no coverage file was specified.

    Returns:
        Dict mapping relative file path → percent_covered (float [0, 100]),
        or None when coverage_json is None.

    Raises:
        GazeConfigError: When the file does not exist, cannot be read, is not
            valid JSON, or lacks the required 'files' key.
    """
    if coverage_json is None:
        return None

    cov_path = Path(coverage_json).resolve()

    if not cov_path.exists():
        raise GazeConfigError(f"coverage file does not exist: {cov_path}")

    try:
        raw_text = cov_path.read_text(encoding="utf-8")
    except OSError as e:
        raise GazeConfigError(f"Cannot read coverage JSON {cov_path}: {e}") from e

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise GazeConfigError(f"Failed to parse coverage JSON {cov_path}: {e}") from e

    if not isinstance(raw, dict) or "files" not in raw:
        raise GazeConfigError(
            f"coverage JSON {cov_path} lacks required 'files' key. "
            'Expected format: {"files": {"<path>": {"summary": {"percent_covered": N}}}}'
        )

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
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
    }
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

    Tries three lookup keys in order (most specific → least specific):

    1. Root-relative path (``analysis/complexity.py``) — matches when the
       analysis root equals the working directory from which pytest was run.
    2. Cwd-relative path (``src/gaze_py/analysis/complexity.py``) — matches
       the common case where users run ``gazepy crap src/mypackage/`` from
       the project root and coverage.py stores keys relative to that root.
       This attempt is silently skipped (falls through to filename-only) when
       ``py_file`` is not under ``Path.cwd()``, e.g. for absolute paths that
       lie outside the project or unusual filesystem layouts.
    3. Filename-only (``complexity.py``) — last-resort fallback for any
       remaining edge cases.

    Converts ``percent_covered`` (0–100) from *coverage_data* to a fraction
    (0.0–1.0) for the CRAP scorer.

    Args:
        py_file: Absolute path to the Python source file.
        root: Project root directory used to compute the root-relative key.
        coverage_data: Dict mapping relative path → percent_covered (0-100),
            or None when no coverage data is available.

    Returns:
        Line coverage fraction in [0.0, 1.0], or None when not available.
    """
    if coverage_data is None:
        return None
    if py_file.is_relative_to(root):
        rel = str(py_file.relative_to(root))
    else:
        rel = py_file.name

    # Attempt 2: cwd-relative key (e.g. "src/gaze_py/analysis/complexity.py").
    # Silently skipped when py_file is not under Path.cwd().
    cwd_rel: str | None = None
    if py_file.is_relative_to(Path.cwd()):
        cwd_rel = str(py_file.relative_to(Path.cwd()))

    pct = (
        coverage_data.get(rel)
        or (coverage_data.get(cwd_rel) if cwd_rel else None)
        or coverage_data.get(py_file.name)
    )
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
    crap_score = compute_crap(target.complexity, line_coverage_frac)
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
    """Build the Summary aggregate from all analyzed and scored targets.

    Args:
        all_targets: All FunctionTargets from the analysis run (must have scores).
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

    # avg_line_coverage: None when coverage not provided.
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


def _run_detect_classify(
    src_path: Path,
    *,
    config: GazeConfig,
    classify: bool = False,
    function_filter: str | None = None,
    include_unexported: bool = False,
) -> list[FunctionTarget]:
    """Run the detect pipeline and optionally classify side effects.

    Does NOT compute CRAP scores — use _run_crap() for the full scoring
    pipeline.

    Args:
        src_path: Resolved source path (file or directory) to analyze.
        config: GazeConfig with threshold values.
        classify: When True, run the classification engine on each effect.
        function_filter: When set, only include the function with this exact name.
        include_unexported: When True, include underscore-prefixed functions.
            When False (default), underscore-prefixed functions are skipped.

    Returns:
        List of FunctionTarget with effects and optional classification results.
        No Score objects are attached.
    """
    root = src_path if src_path.is_dir() else src_path.parent
    py_files = _collect_py_files(src_path)

    engine = (
        ClassificationEngine(config.contractual_threshold, config.incidental_threshold)
        if classify
        else None
    )
    all_targets: list[FunctionTarget] = []

    for py_file in py_files:
        try:
            targets = FileDetector.detect(py_file, root=root, callers=None)
        except GazeParseError as e:
            click.echo(f"Warning: {e}", err=True)
            continue

        for target in targets:
            # Apply --include-unexported filter.
            if not include_unexported and target.name.startswith("_"):
                continue
            # Apply --function name filter.
            if function_filter is not None and target.name != function_filter:
                continue
            # Classify each effect if classification engine is active.
            if engine is not None:
                for effect in target.effects:
                    target.classification = engine.classify(effect, target)
            all_targets.append(target)

    return all_targets


def _run_crap(
    path: Path,
    coverage_data: dict[str, float] | None,
    *,
    config: GazeConfig,
) -> AnalysisResult:
    """Run the full detect → classify → score pipeline for CRAP analysis.

    Always runs classification (required for fix_strategy computation) and
    scoring.

    Args:
        path: Resolved source path (file or directory) to analyze.
        coverage_data: Dict mapping relative path → percent_covered (0-100),
            or None when no coverage data is available.
        config: GazeConfig with threshold and classification values.

    Returns:
        AnalysisResult with all functions scored and summary populated.
    """
    root = path if path.is_dir() else path.parent
    targets = _run_detect_classify(
        path,
        config=config,
        classify=True,
        include_unexported=True,  # crap analyzes all functions by default
    )

    for target in targets:
        abs_file = root / target.file_path
        line_coverage_frac = _resolve_line_coverage(abs_file, root, coverage_data)
        _score_target(target, line_coverage_frac=line_coverage_frac, config=config)

    summary = _build_summary(targets, config=config, coverage_data=coverage_data)
    return AnalysisResult(functions=targets, summary=summary)


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


def _find_project_root() -> Path:
    """Walk up from cwd looking for pyproject.toml; return the directory that holds it.

    Terminates at the filesystem root (p.parent == p). Emits a warning to
    stderr and returns cwd when no pyproject.toml is found in the hierarchy.

    Returns:
        Path to the project root directory (containing pyproject.toml), or
        Path.cwd() when no pyproject.toml is found above cwd.
    """
    p = Path.cwd()
    while True:
        if (p / "pyproject.toml").exists():
            return p
        parent = p.parent
        if parent == p:  # filesystem root — terminate
            click.echo(
                "Warning: no pyproject.toml found in current directory or "
                "any parent. gazepy self-check works best in a Python "
                "project root.",
                err=True,
            )
            return Path.cwd()
        p = parent


# ---------------------------------------------------------------------------
# schema command (task 6)
# ---------------------------------------------------------------------------


@cli.command()
def schema() -> None:
    """Emit the JSON schema for AnalysisResult output (analyze and crap commands)."""
    click.echo(SCHEMA)


# ---------------------------------------------------------------------------
# self-check command (task 7)
# ---------------------------------------------------------------------------


@cli.command(name="self-check")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--max-crapload",
    "max_crapload",
    type=int,
    default=0,
    show_default=True,
    help="CI gate: fail (exit 1) when crapload exceeds this value. 0 = no limit.",
)
@click.option(
    "--max-gaze-crapload",
    "max_gaze_crapload",
    type=int,
    default=0,
    show_default=True,
    help="CI gate: accepted, enforcement deferred until O1. 0 = no limit.",
)
def self_check(output_format: str, max_crapload: int, max_gaze_crapload: int) -> None:
    """Run CRAP analysis on gaze-py's own source (dogfooding).

    Walks up from cwd to find the project root (pyproject.toml), then runs
    'gazepy crap' on src/gaze_py/ within that root.

    Only works inside the gaze-py repository — exits 2 if src/gaze_py/ is
    not found relative to the project root.
    """
    root = _find_project_root()
    gaze_py_src = root / "src" / "gaze_py"
    if not gaze_py_src.exists():
        click.echo(
            "Error: self-check only works within the gaze-py repository (src/gaze_py/ not found).",
            err=True,
        )
        raise SystemExit(2)

    config = load_config(gaze_py_src)

    if max_gaze_crapload > 0:
        click.echo(
            "Warning: --max-gaze-crapload is not enforced until O1 "
            "(quality assessment) is implemented. Threshold check skipped.",
            err=True,
        )

    result = _run_crap(gaze_py_src.resolve(), None, config=config)
    _emit(result, output_format)

    if (
        max_crapload > 0
        and result.summary.crapload is not None
        and result.summary.crapload > max_crapload
    ):
        click.echo(
            f"CI gate: crapload={result.summary.crapload} exceeds --max-crapload={max_crapload}",
            err=True,
        )
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# init command (task 8)
# ---------------------------------------------------------------------------


@cli.command(name="init")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing files (user-owned assets).",
)
def init(force: bool) -> None:
    """Scaffold .opencode agent and command assets into the current project.

    Creates (or updates with --force):
      .opencode/agents/gazepy-reporter.md
      .opencode/commands/gazepy.md

    Skips existing files unless --force is given. Warns when no pyproject.toml
    is found in cwd (assets are still written).
    """
    result = _scaffold_run(
        target_dir=Path.cwd() / ".opencode",
        force=force,
        version=_version,
        stdout=True,
    )
    for path in result.created:
        click.echo(f"created  {path}")
    for path in result.skipped:
        click.echo(f"skipped  {path} (use --force to overwrite)")
    for path in result.overwritten:
        click.echo(f"overwrote {path}")
