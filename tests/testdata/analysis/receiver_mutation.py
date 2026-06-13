"""Fixture: methods with receiver-mutation side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Predetermined side effects:
- Counter.__init__: ReceiverMutation (self.value = 0)
- Counter.increment: ReceiverMutation (self.value += 1)
- Counter.reset:     ReceiverMutation (self.value = 0)
"""


class Counter:
    """A simple counter with mutable state for fixture purposes."""

    def __init__(self) -> None:
        """Initialise the counter to zero."""
        self.value = 0

    def increment(self) -> None:
        """Increment the counter by one."""
        self.value += 1

    def reset(self) -> None:
        """Reset the counter to zero."""
        self.value = 0
