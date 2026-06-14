# AST fixture — never executed. Parsed by the quality engine only.


def raises_on_negative(x: int) -> int:
    """Return x if positive, raise ValueError otherwise."""
    if x < 0:
        raise ValueError(f"Expected non-negative, got {x}")
    return x
