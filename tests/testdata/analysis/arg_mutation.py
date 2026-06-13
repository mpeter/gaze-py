"""Fixture: functions with argument-mutation side effects.

These are static source fixtures for the gaze-py analysis engine.
The analysis engine reads and parses these files — they are NOT tests.

Predetermined side effects:
- update_dict:    PointerArgMutation (d.update(...) call on arg)
- append_list:    PointerArgMutation (lst.append(...) call on arg)
- subscript_dict: PointerArgMutation (d["key"] = "val" subscript on arg)
"""


def update_dict(d: dict) -> None:
    """Mutate dict argument via .update()."""
    d.update({"key": "val"})


def append_list(lst: list) -> None:
    """Mutate list argument via .append()."""
    lst.append(1)


def subscript_dict(d: dict) -> None:
    """Mutate dict argument via subscript assignment."""
    d["key"] = "val"
