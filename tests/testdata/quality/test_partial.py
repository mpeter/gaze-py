"""Test fixture: covers only ReturnValue, not ErrorReturn (SC-018, 50% coverage).

This file is parsed as AST by the quality engine — it is never executed.
The import is intentionally absent; the engine detects calls by name, not
by resolved symbol.
"""



def test_process_partial() -> None:
    result = process([1, 2, 3])
    assert result == (6, 3)
