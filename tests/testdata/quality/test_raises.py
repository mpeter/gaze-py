"""Test fixture: covers ErrorReturn via pytest.raises (SC-015)."""

import pytest
from tests.testdata.quality.src_raises import divide


def test_divide_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
