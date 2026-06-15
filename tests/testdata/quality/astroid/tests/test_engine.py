# ruff: noqa
# AST fixture for Astroid Strategy 3 pairing tests.
# See pyproject.toml norecursedirs = ["tests/testdata"] (CR-002).
# This file is never collected by pytest.
from engine import _make_engine  # noqa: F821


def test_classify():
    e = _make_engine()
    assert e.classify(1) == 2
