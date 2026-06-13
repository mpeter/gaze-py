"""Fixture: function with multiple return statements (SC-013 deduplication).

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

SC-013 requires that multiple return statements in a single function
produce exactly ONE ReturnValue side effect (deduplicated by type).

Predetermined side effects:
- two_returns: ReturnValue (ONE effect, despite two return statements)
"""


def two_returns(x: int) -> int:
    """Return x if positive, otherwise return 0.

    Contains two return statements — the analysis engine MUST
    deduplicate these into a single ReturnValue side effect.
    """
    if x > 0:
        return x
    return 0
