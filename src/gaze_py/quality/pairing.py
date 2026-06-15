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
import sys
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
    """Extract the simple function name from a Call node.

    Returns the name only for simple name calls (e.g., ``foo(...)``).
    Method calls and qualified names (e.g., ``obj.method()``, ``mod.fn()``)
    return None — the call graph strategy targets direct function calls only.

    Args:
        node: The ast.Call node to inspect.

    Returns:
        The function name string if the call is a simple name call, else None.
    """
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _build_astroid_graph(
    test_files: list[Path],
    src_files: list[Path],
) -> dict[str, set[str]]:
    """Build a caller→callees adjacency dict using Astroid type inference.

    Loads each file once via Astroid's MANAGER, walks all FunctionDef nodes,
    and infers the fully-qualified names of every callee. Returns a plain dict
    mapping caller FQN to the set of callee FQNs reachable from that function.

    MANAGER.clear_cache() is called at the start of every invocation to prevent
    stale data when assess() is called multiple times in the same process (D2).
    This evicts all cached AST modules from the global MANAGER — a known
    trade-off documented in design.md D2 and CHANGELOG.

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
    # D2: clear stale data before each build.
    MANAGER.clear_cache()

    # Deduplicate while preserving insertion order (test_files first so test
    # FQNs are available as graph keys before src FQNs are added as callees).
    unique_files: list[Path] = list(dict.fromkeys(test_files + src_files))

    graph: collections.defaultdict[str, set[str]] = collections.defaultdict(set)

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

    return dict(graph)


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

    Derives the test function's fully-qualified name using the D8 project-root
    heuristic, then performs a BFS over the Astroid call graph up to
    ``depth_limit`` hops. At each callee FQN, the short name (last segment
    after the final ``.``) is checked against ``source_names``. The first
    matching short name is returned.

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
    # D8: derive FQN from filename using project-root heuristic.
    file_path = Path(test_func.filename)
    project_root = _find_project_root(file_path)

    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        # filename is not under project_root — fall back to stem only.
        rel = Path(file_path.stem)

    # Convert path separators to dots and strip .py suffix.
    parts = list(rel.with_suffix("").parts)

    # Strip leading "tests", "test", "src" components to match Astroid's
    # module naming (Astroid sees the module name, not the filesystem path).
    if parts and parts[0] in {"tests", "test", "src"}:
        parts = parts[1:]

    module_fqn = ".".join(parts)
    start_fqn = f"{module_fqn}.{test_func.name}" if module_fqn else test_func.name

    # BFS over the call graph, tracking (node_fqn, depth) pairs.
    queue: collections.deque[tuple[str, int]] = collections.deque()
    queue.append((start_fqn, 0))
    visited: set[str] = {start_fqn}

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
) -> TestTargetPair:
    """Pair a test function with its most likely production target.

    Uses four strategies in priority order (first match wins):

    1. **Name convention** — strips the "test_" prefix and looks for an exact
       match (confidence 0.9) or case-insensitive match (confidence 0.7) in
       source_functions.
    2. **Call graph** — deep AST walk of the test function body; the first
       source function name found in a direct call is selected (confidence 0.8).
    3. **Transitive call graph** — BFS over the Astroid-inferred call graph
       (confidence 0.75). Only fires when ``astroid_graph`` is provided.
    4. **Unmatched** — no match found (confidence 0.0, target_name=None).

    When source_functions is empty, returns immediately with method="unmatched".
    Existing callers that omit ``astroid_graph`` are unaffected (default None).

    Args:
        test_func: The test function to pair.
        source_functions: All production FunctionTargets available for pairing.
        astroid_graph: Optional caller→callees adjacency dict from
            ``_build_astroid_graph()``. When None, Strategy 3 is skipped.

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
        if fn.name == candidate:
            return TestTargetPair(
                test_name=test_func.name,
                target_name=fn.name,
                inference_method="name_convention",
                confidence=0.9,
            )

    # Case-insensitive match (confidence 0.7).
    for fn in source_functions:
        if fn.name.lower() == candidate.lower():
            return TestTargetPair(
                test_name=test_func.name,
                target_name=fn.name,
                inference_method="name_convention",
                confidence=0.7,
            )

    # Strategy 2 — Call graph: deep AST walk for direct calls to source functions.
    # Intentional deep walk — tests frequently call targets from within with-blocks,
    # comprehensions, or inline helpers. Known limitation: first match in pre-order
    # traversal is selected when multiple source functions are called.
    source_names = {fn.name for fn in source_functions}
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
    # Only fires when astroid_graph is provided; existing callers are unaffected.
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
