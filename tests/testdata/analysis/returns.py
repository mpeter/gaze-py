"""Fixture: functions with return-value side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Predetermined side effects:
- returns_int:   ReturnValue (returns int literal)
- returns_tuple: ReturnValue (returns tuple)
- returns_none:  (no ReturnValue — implicit None is not a side effect)
"""


def returns_int() -> int:
    """Return a constant integer."""
    return 42


def returns_tuple() -> tuple[int, int]:
    """Return a two-element tuple."""
    return 1, 2


def returns_none() -> None:
    """Return nothing (implicit None — no ReturnValue side effect)."""
    pass
