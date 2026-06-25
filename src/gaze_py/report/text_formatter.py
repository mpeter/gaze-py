"""Plain-text output formatter for gaze-py analysis results.

Produces one line per function in the format:
  <file_path>:<name>  complexity=N  CRAP=<value|null>  effects=<count>  strategy=<value|null>

No rich dependency — plain string formatting only per CR-006.
Per OC-002: text output is informational; JSON is the canonical machine-readable format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gaze_py.crap.compare import FunctionStatus
from gaze_py.taxonomy.models import AnalysisResult, FunctionTarget

if TYPE_CHECKING:
    from gaze_py.crap.compare import ComparisonResult


def to_text(result: AnalysisResult) -> str:
    """Serialize an AnalysisResult to a plain-text string.

    Produces one line per function with key metrics. Null values are shown
    as the literal string "null".

    Format per function:
        <file_path>:<name>  complexity=N  CRAP=<value|null>  effects=<count>  strategy=<value|null>

    Args:
        result: The AnalysisResult to format.

    Returns:
        Multi-line plain-text string. Each non-empty line corresponds to one
        analyzed function.
    """
    lines: list[str] = []
    for target in result.results:
        lines.append(_format_function(target))
    return "\n".join(lines)


def _format_function(target: FunctionTarget) -> str:
    """Format a single FunctionTarget as a text line.

    Args:
        target: The FunctionTarget to format.

    Returns:
        A single-line string with the function's key metrics.
    """
    crap_val: str
    strategy_val: str

    if target.score is not None and target.score.crap is not None:
        crap_val = f"{target.score.crap:.2f}"
    else:
        crap_val = "null"

    if target.score is not None and target.score.fix_strategy is not None:
        strategy_val = target.score.fix_strategy
    else:
        strategy_val = "null"

    effect_count = len(target.effects)

    return (
        f"{target.file_path}:{target.function}"
        f"  complexity={target.complexity}"
        f"  CRAP={crap_val}"
        f"  effects={effect_count}"
        f"  strategy={strategy_val}"
    )


def _fn_name(entry: dict[str, object]) -> str:
    """Extract the function name from a result entry dict.

    Args:
        entry: A result dict with an optional ``target`` sub-dict.

    Returns:
        The function name string, or ``"?"`` when unavailable.
    """
    target = entry.get("target")
    if isinstance(target, dict):
        fn = target.get("function", "?")
        return str(fn) if fn is not None else "?"
    return "?"


def _crap_float(value: object) -> float:
    """Coerce a CRAP value to float, treating None as 0.0.

    OC-003: None means "not computed" — treat as 0.0 for threshold comparisons.
    Uses explicit isinstance check to avoid treating crap=0.0 as missing.

    Args:
        value: Raw CRAP value from a result dict (may be int, float, or None).

    Returns:
        Float representation, or 0.0 when value is None or non-numeric.
    """
    return float(value) if isinstance(value, (int, float)) else 0.0


def comparison_to_text(crap_text: str, result: ComparisonResult) -> str:
    """Format a baseline comparison result as plain text.

    Appends a comparison section to the existing CRAP text output.
    Empty sections (Improvements, New violations, Removed) are omitted.

    Args:
        crap_text: The existing CRAP text output (from ``to_text()``).
        result: The ComparisonResult to format.

    Returns:
        Combined string: crap_text + comparison section.
    """
    s = result.summary
    verdict = "PASS" if s.passed else "FAIL"
    lines: list[str] = [
        crap_text,
        f"--- Baseline Comparison: {verdict} ---",
        (
            f"Regressions: {s.regressions}  "
            f"Improvements: {s.improvements}  "
            f"Unchanged: {s.unchanged}  "
            f"New: {s.new_functions}  "
            f"New violations: {s.new_violations}  "
            f"Removed: {s.removed_functions}"
        ),
    ]

    # Regressions table — always shown when non-zero.
    # M-4: compare against enum members, not .value strings.
    regressions = [d for d in result.deltas if d.status == FunctionStatus.REGRESSION]
    if regressions:
        lines.append("")
        lines.append("Regressions:")
        lines.append(f"  {'Function':<40}  {'CRAP delta':>10}  {'GazeCRAP delta':>14}")
        lines.append(f"  {'-' * 40}  {'-' * 10}  {'-' * 14}")
        for d in regressions:
            fn_key = _fn_name(d.current)
            gaze_str = f"{d.gaze_crap_delta:+.2f}" if d.gaze_crap_delta is not None else "n/a"
            lines.append(f"  {fn_key:<40}  {d.crap_delta:+10.2f}  {gaze_str:>14}")

    # Improvements table — omitted when empty.
    improvements = [d for d in result.deltas if d.status == FunctionStatus.IMPROVEMENT]
    if improvements:
        lines.append("")
        lines.append("Improvements:")
        lines.append(f"  {'Function':<40}  {'CRAP delta':>10}  {'GazeCRAP delta':>14}")
        lines.append(f"  {'-' * 40}  {'-' * 10}  {'-' * 14}")
        for d in improvements:
            fn_key = _fn_name(d.current)
            gaze_str = f"{d.gaze_crap_delta:+.2f}" if d.gaze_crap_delta is not None else "n/a"
            lines.append(f"  {fn_key:<40}  {d.crap_delta:+10.2f}  {gaze_str:>14}")

    # New violations — omitted when empty.
    threshold = s.new_function_threshold
    new_violations = [
        fn
        for fn in result.new_functions
        # OC-003: explicit None check — crap=0.0 is valid and must not be treated as missing.
        if _crap_float(fn.get("crap")) > threshold
    ]
    if new_violations:
        lines.append("")
        lines.append("New violations (CRAP above threshold):")
        for fn_entry in new_violations:
            fn_key = _fn_name(fn_entry)
            crap_val = _crap_float(fn_entry.get("crap"))
            lines.append(f"  {fn_key}  CRAP={crap_val:.2f}")

    # Removed functions — omitted when empty.
    if result.removed_functions:
        lines.append("")
        lines.append("Removed functions:")
        for fn_entry in result.removed_functions:
            fn_key = _fn_name(fn_entry)
            lines.append(f"  {fn_key}")

    return "\n".join(lines)
