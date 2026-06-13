"""Test fixture: calls function but has no assertions (SC-016)."""
from tests.testdata.quality.src_no_assert import multiply


def test_multiply_no_assert() -> None:
    multiply(3, 4)  # called but no assert — coverage = 0%
