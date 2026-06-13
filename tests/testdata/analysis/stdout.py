"""Fixture: functions with stdout-write side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Predetermined side effects:
- prints_hello:     StdoutWrite (print("hello"))
- prints_formatted: StdoutWrite (print(f"Hello, {name}!"))
"""


def prints_hello() -> None:
    """Print a fixed greeting to stdout."""
    print("hello")


def prints_formatted(name: str) -> None:
    """Print a personalised greeting to stdout."""
    print(f"Hello, {name}!")
