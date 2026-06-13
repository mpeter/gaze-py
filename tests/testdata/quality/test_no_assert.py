"""Test fixture: calls function but has no assertions (SC-016).

This file is parsed as AST by the quality engine — it is never executed.
The import is intentionally absent; the engine detects calls by name, not
by resolved symbol.
"""



def test_multiply_no_assert() -> None:
    multiply(3, 4)  # called but no assert — coverage = 0%
