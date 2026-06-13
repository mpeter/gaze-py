"""Fixture: functions with environment-mutation side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Covers BOTH detection forms required by the spec:
- SC-010 (subscript form):  os.environ[key] = val
- SC-011 (call form):       os.environ.update(data)

Predetermined side effects:
- set_env_subscript: EnvMutation via subscript assignment (SC-010)
- set_env_update:    EnvMutation via .update() call (SC-011)
"""

import os


def set_env_subscript(key: str, val: str) -> None:
    """Set an environment variable via subscript assignment."""
    os.environ[key] = val


def set_env_update(data: dict) -> None:
    """Update multiple environment variables via os.environ.update()."""
    os.environ.update(data)
