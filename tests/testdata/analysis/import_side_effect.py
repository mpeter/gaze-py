"""Fixture: ImportSideEffect — deferred imports inside a function body."""


def lazy_load():
    import json
    from os import path

    return json, path
