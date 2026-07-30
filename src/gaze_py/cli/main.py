"""CLI entry point for gaze-py.

Provides subcommands:
- analyze <path>: Detect side effects and optionally classify them. CRAP scoring
  has moved to 'gazepy crap'. All CRAP-derived output fields are null.
- crap <path>: Detect, classify, and compute CRAP/GazeCRAP scores. Optionally
  runs pytest as a subprocess to collect coverage data automatically.
- quality <path>: Assess contract coverage and GazeCRAP via the O1 pipeline.
- docscan [path]: Scan project .md files and emit doc entries (O3 implemented).
- report [path]: Generate analysis report; AI via .gaze.yaml ai: section.
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
import time
import warnings
from collections.abc import Sequence
from pathlib import Path

import click

from gaze_py import __version__ as _version
from gaze_py.analysis.detector import FileDetector
from gaze_py.analysis.docscan import scan_docs
from gaze_py.analysis.files import collect_py_files
from gaze_py.analysis.runner import detect_and_classify
from gaze_py.cli.scaffold import run as _scaffold_run
from gaze_py.config.loader import GazeConfig, load_config, load_config_explicit
from gaze_py.crap.compare import CompareOptions, compare, load_baseline
from gaze_py.crap.scorer import (
    crap as compute_crap,
)
from gaze_py.crap.scorer import (
    crapload,
    fix_strategy,
    gaze_crap,
    quadrant,
    recommended_actions,
)
from gaze_py.report.json_formatter import (
    SCHEMA,
    analysis_to_json,
    comparison_to_json,
    quality_to_json,
)
from gaze_py.report.text_formatter import comparison_to_text, to_text
from gaze_py.taxonomy.exceptions import GazeConfigError, GazeParseError
from gaze_py.taxonomy.models import (
    AnalysisResult,
    ContractCoverageResult,
    FunctionTarget,
    QualityReport,
    Score,
    Summary,
)


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

    start_time = time.monotonic()
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
    result = AnalysisResult(results=targets, summary=summary)
    _emit(result, output_format, start_time=start_time)


# ---------------------------------------------------------------------------
# Baseline path resolution (T216)
# ---------------------------------------------------------------------------


def resolve_baseline_path(
    flag_path: str | None,
    config: GazeConfig,
    project_root: Path,
) -> tuple[Path | None, bool]:
    """Resolve the baseline file path from flag, config, or auto-discovery.

    Resolution order:
    1. ``--baseline`` flag → explicit path (``is_explicit=True``).
    2. ``config.baseline.file`` set → explicit path (``is_explicit=True``).
    3. Auto-discovery: ``project_root / ".gaze" / "baseline.json"`` — returns
       ``(path, False)`` when it exists as a regular file, ``(None, False)``
       when absent or a directory.

    Args:
        flag_path: Raw value of the ``--baseline`` CLI flag, or ``None``.
        config: Loaded GazeConfig (may have ``baseline.file`` set).
        project_root: Directory to use as the root for auto-discovery.

    Returns:
        Tuple of ``(resolved_path_or_None, is_explicit)``.
        ``is_explicit=True`` when the path came from a flag or config key
        (caller should exit 2 on load failure).
        ``is_explicit=False`` when auto-discovered (caller should warn and
        skip on load failure).
    """
    if flag_path is not None:
        return (Path(flag_path), True)

    if config.baseline.file is not None:
        return (Path(config.baseline.file), True)

    # Auto-discovery: .gaze/baseline.json relative to project root.
    # H-4: check for directory BEFORE is_file() — a directory at the expected
    # path must be treated as an explicit error (exit 2), not a silent skip.
    # Return is_explicit=True so the caller exits 2 on load failure.
    candidate = project_root / ".gaze" / "baseline.json"
    if candidate.exists():
        if candidate.is_dir():
            return (candidate, True)  # is_explicit=True → caller exits 2
        if candidate.is_file():
            return (candidate, False)
    return (None, False)


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
    help="CI gate: fail (exit 1) when gaze_crapload exceeds this value. 0 = no limit.",
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
    help=(
        "Path to a baseline JSON file produced by a previous "
        "'gazepy crap --format=json' run. When provided, compares current "
        "CRAP scores against the baseline and exits 1 on regressions. "
        "Auto-discovered from .gaze/baseline.json when not specified."
    ),
)
@click.option(
    "--tests",
    "tests_path",
    default=None,
    help="Test directory or file. Auto-discovered if omitted.",
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
    tests_path: str | None = None,
) -> None:
    """Detect side effects and compute CRAP scores for PATH.

    PATH may be a single .py file or a directory. Directories are scanned
    recursively for all .py files.

    When --coverprofile is not provided, gazepy automatically runs pytest with
    coverage collection. Use --coverprofile to supply a pre-generated report.

    CI gate: --max-crapload exits 1 when the crapload count exceeds the limit.
    """
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

    start_time = time.monotonic()
    result = _run_crap(src, coverage_data, config=config)
    _enrich_with_quality(result, src, tests_path, coverage_data, config=config)

    # --baseline comparison (T217/T218).
    project_root = src if src.is_dir() else src.parent
    baseline_path, is_explicit = resolve_baseline_path(baseline, config, project_root)

    if baseline_path is not None:
        _run_baseline_comparison(
            result=result,
            baseline_path=baseline_path,
            is_explicit=is_explicit,
            output_format=output_format,
            config=config,
        )
        return  # comparison path handles all output and gates

    _emit(result, output_format, start_time=start_time)

    # CI threshold enforcement — after emitting output.
    if (
        max_gaze_crapload > 0
        and result.summary.gaze_crapload is not None
        and result.summary.gaze_crapload > max_gaze_crapload
    ):
        click.echo(
            f"CI gate: gaze_crapload={result.summary.gaze_crapload} "
            f"exceeds --max-gaze-crapload={max_gaze_crapload}",
            err=True,
        )
        raise SystemExit(1)

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
# quality command
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
    "--tests",
    "tests_path",
    type=str,
    default=None,
    help="Path to test directory or file. Auto-discovered if not provided.",
)
@click.option(
    "--target",
    type=str,
    default=None,
    help="Restrict to tests exercising this production function name.",
)
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
    default=True,
    help=(
        "Include underscore-prefixed functions (default: on)."
        " Pass --no-include-unexported to restrict to public functions only."
    ),
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
    help="CI gate: exit 1 if avg contract coverage is below this percentage.",
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
    help="AI mapper for classification (accepted; ignored).",
)
@click.option(
    "--ai-mapper-model",
    "ai_mapper_model",
    type=str,
    default=None,
    hidden=True,
    help="AI mapper model (accepted; ignored).",
)
def quality(
    path: str,
    output_format: str,
    tests_path: str | None,
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
    """Assess contract coverage and GazeCRAP for PATH.

    PATH may be a single .py file or a directory. Directories are scanned
    recursively for all .py files.

    When --tests is not provided, auto-discovers the test directory by searching
    for tests/, test/, or test_*.py relative to PATH's parent, then relative
    to the current working directory.

    CI gate: --min-contract-coverage exits 1 when average coverage is below
    the specified percentage.
    """
    from gaze_py.quality.pipeline import assess

    # PATH validation.
    src_path = Path(path)
    if not src_path.exists():
        click.echo(f"Error: path does not exist: {path}", err=True)
        raise SystemExit(2)

    # Config loading.
    if config_path is not None:
        try:
            config = load_config_explicit(Path(config_path))
        except GazeConfigError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(2) from e
    else:
        config = load_config(src_path)

    # Apply CLI threshold overrides.
    if contractual_threshold is not None:
        config.contractual_threshold = contractual_threshold
    if incidental_threshold is not None:
        config.incidental_threshold = incidental_threshold

    # Resolve tests path — auto-discover if not provided.
    resolved_tests: Path
    if tests_path is not None:
        resolved_tests = Path(tests_path)
        if not resolved_tests.exists():
            click.echo(f"Error: tests path does not exist: {tests_path}", err=True)
            raise SystemExit(2)
    else:
        resolved_tests = _discover_tests_path(src_path)

    # Run the O1 quality assessment pipeline.
    result = assess(
        src_path.resolve(),
        resolved_tests,
        config=config,
        target_func=target,
        include_unexported=include_unexported,
    )

    # Emit output.
    if output_format == "json":
        _emit_quality_json(result.reports)
    else:
        _emit_quality_text(result.reports, src_path=src_path)

    # CI threshold enforcement — after emitting output.
    if min_contract_coverage is not None:
        _check_min_contract_coverage(result.reports, min_contract_coverage)


def _discover_tests_path(src_path: Path) -> Path:
    """Auto-discover the test directory for a given source path.

    Searches in order:
    1. tests/ relative to src_path.parent
    2. test/ relative to src_path.parent
    3. test_*.py files relative to src_path.parent
    4. tests/ relative to Path.cwd()
    5. test/ relative to Path.cwd()
    6. test_*.py files relative to Path.cwd()

    Args:
        src_path: Source path being analyzed.

    Returns:
        Discovered tests path.

    Raises:
        SystemExit(2): When no tests directory can be found.
    """
    parent = src_path.parent if src_path.is_file() else src_path
    search_roots = [parent, Path.cwd()]

    for root in search_roots:
        for candidate_name in ("tests", "test"):
            candidate = root / candidate_name
            if candidate.is_dir():
                return candidate
        # Return the first matching file (not the directory); skip project roots.
        if (root / "pyproject.toml").exists() or (root / "go.mod").exists():
            continue
        test_files = sorted(root.glob("test_*.py"))
        if test_files:
            return test_files[0]

    click.echo("Error: no tests directory found — use --tests", err=True)
    raise SystemExit(2)


def _emit_quality_json(reports: Sequence[QualityReport]) -> None:
    """Emit quality reports as a JSON array.

    Uses quality_to_json() from the public formatter API. Emits a JSON
    array (NOT wrapped in AnalysisResult) per design.md A.5.

    Args:
        reports: Sequence of QualityReport dataclass instances.
    """
    click.echo(quality_to_json(reports))


def _emit_quality_text(reports: Sequence[QualityReport], *, src_path: Path) -> None:
    """Emit quality reports as a plain-text table.

    Format per design.md A.5:
        Function                      Contract Coverage  GazeCRAP
        ─────────────────────────────────────────────────────────
        <name> (← <test_name>)        <pct>%             <score>

    No quadrant column — quality command has no line coverage so quadrant
    is always None.

    Args:
        reports: Sequence of QualityReport dataclass instances.
        src_path: Source path (used in the header).
    """
    sep = "─" * 56
    click.echo(f"Quality Report: {src_path}")
    click.echo(sep)
    click.echo(f"{'Function':<30}  {'Contract Coverage':>17}  {'GazeCRAP':>8}")
    click.echo(sep)

    for report in reports:
        fn_label = report.target_function.function if report.target_function is not None else "?"
        test_label = f" (← {report.test_function})"
        fn_col = f"{fn_label}{test_label}"

        if report.contract_coverage is not None and report.contract_coverage.percentage is not None:
            cov_str = f"{report.contract_coverage.percentage:.1f}%"
        else:
            reason = (
                report.contract_coverage.reason
                if report.contract_coverage is not None
                else "no_target"
            )
            cov_str = f"null ({reason})"

        # GazeCRAP is computed inline from contract coverage and complexity.
        gaze_crap_str = _compute_gaze_crap_for_report(report)

        click.echo(f"{fn_col:<30}  {cov_str:>17}  {gaze_crap_str:>8}")

    click.echo(sep)

    coverages = [
        r.contract_coverage.percentage
        for r in reports
        if r.contract_coverage is not None and r.contract_coverage.percentage is not None
    ]
    avg_str = f"{sum(coverages) / len(coverages):.1f}%" if coverages else "null"
    click.echo(f"Avg contract coverage: {avg_str}")


def _compute_gaze_crap_for_report(report: QualityReport) -> str:
    """Compute GazeCRAP string for a QualityReport in text output.

    The quality command does not call _score_target(); GazeCRAP is computed
    inline from the report's complexity and contract coverage fields.
    Returns "null" when contract coverage or complexity is unavailable.

    Args:
        report: A QualityReport instance.

    Returns:
        Formatted GazeCRAP string (e.g. "1.0") or "null".
    """
    if report.contract_coverage is None or report.contract_coverage.percentage is None:
        return "null"
    if report.complexity is None:
        return "null"
    frac = report.contract_coverage.percentage / 100.0
    score = gaze_crap(report.complexity, frac)
    if score is None:
        return "null"
    return f"{score:.1f}"


def _check_min_contract_coverage(reports: Sequence[QualityReport], threshold: float) -> None:
    """Check the min-contract-coverage CI gate and exit 1 if violated.

    Emits a summary line and per-function failure lines to stderr, then
    raises SystemExit(1).

    Args:
        reports: Sequence of QualityReport instances.
        threshold: Minimum required average contract coverage percentage.
    """
    coverages: list[tuple[str, float]] = []
    for report in reports:
        if report.contract_coverage is not None and report.contract_coverage.percentage is not None:
            fn_name = (
                report.target_function.function
                if report.target_function is not None
                else report.test_function
            )
            coverages.append((fn_name, report.contract_coverage.percentage))

    if not coverages:
        return

    avg = sum(pct for _, pct in coverages) / len(coverages)
    click.echo(
        f"contract coverage: {avg:.1f}% avg, min {threshold:.0f}% "
        f"({'PASS' if avg >= threshold else 'FAIL'})",
        err=True,
    )

    if avg < threshold:
        for fn_name, pct in coverages:
            if pct < threshold:
                click.echo(
                    f"Error: contract coverage below minimum: "
                    f"{fn_name}: {pct:.1f}% < {threshold:.0f}%",
                    err=True,
                )
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# docscan command (O3 implementation)
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--format",
    "fmt",
    default="json",
    type=click.Choice(["json", "text"]),
    help="Output format: json (default) or text.",
)
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to .gaze.yaml configuration file.",
)
@click.option(
    "--exclude",
    "extra_excludes",
    multiple=True,
    help="Glob pattern to exclude (repeatable). Replaces config excludes when provided.",
)
@click.option(
    "--include",
    "extra_includes",
    multiple=True,
    help="Glob pattern to include (repeatable). Replaces config includes when provided.",
)
@click.option(
    "--timeout",
    "timeout",
    default=None,
    type=float,
    help="Maximum seconds to spend scanning (overrides config).",
)
def docscan(
    path: str,
    fmt: str,
    config_path: str | None,
    extra_excludes: tuple[str, ...],
    extra_includes: tuple[str, ...],
    timeout: float | None,
) -> None:
    """Scan project documentation files under PATH.

    Discovers .md files under the repository root, applies exclude/include
    filters, and emits a list of documents with their priority.

    Priority: 1 = same directory as PATH, 2 = repository root, 3 = other.
    """
    try:
        root = Path(path).resolve()
        if config_path is not None:
            config = load_config_explicit(Path(config_path))
        else:
            config = load_config(root)

        # CLI flags replace (not extend) config lists when provided.
        if extra_excludes:
            config.doc_scan_exclude = list(extra_excludes)
        if extra_includes:
            config.doc_scan_include = list(extra_includes)
        if timeout is not None:
            config.doc_scan_timeout = timeout

        entries = scan_docs(root, config)
        cwd = Path.cwd()

        if fmt == "json":
            payload = [
                {
                    "path": (
                        str(e.path.relative_to(cwd)) if e.path.is_relative_to(cwd) else str(e.path)
                    ),
                    "content": e.content,
                    "priority": e.priority,
                }
                for e in entries
            ]
            click.echo(json.dumps(payload, indent=2))
        else:
            for e in entries:
                rel = str(e.path.relative_to(cwd)) if e.path.is_relative_to(cwd) else str(e.path)
                click.echo(f"[P{e.priority}] {rel}")
                click.echo(f"  ({len(e.content.split())} words)")
    except GazeConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", type=click.Path(exists=False), required=False)
@click.option(
    "--model",
    type=str,
    default=None,
    help="AI model override (takes precedence over ai.model in .gaze.yaml).",
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
    help="CI gate: fail (exit 1) when gaze_crapload exceeds this value. 0 = no limit.",
)
@click.option(
    "--min-contract-coverage",
    "min_contract_coverage",
    type=float,
    default=None,
    help="Minimum contract coverage percentage (requires O1).",
)
@click.option(
    "--tests",
    "tests_path",
    default=None,
    help="Test directory or file. Auto-discovered if omitted.",
)
def report(
    path: str | None,
    model: str | None,
    output_format: str,
    coverprofile: str | None,
    max_crapload: int,
    max_gaze_crapload: int,
    min_contract_coverage: float | None,
    tests_path: str | None,
) -> None:
    """Generate an analysis report for PATH.

    The AI provider is selected via the ``ai:`` section of ``.gaze.yaml`` or
    ``GAZEPY_AI_*`` environment variables. Use ``--model`` to override the
    model for a single invocation.

    When no provider is configured, emits the JSON analysis payload to stdout
    (prompt-only mode). When a provider is configured but unavailable, falls
    back to prompt-only mode with a warning on stderr. Exit code is 0 in both
    cases.

    PATH may be a single .py file or a directory. Directories are scanned
    recursively for all .py files.

    When --coverprofile is not provided, gazepy automatically runs pytest with
    coverage collection. Use --coverprofile to supply a pre-generated report.

    CI gate: --max-crapload exits 1 when the crapload count exceeds the limit.
    CI gate: --max-gaze-crapload exits 1 when gaze_crapload exceeds the limit.
    """
    # PATH validation.
    if path is None:
        click.echo("Error: missing argument 'PATH'.", err=True)
        raise SystemExit(2)

    src = Path(path).resolve()
    if not src.exists():
        click.echo(f"Error: path does not exist: {path}", err=True)
        raise SystemExit(2)

    config = load_config(src)
    coverage_data = _acquire_coverage(src, coverprofile)
    result = _run_crap(src, coverage_data, config=config)
    _enrich_with_quality(result, src, tests_path, coverage_data, config=config)

    # Lazy imports — avoids loading report.config / report.provider on every
    # invocation. Mirrors the pattern used by _load_report_prompt().
    from gaze_py.report.config import read_ai_config
    from gaze_py.report.provider import new_synthesizer_from_config

    cfg = read_ai_config(config, model)
    synth = new_synthesizer_from_config(cfg)

    # Prompt-only mode: no provider configured.
    if synth is None:
        click.echo(_assemble_report_payload(result))
        click.echo(
            "Tip: configure an AI provider in .gaze.yaml (ai: section) "
            "or set GAZEPY_AI_MODEL env var",
            err=True,
        )
        _enforce_crap_gates(result, max_crapload=max_crapload, max_gaze_crapload=max_gaze_crapload)
        _enforce_min_contract_coverage_from_result(result, min_contract_coverage)
        return

    # Prompt-only fallback: provider configured but not available.
    if not synth.available():
        provider_name = cfg.provider if cfg.provider else "ollama"
        click.echo(
            f"Warning: {provider_name} provider configured but not available "
            f"({synth.model_id()} not found) — falling back to prompt-only mode",
            err=True,
        )
        click.echo(_assemble_report_payload(result))
        _enforce_crap_gates(result, max_crapload=max_crapload, max_gaze_crapload=max_gaze_crapload)
        _enforce_min_contract_coverage_from_result(result, min_contract_coverage)
        return

    # AI mode: synthesize and emit the narrative report.
    prompt = _load_report_prompt(Path.cwd()) + "\n\n" + _assemble_report_payload(result)
    response = synth.synthesize(prompt)
    click.echo(response)
    # Gates fire after output (HIGH-1 fix: payload always written before exit).
    _enforce_crap_gates(result, max_crapload=max_crapload, max_gaze_crapload=max_gaze_crapload)
    _enforce_min_contract_coverage_from_result(result, min_contract_coverage)


# ---------------------------------------------------------------------------
# Baseline comparison helper (T217/T218)
# ---------------------------------------------------------------------------


def _run_baseline_comparison(
    result: AnalysisResult,
    *,
    baseline_path: Path,
    is_explicit: bool,
    output_format: str,
    config: GazeConfig,
) -> None:
    """Load baseline, compare, emit output, and apply the pass/fail gate.

    Handles all error paths for baseline loading:
    - Explicit path (``--baseline`` flag or ``config.baseline.file``): exits 2
      on ``ValueError``.
    - Auto-discovered path: emits a stderr warning and returns (no exit 2).

    Emits comparison output and raises ``SystemExit(1)`` when the comparison
    fails (regressions or new violations found).

    Args:
        result: Current CRAP analysis result.
        baseline_path: Resolved path to the baseline JSON file.
        is_explicit: True when the path came from a flag or config key.
        output_format: One of ``"json"`` or ``"text"``.
        config: Loaded GazeConfig with baseline options.
    """
    # Load baseline — error handling differs by explicit vs auto-discovered.
    try:
        baseline_entries = load_baseline(baseline_path)
    except ValueError as e:
        if is_explicit:
            click.echo(str(e), err=True)
            raise SystemExit(2) from e
        # Auto-discovered: warn and skip comparison (do NOT exit 2).
        click.echo(
            f"Warning: auto-discovered baseline could not be loaded — skipping comparison. ({e})",
            err=True,
        )
        _emit(result, output_format)
        return

    # T218: wire CompareOptions — explicit is not None check for epsilon=0.0 safety.
    new_fn_threshold = (
        config.baseline.new_function_threshold
        if config.baseline.new_function_threshold is not None
        else config.crap_threshold
    )
    opts = CompareOptions(
        epsilon=config.baseline.epsilon,
        new_function_threshold=new_fn_threshold,
    )

    # Build current entries list from the analysis result JSON.
    current_json = analysis_to_json(result)
    current_data = json.loads(current_json)
    current_entries: list[dict[str, object]] = current_data.get("results", [])
    crap_summary: dict[str, object] = current_data.get("summary", {})

    cmp_result = compare(baseline_entries, current_entries, opts)

    # Emit warnings to stderr (T205: warnings are stderr-only).
    for warning in cmp_result.warnings:
        click.echo(warning, err=True)

    # Emit comparison output.
    if output_format == "json":
        click.echo(comparison_to_json(cmp_result, crap_summary))
    else:
        crap_text = to_text(result)
        click.echo(comparison_to_text(crap_text, cmp_result))

    # Gate: exit 1 when comparison failed (regressions or new violations).
    if not cmp_result.summary.passed:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _acquire_coverage(src: Path, coverprofile: str | None) -> dict[str, float] | None:
    """Acquire coverage data from a coverprofile or by auto-running pytest.

    Shared by the crap and report commands. When coverprofile is provided,
    loads it directly. Otherwise runs pytest with --cov and captures the
    JSON report. Failures are non-fatal — returns None with a warning.

    Args:
        src: Resolved source path to analyze (passed to --cov).
        coverprofile: Path to a pre-generated coverage.py JSON report, or None.

    Returns:
        Dict mapping relative path → percent_covered (0-100), or None.
    """
    if coverprofile is not None:
        try:
            return _load_coverage_json(coverprofile)
        except Exception as e:  # noqa: BLE001
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(2) from e

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
        return _load_coverage_json(tmp)
    except (subprocess.CalledProcessError, OSError):
        click.echo(
            "Warning: pytest failed or is not installed — "
            "continuing without coverage data. "
            "Use --coverprofile to provide a pre-generated report.",
            err=True,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        click.echo(
            f"Warning: coverage JSON could not be parsed — continuing without coverage data. "
            f"({exc})",
            err=True,
        )
        return None
    finally:
        Path(tmp).unlink(missing_ok=True)


def _enforce_crap_gates(
    result: AnalysisResult,
    *,
    max_crapload: int,
    max_gaze_crapload: int,
) -> None:
    """Enforce --max-gaze-crapload and --max-crapload CI gates.

    Emits a message to stderr and raises SystemExit(1) when a gate is
    exceeded. Called after emitting output so the payload is always written
    before the exit.

    Args:
        result: AnalysisResult with populated summary.
        max_crapload: Maximum allowed crapload count. 0 = no limit.
        max_gaze_crapload: Maximum allowed gaze_crapload count. 0 = no limit.
    """
    if (
        max_gaze_crapload > 0
        and result.summary.gaze_crapload is not None
        and result.summary.gaze_crapload > max_gaze_crapload
    ):
        click.echo(
            f"CI gate: gaze_crapload={result.summary.gaze_crapload} "
            f"exceeds --max-gaze-crapload={max_gaze_crapload}",
            err=True,
        )
        raise SystemExit(1)

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


def _enforce_min_contract_coverage_from_result(
    result: AnalysisResult,
    min_contract_coverage: float | None,
) -> None:
    """Enforce --min-contract-coverage CI gate from an AnalysisResult.

    Inline enforcement for the report command: _check_min_contract_coverage
    takes QualityReport objects; here we have FunctionTargets with scores.

    Args:
        result: AnalysisResult with scored FunctionTargets.
        min_contract_coverage: Minimum required average contract coverage
            percentage, or None to skip enforcement.
    """
    if min_contract_coverage is None:
        return

    coverages = [
        (t.function, t.score.contract_coverage)
        for t in result.results
        if t.score is not None and t.score.contract_coverage is not None
    ]
    if not coverages:
        return

    avg_cc = sum(pct for _, pct in coverages) / len(coverages)
    click.echo(
        f"contract coverage: {avg_cc:.1f}% avg, min {min_contract_coverage:.0f}% "
        f"({'PASS' if avg_cc >= min_contract_coverage else 'FAIL'})",
        err=True,
    )
    if avg_cc < min_contract_coverage:
        for fn_name, pct in coverages:
            if pct < min_contract_coverage:
                click.echo(
                    f"Error: contract coverage below minimum: "
                    f"{fn_name}: {pct:.1f}% < {min_contract_coverage:.0f}%",
                    err=True,
                )
        raise SystemExit(1)


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter block from content.

    Frontmatter is the block between the first '---\\n' and the
    next '\\n---' line. Returns content unchanged if no frontmatter.

    Edge-case contract: handles well-formed frontmatter (opening
    '---\\n', closing '\\n---\\n'). Malformed frontmatter (no
    closing '---') returns the full content unchanged — acceptable
    since gaze-reporter.md always has well-formed frontmatter.
    Note: leading blank lines immediately after the closing '---'
    are stripped by lstrip("\\n"). This is intentional — it matches
    Go's stripFrontmatter() behavior and gaze-reporter.md does not
    use intentional leading blank lines in its body.

    Args:
        content: Raw file content, possibly with YAML frontmatter.

    Returns:
        Content with frontmatter removed, or original content unchanged.
    """
    if not content.startswith("---"):
        return content
    rest = content[3:].lstrip("\n")
    idx = rest.find("\n---")
    if idx < 0:
        return content
    after = rest[idx + 4 :]
    return after.lstrip("\n")


def _load_report_prompt(workdir: Path) -> str:
    """Load the gaze-reporter system prompt.

    Checks for a local .opencode/agents/gaze-reporter.md first
    (user override). Falls back to the bundled asset.

    AP-004: use importlib.resources, not __file__, for bundled assets.
    Consistent with scaffold.py anchor: files("gaze_py.cli.assets").
    The lazy import avoids loading importlib.resources on every
    CLI invocation without --ai (same pattern as call_ai in report()).

    MEDIUM-1 fix: workdir is resolved to an absolute path before use,
    and the local file is only read when it resolves to a path contained
    within workdir (path traversal guard).

    Args:
        workdir: Project root to search for local override.

    Returns:
        System prompt string with YAML frontmatter stripped.
    """
    workdir = workdir.resolve()
    local = workdir / ".opencode" / "agents" / "gaze-reporter.md"
    if local.exists() and local.resolve().is_relative_to(workdir):
        content = local.read_text(encoding="utf-8")
    else:
        # AP-004: use importlib.resources, not __file__, for bundled assets.
        # Lazy import — avoids loading importlib.resources on every
        # CLI invocation without --ai (same pattern as call_ai in 4.2).
        from importlib.resources import files as _pkg_files

        content = (
            _pkg_files("gaze_py.cli.assets")
            .joinpath("agents/gaze-reporter.md")
            .read_text(encoding="utf-8")
        )
    return _strip_frontmatter(content)


def _assemble_report_payload(result: AnalysisResult) -> str:
    """Serialize the analysis result as the AI report payload.

    Returns the same JSON that 'gazepy crap --format=json' produces.

    Args:
        result: AnalysisResult from the CRAP pipeline.

    Returns:
        JSON string representation of the analysis result.
    """
    return analysis_to_json(result)


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


def _resolve_line_coverage(
    py_file: Path,
    root: Path,
    coverage_data: dict[str, float] | None,
) -> float | None:
    """Resolve line coverage fraction for a single file.

    Tries three lookup keys in order (most specific → least specific):

    1. Root-relative path (`analysis/complexity.py`) — matches when the
       analysis root equals the working directory from which pytest was run.
    2. Cwd-relative path (`src/gaze_py/analysis/complexity.py`) — matches
       the common case where users run `gazepy crap src/mypackage/` from
       the project root and coverage.py stores keys relative to that root.
       This attempt is silently skipped (falls through to filename-only) when
       `py_file` is not under `Path.cwd()`, e.g. for absolute paths that
       lie outside the project or unusual filesystem layouts.
    3. Filename-only (`complexity.py`) — last-resort fallback for any
       remaining edge cases.

    Converts `percent_covered` (0–100) from `coverage_data` to a fraction
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
    # Attempt 1: root-relative key (e.g. "analysis/complexity.py").
    if py_file.is_relative_to(root):
        rel = str(py_file.relative_to(root))
    else:
        rel = py_file.name

    # Attempt 2: cwd-relative key (e.g. "src/gaze_py/analysis/complexity.py").
    # Silently skipped when py_file is not under Path.cwd().
    cwd_rel: str | None = None
    if py_file.is_relative_to(Path.cwd()):
        cwd_rel = str(py_file.relative_to(Path.cwd()))

    pct = coverage_data.get(rel)
    if pct is None and cwd_rel is not None:
        pct = coverage_data.get(cwd_rel)
    if pct is None:
        pct = coverage_data.get(py_file.name)
    if pct is None:
        return None
    # Convert percentage (0-100) to fraction (0.0-1.0) for the scorer.
    return pct / 100.0


def _score_target(
    target: FunctionTarget,
    *,
    line_coverage_frac: float | None,
    config: GazeConfig,
    quality_result: ContractCoverageResult | None = None,
) -> None:
    """Compute and attach a Score to a FunctionTarget in-place.

    When quality_result is provided (from the O1 pipeline), GazeCRAP and
    quadrant are computed using contract coverage. Existing callers that pass
    no quality_result preserve backward compatibility via the default None.

    Args:
        target: The FunctionTarget to score.
        line_coverage_frac: Line coverage fraction in [0.0, 1.0], or None.
        config: GazeConfig providing CRAP threshold values.
        quality_result: Contract coverage result from O1 pipeline, or None.
            When provided and percentage is not None, GazeCRAP and quadrant
            are computed. NOTE: percentage is [0,100]; divide by 100 before
            passing to gaze_crap() and quadrant() which take fractions [0,1].
    """
    crap_score = compute_crap(target.complexity, line_coverage_frac)

    # Compute GazeCRAP and quadrant when O1 quality result is available.
    gaze_crap_score: float | None
    quad: str | None
    contract_coverage_pct: float | None
    contract_coverage_reason: str | None

    if quality_result is not None and quality_result.percentage is not None:
        # MUST divide by 100: ContractCoverageResult.percentage is [0,100],
        # but gaze_crap() and quadrant() take fractions [0.0, 1.0].
        contract_frac = quality_result.percentage / 100.0
        gaze_crap_score = gaze_crap(target.complexity, contract_frac)
        # quadrant() returns None when either arg is None; line_coverage_frac
        # is None from the quality command (no line coverage collected).
        quad = quadrant(line_coverage_frac, contract_frac)
        strategy = fix_strategy(
            crap_score=crap_score,
            complexity=target.complexity,
            line_coverage=line_coverage_frac,
            quadrant_label=quad,
            threshold=config.crap_threshold,
            complexity_threshold=int(config.crap_threshold),
        )
        contract_coverage_pct = quality_result.percentage
        contract_coverage_reason = quality_result.reason
    else:
        gaze_crap_score = None
        quad = None
        strategy = fix_strategy(
            crap_score=crap_score,
            complexity=target.complexity,
            line_coverage=line_coverage_frac,
            quadrant_label=None,
            threshold=config.crap_threshold,
            complexity_threshold=int(config.crap_threshold),
        )
        contract_coverage_pct = None
        contract_coverage_reason = quality_result.reason if quality_result else None

    # Preserve pure-function fallback: if no quality result and the function
    # has zero effects, set "no_effects_detected" reason per OC-003.
    if contract_coverage_reason is None and not target.effects:
        contract_coverage_reason = "no_effects_detected"

    target.score = Score(
        line_coverage=line_coverage_frac,
        crap=crap_score,
        gaze_crap=gaze_crap_score,
        contract_coverage=contract_coverage_pct,
        contract_coverage_reason=contract_coverage_reason,
        fix_strategy=strategy,
        quadrant=quad,
        effect_confidence_range=(
            (quality_result.min_confidence, quality_result.max_confidence)
            if (
                quality_result is not None
                and quality_result.reason == "all_effects_ambiguous"
                and quality_result.min_confidence is not None
                and quality_result.max_confidence is not None
            )
            else None
        ),
    )


def _compute_avg_line_coverage(
    targets: list[FunctionTarget],
    coverage_data: dict[str, float] | None,
) -> float | None:
    """Compute the average line coverage fraction across all scored targets.

    Args:
        targets: All FunctionTargets from the analysis run.
        coverage_data: Coverage data dict, or None when not provided.

    Returns:
        Mean line_coverage fraction, or None when coverage_data is None or
        no targets have a non-None line_coverage score.
    """
    if coverage_data is None:
        return None
    line_coverages = [
        t.score.line_coverage
        for t in targets
        if t.score is not None and t.score.line_coverage is not None
    ]
    return sum(line_coverages) / len(line_coverages) if line_coverages else None


def _compute_gaze_crapload(
    targets: list[FunctionTarget],
    config: GazeConfig,
) -> int | None:
    """Count targets whose GazeCRAP score meets or exceeds the threshold.

    Args:
        targets: All FunctionTargets from the analysis run.
        config: GazeConfig providing the gaze_crap_threshold.

    Returns:
        Count of targets above threshold, or None when no targets have a
        non-None gaze_crap score (GazeCRAP requires O1 quality run).
    """
    gaze_crap_targets = [
        t for t in targets if t.score is not None and t.score.gaze_crap is not None
    ]
    if not gaze_crap_targets:
        return None
    return sum(
        1
        for t in gaze_crap_targets
        if t.score is not None
        and t.score.gaze_crap is not None
        and t.score.gaze_crap >= config.gaze_crap_threshold
    )


def _compute_avg_contract_coverage(targets: list[FunctionTarget]) -> float | None:
    """Compute the average contract coverage percentage across all scored targets.

    Args:
        targets: All FunctionTargets from the analysis run.

    Returns:
        Mean contract_coverage percentage, or None when no targets have a
        non-None contract_coverage score (requires O1 quality run).
    """
    contract_coverages = [
        t.score.contract_coverage
        for t in targets
        if t.score is not None and t.score.contract_coverage is not None
    ]
    return sum(contract_coverages) / len(contract_coverages) if contract_coverages else None


def _compute_quadrant_counts(targets: list[FunctionTarget]) -> dict[str, int] | None:
    """Count functions per quadrant label.

    Args:
        targets: All FunctionTargets from the analysis run.

    Returns:
        Dict mapping quadrant label to count, or None when no targets have a
        non-None quadrant label (requires both line and contract coverage).
    """
    quadrant_labels = [
        t.score.quadrant for t in targets if t.score is not None and t.score.quadrant is not None
    ]
    if not quadrant_labels:
        return None
    counts: dict[str, int] = {}
    for label in quadrant_labels:
        counts[label] = counts.get(label, 0) + 1
    return counts


def _compute_fix_strategy_counts(targets: list[FunctionTarget]) -> dict[str, int] | None:
    """Count functions per fix strategy.

    Args:
        targets: All FunctionTargets from the analysis run.

    Returns:
        Dict mapping fix strategy to count, or None when no targets have a
        non-None fix_strategy (populated whenever CRAP scores are available).
    """
    fix_counts: dict[str, int] = {}
    for t in targets:
        if t.score is not None and t.score.fix_strategy is not None:
            strat = t.score.fix_strategy
            fix_counts[strat] = fix_counts.get(strat, 0) + 1
    return fix_counts if fix_counts else None


def _build_summary(
    all_targets: list[FunctionTarget],
    *,
    config: GazeConfig,
    coverage_data: dict[str, float] | None,
) -> Summary:
    """Build the Summary aggregate from all analyzed and scored targets.

    Thin coordinator: delegates each aggregate computation to a focused
    helper and assembles the final Summary.

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

    return Summary(
        function_count=len(all_targets),
        crapload=crapload_count,
        gaze_crapload=_compute_gaze_crapload(all_targets, config),
        avg_line_coverage=_compute_avg_line_coverage(all_targets, coverage_data),
        avg_contract_coverage=_compute_avg_contract_coverage(all_targets),
        quadrant_counts=_compute_quadrant_counts(all_targets),
        fix_strategy_counts=_compute_fix_strategy_counts(all_targets),
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
    pipeline. Delegates to detect_and_classify() from analysis.runner.
    CLI-specific behavior (verbose output, classify flag) is handled here.

    When classify=True, doc scanning (O3) is performed before classification
    to augment Signal 5 with project-wide documentation text. Scan failures
    are logged as warnings and do not abort the analysis run.

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
    if classify:
        # O3: scan project docs to augment Signal 5 (docstring_signal).
        # BLE001 suppression is justified: scan failure must never abort
        # analysis (Principle VI graceful degradation).
        _docs_text: str | None = None
        try:
            _doc_entries = scan_docs(src_path, config)
            _joined = "\n".join(e.content for e in _doc_entries)
            _docs_text = _joined if _joined.strip() else None
        except Exception as _exc:  # noqa: BLE001
            warnings.warn(
                f"docscan failed, continuing without doc augmentation: {_exc}",
                stacklevel=2,
            )

        # Use shared runner which always classifies.
        return detect_and_classify(
            src_path,
            config=config,
            include_unexported=include_unexported,
            function_filter=function_filter,
            docs_text=_docs_text,
        )

    # No classification requested — run detect-only path.
    root = src_path if src_path.is_dir() else src_path.parent
    py_files = collect_py_files(src_path)
    all_targets: list[FunctionTarget] = []

    for py_file in py_files:
        try:
            targets = FileDetector.detect(py_file, root=root, callers=None)
        except GazeParseError as e:
            click.echo(f"Warning: {e}", err=True)
            continue

        for target in targets:
            # Apply --include-unexported filter.
            if not include_unexported and target.function.startswith("_"):
                continue
            # Apply --function name filter.
            if function_filter is not None and target.function != function_filter:
                continue
            all_targets.append(target)

    return all_targets


def _resolve_crap_tests_path(src: Path, tests_path: str | None) -> Path | None:
    """Resolve the tests path for the crap command quality integration.

    When ``tests_path`` is provided, returns it as a ``Path``.  Otherwise
    auto-discovers by searching ``tests/``, ``test/``, and ``test_*.py``
    relative to ``src.parent`` and then relative to ``Path.cwd()``.

    Args:
        src: Resolved source path passed to the crap command.
        tests_path: Raw ``--tests`` option value, or ``None`` when omitted.

    Returns:
        Resolved ``Path`` when a tests location is found and exists, or
        ``None`` when no tests directory can be discovered.
    """
    if tests_path is not None:
        candidate = Path(tests_path)
        return candidate if candidate.exists() else None

    search_roots = [src.parent if src.is_file() else src, Path.cwd()]
    for root in search_roots:
        for name in ("tests", "test"):
            candidate = root / name
            if candidate.is_dir():
                return candidate
        test_files = sorted(root.glob("test_*.py"))
        if test_files:
            return test_files[0]
    return None


def _enrich_with_quality(
    result: AnalysisResult,
    src: Path,
    tests_path: str | None,
    coverage_data: dict[str, float] | None,
    *,
    config: GazeConfig,
) -> None:
    """Enrich an AnalysisResult in-place with O1 contract coverage data.

    Resolves the tests path, runs ``build_contract_coverage_map()``, and
    re-scores each ``FunctionTarget`` that has a matching
    ``ContractCoverageResult``.  When no tests path can be resolved the
    function returns immediately (GazeCRAP stays null, OC-003 compliant).

    The lazy import of ``build_contract_coverage_map`` is intentional: it
    avoids loading ``quality/pipeline.py`` on every ``gazepy crap``
    invocation that omits ``--tests`` (same pattern as the ``quality``
    command at line 512).

    Args:
        result: AnalysisResult produced by ``_run_crap()``; mutated in-place.
        src: Resolved source path passed to the crap command.
        tests_path: Raw ``--tests`` option value, or ``None`` when omitted.
        coverage_data: Line coverage dict from the coverage step, or ``None``.
        config: GazeConfig with threshold and classification values.
    """
    resolved_tests = _resolve_crap_tests_path(src, tests_path)
    if resolved_tests is None:
        return

    from gaze_py.quality.pipeline import build_contract_coverage_map

    # include_unexported defaults to True — matches _run_crap() at line 1762.
    coverage_map = build_contract_coverage_map(src, resolved_tests, config)
    for target in result.results:
        ccr = coverage_map.get((target.function, target.file_path))
        if ccr is not None:
            # "no_test_coverage": percentage=None → else branch →
            # gaze_crap stays null per Go contract (D5).
            _score_target(
                target,
                line_coverage_frac=target.score.line_coverage if target.score else None,
                config=config,
                quality_result=ccr,
            )
    # Re-build summary to reflect updated contract_coverage data.
    result.summary = _build_summary(result.results, config=config, coverage_data=coverage_data)


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
    return AnalysisResult(results=targets, summary=summary)


def _emit(
    result: AnalysisResult,
    output_format: str,
    *,
    start_time: float | None = None,
) -> None:
    """Emit the analysis result in the requested format.

    Args:
        result: The AnalysisResult to emit.
        output_format: One of "json" or "text".
        start_time: time.monotonic() captured before analysis ran. Used to
            compute duration_ms in the metadata block. When None, duration_ms
            is 0.
    """
    if output_format == "json":
        click.echo(analysis_to_json(result, start_time=start_time))
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
    help="CI gate: fail (exit 1) when gaze_crapload exceeds this value. 0 = no limit.",
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

    result = _run_crap(gaze_py_src.resolve(), None, config=config)
    _emit(result, output_format)

    if (
        max_gaze_crapload > 0
        and result.summary.gaze_crapload is not None
        and result.summary.gaze_crapload > max_gaze_crapload
    ):
        click.echo(
            f"CI gate: gaze_crapload={result.summary.gaze_crapload} "
            f"exceeds --max-gaze-crapload={max_gaze_crapload}",
            err=True,
        )
        raise SystemExit(1)

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
      .opencode/agents/gaze-reporter.md
      .opencode/agents/gaze-test-generator.md
      .opencode/agents/reviewer-testing.md
      .opencode/commands/gaze.md
      .opencode/commands/gaze-fix.md
      .opencode/commands/speckit.testreview.md
      .opencode/references/doc-scoring-model.md
      .opencode/references/example-report.md

    User-owned files (gaze-reporter.md, reviewer-testing.md, gaze.md) are
    skipped when they already exist unless --force is given. Tool-owned files
    (gaze-test-generator.md, gaze-fix.md, speckit.testreview.md, references/)
    are updated automatically when their content changes (overwrite-on-diff).

    Warns when no pyproject.toml is found in cwd (assets are still written).
    """
    result = _scaffold_run(
        target_dir=Path.cwd() / ".opencode",
        force=force,
        version=_version,
        stdout=True,
    )

    any_action = result.created or result.overwritten or result.updated
    if any_action:
        click.echo("gazepy OpenCode integration initialized:")
    else:
        click.echo("gazepy OpenCode integration already up to date:")

    for path in result.created:
        click.echo(f"  created: .opencode/{path}")
    for path in result.skipped:
        click.echo(f"  skipped: .opencode/{path} (already exists)")
    for path in result.overwritten:
        click.echo(f"  overwritten: .opencode/{path}")
    for path in result.updated:
        click.echo(f"  updated: .opencode/{path} (content changed)")

    click.echo()
    click.echo("Run /gaze for quality reports and /speckit.testreview for testability analysis.")

    # Count only user-owned skipped files for the --force hint.
    from gaze_py.cli.scaffold import _TOOL_OWNED

    user_skipped = [p for p in result.skipped if p not in _TOOL_OWNED]
    if user_skipped:
        word = "file" if len(user_skipped) == 1 else "files"
        click.echo(f"{len(user_skipped)} {word} skipped (use --force to overwrite).")
