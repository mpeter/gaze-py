"""Test fixture: asserts inline (SC-019 — no assignment before assert).

This file is parsed as AST by the quality engine — it is never executed.
The import is intentionally absent; the engine detects calls by name, not
by resolved symbol.
"""

# ruff: noqa: F821


def test_negate_inline() -> None:
    assert negate(5) == -5
