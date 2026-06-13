"""Fixture: functions with error-return (raise) side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Predetermined side effects:
- raises_value_error:     ErrorReturn (unconditional ValueError)
- raises_conditionally:   ErrorReturn (conditional ValueError)
- raises_not_implemented: ErrorReturn (unconditional NotImplementedError)
"""


def raises_value_error() -> None:
    """Always raise ValueError."""
    raise ValueError("bad")


def raises_conditionally(x: int) -> None:
    """Raise ValueError when x is negative."""
    if x < 0:
        raise ValueError("negative")


def raises_not_implemented() -> None:
    """Always raise NotImplementedError."""
    raise NotImplementedError
