"""gaze-py CLI — Click-based command interface matching Go gaze flags."""

from __future__ import annotations

import click

from gaze_py import __version__


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
    """Analyze Go source for side-effect taxonomy."""
    click.echo("gaze-py analyze: not yet implemented")


# ---------------------------------------------------------------------------
# crap
# ---------------------------------------------------------------------------
@main.command()
@click.option("--coverprofile", type=click.Path(), default=None, help="Path to Go coverage profile.")
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
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
def quality(
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
    output_format: str,
) -> None:
    """Evaluate contract-aware test quality gates."""
    click.echo("gaze-py quality: not yet implemented")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
@main.command()
@click.option("--ai", is_flag=True, default=False, help="Enable AI-powered report generation.")
@click.option("--model", type=str, default=None, help="AI model to use for report generation.")
@click.option("--ai-timeout", type=str, default=None, help="Timeout for AI operations.")
@click.option("--max-crapload", type=float, default=None, help="Maximum aggregate CRAP load.")
@click.option("--max-gaze-crapload", type=float, default=None, help="Maximum aggregate GazeCRAP load.")
@click.option("--min-contract-coverage", type=float, default=None, help="Minimum contract coverage percentage.")
@click.option("--coverprofile", type=click.Path(), default=None, help="Path to Go coverage profile.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
@click.argument("target", required=False)
def report(
    ai: bool,
    model: str | None,
    ai_timeout: str | None,
    max_crapload: float | None,
    max_gaze_crapload: float | None,
    min_contract_coverage: float | None,
    coverprofile: str | None,
    output_format: str,
    target: str | None,
) -> None:
    """Generate analysis reports."""
    click.echo("gaze-py report: not yet implemented")


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
