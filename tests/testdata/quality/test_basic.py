"""Test fixture: covers ReturnValue via assignment + assert (SC-014)."""
from tests.testdata.quality.src_basic import compute


def test_compute() -> None:
    result = compute(1, 2)
    assert result == 3
