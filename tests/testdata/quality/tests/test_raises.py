# ruff: noqa: F821
# AST fixture — never executed. Parsed by the quality engine only.
import pytest


def test_raises_on_negative() -> None:
    with pytest.raises(ValueError):
        raises_on_negative(-1)
