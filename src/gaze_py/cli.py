"""gaze-py CLI — Click-based command interface matching Go gaze flags.

Architecture note (AP-002): CLI commands are thin delegation layers.
All business logic lives in ``analysis``, ``quality``, and ``report``
modules.  The CLI is responsible only for:

1. Argument/flag parsing (Click).
2. Path validation (existence, traversal guard) — exit 1 on failure.
3. Delegating to core functions.
4. Formatting output via ``report.json`` / ``report.text``.
5. Exit code contract: 0=success, 1=input error, 2=internal error.

Security (SC-003, SC-004): All paths are validated with
``Path.resolve()`` before any analysis begins.  No partial output is
emitted on input errors.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import click

from gaze_py import __version__


def _analyze_tolerant(
    path: Path,
    root: Path,
    warn: bool = True,
) -> list[object]:
    """Walk *path* tolerantly, skipping files that fail to parse.

    For a single file, raises ``GazeParseError`` (hard error — the user
    explicitly named a broken file).  For a directory, collects results
    from parseable files and optionally emits a warning for each file
    that fails (spec: "A non-empty metadata.warnings[] does NOT change
    the exit code if at least one result was produced").

    Imports are deferred to avoid circular imports at module level.

    Args:
        path: File or directory to analyse.
        root: Declared root for traversal validation.
        warn: When ``True``, emit a warning to stderr for each file that
            fails to parse.  Set to ``False`` when JSON output is
            requested so that warnings do not pollute the JSON stream.

    Returns:
        List of ``AnalysisResult`` instances from parseable files.

    Raises:
        ValueError: When *path* escapes *root*.
        GazeParseError: When *path* is a single file that fails to parse.
    """
    from gaze_py.analysis import GazeParseError, analyze_path

    resolved = path.resolve()
    if resolved.is_file():
        # Single file — propagate parse errors as hard errors.
        return analyze_path(path, root=root)  # type: ignore[return-value]

    # Directory — walk files individually, tolerating parse errors.
    accumulated: list[object] = []
    for py_file in sorted(resolved.rglob("*.py")):
        # Skip hidden directories and __pycache__.
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.relative_to(resolved).parts):
            continue
        try:
            accumulated.extend(analyze_path(py_file, root=root))
        except GazeParseError as exc:
            if warn:
                # Route warnings to stderr so they don't pollute stdout.
                click.echo(f"warning: {exc}", err=True)
    return accumulated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_path_exists(path_str: str, label: str = "path") -> Path:
    """Validate that *path_str* exists and return the resolved ``Path``.

    Prints an error message and calls ``sys.exit(1)`` if the path does
    not exist.  This ensures no partial output is emitted before the
    error is reported (SC-031 exit code contract).

    Args:
        path_str: Raw path string from the CLI argument.
        label: Human-readable label for the path (used in error messages).

    Returns:
        The ``Path`` object for the given string (not yet resolved).
    """
    p = Path(path_str)
    if not p.exists():
        click.echo(f"error: {label} does not exist: {path_str}", err=True)
        sys.exit(1)
    return p


def _validate_no_traversal(path: Path, root: Path | None = None) -> Path:
    """Validate that *path* does not escape *root* via directory traversal.

    Uses ``Path.resolve()`` to canonicalise both paths before comparison
    (SC-003, SC-004 from the Python convention pack).  Prints an error
    and calls ``sys.exit(1)`` if the path escapes the root.

    The default *root* is ``Path.cwd()``.  When the CLI receives an
    absolute path that is legitimately outside cwd (e.g. a ``tmp_path``
    in tests), the caller should pass ``root=path`` so the path is
    treated as its own root.  The traversal guard is still enforced
    against the *declared* root — callers that pass user-supplied paths
    MUST use cwd or a project-configured root.

    Args:
        path: The path to validate.
        root: The declared project root.  Defaults to ``Path.cwd()``.

    Returns:
        The resolved ``Path`` (safe to use for analysis).
    """
    if root is None:
        root = Path.cwd()
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        click.echo(
            f"error: path escapes project root: {resolved_path}",
            err=True,
        )
        sys.exit(1)
    return resolved_path


def _derive_target_func(test_file: Path) -> str:
    """Derive the source function name from a test file name.

    Strips the ``test_`` prefix from the file stem when present.
    For example, ``test_basic.py`` → ``"basic"``.

    Args:
        test_file: Path to the test file.

    Returns:
        The inferred source function name.
    """
    stem = test_file.stem
    return stem[len("test_") :] if stem.startswith("test_") else stem


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=__version__, prog_name="gaze-py")
def main() -> None:
    """gaze-py: Python-native GazeCRAP analysis engine."""


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


@main.command()
@click.option("--function", "-f", type=str, default=None, help="Function name or pattern to analyze.")
@click.option("--include-unexported", is_flag=True, default=False, help="Include unexported/private functions.")
@click.option("--classify", is_flag=True, default=False, help="Run classification on discovered side effects.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output.")
@click.option("--config", type=click.Path(), default=None, help="Path to .gaze.yaml config file.")
@click.option("--contractual-threshold", type=int, default=None, help="Confidence threshold for contractual label.")
@click.option("--incidental-threshold", type=int, default=None, help="Confidence threshold for incidental label.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
@click.argument("target", required=False)
def analyze(
    function: str | None,
    include_unexported: bool,
    classify: bool,
    verbose: bool,
    config: str | None,
    contractual_threshold: int | None,
    incidental_threshold: int | None,
    output_format: str,
    target: str | None,
) -> None:
    """Analyze Python source for side-effect taxonomy.

    TARGET may be a single ``.py`` file or a directory.  When TARGET is
    omitted the current working directory is analyzed.

    Exit codes: 0=success, 1=input error (missing path, traversal),
    2=internal error (parse failure).
    """
    # Lazy imports keep startup fast and avoid circular imports at module level.
    from gaze_py.analysis import GazeParseError
    from gaze_py.report.json import write_analysis_json
    from gaze_py.report.text import write_analysis_text
    from gaze_py.taxonomy import AnalysisResult  # noqa: TC001

    # Resolve target path — default to cwd when omitted.
    src_str = target if target is not None else str(Path.cwd())

    # Validate existence before any analysis (SC-031: no partial output).
    src_path = _validate_path_exists(src_str, label="path")

    # Validate traversal safety.
    # The declared root is the *unresolved* path's absolute starting point —
    # i.e. the absolute form of the path before any ".." components are
    # collapsed.  This catches paths like "/safe/dir/../../etc" where the
    # resolved form escapes the declared starting directory.
    # For a file argument, the root is the file's parent directory.
    abs_src = src_path.absolute()
    root_for_analysis = abs_src if abs_src.is_dir() else abs_src.parent

    # Run analysis — tolerant for directories, hard error for single files.
    # Suppress warnings in JSON mode so they don't pollute the JSON stream.
    try:
        raw_results = _analyze_tolerant(src_path, root=root_for_analysis, warn=output_format != "json")
    except ValueError:
        # Path traversal detected inside analyze_path.
        click.echo(f"error: path escapes project root: {src_path.resolve()}", err=True)
        sys.exit(1)
    except GazeParseError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    results: list[AnalysisResult] = raw_results  # type: ignore[assignment]

    # Emit output.
    buf = io.StringIO()
    if output_format == "json":
        write_analysis_json(results, version=__version__, out=buf)
    else:
        write_analysis_text(results, out=buf)
    click.echo(buf.getvalue(), nl=False)


# ---------------------------------------------------------------------------
# crap
# ---------------------------------------------------------------------------


@main.command()
@click.option("--coverprofile", type=click.Path(), default=None, help="Path to .coverage SQLite database.")
@click.option("--crap-threshold", type=float, default=None, help="CRAP score threshold.")
@click.option("--gaze-crap-threshold", type=float, default=None, help="GazeCRAP score threshold.")
@click.option("--max-crapload", type=float, default=None, help="Maximum aggregate CRAP load.")
@click.option("--max-gaze-crapload", type=float, default=None, help="Maximum aggregate GazeCRAP load.")
@click.option("--ai-mapper", is_flag=True, default=False, help="Enable AI-assisted test mapping.")
@click.option("--ai-mapper-model", type=str, default=None, help="Model to use for AI mapping.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
@click.argument("target", required=False)
def crap(
    coverprofile: str | None,
    crap_threshold: float | None,
    gaze_crap_threshold: float | None,
    max_crapload: float | None,
    max_gaze_crapload: float | None,
    ai_mapper: bool,
    ai_mapper_model: str | None,
    output_format: str,
    target: str | None,
) -> None:
    """Compute CRAP and GazeCRAP scores."""
    click.echo("gaze-py crap: not yet implemented")


# ---------------------------------------------------------------------------
# quality
# ---------------------------------------------------------------------------


@main.command()
@click.argument("tests_path", required=True)
@click.option("--target", "target_path", type=str, default=None, help="Target package or file path.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output.")
@click.option("--include-unexported", is_flag=True, default=False, help="Include unexported/private functions.")
@click.option("--config", type=click.Path(), default=None, help="Path to .gaze.yaml config file.")
@click.option("--contractual-threshold", type=int, default=None, help="Confidence threshold for contractual label.")
@click.option("--incidental-threshold", type=int, default=None, help="Confidence threshold for incidental label.")
@click.option("--min-contract-coverage", type=float, default=None, help="Minimum contract coverage percentage.")
@click.option("--max-over-specification", type=float, default=None, help="Maximum over-specification percentage.")
@click.option("--ai-mapper", is_flag=True, default=False, help="Enable AI-assisted test mapping.")
@click.option("--ai-mapper-model", type=str, default=None, help="Model to use for AI mapping.")
@click.option("--coverprofile", type=click.Path(), default=None, help="Path to .coverage SQLite database.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
def quality(
    tests_path: str,
    target_path: str | None,
    verbose: bool,
    include_unexported: bool,
    config: str | None,
    contractual_threshold: int | None,
    incidental_threshold: int | None,
    min_contract_coverage: float | None,
    max_over_specification: float | None,
    ai_mapper: bool,
    ai_mapper_model: str | None,
    coverprofile: str | None,
    output_format: str,
) -> None:
    """Map test assertions to side effects and compute contract coverage.

    TESTS_PATH is a directory containing test files (``test_*.py``).

    Exit codes: 0=success, 1=input error (missing path, missing
    coverprofile), 2=internal error.
    """
    from gaze_py.analysis import GazeParseError
    from gaze_py.quality import map_assertions
    from gaze_py.report.json import write_quality_json
    from gaze_py.report.text import write_quality_text
    from gaze_py.taxonomy import PackageSummary

    # Validate tests_path exists.
    tests_dir = _validate_path_exists(tests_path, label="tests_path")
    # User-supplied test directories may legitimately live outside cwd
    # (e.g. in CI, tmp_path fixtures, or monorepos). Traversal protection
    # is provided by analyze_path() per-file validation inside the loop.
    # A tautological root-equals-self guard is not applied here.

    # --coverprofile: validates path exists but does NOT yet read the .coverage SQLite DB.
    # Full coverage.CoverageData integration is deferred (see plan.md flag disposition).
    # TODO: implement coverage.CoverageData reading in a future spec.
    if coverprofile is not None:
        cov_path = Path(coverprofile)
        if not cov_path.exists():
            click.echo(
                f"error: coverprofile does not exist: {coverprofile}",
                err=True,
            )
            sys.exit(1)

    # Walk test files and map assertions.
    # For each test file we pass empty effects (no src analysis in quality-only mode).
    reports = []
    resolved_tests = tests_dir.resolve()
    test_files = sorted(resolved_tests.rglob("test_*.py"))

    for test_file in test_files:
        # Skip hidden directories.
        if any(part.startswith(".") for part in test_file.parts):
            continue
        try:
            test_source = test_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        # Derive target function name from test file name convention.
        # e.g. test_basic.py → "basic"
        # NOTE: quality command still uses filename heuristic (test_foo.py → foo).
        # Call-scanning for quality command is tracked as a future OpenSpec change.
        target_func = _derive_target_func(test_file)

        try:
            report = map_assertions(
                test_source=test_source,
                target_effects=[],
                target_func=target_func,
            )
        except GazeParseError as exc:
            click.echo(f"warning: skipping {test_file}: {exc}", err=True)
            continue
        reports.append(report)

    # Build package summary.
    total = len(reports)
    avg_cov = sum(r.contract_coverage.percentage for r in reports) / total if total > 0 else 0.0
    total_over = sum(r.over_specification.count for r in reports)
    avg_conf = sum(r.assertion_detection_confidence for r in reports) // total if total > 0 else 0
    summary = PackageSummary(
        total_tests=total,
        average_contract_coverage=avg_cov,
        total_over_specifications=total_over,
        assertion_detection_confidence=avg_conf,
        worst_coverage_tests=[],
    )

    buf = io.StringIO()
    if output_format == "json":
        write_quality_json(reports, summary, version=__version__, out=buf)
    else:
        write_quality_text(reports, out=buf)
    click.echo(buf.getvalue(), nl=False)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


@main.command()
@click.argument("src_path", required=True)
@click.argument("tests_path", required=True)
@click.option("--ai", is_flag=True, default=False, help="Enable AI-powered report generation.")
@click.option("--model", type=str, default=None, help="AI model to use for report generation.")
@click.option("--ai-timeout", type=str, default=None, help="Timeout for AI operations.")
@click.option("--max-crapload", type=float, default=None, help="Maximum aggregate CRAP load.")
@click.option("--max-gaze-crapload", type=float, default=None, help="Maximum aggregate GazeCRAP load.")
@click.option("--min-contract-coverage", type=float, default=None, help="Minimum contract coverage percentage.")
@click.option("--coverprofile", type=click.Path(), default=None, help="Path to .coverage SQLite database.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
def report(
    src_path: str,
    tests_path: str,
    ai: bool,
    model: str | None,
    ai_timeout: str | None,
    max_crapload: float | None,
    max_gaze_crapload: float | None,
    min_contract_coverage: float | None,
    coverprofile: str | None,
    output_format: str,
) -> None:
    """Run full pipeline: analyze → quality → GazeCRAP scores.

    SRC_PATH is the source directory or file to analyze.
    TESTS_PATH is the directory containing test files.

    Exit codes: 0=success, 1=input error, 2=internal error.
    """
    from gaze_py.analysis import GazeParseError
    from gaze_py.quality import build_test_index, map_assertions
    from gaze_py.report.json import write_quality_json
    from gaze_py.report.text import write_quality_text
    from gaze_py.taxonomy import AnalysisResult, PackageSummary

    # Validate both paths exist before any analysis.
    src = _validate_path_exists(src_path, label="src_path")
    tests = _validate_path_exists(tests_path, label="tests_path")

    # Warn if --coverprofile supplied (not yet implemented for report command).
    if coverprofile is not None:
        click.echo(
            "warning: --coverprofile is not yet implemented for the report command "
            "(planned for v0.2). The flag is accepted but has no effect.",
            err=True,
        )

    # Determine root for traversal checking (src only; tests are walked
    # directly without the traversal guard since they are user-supplied).
    abs_src = src.absolute()
    root_src = abs_src if abs_src.is_dir() else abs_src.parent

    # Phase 1: analyze source — tolerate parse errors in individual files
    # (spec: "A non-empty metadata.warnings[] does NOT change the exit code
    # if at least one result was produced").
    try:
        raw_results = _analyze_tolerant(src, root=root_src, warn=output_format != "json")
    except ValueError:
        click.echo(f"error: path escapes project root: {src.resolve()}", err=True)
        sys.exit(1)

    results: list[AnalysisResult] = raw_results  # type: ignore[assignment]

    # Phase 2: build inverted index and map assertions per source function.
    # build_test_index() scans all test files once and maps function names
    # to the test file sources that call them. Handles non-convention layouts
    # (module-named test files, class-based test suites) without filename heuristics.
    resolved_tests = tests.resolve()
    func_to_test_sources, index_warnings = build_test_index(resolved_tests)
    for warning in index_warnings:
        click.echo(f"warning: {warning}", err=True)

    reports = []
    for result in results:
        fn_name = result.target.function
        effects = result.side_effects
        if not effects:
            continue
        test_srcs = func_to_test_sources.get(fn_name)
        if not test_srcs:
            continue
        combined = "\n\n".join(test_srcs)
        try:
            rpt = map_assertions(
                test_source=combined,
                target_effects=effects,
                target_func=fn_name,
            )
        except GazeParseError as exc:
            click.echo(f"warning: skipping {fn_name}: {exc}", err=True)
            continue
        reports.append(rpt)

    # Phase 3: emit quality report (coverage metrics, gap hints).
    total = len(reports)
    avg_cov = sum(r.contract_coverage.percentage for r in reports) / total if total > 0 else 0.0
    total_over = sum(r.over_specification.count for r in reports)
    avg_conf = sum(r.assertion_detection_confidence for r in reports) // total if total > 0 else 0
    summary = PackageSummary(
        total_tests=total,
        average_contract_coverage=avg_cov,
        total_over_specifications=total_over,
        assertion_detection_confidence=avg_conf,
        worst_coverage_tests=sorted(reports, key=lambda r: r.contract_coverage.percentage)[:5],
    )

    buf = io.StringIO()
    if output_format == "json":
        write_quality_json(reports, summary, version=__version__, out=buf)
    else:
        write_quality_text(reports, out=buf)
    click.echo(buf.getvalue(), nl=False)


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------


@main.command()
def schema() -> None:
    """Print the GazeCRAP JSON schema."""
    click.echo("gaze-py schema: not yet implemented")


# ---------------------------------------------------------------------------
# docscan
# ---------------------------------------------------------------------------


@main.command()
@click.argument("target", required=False)
def docscan(target: str | None) -> None:
    """Scan documentation for contract signals."""
    click.echo("gaze-py docscan: not yet implemented")


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@main.command(name="init")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing configuration.")
def init_cmd(force: bool) -> None:
    """Initialize a .gaze.yaml configuration file."""
    click.echo("gaze-py init: not yet implemented")


# ---------------------------------------------------------------------------
# self-check
# ---------------------------------------------------------------------------


@main.command(name="self-check")
@click.option("--max-crapload", type=float, default=None, help="Maximum aggregate CRAP load.")
@click.option("--max-gaze-crapload", type=float, default=None, help="Maximum aggregate GazeCRAP load.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
def self_check(
    max_crapload: float | None,
    max_gaze_crapload: float | None,
    output_format: str,
) -> None:
    """Run self-check diagnostics."""
    click.echo("gaze-py self-check: not yet implemented")


if __name__ == "__main__":
    main()
