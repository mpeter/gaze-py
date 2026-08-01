"""Per-function line coverage attribution — ownership rules and resolution.

CRAP is a per-function metric. Applying a file's aggregate coverage to every
function in it conceals untested functions behind well-covered file-mates and
falsely flags well-tested ones. These tests pin the two line-ownership rules
and the resolution edge cases against a *real* coverage.py reference.

The reference — `tests/testdata/coverage_ownership.json` — was produced by
running coverage.py over `tests/testdata/analysis/coverage_ownership.py` with a
driver that calls every function except `never_called` and `unused_inner`. It
is committed rather than regenerated so these tests stay fast and
deterministic. To regenerate after editing the fixture:

    mkdir -p /tmp/own_src
    cp tests/testdata/analysis/coverage_ownership.py /tmp/own_src/
    # driver imports the module and calls every function except
    # never_called and has_uncalled_nested.unused_inner
    coverage run --rcfile=/dev/null --data-file=/tmp/own.cov \\
        --source=/tmp/own_src driver.py
    coverage json --rcfile=/dev/null --data-file=/tmp/own.cov -o out.json

then rewrite the single file key to the repo-relative fixture path.

Both the fixture module and this reference are load-bearing: the fixture's line
layout is what the recorded line numbers refer to.
"""

from __future__ import annotations

import ast
import itertools
import json
from pathlib import Path
from typing import cast

import pytest

# CR-004: `_fn_owned_lines`, `_FileCoverage`, `_line_set` and
# `_resolve_line_coverage` are imported and tested directly. `_fn_owned_lines`
# is pure AST arithmetic with no public surface — the ownership rules it encodes
# are the whole subject of this module, and reaching them through `gazepy crap`
# would only observe them blurred through a CRAP score. `_line_set`'s malformed
# and degraded branches cannot be reached through the CLI without hand-writing a
# broken coverage JSON per case, which would obscure what is being pinned.
# `_resolve_line_coverage` and `_FileCoverage` are exercised directly so the
# resolution edge cases (zero-statement body, stale report, report that
# describes none of a function's lines) are each isolated to one assertion.
from gaze_py.analysis.detector import _fn_owned_lines, _module_end_line, _owned_lines
from gaze_py.analysis.runner import detect_and_classify
from gaze_py.cli.main import _FileCoverage, _line_set, _resolve_line_coverage
from gaze_py.config.loader import GazeConfig
from gaze_py.taxonomy.models import FunctionTarget

_FIXTURE_SRC = Path(__file__).parent / "testdata" / "analysis" / "coverage_ownership.py"
_FIXTURE_COV = Path(__file__).parent / "testdata" / "coverage_ownership.json"
_FIXTURE_KEY = "tests/testdata/analysis/coverage_ownership.py"


def _reference() -> dict[str, object]:
    """Load the committed coverage.py reference for the fixture module."""
    raw = json.loads(_FIXTURE_COV.read_text(encoding="utf-8"))
    entry = raw["files"][_FIXTURE_KEY]
    assert isinstance(entry, dict)
    return entry


def _fixture_functions() -> dict[int, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Map each fixture function's *definition line* to its AST node.

    Keyed by line so nested functions (which share a simple name space with
    their parents only by qualname) join unambiguously against coverage.py's
    `start_line`.
    """
    tree = ast.parse(_FIXTURE_SRC.read_text(encoding="utf-8"), filename=str(_FIXTURE_SRC))
    return {
        node.lineno: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _reference_functions() -> list[tuple[str, dict[str, object]]]:
    """Return the reference's per-function entries, module scope excluded.

    Evaluated at import so tests can parametrize over the cases rather than
    loop (TC-005): a loop aborts at the first failure and hides how many of
    the eight functions actually reconcile.
    """
    functions = _reference()["functions"]
    assert isinstance(functions, dict)
    cases: list[tuple[str, dict[str, object]]] = []
    for qualname, fn_entry in functions.items():
        if qualname == "":
            continue  # module scope is not a function target
        assert isinstance(fn_entry, dict)
        cases.append((str(qualname), fn_entry))
    return cases


_REFERENCE_FUNCTIONS = _reference_functions()
_REFERENCE_IDS = [qualname for qualname, _ in _REFERENCE_FUNCTIONS]


def _node_for(fn_entry: dict[str, object], qualname: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Join a reference entry to its AST node via the recorded `start_line`.

    The name check is the fixture-drift guard: editing
    `tests/testdata/analysis/coverage_ownership.py` shifts `def` lines, and
    without it a recorded `start_line` that happens to land on a *different*
    function would silently compare the wrong function against the wrong
    reference and pass.
    """
    start_line = fn_entry["start_line"]
    assert isinstance(start_line, int)
    nodes = _fixture_functions()
    assert start_line in nodes, (
        f"reference entry {qualname} points at line {start_line}, which is no "
        f"longer a function definition — regenerate {_FIXTURE_COV.name} "
        f"(see this module's docstring)"
    )
    node = nodes[start_line]
    assert node.name == qualname.rsplit(".", maxsplit=1)[-1], (
        f"reference entry {qualname} now lands on {node.name!r} — regenerate "
        f"{_FIXTURE_COV.name} (see this module's docstring)"
    )
    return node


def _target_for(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionTarget:
    """Build a scoring target carrying the node's computed line ownership."""
    return FunctionTarget(
        function=node.name,
        file_path=_FIXTURE_KEY,
        line=node.lineno,
        complexity=1,
        package=_FIXTURE_KEY,
        receiver=None,
        signature=f"def {node.name}()",
        owned_lines=_fn_owned_lines(node),
    )


def _reference_pct(entry: dict[str, object]) -> float:
    """Read `summary.percent_covered` from a coverage.py entry as a float."""
    summary = entry["summary"]
    assert isinstance(summary, dict)
    pct = summary["percent_covered"]
    assert isinstance(pct, (int, float))
    return float(pct)


def _reference_lines(entry: dict[str, object], key: str) -> frozenset[int]:
    """Read a coverage.py line array (`executed_lines`/`missing_lines`)."""
    raw = entry[key]
    assert isinstance(raw, list)
    return frozenset(cast("list[int]", raw))


def _file_coverage() -> _FileCoverage:
    """Build a _FileCoverage from the reference's FILE-level line arrays.

    File-level arrays are what the resolver actually consumes in production —
    per-function attribution is derived from them, not read from coverage.py's
    per-function map. Using them here means these tests exercise the real path.
    """
    entry = _reference()
    return _FileCoverage(
        percent_covered=_reference_pct(entry),
        executed_lines=_reference_lines(entry, "executed_lines"),
        missing_lines=_reference_lines(entry, "missing_lines"),
    )


def _resolve(name: str) -> float | None:
    """Resolve per-function coverage for a fixture function by name."""
    nodes = _fixture_functions()
    node = next(n for n in nodes.values() if n.name == name)
    resolved = _resolve_line_coverage(
        Path(_FIXTURE_KEY),
        Path("."),
        {_FIXTURE_KEY: _file_coverage()},
        target=_target_for(node),
    )
    return resolved


# ---------------------------------------------------------------------------
# Ownership rules validated against the coverage.py reference
# ---------------------------------------------------------------------------


def test_fixture_contributes_every_expected_function() -> None:
    """The reference must describe all 8 fixture functions, 2 of them nested.

    Pins the case count that the parametrized tests below iterate, so a
    truncated or stale reference fails loudly instead of silently shrinking
    the acceptance suite to whatever it still contains.
    """
    assert len(_REFERENCE_FUNCTIONS) == 8


@pytest.mark.parametrize(("qualname", "fn_entry"), _REFERENCE_FUNCTIONS, ids=_REFERENCE_IDS)
def test_owned_lines_reproduce_coverage_py_statement_sets(
    qualname: str, fn_entry: dict[str, object]
) -> None:
    """Computed ownership MUST cover coverage.py's own per-function statements.

    This is the acceptance test for both ownership rules. It compares *sets*,
    not counts, so an off-by-one that happens to preserve the total still fails.

    The assertion is containment rather than equality, and must stay that way:
    `owned_lines` deliberately includes blank, comment and docstring lines that
    coverage.py excludes from its statement set, so equality is unachievable.
    Over-ownership is bounded separately, by
    `test_ownership_is_pairwise_disjoint_and_within_each_function_extent`.
    """
    node = _node_for(fn_entry, qualname)
    reference_stmts = set(_reference_lines(fn_entry, "executed_lines")) | set(
        _reference_lines(fn_entry, "missing_lines")
    )
    owned = _fn_owned_lines(node)
    assert owned & reference_stmts == reference_stmts, (
        f"{qualname}: ownership does not cover coverage.py's statements "
        f"(missing {sorted(reference_stmts - owned)})"
    )


@pytest.mark.parametrize(("qualname", "fn_entry"), _REFERENCE_FUNCTIONS, ids=_REFERENCE_IDS)
def test_resolved_coverage_matches_coverage_py_percentages(
    qualname: str, fn_entry: dict[str, object]
) -> None:
    """Resolving from FILE-level arrays MUST reproduce coverage.py's per-function %.

    This is the end-to-end guard. It is where rule A (excluding the `def` line)
    actually bites: the `def` line appears in the file's executed_lines, so
    owning it would inflate every uncovered function above 0%.
    """
    node = _node_for(fn_entry, qualname)
    resolved = _resolve_line_coverage(
        Path(_FIXTURE_KEY),
        Path("."),
        {_FIXTURE_KEY: _file_coverage()},
        target=_target_for(node),
    )
    expected = _reference_pct(fn_entry) / 100.0
    assert resolved == pytest.approx(expected), (
        f"{qualname}: resolved {resolved} but coverage.py reports {expected}"
    )


def test_ownership_is_pairwise_disjoint_and_within_each_function_extent() -> None:
    """Bounds over-ownership, which the containment acceptance test cannot see.

    Two functions must never claim the same line, and no function may own a
    line outside its own body extent. Without this, extending a single
    function's range into surrounding non-statement lines would pass both the
    containment check and the percentage check — those lines appear in neither
    coverage.py array, so they intersect away to nothing.
    """
    nodes = _fixture_functions()
    owned_by_line = {node.lineno: (node, _fn_owned_lines(node)) for node in nodes.values()}

    for node, owned in owned_by_line.values():
        extent = frozenset(range(node.body[0].lineno, (node.end_lineno or node.lineno) + 1))
        assert owned <= extent, (
            f"{node.name} owns lines outside its body extent: {sorted(owned - extent)}"
        )

    for (node_a, owned_a), (node_b, owned_b) in itertools.combinations(owned_by_line.values(), 2):
        assert owned_a.isdisjoint(owned_b), (
            f"{node_a.name} and {node_b.name} both own {sorted(owned_a & owned_b)}"
        )


def test_parent_owns_the_nested_def_line_but_not_the_nested_body() -> None:
    """Rule B: the nested `def` statement executes in the parent's scope.

    Verified directly against the reference, which records line 48 (the
    `def inner(...)` line) among `has_nested`'s executed lines, and lines
    49-50 (inner's body) under `has_nested.inner`.
    """
    nodes = _fixture_functions()
    parent = next(n for n in nodes.values() if n.name == "has_nested")
    inner = next(n for n in nodes.values() if n.name == "inner")

    parent_owned = _fn_owned_lines(parent)
    inner_owned = _fn_owned_lines(inner)

    assert inner.lineno in parent_owned, "parent must own the nested def line"
    assert inner.lineno not in inner_owned, "nested function must not own its own def line"
    assert not (parent_owned & inner_owned), "parent and nested ownership must be disjoint"
    for body_line in range(inner.body[0].lineno, (inner.end_lineno or 0) + 1):
        assert body_line not in parent_owned, f"parent must not own nested body line {body_line}"


@pytest.mark.parametrize("lineno", [node.lineno for node in _fixture_functions().values()], ids=str)
def test_fixture_function_does_not_own_its_own_def_line(lineno: int) -> None:
    """Rule A: the `def` line executes at import, so the function cannot own it."""
    node = _fixture_functions()[lineno]
    owned = _fn_owned_lines(node)
    assert node.lineno not in owned, f"{node.name} must not own its def line"


@pytest.mark.parametrize(
    ("source", "excluded"),
    [
        ("@deco\ndef f():\n    return 1\n", (1, 2)),
        ("@a\n@b\ndef f():\n    return 1\n", (1, 2, 3)),
        ("async def f():\n    return 1\n", (1,)),
        ("@property\ndef m(self):\n    return 1\n", (1, 2)),
        ("@deco\nasync def f():\n    return 1\n", (1, 2)),
    ],
    ids=["decorated", "stacked-decorators", "async", "decorated-method", "decorated-async"],
)
def test_decorator_and_def_lines_are_never_owned(source: str, excluded: tuple[int, ...]) -> None:
    """Rule A covers decorator lines too, and applies to `async def`.

    The committed fixture contains no decorated or async function, so without
    these cases the rule-A guard above proves only the plain-`def` half of what
    its name claims. Decorators execute at import exactly as `def` does, so
    owning them would make 0% unreachable for a decorated function — the same
    defect rule A exists to prevent.

    Parsed inline rather than added to the fixture so the committed
    coverage.py reference stays valid.
    """
    node = next(
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    owned = _fn_owned_lines(node)
    assert owned.isdisjoint(excluded), (
        f"owned {sorted(owned)} must exclude def/decorator lines {list(excluded)}"
    )


def test_methods_of_a_nested_class_are_subtracted_from_the_enclosing_scope() -> None:
    """A nested class body stays with the parent; its methods do not.

    A class body executes in the enclosing scope at definition time, so its
    statements belong to the enclosing function. Each method is an
    independently scored target, so its body must be subtracted.
    """
    source = (
        "def outer():\n"
        "    class C:\n"
        "        x = 1\n"
        "\n"
        "        def m(self):\n"
        "            return 2\n"
        "    return C\n"
    )
    tree = ast.parse(source)
    outer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "outer")
    owned = _fn_owned_lines(outer)

    assert 2 in owned, "class statement executes in the parent scope"
    assert 3 in owned, "class body statement executes in the parent scope"
    assert 5 in owned, "the method's def line executes in the class body (rule B)"
    assert 6 not in owned, "the method's body belongs to the method, not the parent"


# ---------------------------------------------------------------------------
# Resolution edge cases
# ---------------------------------------------------------------------------


def test_never_called_function_resolves_to_exactly_zero() -> None:
    """A never-invoked function reports 0.0, not a small positive fraction.

    Regression guard for rule A: its `def` line is in the file's executed_lines,
    so owning it would yield a nonzero fraction and understate CRAP.
    """
    resolved = _resolve("never_called")
    assert resolved == 0.0


def test_fully_covered_function_resolves_to_one() -> None:
    """A fully exercised function reports 1.0 even though its file is at 72%."""
    resolved = _resolve("fully_covered")
    assert resolved == 1.0


def test_partially_covered_function_reports_its_own_fraction() -> None:
    """Partial coverage is the function's own ratio, not the file's."""
    resolved = _resolve("partially_covered")
    assert resolved == pytest.approx(2 / 3)


def test_docstring_only_body_resolves_to_full_coverage() -> None:
    """A body with no statements is vacuously complete, as coverage.py reports it."""
    resolved = _resolve("docstring_only")
    assert resolved == 1.0


def test_uncalled_nested_function_does_not_drag_down_its_parent() -> None:
    """The parent is fully covered; only the nested function is uncovered."""
    parent_resolved = _resolve("has_uncalled_nested")
    nested_resolved = _resolve("unused_inner")
    assert parent_resolved == 1.0
    assert nested_resolved == 0.0


def test_functions_in_one_file_receive_distinct_coverage() -> None:
    """The core bug: one file must not yield one coverage value for all functions.

    Before per-function attribution every function here reported the file's
    72%, concealing `never_called` entirely.
    """
    names = ["fully_covered", "never_called", "partially_covered"]
    resolved = {name: _resolve(name) for name in names}
    assert len(set(resolved.values())) == 3, f"expected 3 distinct values, got {resolved}"


# ---------------------------------------------------------------------------
# Degraded input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("executed", "missing"),
    [
        (None, None),
        (frozenset({1, 2}), None),
        (None, frozenset({1, 2})),
    ],
    ids=["both-absent", "missing-absent", "executed-absent"],
)
def test_missing_line_arrays_fall_back_to_file_level(
    executed: frozenset[int] | None,
    missing: frozenset[int] | None,
) -> None:
    """Without both line arrays, per-function attribution is impossible."""
    nodes = _fixture_functions()
    node = next(n for n in nodes.values() if n.name == "never_called")
    resolved = _resolve_line_coverage(
        Path(_FIXTURE_KEY),
        Path("."),
        {
            _FIXTURE_KEY: _FileCoverage(
                percent_covered=80.0, executed_lines=executed, missing_lines=missing
            )
        },
        target=_target_for(node),
    )
    assert resolved == 0.8


def test_unknown_extent_falls_back_to_file_level() -> None:
    """A target with no computed ownership degrades rather than guessing."""
    target = FunctionTarget(
        function="unknown",
        file_path=_FIXTURE_KEY,
        line=1,
        complexity=1,
        package=_FIXTURE_KEY,
        receiver=None,
        signature="def unknown()",
    )
    assert target.owned_lines is None
    resolved = _resolve_line_coverage(
        Path(_FIXTURE_KEY), Path("."), {_FIXTURE_KEY: _file_coverage()}, target=target
    )
    assert resolved == pytest.approx(0.72)


def test_report_that_describes_none_of_a_functions_lines_degrades() -> None:
    """A stale report must not fabricate a perfect score.

    When a coverage report predates the source — a file grew, or the artifact
    was generated against different code — a function's lines appear in neither
    `executed_lines` nor `missing_lines`. Inferring 1.0 from that silence would
    hand a brand-new, wholly untested function CRAP == complexity on the very
    path that feeds `--max-crapload`. Degrading to the file aggregate keeps the
    number derived from real data.
    """
    stale = _FileCoverage(
        percent_covered=90.0,
        executed_lines=frozenset(range(1, 20)),
        missing_lines=frozenset(),
    )
    appended = FunctionTarget(
        function="brand_new_untested",
        file_path=_FIXTURE_KEY,
        line=100,
        complexity=20,
        package=_FIXTURE_KEY,
        receiver=None,
        signature="def brand_new_untested()",
        owned_lines=frozenset(range(101, 121)),
    )
    resolved = _resolve_line_coverage(
        Path(_FIXTURE_KEY), Path("."), {_FIXTURE_KEY: stale}, target=appended
    )
    assert resolved == 0.9, "expected the file aggregate, not a fabricated 1.0"


def test_owning_no_statements_is_distinct_from_owning_undescribed_statements() -> None:
    """The two empty-intersection cases must not collapse into one answer.

    A docstring-only body genuinely owns nothing and is vacuously covered.
    A function that owns lines the report ignores is unmeasured. Only the
    first may resolve to 1.0.
    """
    nodes = _fixture_functions()
    docstring_only = next(n for n in nodes.values() if n.name == "docstring_only")
    assert _fn_owned_lines(docstring_only) == frozenset(), (
        "a docstring-only body must own no lines so the resolver can tell the cases apart"
    )

    covered = next(n for n in nodes.values() if n.name == "fully_covered")
    assert _fn_owned_lines(covered), "a body with statements must own lines"


@pytest.mark.parametrize(
    "raw",
    [["1", "2"], [None], [{"line": 1}], "12", {"1": 2}, 7, None],
    ids=["strings", "nulls", "objects", "str", "dict", "int", "absent"],
)
def test_malformed_line_arrays_degrade_rather_than_read_as_empty(raw: object) -> None:
    """Anything that is not a usable list of line numbers must degrade to None.

    Reading a malformed array as an empty set would claim the file has no
    statements, scoring every function in it as fully covered. `None` is the
    signal that routes the file to the documented file-level fallback.
    """
    lines = _line_set(raw)
    assert lines is None


def test_empty_line_array_is_empty_not_degraded() -> None:
    """`[]` is a legitimate answer and must stay distinct from malformed input.

    A file with no executed lines reports `executed_lines: []`. Collapsing that
    to None would route a genuinely-measured file into the degraded fallback.
    """
    lines = _line_set([])
    assert lines == frozenset()


def test_boolean_line_numbers_are_not_treated_as_lines() -> None:
    """`isinstance(True, int)` is True, so booleans would masquerade as line 1."""
    booleans_only = _line_set([True, False])
    assert booleans_only is None

    mixed = _line_set([1, True, 2])
    assert mixed == frozenset({1, 2})


def test_unmatched_file_resolves_to_none() -> None:
    """No matching coverage key yields None, so CRAP is null per OC-003."""
    nodes = _fixture_functions()
    node = next(n for n in nodes.values() if n.name == "fully_covered")
    resolved = _resolve_line_coverage(
        Path("some/other/file.py"),
        Path("."),
        {_FIXTURE_KEY: _file_coverage()},
        target=_target_for(node),
    )
    assert resolved is None


# ---------------------------------------------------------------------------
# Detector wiring
# ---------------------------------------------------------------------------


def test_detector_populates_owned_lines_for_every_function() -> None:
    """Targets produced by the real pipeline must carry a known extent.

    Guards the degraded fallback from silently becoming the normal path.
    """
    targets = detect_and_classify(_FIXTURE_SRC, config=GazeConfig(), include_unexported=True)
    assert targets, "fixture should produce targets"
    without_extent = [t.function for t in targets if t.owned_lines is None]
    assert not without_extent, f"targets with no computed extent: {without_extent}"


# ---------------------------------------------------------------------------
# Module extent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x = 1\ny = 2\n", 2),
        # \f, \v and U+2028 are str.splitlines terminators that the Python
        # tokenizer does not treat as line breaks. Deriving the extent from
        # splitlines() would overcount on any of them.
        ("x = '\f'\ny = 2\n", 2),
        ("x = '\v'\ny = 2\n", 2),
        ("x = '\u2028'\ny = 2\n", 2),
        ("x = '\u2029'\ny = 2\n", 2),
        # A multi-line final statement ends at its last line, not its first.
        ("x = 1\ny = (\n    2\n)\n", 4),
    ],
    ids=["plain", "formfeed", "vtab", "u2028", "u2029", "multiline-tail"],
)
def test_module_end_line_uses_the_ast_not_splitlines(source: str, expected: int) -> None:
    """The module extent must come from the AST, not `str.splitlines()`.

    `<module>` targets feed `avg_line_coverage`, so an overcounted extent
    skews a reported project metric even though module CRAP is bounded at 2.0
    and can never flag.
    """
    end = _module_end_line(ast.parse(source))
    assert end == expected


def test_module_target_owns_lines_outside_every_function_body() -> None:
    """The `<module>` sentinel owns module-level code but not function bodies."""
    source = "import os\n\n\ndef f():\n    return os.getcwd()\n\n\nx = f()\n"
    module = ast.parse(source)
    owned = _owned_lines(module, 1, _module_end_line(module))

    assert 1 in owned, "module owns its import"
    assert 4 in owned, "module owns the def statement itself"
    assert 8 in owned, "module owns trailing module-level code"
    assert 5 not in owned, "module must not own the function's body"
