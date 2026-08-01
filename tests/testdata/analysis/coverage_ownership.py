"""Static fixture for per-function line-coverage ownership tests.

Exercised once by coverage.py to generate `tests/testdata/coverage_ownership.json`,
which is committed alongside it as a real reference. Tests parse this file with
`ast` and compare computed line ownership against that recorded reference.

Structure is deliberate — each function pins one ownership rule:

- `never_called`      — must resolve to exactly 0.0 (rule A: the `def` line
                        executes at import, so owning it would make 0%
                        unreachable).
- `has_nested`        — contains a nested `def`; the nested `def` line belongs
                        to the parent, the nested body does not (rule B).
- `docstring_only`    — no statements at all; must resolve to 1.0.
- `partially_covered` — some branches taken, some not.

Do not "tidy" this file: the line layout is part of the fixture. Regenerating
the JSON requires re-running the generator described in the test module.
"""

from __future__ import annotations


def fully_covered(value: int) -> int:
    """Every line runs when called once."""
    doubled = value * 2
    return doubled + 1


def never_called(value: int) -> int:
    """Never invoked by the driver — must report exactly 0% coverage."""
    intermediate = value * 3
    if intermediate > 10:
        intermediate -= 1
    return intermediate


def partially_covered(flag: bool) -> str:
    """Only the falsy branch is exercised."""
    if flag:
        return "taken"
    return "not-taken"


def has_nested(value: int) -> int:
    """Parent owns the nested `def` line but not the nested body."""

    def inner(inner_value: int) -> int:
        squared = inner_value * inner_value
        return squared

    result = inner(value)
    return result + 1


def has_uncalled_nested(value: int) -> int:
    """The nested function is defined but never invoked."""

    def unused_inner(inner_value: int) -> int:
        never_runs = inner_value * 99
        return never_runs

    return value + 1


def docstring_only() -> None:
    """No executable statements — vacuously fully covered."""
