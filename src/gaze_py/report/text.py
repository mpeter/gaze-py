"""Human-readable text report formatters for gaze-py analysis and quality reports.

Uses ``rich`` for terminal output (python.md CS-009).  Falls back
gracefully to plain text if ``rich`` is not available in the
environment (e.g., minimal CI containers).

Design note: ``_HAS_RICH`` is checked at import time so the fallback
path is exercised in tests by monkeypatching or by running in an
environment without ``rich``.  The fallback produces the same
structural information as the rich path — just without colour and
table borders.
"""

from __future__ import annotations

from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from gaze_py.taxonomy import AnalysisResult, QualityReport

try:
    from rich.console import Console
    from rich.table import Table

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


def write_analysis_text(results: list[AnalysisResult], out: IO[str]) -> None:
    """Write analysis results as a human-readable text table to *out*.

    Produces one table per function showing effect type, tier, location,
    and description (SC-025).  Uses ``rich.Table`` when available;
    falls back to plain text otherwise.

    Args:
        results: List of ``AnalysisResult`` objects to format.
        out: Writable text stream to write output to.
    """
    if not results:
        out.write("No functions analyzed.\n")
        return

    if _HAS_RICH:
        # force_terminal=False prevents ANSI codes in StringIO during tests.
        # highlight=False avoids rich auto-highlighting numbers/strings.
        console = Console(file=out, highlight=False, force_terminal=False)
        for result in results:
            table = Table(
                title=f"{result.target.function} ({result.target.package})",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Type", style="cyan")
            table.add_column("Tier", style="magenta")
            table.add_column("Location")
            table.add_column("Description")
            for effect in result.side_effects:
                table.add_row(
                    effect.type.value,
                    effect.tier.value,
                    effect.location,
                    effect.description,
                )
            console.print(table)
    else:
        # Fallback: plain text for environments without rich.
        for result in results:
            out.write(f"\n=== {result.target.function} ({result.target.package}) ===\n")
            out.write(f"{'Type':<30}  {'Tier':<6}  {'Location'}\n")
            out.write("-" * 70 + "\n")
            for effect in result.side_effects:
                out.write(f"{effect.type.value:<30}  {effect.tier.value:<6}  {effect.location}\n")
            out.write("\n")


def write_quality_text(reports: list[QualityReport], out: IO[str]) -> None:
    """Write quality reports as human-readable text to *out*.

    Produces one summary line per test function showing contract
    coverage percentage and over-specification count.  Uses ``rich``
    when available; falls back to plain text otherwise.

    Args:
        reports: List of ``QualityReport`` objects to format.
        out: Writable text stream to write output to.
    """
    if not reports:
        out.write("No quality reports.\n")
        return

    if _HAS_RICH:
        console = Console(file=out, highlight=False, force_terminal=False)
        for report in reports:
            cov = report.contract_coverage
            over = report.over_specification
            console.print(
                f"[bold]{report.test_function}[/bold] → "
                f"{report.target_function.function}  "
                f"coverage={cov.percentage:.0f}%  "
                f"over-spec={over.count}"
            )
    else:
        for report in reports:
            cov = report.contract_coverage
            out.write(
                f"{report.test_function} → {report.target_function.function}  "
                f"coverage={cov.percentage:.0f}%  over-spec={report.over_specification.count}\n"
            )
