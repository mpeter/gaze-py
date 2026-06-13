"""Fixture: functions with global-mutation side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Module-level state (intentional for fixture purposes — the analysis
engine must detect GlobalMutation on these functions):
- COUNTER: module-level integer variable

Predetermined side effects:
- increment_global: GlobalMutation (COUNTER += 1)
- set_global:       GlobalMutation (COUNTER = val)
"""

COUNTER: int = 0


def increment_global() -> None:
    """Increment the module-level COUNTER by one."""
    global COUNTER
    COUNTER += 1


def set_global(val: int) -> None:
    """Set the module-level COUNTER to val."""
    global COUNTER
    COUNTER = val
