"""Plain-text output formatter for gaze-py analysis results.

Produces one line per function in the format:
  <file_path>:<name>  complexity=N  CRAP=<value|null>  effects=<count>  strategy=<value|null>

No rich dependency — plain string formatting only per CR-006.
Per OC-002: text output is informational; JSON is the canonical machine-readable format.
"""

from __future__ import annotations

from gaze_py.taxonomy.models import AnalysisResult, FunctionTarget


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
