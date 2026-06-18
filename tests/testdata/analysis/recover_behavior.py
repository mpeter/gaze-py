# ruff: noqa
"""Fixture for RecoverBehavior detection."""


def parse_int_with_fallback(value: str) -> int:
    """Returns 0 on parse failure — assignment in except."""
    try:
        return int(value)
    except ValueError:
        result = 0
        return result


def suppress_error() -> None:
    """Suppresses error silently — bare pass in except."""
    try:
        risky_op()
    except Exception:
        pass


def return_none_on_error(value: str) -> int | None:
    """Returns None fallback — return only (no assignment)."""
    try:
        return int(value)
    except ValueError:
        return None


def double_try_recovers_once(value: str) -> int:
    """Two qualifying try/except blocks — RecoverBehavior emitted once."""
    try:
        result = int(value)
    except ValueError:
        result = 0
    try:
        result = result + 1
    except TypeError:
        result = -1
    return result


def reraise_is_not_recovery(value: str) -> int:
    """Re-raise is NOT RecoverBehavior."""
    try:
        return int(value)
    except ValueError:
        raise


def transform_reraise_is_not_recovery(value: str) -> int:
    """Transform-and-reraise is NOT RecoverBehavior."""
    try:
        return int(value)
    except ValueError as e:
        raise RuntimeError("bad value") from e
