"""Fixture: functions with stderr-write side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Predetermined side effects:
- writes_stderr: StderrWrite (sys.stderr.write(msg))
"""

import sys


def writes_stderr(msg: str) -> None:
    """Write a message to stderr."""
    sys.stderr.write(msg)
