"""A.1 — Test-target pairing for the O1 quality assessment pipeline.

Discovers test functions in a source file and pairs each one with its most
likely production target using four strategies in priority order:
1. Name convention (test_foo → foo), confidence 0.9 exact / 0.7 case-insensitive.
2. Call graph (deep AST walk for calls to source functions), confidence 0.8.
3. Transitive call graph via Astroid inference, confidence 0.75.
4. Unmatched (no match found), confidence 0.0.
"""

from __future__ import annotations

import ast
import collections
import contextlib
import sys
from collections.abc import Callable
from pathlib import Path

import astroid
import astroid.exceptions
import astroid.util
from astroid import MANAGER

from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.models import FunctionTarget, TestTargetPair

# Marker files used to locate the project root when computing FQNs (D8).
_PROJECT_ROOT_MARKERS: frozenset[str] = frozenset({"pyproject.toml", "setup.py"})


def find_test_functions(filepath: Path) -> list[TestFunc]:
    """Parse a Python file and return all test functions found.

    Collects:
    - Top-level FunctionDef nodes whose name starts with "test_".
    - Methods of classes named "Test*" whose name starts with "test_".

    Args:
        filepath: Path to the Python test file to parse.

    Returns:
        List of TestFunc objects, one per discovered test function.
        Returns an empty list when the file cannot be parsed.
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        module = ast.parse(source, filename=str(filepath))
    except (OSError, SyntaxError, ValueError):
        return []

    results: list[TestFunc] = []
    filename = str(filepath)

    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            results.append(
                TestFunc(
                    name=node.name,
                    filename=filename,
                    lineno=node.lineno,
                    node=node,
                )
            )
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    results.append(
                        TestFunc(
                            name=item.name,
                            filename=filename,
                            lineno=item.lineno,
                            node=item,
                        )
                    )

    return results


def _extract_call_name(node: ast.Call) -> str | None:
    """Extract the function name from a Call node.

    Handles both simple name calls (``foo(...)``) and attribute calls
    (``mod.fn()``, ``obj.method()``).  For attribute calls the attribute
    name is returned — e.g., ``dq.parse_drafts()`` yields ``"parse_drafts"``.

    Args:
        node: The ast.Call node to inspect.

    Returns:
        The function name string, or None for unsupported call shapes
        (e.g., subscript calls like ``funcs[0](...)``).
    """
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _evict_analyzed_from_cache(files: list[Path]) -> None:
    """Evict MANAGER cache entries belonging to the given analyzed files.

    An entry is evicted when its source file is one of the analyzed paths,
    or when its module name's last component matches an analyzed file's stem
    (astroid keys its cache by module name, so a same-named fixture at a
    different path would otherwise hit a stale entry). Over-eviction of an
    unrelated same-named module is safe — it is simply re-parsed on demand.

    Args:
        files: The files about to be analyzed in this build.
    """
    analyzed_paths = {str(p.resolve()) for p in files}
    analyzed_stems = {p.stem for p in files}
    for name, mod in list(MANAGER.astroid_cache.items()):
        mod_file = getattr(mod, "file", None)
        if mod_file in analyzed_paths or name.rsplit(".", 1)[-1] in analyzed_stems:
            del MANAGER.astroid_cache[name]


def _build_astroid_graph(
    test_files: list[Path],
    src_files: list[Path],
) -> dict[str, set[str]]:
    """Build a caller→callees adjacency dict using Astroid type inference.

    Loads each file once via Astroid's MANAGER, walks all FunctionDef nodes,
    and infers the fully-qualified names of every callee. Returns a plain dict
    mapping caller FQN to the set of callee FQNs reachable from that function.

    Staleness control (D2): before each build, cached MANAGER entries for the
    analyzed files are evicted — matched by resolved file path AND by module
    name, so a re-used module name at a different path (two tmp fixtures both
    named ``fixture.py``) cannot serve stale content. Entries for everything
    else — builtins, stdlib, site-packages — are deliberately retained: the
    previous ``MANAGER.clear_cache()`` evicted astroid's bootstrap modules
    too, forcing a multi-second rebuild of builtin inference state on every
    invocation (audit P3, docs/audit-2026-07-12.md). Third-party modules do
    not change mid-process; the analyzed files are the only staleness risk.

    Import resolution: astroid resolves cross-file imports (a test file's
    ``from mypkg.mod import fn``) via ``sys.path``. When gaze-py runs as a
    console script against another project, that project's import roots are
    NOT on ``sys.path``, so every cross-file inference fails and the graph
    contains no test→source edges — Strategy 3 silently pairs nothing. To
    make the build cwd- and entry-point-independent, each analyzed file's
    package import root — the first ancestor directory WITHOUT an
    ``__init__.py`` (see ``_import_root``) — is prepended to ``sys.path``
    for the duration of the build and removed afterwards. Marker-based
    project roots (pyproject.toml/setup.py, D8) are wrong for src-layout
    projects: ``from mypkg import x`` resolves from ``root/src``, not
    ``root``, so the package-boundary walk is used instead.

    Files that Astroid cannot load (encoding errors, unresolvable imports,
    syntax errors) are skipped with a stderr warning; the graph is partial
    but no exception is raised (D4).

    Args:
        test_files: Paths to test source files to include in the graph.
        src_files: Paths to production source files to include in the graph.

    Returns:
        Adjacency dict mapping caller FQN (str) to set of callee FQNs (set[str]).
        Empty dict when no files could be loaded.
    """
    # Deduplicate while preserving insertion order (test_files first so test
    # FQNs are available as graph keys before src FQNs are added as callees).
    unique_files: list[Path] = list(dict.fromkeys(test_files + src_files))

    # D2: evict cached entries for the analyzed files only (see docstring).
    _evict_analyzed_from_cache(unique_files)

    # Make analyzed projects importable so astroid can resolve their
    # cross-file imports (see docstring). Only roots not already present
    # are added, and they are removed in the finally block.
    roots = {str(_import_root(p.resolve())) for p in unique_files}
    added_roots = [r for r in roots if r not in sys.path]
    sys.path[:0] = added_roots

    graph: collections.defaultdict[str, set[str]] = collections.defaultdict(set)

    try:
        for path in unique_files:
            try:
                module = MANAGER.ast_from_file(str(path))
            except astroid.exceptions.AstroidBuildingError as exc:
                sys.stderr.write(f"warning: astroid could not load {path}: {exc}\n")
                continue

            for fn in module.nodes_of_class(astroid.nodes.FunctionDef):
                caller_qname = fn.qname()
                for call in fn.nodes_of_class(astroid.nodes.Call):
                    try:
                        for inferred in call.func.infer():
                            if inferred is astroid.util.Uninferable:
                                continue
                            callee_qname = inferred.qname()
                            graph[caller_qname].add(callee_qname)
                    except astroid.exceptions.InferenceError:
                        continue
    finally:
        for r in added_roots:
            with contextlib.suppress(ValueError):
                sys.path.remove(r)

    return dict(graph)


def _import_root(file_path: Path) -> Path:
    """Return the directory that must be on sys.path to import file_path.

    Walks up from the file's directory while ``__init__.py`` is present:
    the first ancestor WITHOUT one is the package import root — the exact
    directory Python (and astroid) needs on ``sys.path`` for the file's
    dotted module name to resolve. Handles all layouts uniformly:

    - flat layout (``root/mypkg/mod.py``) → root
    - src layout (``root/src/mypkg/mod.py``) → root/src
    - standalone module (``root/script.py``, no __init__.py) → root
    - tests package (``root/tests/__init__.py``) → root

    Args:
        file_path: Resolved path to a Python source file.

    Returns:
        The import-root directory for the file.
    """
    current = file_path.parent
    while (current / "__init__.py").exists():
        parent = current.parent
        if parent == current:  # filesystem root — cannot walk further
            break
        current = parent
    return current


def _find_project_root(start: Path) -> Path:
    """Walk up from start to find the project root directory.

    The project root is the first ancestor directory that contains
    ``pyproject.toml`` or ``setup.py``. Falls back to the parent of
    ``start`` when no marker is found (D8).

    Args:
        start: Starting path (typically the test file's parent directory).

    Returns:
        The project root Path.
    """
    current = start if start.is_dir() else start.parent
    for candidate in [current, *current.parents]:
        if any((candidate / marker).exists() for marker in _PROJECT_ROOT_MARKERS):
            return candidate
    # Fallback: parent of the starting file (D8).
    return start.parent if start.is_file() else start


def _pair_astroid(
    test_func: TestFunc,
    source_names: set[str],
    graph: dict[str, set[str]],
    *,
    depth_limit: int = 5,
) -> str | None:
    """Pair a test function to a source function via transitive call graph BFS.

    Locates the test function's entry in the Astroid call graph by matching
    graph keys instead of reconstructing the FQN from the file path: a key
    matches when its last component equals the test's name and the test
    file's stem appears among its components. Astroid qnames keep the full
    package path (``tests.test_mod``) and include the enclosing test class
    (``tests.test_mod.TestCase.test_x``) — the previous path-derived
    reconstruction (``test_mod.test_x``) missed both, so Strategy 3 never
    fired for class-based tests or tests inside a ``tests`` package.

    From the matched key(s), performs a BFS over the call graph up to
    ``depth_limit`` hops. At each callee FQN, the short name (last segment
    after the final ``.``) is checked against ``source_names``. The first
    matching short name is returned; start keys are scanned in sorted order
    for determinism.

    Uses ``graph.get(fqn, set())`` at every lookup — a callee that was never
    itself a caller has no key in the adjacency dict; ``graph[fqn]`` would
    raise KeyError (CRITICAL: see implementer notes in tasks.md).

    Args:
        test_func: The test function to pair.
        source_names: Short names of all production functions available for
            pairing (e.g. ``{"classify", "caller_signal"}``).
        graph: Caller→callees adjacency dict from ``_build_astroid_graph()``.
        depth_limit: Maximum BFS hops from the test function FQN. Default 5.

    Returns:
        The short name of the first matching source function, or None.
    """
    # Match the test's graph key(s) directly: last component == test name,
    # and the test file's stem appears among the key's components. This is
    # robust to package prefixes and enclosing test classes, neither of
    # which TestFunc knows about.
    stem = Path(test_func.filename).stem
    start_keys = sorted(
        key for key in graph if key.rsplit(".", 1)[-1] == test_func.name and stem in key.split(".")
    )
    if not start_keys:
        return None

    # BFS over the call graph, tracking (node_fqn, depth) pairs.
    queue: collections.deque[tuple[str, int]] = collections.deque((key, 0) for key in start_keys)
    visited: set[str] = set(start_keys)

    while queue:
        fqn, depth = queue.popleft()

        # CRITICAL: use .get() — callees that were never callers have no key.
        for callee_fqn in graph.get(fqn, set()):
            if callee_fqn in visited:
                continue
            visited.add(callee_fqn)

            # Extract short name (last segment after final dot).
            short_name = callee_fqn.rsplit(".", 1)[-1]
            if short_name in source_names:
                return short_name

            if depth + 1 < depth_limit:
                queue.append((callee_fqn, depth + 1))

    return None


def pair_to_targets(
    test_func: TestFunc,
    source_functions: list[FunctionTarget],
    *,
    astroid_graph: dict[str, set[str]] | None = None,
    astroid_graph_provider: Callable[[], dict[str, set[str]]] | None = None,
) -> TestTargetPair:
    """Pair a test function with its most likely production target.

    Uses four strategies in priority order (first match wins):

    1. **Name convention** — strips the "test_" prefix and looks for an exact
       match (confidence 0.9) or case-insensitive match (confidence 0.7) in
       source_functions.
    2. **Call graph** — deep AST walk of the test function body; the first
       source function name found in a direct call is selected (confidence 0.8).
    3. **Transitive call graph** — BFS over the Astroid-inferred call graph
       (confidence 0.75). Only fires when ``astroid_graph`` or
       ``astroid_graph_provider`` is provided.
    4. **Unmatched** — no match found (confidence 0.0, target_name=None).

    When source_functions is empty, returns immediately with method="unmatched".
    Existing callers that omit both astroid parameters are unaffected.

    Args:
        test_func: The test function to pair.
        source_functions: All production FunctionTargets available for pairing.
        astroid_graph: Optional pre-built caller→callees adjacency dict from
            ``_build_astroid_graph()``. When set, used directly.
        astroid_graph_provider: Optional zero-arg callable returning the
            adjacency dict. Invoked ONLY when Strategies 1–2 fail, so an
            expensive graph build is skipped entirely when every test pairs
            by name or direct call (audit P3). Ignored when ``astroid_graph``
            is also set.

    Returns:
        A TestTargetPair with the best match found.
    """
    if not source_functions:
        return TestTargetPair(
            test_name=test_func.name,
            target_name=None,
            inference_method="unmatched",
            confidence=0.0,
        )

    # Strategy 1 — Name convention: strip "test_" prefix.
    candidate = test_func.name.removeprefix("test_")

    # Exact match (confidence 0.9).
    for fn in source_functions:
        if fn.function == candidate:
            return TestTargetPair(
                test_name=test_func.name,
                target_name=fn.function,
                inference_method="name_convention",
                confidence=0.9,
            )

    # Case-insensitive match (confidence 0.7).
    for fn in source_functions:
        if fn.function.lower() == candidate.lower():
            return TestTargetPair(
                test_name=test_func.name,
                target_name=fn.function,
                inference_method="name_convention",
                confidence=0.7,
            )

    # Strategy 2 — Call graph: deep AST walk for direct calls to source functions.
    # Intentional deep walk — tests frequently call targets from within with-blocks,
    # comprehensions, or inline helpers. Known limitation: first match in pre-order
    # traversal is selected when multiple source functions are called.
    source_names = {fn.function for fn in source_functions}
    for node in ast.walk(test_func.node):
        if isinstance(node, ast.Call):
            called = _extract_call_name(node)
            if called is not None and called in source_names:
                return TestTargetPair(
                    test_name=test_func.name,
                    target_name=called,
                    inference_method="call_graph",
                    confidence=0.8,
                )

    # Strategy 3 — Transitive call graph via Astroid inference.
    # Only fires when a graph or provider is supplied; existing callers are
    # unaffected. The provider is invoked here — after Strategies 1–2 have
    # failed — so the expensive astroid build is lazy (audit P3).
    if astroid_graph is None and astroid_graph_provider is not None:
        astroid_graph = astroid_graph_provider()
    if astroid_graph is not None:
        matched_name = _pair_astroid(test_func, source_names, astroid_graph)
        if matched_name is not None:
            return TestTargetPair(
                test_name=test_func.name,
                target_name=matched_name,
                inference_method="call_graph_transitive",
                confidence=0.75,
            )

    # Strategy 4 — Unmatched.
    return TestTargetPair(
        test_name=test_func.name,
        target_name=None,
        inference_method="unmatched",
        confidence=0.0,
    )
