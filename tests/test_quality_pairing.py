"""Tests for quality/pairing.py — A.1 test-target pairing."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import astroid
import pytest

from gaze_py.quality.models import TestFunc

# CR-004: testing _extract_call_name directly because pair_to_targets() requires a
# full source_functions list and a TestFunc; the method/qualified-name distinction
# is cleaner to assert at the unit level without constructing elaborate fixtures.
from gaze_py.quality.pairing import (
    _build_astroid_graph,
    _extract_call_name,
    _find_project_root,
    _pair_astroid,
    find_test_functions,
    pair_to_targets,
)
from gaze_py.taxonomy.models import FunctionTarget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_func(src: str, name: str = "test_foo") -> TestFunc:
    """Parse src and return a TestFunc for the named function."""
    module = ast.parse(textwrap.dedent(src))
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return TestFunc(name=name, filename="test_example.py", lineno=node.lineno, node=node)
    raise ValueError(f"Function {name!r} not found in source")


def _make_target(name: str) -> FunctionTarget:
    """Create a minimal FunctionTarget with the given name."""
    return FunctionTarget(
        function=name,
        file_path="src/example.py",
        line=1,
        complexity=1,
        package="src/example.py",
        receiver=None,
        signature=f"def {name}()",
    )


# ---------------------------------------------------------------------------
# pair_to_targets tests
# ---------------------------------------------------------------------------


def test_pair_empty_source_functions() -> None:
    """Empty source_functions → unmatched immediately."""
    tf = _make_test_func("def test_foo() -> None: pass")
    result = pair_to_targets(tf, [])
    assert result.target_name is None
    assert result.inference_method == "unmatched"
    assert result.confidence == 0.0


def test_pair_name_convention_exact() -> None:
    """test_foo → foo → confidence 0.9 exact match."""
    tf = _make_test_func("def test_foo() -> None: pass")
    targets = [_make_target("foo"), _make_target("bar")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "foo"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.9


def test_pair_name_convention_case_insensitive() -> None:
    """test_foo → Foo (case-insensitive) → confidence 0.7."""
    tf = _make_test_func("def test_foo() -> None: pass")
    targets = [_make_target("Foo")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "Foo"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.7


def test_pair_call_graph_no_name_match() -> None:
    """No name match but call to source function found → confidence 0.8."""
    src = """
    def test_something() -> None:
        result = process_data(1, 2)
        assert result == 3
    """
    tf = _make_test_func(src, "test_something")
    targets = [_make_target("process_data"), _make_target("other_fn")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "process_data"
    assert result.inference_method == "call_graph"
    assert result.confidence == 0.8


def test_pair_unmatched() -> None:
    """No name match and no call found → None target."""
    tf = _make_test_func("def test_xyz() -> None: pass", "test_xyz")
    targets = [_make_target("alpha"), _make_target("beta")]
    result = pair_to_targets(tf, targets)
    assert result.target_name is None
    assert result.inference_method == "unmatched"
    assert result.confidence == 0.0


def test_pair_class_method() -> None:
    """Method of a Test* class is paired correctly."""
    src = """
    class TestMyClass:
        def test_process(self) -> None:
            process(1)
    """
    module = ast.parse(textwrap.dedent(src))
    class_node = module.body[0]
    assert isinstance(class_node, ast.ClassDef)
    method_node = class_node.body[0]
    assert isinstance(method_node, ast.FunctionDef)
    tf = TestFunc(
        name="test_process",
        filename="test_myclass.py",
        lineno=method_node.lineno,
        node=method_node,
    )
    targets = [_make_target("process")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "process"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.9


def test_pair_underscore_name() -> None:
    """test_process_items → process_items (exact match with underscores)."""
    tf = _make_test_func("def test_process_items() -> None: pass", "test_process_items")
    targets = [_make_target("process_items")]
    result = pair_to_targets(tf, targets)
    assert result.target_name == "process_items"
    assert result.inference_method == "name_convention"
    assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# find_test_functions tests
# ---------------------------------------------------------------------------


def test_find_test_functions(tmp_path: Path) -> None:
    """Returns only test_* prefixed functions, not helpers."""
    src = textwrap.dedent("""
    def test_alpha() -> None:
        pass

    def helper_setup() -> None:
        pass

    def test_beta() -> None:
        pass

    class TestSuite:
        def test_gamma(self) -> None:
            pass

        def setup_method(self) -> None:
            pass
    """)
    test_file = tmp_path / "test_example.py"
    test_file.write_text(src)
    results = find_test_functions(test_file)
    assert isinstance(results, list)
    names = [tf.name for tf in results]
    assert "test_alpha" in names
    assert "test_beta" in names
    assert "test_gamma" in names
    assert "helper_setup" not in names
    assert "setup_method" not in names


def test_find_test_functions_empty_file(tmp_path: Path) -> None:
    """Empty file returns empty list."""
    test_file = tmp_path / "test_empty.py"
    test_file.write_text("")
    assert find_test_functions(test_file) == []


def test_find_test_functions_nonexistent(tmp_path: Path) -> None:
    """Non-existent file returns empty list (graceful degradation)."""
    assert find_test_functions(tmp_path / "missing.py") == []


# ---------------------------------------------------------------------------
# _extract_call_name tests
# ---------------------------------------------------------------------------


def test_extract_call_name_simple() -> None:
    """Simple name call → returns the name."""
    stmt = ast.parse("foo()").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    assert _extract_call_name(stmt.value) == "foo"


def test_extract_call_name_method() -> None:
    """Method call → returns None."""
    stmt = ast.parse("obj.method()").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    assert _extract_call_name(stmt.value) is None


def test_extract_call_name_qualified() -> None:
    """Qualified name call → returns None."""
    stmt = ast.parse("mod.fn()").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    assert _extract_call_name(stmt.value) is None


# ---------------------------------------------------------------------------
# Strategy 3 — Astroid transitive call graph (_pair_astroid / pair_to_targets)
# ---------------------------------------------------------------------------
# TC-013: _pair_astroid and _build_astroid_graph are tested directly because
# pair_to_targets() cannot exercise FQN alignment, depth-limit behaviour, or
# cache-clear semantics without prohibitive fixture complexity.
# ---------------------------------------------------------------------------


def _make_tf_with_fqn(name: str, fqn_prefix: str, tmp_path: Path) -> TestFunc:
    """Create a TestFunc whose D8 FQN resolves to ``fqn_prefix.name``.

    Places a pyproject.toml marker at ``tmp_path`` so ``_find_project_root``
    stops there. The test file is placed at ``tmp_path/tests/<module>.py``
    where ``<module>`` is the last segment of ``fqn_prefix``.

    Args:
        name: Test function name (e.g. "test_engine_integration").
        fqn_prefix: Dotted module path without the function name
            (e.g. "test_mod" → FQN becomes "test_mod.test_engine_integration").
        tmp_path: Pytest tmp_path fixture — used as the project root.

    Returns:
        A TestFunc whose filename produces the expected FQN via D8.
    """
    # Place the project-root marker so _find_project_root stops at tmp_path.
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    # The module name is the last segment of fqn_prefix.
    module_name = fqn_prefix.rsplit(".", 1)[-1]
    test_dir = tmp_path / "tests"
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / f"{module_name}.py"
    src = f"def {name}() -> None: pass\n"
    test_file.write_text(src, encoding="utf-8")

    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return TestFunc(name=name, filename=str(test_file), lineno=1, node=node)


def test_pair_astroid_resolves_method_call(tmp_path: Path) -> None:
    """_pair_astroid resolves a direct method-call edge in a hand-built graph.

    Strategy 2 (ast.Name walk) cannot match method calls; Strategy 3 must.
    The graph has one hop: test FQN → Engine.classify.
    """
    graph: dict[str, set[str]] = {
        "test_mod.test_engine_integration": {"src_mod.Engine.classify"},
        "src_mod.Engine.classify": set(),
    }
    tf = _make_tf_with_fqn("test_engine_integration", "test_mod", tmp_path)

    # Direct _pair_astroid call: should return the short name "classify".
    result = _pair_astroid(tf, {"classify"}, graph)
    assert result == "classify"

    # pair_to_targets integration: inference_method and confidence.
    source_funcs = [_make_target("classify"), _make_target("Engine")]
    pair = pair_to_targets(tf, source_funcs, astroid_graph=graph)
    assert pair.inference_method == "call_graph_transitive"
    assert pair.confidence == 0.75
    assert pair.target_name == "classify"


def test_pair_astroid_transitive_reaches_caller_signal(tmp_path: Path) -> None:
    """_pair_astroid follows a 3-hop chain to reach caller_signal.

    test_foo → _make_engine → Engine.classify → caller_signal.
    """
    graph: dict[str, set[str]] = {
        "test_mod.test_foo": {"src_mod._make_engine"},
        "src_mod._make_engine": {"src_mod.Engine.classify"},
        "src_mod.Engine.classify": {"src_mod.caller_signal"},
    }
    tf = _make_tf_with_fqn("test_foo", "test_mod", tmp_path)

    result = _pair_astroid(tf, {"caller_signal"}, graph)
    assert result == "caller_signal"


def test_pair_astroid_depth_limit(tmp_path: Path) -> None:
    """_pair_astroid does not return a function beyond the depth limit.

    A 6-hop chain with depth_limit=5 must NOT return the function at hop 6.
    """
    # Build a linear chain: start → hop1 → hop2 → hop3 → hop4 → hop5 → hop6_target
    graph: dict[str, set[str]] = {
        "test_mod.test_deep": {"mod.hop1"},
        "mod.hop1": {"mod.hop2"},
        "mod.hop2": {"mod.hop3"},
        "mod.hop3": {"mod.hop4"},
        "mod.hop4": {"mod.hop5"},
        "mod.hop5": {"mod.hop6_target"},
    }
    tf = _make_tf_with_fqn("test_deep", "test_mod", tmp_path)

    # hop6_target is at depth 6 from start; depth_limit=5 must exclude it.
    result = _pair_astroid(tf, {"hop6_target"}, graph, depth_limit=5)
    assert result is None

    # Sanity: with depth_limit=6 it IS reachable.
    result_deep = _pair_astroid(tf, {"hop6_target"}, graph, depth_limit=6)
    assert result_deep == "hop6_target"


def test_pair_astroid_empty_graph_falls_through_to_unmatched(tmp_path: Path) -> None:
    """Empty astroid_graph with no name/call match → unmatched pair.

    Strategy 3 fires but finds nothing; falls through to unmatched (Strategy 4).
    """
    tf = _make_tf_with_fqn("test_nothing", "test_mod", tmp_path)
    source_funcs = [_make_target("alpha"), _make_target("beta")]

    pair = pair_to_targets(tf, source_funcs, astroid_graph={})
    assert pair.inference_method == "unmatched"
    assert pair.confidence == 0.0
    assert pair.target_name is None


def test_pair_astroid_confidence_and_method(tmp_path: Path) -> None:
    """Strategy 3 match → inference_method=="call_graph_transitive", confidence==0.75."""
    graph: dict[str, set[str]] = {
        "test_mod.test_score": {"src_mod.compute_score"},
    }
    tf = _make_tf_with_fqn("test_score", "test_mod", tmp_path)
    source_funcs = [_make_target("compute_score")]

    pair = pair_to_targets(tf, source_funcs, astroid_graph=graph)
    assert pair.inference_method == "call_graph_transitive"
    assert pair.confidence == 0.75
    assert pair.target_name == "compute_score"


def test_build_astroid_graph_skips_bad_file() -> None:
    """Non-existent file is skipped; valid files still produce a non-empty graph.

    _build_astroid_graph must not raise when a path does not exist (D4).
    """
    engine_fixture = (
        Path(__file__).parent / "testdata" / "quality" / "astroid" / "src" / "engine.py"
    )
    bad_path = Path("/nonexistent/path/to/missing_file.py")

    result = _build_astroid_graph([bad_path], [engine_fixture])
    # Valid file was loaded — graph is non-empty.
    assert len(result) > 0


def test_build_astroid_graph_rereads_changed_file(tmp_path: Path) -> None:
    """D2: a file whose content changed between builds is re-read, not cached.

    The full MANAGER.clear_cache() was replaced with targeted eviction of the
    analyzed files (audit P3) — this test pins the staleness contract the
    old call provided: same path, new content, fresh graph.
    """
    mod = tmp_path / "mymod.py"
    mod.write_text("def helper():\n    return 1\n\ndef old_caller():\n    return helper()\n")
    graph1 = _build_astroid_graph([], [mod])
    assert any("old_caller" in caller for caller in graph1), graph1

    mod.write_text("def helper():\n    return 1\n\ndef new_caller():\n    return helper()\n")
    graph2 = _build_astroid_graph([], [mod])
    assert any("new_caller" in caller for caller in graph2), graph2
    assert not any("old_caller" in caller for caller in graph2), graph2


def test_build_astroid_graph_same_name_different_path_not_stale(tmp_path: Path) -> None:
    """D2: a same-named module at a different path does not hit a stale entry.

    astroid keys its cache by module name; two tmp fixtures both named
    fixture.py must each see their own content. Eviction matches module
    name as well as file path to guarantee this.
    """
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "fixture.py").write_text(
        "def alpha_helper():\n    return 1\n\ndef alpha():\n    return alpha_helper()\n"
    )
    (dir_b / "fixture.py").write_text(
        "def beta_helper():\n    return 1\n\ndef beta():\n    return beta_helper()\n"
    )

    graph_a = _build_astroid_graph([], [dir_a / "fixture.py"])
    graph_b = _build_astroid_graph([], [dir_b / "fixture.py"])

    assert any("alpha" in caller for caller in graph_a), graph_a
    assert any("beta" in caller for caller in graph_b), graph_b
    assert not any("alpha" in caller for caller in graph_b), graph_b


def test_build_astroid_graph_preserves_third_party_cache() -> None:
    """P3: building the graph does not evict astroid's builtins cache.

    The old clear_cache() evicted bootstrap modules, forcing a multi-second
    rebuild of builtin inference state on every assess() call. Targeted
    eviction must leave non-analyzed entries (e.g. 'builtins') in place.
    """
    engine_fixture = (
        Path(__file__).parent / "testdata" / "quality" / "astroid" / "src" / "engine.py"
    )
    # Ensure builtins is cached (astroid bootstraps it on first use).
    astroid.MANAGER.ast_from_module_name("builtins")
    assert "builtins" in astroid.MANAGER.astroid_cache

    _build_astroid_graph([], [engine_fixture])

    assert "builtins" in astroid.MANAGER.astroid_cache, (
        "builtins was evicted — targeted eviction regressed to a full clear"
    )


# ---------------------------------------------------------------------------
# Phase 6 — _find_project_root and _pair_astroid edge-case tests
# ---------------------------------------------------------------------------


def test_find_project_root_falls_back_to_parent_when_no_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_find_project_root returns start.parent when no project-root markers found.

    # CR-004: Tested directly because pair_to_targets() always finds a project
    # root via the real filesystem; monkeypatching _PROJECT_ROOT_MARKERS to an
    # empty frozenset forces the walk to exhaust all ancestors and exercise the
    # fallback branch without relying on real filesystem state.
    """
    import gaze_py.quality.pairing as pairing_mod

    monkeypatch.setattr(pairing_mod, "_PROJECT_ROOT_MARKERS", frozenset())
    some_file = tmp_path / "test_example.py"
    some_file.write_text("def test_foo(): pass\n")
    result = _find_project_root(some_file)
    assert result == some_file.parent


def test_pair_astroid_matches_package_and_class_qualified_key(tmp_path: Path) -> None:
    """_pair_astroid matches graph keys carrying a package prefix and test class.

    Regression: astroid qnames for a test inside a ``tests`` package (with
    __init__.py) and a Test* class look like
    ``tests.test_mod.TestCase.test_x`` — the previous path-derived FQN
    reconstruction produced ``test_mod.test_x`` and never matched, so
    Strategy 3 silently paired nothing for class-based tests.
    """
    graph: dict[str, set[str]] = {
        "tests.test_mod.TestParser.test_parses_value": {"pkg.parser.parse_value"},
    }
    test_file = tmp_path / "test_mod.py"
    src = "class TestParser:\n    def test_parses_value(self) -> None: pass\n"
    test_file.write_text(src, encoding="utf-8")
    test_funcs = find_test_functions(test_file)
    assert test_funcs

    result = _pair_astroid(test_funcs[0], {"parse_value"}, graph)
    assert result == "parse_value"


def test_pair_astroid_ignores_same_name_in_other_module(tmp_path: Path) -> None:
    """A graph key with the same test name but a different module stem must not match.

    Guards the stem-component requirement in start-key matching: without it,
    ``test_setup`` in an unrelated module would seed the BFS and produce a
    false pairing.
    """
    graph: dict[str, set[str]] = {
        "tests.test_other.test_setup": {"pkg.other.other_target"},
    }
    test_file = tmp_path / "test_mod.py"
    test_file.write_text("def test_setup() -> None: pass\n", encoding="utf-8")
    test_funcs = find_test_functions(test_file)
    assert test_funcs

    result = _pair_astroid(test_funcs[0], {"other_target"}, graph)
    assert result is None


def test_build_astroid_graph_resolves_imports_without_project_on_sys_path(
    tmp_path: Path,
) -> None:
    """Cross-file import edges are inferred even when the project is not importable.

    Regression: astroid resolves ``from pkg.mod import fn`` via sys.path.
    Running gaze-py as a console script against another repo leaves that
    repo's root off sys.path, so every cross-file inference failed and
    Strategy 3 produced zero test→source edges. _build_astroid_graph must
    temporarily add the analyzed project's root (D8 markers) to sys.path —
    and remove it again afterwards.
    """
    import sys as _sys

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    src_file = pkg / "mod.py"
    src_file.write_text("def target_fn() -> int:\n    return 1\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    test_file = tests_dir / "test_mod.py"
    test_file.write_text(
        "from pkg.mod import target_fn\n\n"
        "def test_target_behaviour() -> None:\n"
        "    assert target_fn() == 1\n",
        encoding="utf-8",
    )

    assert str(tmp_path) not in _sys.path
    path_before = list(_sys.path)

    graph = _build_astroid_graph([test_file], [src_file])

    # The temporary root must be gone again.
    assert _sys.path == path_before

    # The cross-file edge must exist: some test-side key calls pkg.mod.target_fn.
    callees = {c for edges in graph.values() for c in edges}
    assert "pkg.mod.target_fn" in callees

    # And Strategy 3 end-to-end pairs the test to the target.
    test_funcs = find_test_functions(test_file)
    result = _pair_astroid(test_funcs[0], {"target_fn"}, graph)
    assert result == "target_fn"


def test_import_root_flat_src_and_standalone_layouts(tmp_path: Path) -> None:
    """_import_root returns the directory Python needs on sys.path per layout."""
    from gaze_py.quality.pairing import _import_root

    # flat layout: root/mypkg/mod.py → root
    flat = tmp_path / "flat"
    (flat / "mypkg").mkdir(parents=True)
    (flat / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (flat / "mypkg" / "mod.py").write_text("", encoding="utf-8")
    assert _import_root(flat / "mypkg" / "mod.py") == flat

    # src layout: root/src/mypkg/mod.py → root/src
    srcl = tmp_path / "srcl"
    (srcl / "src" / "mypkg").mkdir(parents=True)
    (srcl / "src" / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (srcl / "src" / "mypkg" / "mod.py").write_text("", encoding="utf-8")
    assert _import_root(srcl / "src" / "mypkg" / "mod.py") == srcl / "src"

    # standalone module (no __init__.py anywhere) → containing dir
    (tmp_path / "script.py").write_text("", encoding="utf-8")
    assert _import_root(tmp_path / "script.py") == tmp_path


def test_build_astroid_graph_resolves_imports_in_src_layout(tmp_path: Path) -> None:
    """Cross-file edges are inferred for src-layout projects.

    Regression: the previous sys.path bootstrap used the marker-based
    project root (pyproject.toml), but ``from mypkg import x`` in a
    src-layout project resolves from ``root/src`` — so inference failed
    and Strategy 3 paired nothing for src-layout repos.
    """
    import sys as _sys

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    src_file = pkg / "mod.py"
    src_file.write_text("def target_fn() -> int:\n    return 1\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    test_file = tests_dir / "test_mod.py"
    test_file.write_text(
        "from mypkg.mod import target_fn\n\n"
        "def test_target_behaviour() -> None:\n"
        "    assert target_fn() == 1\n",
        encoding="utf-8",
    )

    path_before = list(_sys.path)
    graph = _build_astroid_graph([test_file], [src_file])
    assert _sys.path == path_before

    callees = {c for edges in graph.values() for c in edges}
    assert "mypkg.mod.target_fn" in callees

    test_funcs = find_test_functions(test_file)
    assert _pair_astroid(test_funcs[0], {"target_fn"}, graph) == "target_fn"
