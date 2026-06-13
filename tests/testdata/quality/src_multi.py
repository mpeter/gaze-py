"""Source fixture: function with two contractual effects (SC-018)."""


def process(items: list[int]) -> tuple[int, int]:
    """Return (sum, count) of items; raises ValueError if empty."""
    if not items:
        raise ValueError("empty list")
    return sum(items), len(items)
