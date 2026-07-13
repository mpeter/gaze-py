"""Fixture: parameter shadowing a from-import suppresses MonkeyPatch."""

from collections import OrderedDict  # noqa: F401


def not_a_patch(OrderedDict, fake):
    OrderedDict.magic = fake
