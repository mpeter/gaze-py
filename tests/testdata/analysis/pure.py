"""Fixture: functions with no side effects (pure functions).

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Used to verify ZERO false positives: the engine MUST NOT report
any side effects other than ReturnValue for these functions.

Predetermined side effects:
- add:         ReturnValue only (returns int)
- truly_pure:  ReturnValue only (returns int — same shape as add)
- no_effects:  NONE (local variables only, no return value)
"""


def add(x: int, y: int) -> int:
    """Return the sum of x and y."""
    return x + y


def truly_pure(x: int, y: int) -> int:
    """Return the sum of x and y (demonstrates pure function shape)."""
    return x + y


def no_effects() -> None:
    """Compute using only local variables — no side effects at all."""
    x = 1
    y = 2
    z = x + y
    # z is intentionally unused; this function has no observable effects
    _ = z
