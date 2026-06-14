"""A.1 — Test-target pairing for the O1 quality assessment pipeline.

Discovers test functions in a source file and pairs each one with its most
likely production target using three strategies in priority order:
1. Name convention (test_foo → foo), confidence 0.9 exact / 0.7 case-insensitive.
2. Call graph (deep AST walk for calls to source functions), confidence 0.8.
3. Unmatched (no match found), confidence 0.0.
"""

from __future__ import annotations

import ast
from pathlib import Path

from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.models import FunctionTarget, TestTargetPair


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


def pair_to_targets(
    test_func: TestFunc,
    source_functions: list[FunctionTarget],
) -> TestTargetPair:
    """Pair a test function with its most likely production target.

    Uses three strategies in priority order (first match wins):

    1. **Name convention** — strips the "test_" prefix and looks for an exact
       match (confidence 0.9) or case-insensitive match (confidence 0.7) in
       source_functions.
    2. **Call graph** — deep AST walk of the test function body; the first
       source function name found in a direct call is selected (confidence 0.8).
    3. **Unmatched** — no match found (confidence 0.0, target_name=None).

    When source_functions is empty, returns immediately with method="unmatched".

    Args:
        test_func: The test function to pair.
        source_functions: All production FunctionTargets available for pairing.

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

    # Strategy 3 — Unmatched.
    return TestTargetPair(
        test_name=test_func.name,
        target_name=None,
        inference_method="unmatched",
        confidence=0.0,
    )
