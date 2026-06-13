"""Source fixture: function where test over-specifies internal state (SC-017)."""


def square(x: int) -> int:
    """Return x squared."""
    intermediate = x * x
    return intermediate
