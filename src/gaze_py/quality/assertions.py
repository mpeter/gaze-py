"""A.2 — Assertion detection for the O1 quality assessment pipeline.

Walks the body of a test function and classifies each assertion site by kind,
location, depth, and the variable names it references.

Detection priority for ast.Assert nodes (first-match-wins):
  1. STDLIB_ERROR_CHECK — condition references a name containing "err"
  2. STDLIB_NONE_CHECK  — condition is an "is None" / "is not None" compare
  3. STDLIB_EQUALITY    — condition is a Compare or BinOp
  4. STDLIB_TRUTH       — fallback (bare assert x)

Helper recursion: calls whose name starts with "assert_" or "check_" are
recursed into (up to max_depth) when the helper is defined in pkg_ast.
"""

from __future__ import annotations

import ast
from pathlib import Path

from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.models import AssertionKind, AssertionSite


def detect_assertions(
    test_func: TestFunc,
    *,
    pkg_ast: dict[str, ast.Module] | None = None,
    max_depth: int = 3,
) -> list[AssertionSite]:
    """Detect all assertion sites in a test function.

    Walks the test function body and classifies each assertion by kind,
    location, depth, and referenced variable names. Recurses into helper
    functions (those whose names start with "assert_" or "check_") up to
    max_depth levels deep.

    Args:
        test_func: The test function to inspect.
        pkg_ast: Optional mapping of module name → parsed AST module. Used
            to resolve helper function bodies for recursion. When None,
            helper recursion is disabled.
        max_depth: Maximum recursion depth for helper functions. 0 means
            no recursion; 3 is the default.

    Returns:
        List of AssertionSite objects, one per detected assertion.
    """
    collector = _AssertionCollector(
        filename=test_func.filename,
        pkg_ast=pkg_ast or {},
        max_depth=max_depth,
    )
    collector.walk_body(test_func.node.body, depth=0)
    return collector.results


def _extract_referenced_names(expr: ast.expr) -> frozenset[str]:
    """Collect variable names referenced in an assertion expression.

    Traverses the expression tree and collects:
    - ast.Name → the name id
    - ast.Attribute → the attribute name AND the base object name
    - ast.Subscript → the base object name (e.g., "result" from result[0])
    - ast.Call → the function name string (e.g., "f" from f())

    Args:
        expr: The AST expression to inspect.

    Returns:
        Frozenset of name strings referenced in the expression.
    """
    names: set[str] = set()
    _collect_names(expr, names)
    return frozenset(names)


def _collect_names(node: ast.AST, names: set[str]) -> None:
    """Recursively collect names from an AST node into the names set.

    Args:
        node: The AST node to traverse.
        names: Mutable set to accumulate name strings into.
    """
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, ast.Attribute):
        names.add(node.attr)
        # Also collect the base object name.
        _collect_names(node.value, names)
    elif isinstance(node, ast.Subscript):
        # Collect the base name (e.g., "result" from result[0]).
        _collect_names(node.value, names)
        # Also collect names from the slice.
        _collect_names(node.slice, names)
    elif isinstance(node, ast.Call):
        # Collect the function name string.
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
            _collect_names(node.func.value, names)
        # Collect names from arguments.
        for arg in node.args:
            _collect_names(arg, names)
        for kw in node.keywords:
            _collect_names(kw.value, names)
    else:
        # For all other node types, recurse into child nodes.
        for child in ast.iter_child_nodes(node):
            _collect_names(child, names)


def _location(filename: str, node: ast.AST) -> str:
    """Format a location string as "file:line:col".

    Uses col=0 when the AST node has no column information.

    Args:
        filename: Source file path string.
        node: AST node providing lineno and col_offset.

    Returns:
        Location string in "filename:lineno:col" format.
    """
    lineno = getattr(node, "lineno", 0)
    col = getattr(node, "col_offset", 0)
    return f"{filename}:{lineno}:{col}"


def _classify_assert(node: ast.Assert) -> tuple[AssertionKind, frozenset[str]]:
    """Classify an ast.Assert node into an AssertionKind.

    Priority order (first-match-wins):
    1. STDLIB_ERROR_CHECK — any Name in the condition contains "err"
    2. STDLIB_NONE_CHECK  — condition is a Compare with "is None" or "is not None"
    3. STDLIB_EQUALITY    — condition is a Compare or BinOp
    4. STDLIB_TRUTH       — fallback

    Args:
        node: The ast.Assert node to classify.

    Returns:
        Tuple of (AssertionKind, frozenset of referenced names).
    """
    test = node.test
    names = _extract_referenced_names(test)

    # Priority 1: error check — any referenced name contains "err".
    if any("err" in name.lower() for name in names):
        return AssertionKind.STDLIB_ERROR_CHECK, names

    # Priority 2: none check — "is None" or "is not None" compare.
    if isinstance(test, ast.Compare):
        for op in test.ops:
            if isinstance(op, (ast.Is, ast.IsNot)):
                for comparator in test.comparators:
                    if isinstance(comparator, ast.Constant) and comparator.value is None:
                        return AssertionKind.STDLIB_NONE_CHECK, names

    # Priority 3: equality — any Compare or BinOp.
    if isinstance(test, (ast.Compare, ast.BinOp)):
        return AssertionKind.STDLIB_EQUALITY, names

    # Priority 4: truth — fallback.
    return AssertionKind.STDLIB_TRUTH, names


def _is_raises_context(node: ast.With) -> bool:
    """Return True if the with-statement is a pytest.raises() context.

    Matches: ``with pytest.raises(SomeError):``

    Args:
        node: The ast.With node to inspect.

    Returns:
        True when the first context manager is a call to an attribute named
        "raises" (e.g., pytest.raises).
    """
    if not node.items:
        return False
    ctx = node.items[0].context_expr
    return (
        isinstance(ctx, ast.Call)
        and isinstance(ctx.func, ast.Attribute)
        and ctx.func.attr == "raises"
    )


def _classify_method_call(node: ast.Call) -> AssertionKind | None:
    """Classify a self.assertXxx() method call.

    Args:
        node: The ast.Call node to inspect.

    Returns:
        The matching AssertionKind, or None if not a recognized unittest assert.
    """
    if not isinstance(node.func, ast.Attribute):
        return None
    if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
        return None

    method = node.func.attr
    if method in {
        "assertEqual",
        "assertNotEqual",
        "assertAlmostEqual",
        "assertGreater",
        "assertLess",
        "assertIn",
        "assertNotIn",
        "assertIs",
        "assertIsNot",
    }:
        return AssertionKind.UNITTEST_EQUAL
    if method in {"assertIsNone", "assertIsNotNone"}:
        return AssertionKind.UNITTEST_NONE
    if method in {"assertRaises", "assertRaisesRegex"}:
        return AssertionKind.UNITTEST_RAISES
    return None


class _AssertionCollector:
    """Stateful collector that walks a test function body for assertion sites.

    Handles direct assertions, with-statement raises contexts, unittest-style
    method assertions, and recursive helper function calls.
    """

    def __init__(
        self,
        *,
        filename: str,
        pkg_ast: dict[str, ast.Module],
        max_depth: int,
    ) -> None:
        """Initialize the collector.

        Args:
            filename: Source file path for location strings.
            pkg_ast: Mapping of module name → parsed AST for helper recursion.
            max_depth: Maximum recursion depth for helper functions.
        """
        self._filename = filename
        self._pkg_ast = pkg_ast
        self._max_depth = max_depth
        self.results: list[AssertionSite] = []

    def walk_body(self, stmts: list[ast.stmt], *, depth: int) -> None:
        """Walk a list of statements and collect assertion sites.

        Args:
            stmts: Statement list to walk (function body or helper body).
            depth: Current recursion depth (0 = direct test body).
        """
        for stmt in stmts:
            self._visit_stmt(stmt, depth=depth)

    def _visit_stmt(self, stmt: ast.stmt, *, depth: int) -> None:
        """Dispatch a single statement to the appropriate handler.

        Args:
            stmt: The statement to inspect.
            depth: Current recursion depth.
        """
        if isinstance(stmt, ast.Assert):
            self._handle_assert(stmt, depth=depth)
        elif isinstance(stmt, ast.With):
            self._handle_with(stmt, depth=depth)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            self._handle_call_expr(stmt.value, stmt, depth=depth)
        else:
            # Recurse into compound statements (if, for, try, etc.).
            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, ast.stmt):
                    self._visit_stmt(child, depth=depth)

    def _handle_assert(self, node: ast.Assert, *, depth: int) -> None:
        """Process an ast.Assert node.

        Args:
            node: The assert statement node.
            depth: Current recursion depth.
        """
        kind, names = _classify_assert(node)
        self.results.append(
            AssertionSite(
                location=_location(self._filename, node),
                kind=kind,
                depth=depth,
                referenced_names=names,
            )
        )

    def _handle_with(self, node: ast.With, *, depth: int) -> None:
        """Process a with-statement, detecting pytest.raises() contexts.

        Args:
            node: The with-statement node.
            depth: Current recursion depth.
        """
        if _is_raises_context(node):
            ctx = node.items[0].context_expr
            names = _extract_referenced_names(ctx)
            self.results.append(
                AssertionSite(
                    location=_location(self._filename, node),
                    kind=AssertionKind.STDLIB_RAISES,
                    depth=depth,
                    referenced_names=names,
                )
            )
        # Always recurse into the with-body for nested assertions.
        for stmt in node.body:
            self._visit_stmt(stmt, depth=depth)

    def _handle_call_expr(
        self,
        call: ast.Call,
        stmt: ast.stmt,
        *,
        depth: int,
    ) -> None:
        """Process a bare call expression statement.

        Handles:
        - self.assertXxx() — unittest-style assertions.
        - assert_* / check_* helper calls — recurse if defined in pkg_ast.

        Args:
            call: The ast.Call node.
            stmt: The parent statement (for location).
            depth: Current recursion depth.
        """
        # Unittest-style: self.assertEqual(a, b) etc.
        kind = _classify_method_call(call)
        if kind is not None:
            names = _extract_referenced_names(call)
            self.results.append(
                AssertionSite(
                    location=_location(self._filename, stmt),
                    kind=kind,
                    depth=depth,
                    referenced_names=names,
                )
            )
            return

        # Helper recursion: assert_* or check_* calls.
        if depth >= self._max_depth:
            return

        called_name: str | None = None
        if isinstance(call.func, ast.Name):
            called_name = call.func.id

        if called_name is None:
            return
        if not (called_name.startswith("assert_") or called_name.startswith("check_")):
            return

        # Look up the helper in pkg_ast.
        helper_node = self._find_helper(called_name)
        if helper_node is not None:
            self.walk_body(helper_node.body, depth=depth + 1)

    def _find_helper(self, name: str) -> ast.FunctionDef | None:
        """Search pkg_ast for a top-level function definition by name.

        Args:
            name: The function name to look up.

        Returns:
            The ast.FunctionDef node if found, else None.
        """
        for module in self._pkg_ast.values():
            for node in module.body:
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    return node
        return None


def _collect_py_files_for_pkg(path: Path) -> dict[str, ast.Module]:
    """Parse all .py files under path into a module AST map.

    Used internally to build the pkg_ast argument for detect_assertions()
    when the caller wants helper recursion across a package.

    Args:
        path: Directory to scan for .py files.

    Returns:
        Mapping of file path string → parsed ast.Module. Files that fail
        to parse are silently skipped.
    """
    result: dict[str, ast.Module] = {}
    if not path.is_dir():
        return result
    for py_file in path.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            module = ast.parse(source, filename=str(py_file))
            result[str(py_file)] = module
        except (OSError, SyntaxError, ValueError):
            continue
    return result
