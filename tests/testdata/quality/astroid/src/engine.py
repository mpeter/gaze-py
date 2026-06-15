# ruff: noqa
# AST fixture for Astroid Strategy 3 pairing tests. Never executed.


def caller_signal(x):  # type: ignore[override]
    return x * 2


class Engine:
    def classify(self, x):
        return caller_signal(x)


def _make_engine():
    return Engine()
