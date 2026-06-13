"""Caller dependency signal analyzer — Signal 3.

Counts how many distinct modules/packages call this function. More callers
means stronger evidence of contractual behavior.

Per CC-005 weight table:
  0 callers → 0 (no signal emitted)
  1 caller  → +5
  2–3 callers → +10
  4+ callers  → +15
"""

from __future__ import annotations

from gaze_py.taxonomy.models import Signal

# Caller count thresholds and corresponding weights per CC-005.
_SINGLE_CALLER_THRESHOLD: int = 1
_MULTI_CALLER_THRESHOLD: int = 3  # 2–3 callers → +10; 4+ → +15

_SINGLE_CALLER_WEIGHT: int = 5
_MULTI_CALLER_WEIGHT: int = 10
_MANY_CALLER_WEIGHT: int = 15


def caller_signal(caller_count: int) -> Signal | None:
    """Compute the caller dependency signal for a function.

    Returns a Signal based on the number of distinct caller modules. Returns
    None when caller_count is 0 (no callers → no signal contribution).

    Args:
        caller_count: Number of distinct modules that call this function.
            Sourced from FunctionTarget.caller_count, which is populated by
            the CLI's pre-pass caller map. Defaults to 0 when no caller map
            is provided.

    Returns:
        A Signal with source='caller' and weight in {5, 10, 15}, or None
        when caller_count is 0.
    """
    if caller_count == 0:
        return None
    if caller_count <= _SINGLE_CALLER_THRESHOLD:
        return Signal(source="caller", weight=_SINGLE_CALLER_WEIGHT)
    if caller_count <= _MULTI_CALLER_THRESHOLD:
        return Signal(source="caller", weight=_MULTI_CALLER_WEIGHT)
    return Signal(source="caller", weight=_MANY_CALLER_WEIGHT)
