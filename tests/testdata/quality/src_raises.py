"""Source fixture: function that raises (SC-015)."""


def divide(a: int, b: int) -> float:
    """Divide a by b; raises ZeroDivisionError if b is zero."""
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b
