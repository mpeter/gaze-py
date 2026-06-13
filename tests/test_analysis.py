"""Tests for gaze_py.analysis — AST-based side-effect detection engine.

Each test maps to a spec acceptance scenario (SC-NNN) from
``specs/001-gaze-py-engine/spec.md``.  Tests are written BEFORE the
implementation exists (TDD) and MUST fail with ``ImportError`` until
``src/gaze_py/analysis.py`` is created.

Convention pack compliance:
- TC-001: pytest only, no unittest.TestCase
- TC-002: direct assert statements
- TC-003: descriptive test names matching SC-NNN identifiers
- TC-004: tmp_path for all filesystem tests
- TC-007: acceptance tests named after spec success criteria
- TC-008: assert specific values, not just truthiness
- TC-009: each test is independently runnable
- TC-010: @pytest.mark.slow for performance tests
- TC-012: error paths and edge cases covered
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from gaze_py.analysis import GazeParseError, analyze_module, analyze_path

from gaze_py.taxonomy import SideEffectType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TESTDATA = Path(__file__).parent / "testdata" / "analysis"


def effects_from_file(filename: str, func_name: str) -> list[SideEffectType]:
    """Analyze a fixture file and return effect types for the named function.

    Args:
        filename: Basename of the fixture file inside ``tests/testdata/analysis/``.
        func_name: Name of the function (or ``ClassName.method``) to look up.

    Returns:
        List of ``SideEffectType`` values detected for the named function.
        Returns an empty list if the function is not found in the results.
    """
    source = (TESTDATA / filename).read_text()
    results = analyze_module(source, str(TESTDATA / filename))
    for result in results:
        if result.target.function == func_name:
            return [e.type for e in result.side_effects]
    return []


# ---------------------------------------------------------------------------
# SC-001 — ReturnValue: simple integer return
# ---------------------------------------------------------------------------


def test_sc001_returns_int() -> None:
    """SC-001: returns_int() in returns.py produces exactly one ReturnValue.

    A function that returns a non-None value MUST produce exactly one
    ReturnValue side effect.  No other effect types should be present.
    """
    effects = effects_from_file("returns.py", "returns_int")
    assert effects == [SideEffectType.ReturnValue], (
        f"Expected [ReturnValue], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-002 — ReturnValue: tuple return is still one ReturnValue
# ---------------------------------------------------------------------------


def test_sc002_returns_tuple() -> None:
    """SC-002: returns_tuple() in returns.py produces exactly one ReturnValue.

    A tuple return is a single return statement and MUST produce exactly
    one ReturnValue side effect — not one per element.
    """
    effects = effects_from_file("returns.py", "returns_tuple")
    assert effects == [SideEffectType.ReturnValue], (
        f"Expected [ReturnValue], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-003 — ErrorReturn: unconditional raise
# ---------------------------------------------------------------------------


def test_sc003_raises_value_error() -> None:
    """SC-003: raises_value_error() in raises.py produces exactly one ErrorReturn.

    An unconditional ``raise`` statement MUST produce exactly one
    ErrorReturn side effect.
    """
    effects = effects_from_file("raises.py", "raises_value_error")
    assert effects == [SideEffectType.ErrorReturn], (
        f"Expected [ErrorReturn], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-004 — GlobalMutation: global keyword + assignment
# ---------------------------------------------------------------------------


def test_sc004_global_mutation() -> None:
    """SC-004: increment_global() in globals.py produces exactly one GlobalMutation.

    A function that uses the ``global`` keyword and mutates a module-level
    variable MUST produce exactly one GlobalMutation side effect.
    """
    effects = effects_from_file("globals.py", "increment_global")
    assert effects == [SideEffectType.GlobalMutation], (
        f"Expected [GlobalMutation], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-005 — PointerArgMutation: dict.update() on a parameter
# ---------------------------------------------------------------------------


def test_sc005_pointer_arg_mutation_update() -> None:
    """SC-005: update_dict() in arg_mutation.py produces exactly one PointerArgMutation.

    Calling ``.update()`` on a dict parameter MUST produce exactly one
    PointerArgMutation side effect.
    """
    effects = effects_from_file("arg_mutation.py", "update_dict")
    assert effects == [SideEffectType.PointerArgMutation], (
        f"Expected [PointerArgMutation], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-006 — ReceiverMutation: self attribute mutation inside a method
# ---------------------------------------------------------------------------


def test_sc006_receiver_mutation() -> None:
    """SC-006: Counter.increment() in receiver_mutation.py produces exactly one ReceiverMutation.

    A method that mutates ``self`` (e.g., ``self.value += 1``) MUST
    produce exactly one ReceiverMutation side effect.  The function name
    in the result MUST be ``increment`` and the receiver MUST be ``Counter``.
    """
    source = (TESTDATA / "receiver_mutation.py").read_text()
    results = analyze_module(source, str(TESTDATA / "receiver_mutation.py"))

    # Find the Counter.increment result by matching both function and receiver
    increment_results = [
        r
        for r in results
        if r.target.function == "increment" and r.target.receiver == "Counter"
    ]
    assert len(increment_results) == 1, (
        f"Expected exactly one result for Counter.increment, got {len(increment_results)}"
    )
    effects = [e.type for e in increment_results[0].side_effects]
    assert effects == [SideEffectType.ReceiverMutation], (
        f"Expected [ReceiverMutation], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-007 — StdoutWrite: print() call
# ---------------------------------------------------------------------------


def test_sc007_stdout_write() -> None:
    """SC-007: prints_hello() in stdout.py produces exactly one StdoutWrite.

    A call to the built-in ``print()`` function MUST produce exactly one
    StdoutWrite side effect.
    """
    effects = effects_from_file("stdout.py", "prints_hello")
    assert effects == [SideEffectType.StdoutWrite], (
        f"Expected [StdoutWrite], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-008 — Pure function: no side effects (zero false positives)
# ---------------------------------------------------------------------------


def test_sc008_pure_function_no_effects() -> None:
    """SC-008: no_effects() in pure.py produces an empty side-effects list.

    A function that only uses local variables and returns None MUST NOT
    produce any side effects.  This is the zero-false-positive gate.
    """
    effects = effects_from_file("pure.py", "no_effects")
    assert effects == [], (
        f"Expected no side effects for pure function, got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-009 — StderrWrite: sys.stderr.write()
# ---------------------------------------------------------------------------


def test_sc009_stderr_write() -> None:
    """SC-009: writes_stderr() in stderr.py produces exactly one StderrWrite.

    A call to ``sys.stderr.write()`` MUST produce exactly one StderrWrite
    side effect.
    """
    effects = effects_from_file("stderr.py", "writes_stderr")
    assert effects == [SideEffectType.StderrWrite], (
        f"Expected [StderrWrite], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-010 — EnvVarMutation: os.environ[key] = val (subscript form)
# ---------------------------------------------------------------------------


def test_sc010_env_mutation_subscript() -> None:
    """SC-010: set_env_subscript() in env_mutation.py produces exactly one EnvVarMutation.

    Subscript assignment to ``os.environ`` (``os.environ[key] = val``)
    MUST produce exactly one EnvVarMutation side effect.
    """
    effects = effects_from_file("env_mutation.py", "set_env_subscript")
    assert effects == [SideEffectType.EnvVarMutation], (
        f"Expected [EnvVarMutation], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-011 — EnvVarMutation: os.environ.update() (call form)
# ---------------------------------------------------------------------------


def test_sc011_env_mutation_call_form() -> None:
    """SC-011: set_env_update() in env_mutation.py produces exactly one EnvVarMutation.

    Calling ``os.environ.update(data)`` MUST produce exactly one
    EnvVarMutation side effect — the same type as the subscript form.
    """
    effects = effects_from_file("env_mutation.py", "set_env_update")
    assert effects == [SideEffectType.EnvVarMutation], (
        f"Expected [EnvVarMutation], got {effects}"
    )


# ---------------------------------------------------------------------------
# SC-012 — GazeParseError raised on invalid Python source
# ---------------------------------------------------------------------------


def test_sc012_syntax_error_raises_parse_error() -> None:
    """SC-012: analyze_module() raises GazeParseError for syntactically invalid source.

    When the source cannot be parsed by the Python AST module,
    ``analyze_module()`` MUST raise ``GazeParseError`` (not a bare
    ``SyntaxError`` or any other unhandled exception).
    """
    source = (TESTDATA / "syntax_error.py").read_text()
    with pytest.raises(GazeParseError):
        analyze_module(source, str(TESTDATA / "syntax_error.py"))


# ---------------------------------------------------------------------------
# SC-013 — Deduplication: two return statements → one ReturnValue
# ---------------------------------------------------------------------------


def test_sc013_multi_return_deduplicated() -> None:
    """SC-013: two_returns() in multi_return.py produces exactly ONE ReturnValue.

    A function with multiple ``return`` statements MUST produce exactly
    one ReturnValue side effect — not one per return statement.
    Deduplication by effect type is required.
    """
    effects = effects_from_file("multi_return.py", "two_returns")
    assert effects.count(SideEffectType.ReturnValue) == 1, (
        f"Expected exactly one ReturnValue (deduplicated), got {effects}"
    )
    assert len(effects) == 1, (
        f"Expected exactly one total effect, got {len(effects)}: {effects}"
    )


# ---------------------------------------------------------------------------
# Unit tests for analyze_path()
# ---------------------------------------------------------------------------


def test_analyze_path_traversal_raises_error(tmp_path: Path) -> None:
    """analyze_path() raises an error when the path escapes the project root.

    Security requirement (SC-003, SC-004 from python.md convention pack):
    ``analyze_path()`` MUST validate that the resolved target path does
    not escape the declared project root via ``..`` traversal.

    The function MUST raise ``GazeParseError``, ``ValueError``, or
    ``PermissionError`` — not silently analyse an out-of-bounds path.
    """
    # Construct a path that attempts to escape the tmp_path root
    escape_path = tmp_path / ".." / ".." / "etc"
    with pytest.raises((GazeParseError, ValueError, PermissionError)):
        analyze_path(escape_path, root=tmp_path)


def test_analyze_path_excludes_hidden_and_pycache(tmp_path: Path) -> None:
    """analyze_path() skips hidden directories and __pycache__ during traversal.

    The analysis engine MUST NOT descend into:
    - Directories whose names start with ``.`` (hidden directories)
    - ``__pycache__`` directories

    Only Python files in non-hidden, non-cache directories should be
    included in the results.
    """
    # Create a normal Python file that SHOULD be analysed
    normal_file = tmp_path / "normal.py"
    normal_file.write_text("def f() -> int:\n    return 1\n")

    # Create a hidden directory with a Python file that MUST be skipped
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.py").write_text("def g() -> int:\n    return 2\n")

    # Create a __pycache__ directory with a Python file that MUST be skipped
    pycache_dir = tmp_path / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "cached.py").write_text("def h() -> int:\n    return 3\n")

    results = analyze_path(tmp_path, root=tmp_path)

    # Collect all function names found in results
    found_functions = {r.target.function for r in results}

    # Only ``f`` from normal.py should appear
    assert "f" in found_functions, (
        "Expected function 'f' from normal.py to be in results"
    )
    assert "g" not in found_functions, (
        "Function 'g' from .hidden/secret.py MUST be excluded"
    )
    assert "h" not in found_functions, (
        "Function 'h' from __pycache__/cached.py MUST be excluded"
    )


# ---------------------------------------------------------------------------
# Performance benchmark
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_performance_50_functions() -> None:
    """analyze_module() on 50 functions completes in under 2 seconds.

    The analysis engine MUST process a module containing 50 functions
    within 2 seconds wall-clock time.  This guards against O(n²) or
    worse complexity in the AST visitor.
    """
    source = (TESTDATA / "large_module.py").read_text()
    start = time.perf_counter_ns()
    results = analyze_module(source, str(TESTDATA / "large_module.py"))
    elapsed_s = (time.perf_counter_ns() - start) / 1e9
    assert elapsed_s < 2.0, f"analyze_module took {elapsed_s:.2f}s, expected < 2s"
    assert len(results) == 50, (
        f"Expected 50 results (one per function), got {len(results)}"
    )
