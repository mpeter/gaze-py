"""Test fixture: covers ErrorReturn via pytest.raises (SC-015).

This file is parsed as AST by the quality engine — it is never executed.
The import is intentionally absent; the engine detects calls by name, not
by resolved symbol.
"""

import pytest


def test_divide_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
