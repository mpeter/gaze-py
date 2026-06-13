"""Test fixture: covers ReturnValue via assignment + assert (SC-014).

This file is parsed as AST by the quality engine — it is never executed.
The import is intentionally absent; the engine detects calls by name, not
by resolved symbol.
"""



def test_compute() -> None:
    result = compute(1, 2)
    assert result == 3
