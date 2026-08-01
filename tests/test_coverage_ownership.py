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
import json
from pathlib import Path

import pytest

from gaze_py.analysis.detector import _fn_owned_lines
from gaze_py.cli.main import _FileCoverage, _line_set, _resolve_line_coverage
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


def _fixture_functions() -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Map each fixture function's *definition line* to its AST node.

    Keyed by line so nested functions (which share a simple name space with
    their parents only by qualname) join unambiguously against coverage.py's
    `start_line`.
    """
    tree = ast.parse(_FIXTURE_SRC.read_text(encoding="utf-8"), filename=str(_FIXTURE_SRC))
    return {
        str(node.lineno): node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


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


def _file_coverage() -> _FileCoverage:
    """Build a _FileCoverage from the reference's FILE-level line arrays.

    File-level arrays are what the resolver actually consumes in production —
    per-function attribution is derived from them, not read from coverage.py's
    per-function map. Using them here means these tests exercise the real path.
    """
    entry = _reference()
    return _FileCoverage(
        percent_covered=float(entry["summary"]["percent_covered"]),  # type: ignore[index,call-overload]
        executed_lines=frozenset(entry["executed_lines"]),  # type: ignore[arg-type]
        missing_lines=frozenset(entry["missing_lines"]),  # type: ignore[arg-type]
    )


def _resolve(name: str) -> float | None:
    """Resolve per-function coverage for a fixture function by name."""
    nodes = _fixture_functions()
    node = next(n for n in nodes.values() if n.name == name)
    return _resolve_line_coverage(
        Path(_FIXTURE_KEY),
        Path("."),
        {_FIXTURE_KEY: _file_coverage()},
        _target_for(node),
    )


# ---------------------------------------------------------------------------
# Ownership rules validated against the coverage.py reference
# ---------------------------------------------------------------------------


def test_owned_lines_reproduce_coverage_py_statement_sets() -> None:
    """Computed ownership MUST match coverage.py's own per-function statements.

    This is the acceptance test for both ownership rules. It compares *sets*,
    not counts, so an off-by-one that happens to preserve the total still fails.
    """
    entry = _reference()
    functions = entry["functions"]
    assert isinstance(functions, dict)
    nodes = _fixture_functions()

    checked = 0
    for qualname, fn_entry in functions.items():
        if qualname == "":
            continue  # module scope is not a function target
        node = nodes[str(fn_entry["start_line"])]
        reference_stmts = set(fn_entry["executed_lines"]) | set(fn_entry["missing_lines"])
        owned = _fn_owned_lines(node)
        assert owned & reference_stmts == reference_stmts, (
            f"{qualname}: ownership does not cover coverage.py's statements "
            f"(missing {sorted(reference_stmts - owned)})"
        )
        checked += 1

    assert checked == 8, "fixture should contribute 8 function entries (2 of them nested)"


def test_resolved_coverage_matches_coverage_py_percentages() -> None:
    """Resolving from FILE-level arrays MUST reproduce coverage.py's per-function %.

    This is the end-to-end guard. It is where rule A (excluding the `def` line)
    actually bites: the `def` line appears in the file's executed_lines, so
    owning it would inflate every uncovered function above 0%.
    """
    entry = _reference()
    functions = entry["functions"]
    assert isinstance(functions, dict)
    nodes = _fixture_functions()
    file_cov = _file_coverage()

    for qualname, fn_entry in functions.items():
        if qualname == "":
            continue
        node = nodes[str(fn_entry["start_line"])]
        resolved = _resolve_line_coverage(
            Path(_FIXTURE_KEY),
            Path("."),
            {_FIXTURE_KEY: file_cov},
            _target_for(node),
        )
        expected = float(fn_entry["summary"]["percent_covered"]) / 100.0
        assert resolved == pytest.approx(expected), (
            f"{qualname}: resolved {resolved} but coverage.py reports {expected}"
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


def test_function_does_not_own_its_own_def_or_decorator_lines() -> None:
    """Rule A: the `def` line executes at import, so the function cannot own it."""
    nodes = _fixture_functions()
    for node in nodes.values():
        owned = _fn_owned_lines(node)
        assert node.lineno not in owned, f"{node.name} must not own its def line"


# ---------------------------------------------------------------------------
# Resolution edge cases
# ---------------------------------------------------------------------------


def test_never_called_function_resolves_to_exactly_zero() -> None:
    """A never-invoked function reports 0.0, not a small positive fraction.

    Regression guard for rule A: its `def` line is in the file's executed_lines,
    so owning it would yield a nonzero fraction and understate CRAP.
    """
    assert _resolve("never_called") == 0.0


def test_fully_covered_function_resolves_to_one() -> None:
    """A fully exercised function reports 1.0 even though its file is at 72%."""
    assert _resolve("fully_covered") == 1.0


def test_partially_covered_function_reports_its_own_fraction() -> None:
    """Partial coverage is the function's own ratio, not the file's."""
    assert _resolve("partially_covered") == pytest.approx(2 / 3)


def test_docstring_only_body_resolves_to_full_coverage() -> None:
    """A body with no statements is vacuously complete, as coverage.py reports it."""
    assert _resolve("docstring_only") == 1.0


def test_uncalled_nested_function_does_not_drag_down_its_parent() -> None:
    """The parent is fully covered; only the nested function is uncovered."""
    assert _resolve("has_uncalled_nested") == 1.0
    assert _resolve("unused_inner") == 0.0


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
        _target_for(node),
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
        Path(_FIXTURE_KEY), Path("."), {_FIXTURE_KEY: _file_coverage()}, target
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
        Path(_FIXTURE_KEY), Path("."), {_FIXTURE_KEY: stale}, appended
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
    [["1", "2"], [None], [{"line": 1}]],
    ids=["strings", "nulls", "objects"],
)
def test_malformed_line_arrays_degrade_rather_than_read_as_empty(raw: list[object]) -> None:
    """A non-empty array yielding no line numbers is malformed, not empty.

    Reading it as an empty set would claim the file has no statements, scoring
    every function in it as fully covered.
    """
    assert _line_set(raw) is None


def test_boolean_line_numbers_are_not_treated_as_lines() -> None:
    """`isinstance(True, int)` is True, so booleans would masquerade as line 1."""
    assert _line_set([True, False]) is None
    assert _line_set([1, True, 2]) == frozenset({1, 2})


def test_unmatched_file_resolves_to_none() -> None:
    """No matching coverage key yields None, so CRAP is null per OC-003."""
    nodes = _fixture_functions()
    node = next(n for n in nodes.values() if n.name == "fully_covered")
    resolved = _resolve_line_coverage(
        Path("some/other/file.py"), Path("."), {_FIXTURE_KEY: _file_coverage()}, _target_for(node)
    )
    assert resolved is None


# ---------------------------------------------------------------------------
# Detector wiring
# ---------------------------------------------------------------------------


def test_detector_populates_owned_lines_for_every_function() -> None:
    """Targets produced by the real pipeline must carry a known extent.

    Guards the degraded fallback from silently becoming the normal path.
    """
    from gaze_py.analysis.runner import detect_and_classify
    from gaze_py.config.loader import GazeConfig

    targets = detect_and_classify(_FIXTURE_SRC, config=GazeConfig(), include_unexported=True)
    assert targets, "fixture should produce targets"
    for target in targets:
        assert target.owned_lines is not None, f"{target.function} has no computed extent"
