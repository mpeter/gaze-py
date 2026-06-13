"""Test fixture: covers only ReturnValue, not ErrorReturn (SC-018, 50% coverage)."""
from tests.testdata.quality.src_multi import process


def test_process_partial() -> None:
    result = process([1, 2, 3])
    assert result == (6, 3)
