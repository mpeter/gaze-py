"""Test fixture: asserts inline (SC-019 — no assignment before assert)."""
from tests.testdata.quality.src_inline import negate


def test_negate_inline() -> None:
    assert negate(5) == -5
