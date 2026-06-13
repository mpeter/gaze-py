"""Test fixture: asserts on internal variable — over-specification (SC-017)."""

from tests.testdata.quality.src_incidental import square


def test_square_overspecified() -> None:
    # This asserts on the return value (correct)
    result = square(4)
    assert result == 16
    # This asserts on an internal variable (incidental) — but we can't actually
    # access internal vars, so we simulate: an additional assert that targets
    # something trivially true but not the contract
    assert isinstance(result, int)  # over-specifying the type
