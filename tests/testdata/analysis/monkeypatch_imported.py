"""Fixture: MonkeyPatch — attribute replacement on imported names."""

import sqlite3
from collections import OrderedDict


def patch_it(fake):
    OrderedDict.magic = fake
    sqlite3.Row.custom = fake
