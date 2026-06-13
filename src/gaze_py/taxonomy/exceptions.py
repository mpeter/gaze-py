"""Domain exception classes for gaze-py.

Per AP-008: all shared exceptions live here and are imported by other
subpackages. No subpackage defines exceptions that other subpackages import.
"""


class GazeParseError(RuntimeError):
    """Raised when ast.parse() fails on a Python source file.

    Carries the file path in the message so the error is actionable.
    """


class GazeConfigError(ValueError):
    """Raised when .gaze.yaml contains invalid configuration values."""
