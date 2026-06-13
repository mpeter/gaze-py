"""Cyclomatic complexity computation using Python's AST (McCabe algorithm).

Computes McCabe cyclomatic complexity for a single function node. Does NOT
recurse into nested function definitions — each function is scored independently.
"""

from __future__ import annotations

import ast


def cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute McCabe cyclomatic complexity for a single function.

    Starts at 1 (base complexity for any function) and increments for each
    decision point: if/elif, for, while, except handler, with item, assert,
    boolean operator, and comprehension if-filter.

    Does NOT recurse into nested function definitions — each function is
    scored independently. Nested function complexity does not roll up into
    the outer function.

    Args:
        node: The AST node for the function to score. Must be a FunctionDef
            or AsyncFunctionDef.

    Returns:
        McCabe cyclomatic complexity as a positive integer (minimum 1).
    """
    counter = _ComplexityVisitor()
    counter.visit(node)
    return counter.complexity


class _ComplexityVisitor(ast.NodeVisitor):
    """AST visitor that counts decision points for McCabe complexity.

    Tracks nesting depth to skip nested function definitions — each function
    is scored independently.
    """

    def __init__(self) -> None:
        self.complexity = 1  # base complexity for any function
        self._depth = 0  # nesting depth; skip nested FunctionDef when > 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Skip nested function definitions — they are scored independently."""
        if self._depth > 0:
            return  # do not recurse into nested functions
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Skip nested async function definitions — they are scored independently."""
        if self._depth > 0:
            return
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        """Each if/elif adds one branch point.

        Note: elif is represented as a nested ast.If in the orelse field —
        there is no ast.ElIf node in Python's AST. Each is counted separately.
        """
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        """Each for loop adds one branch point."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        """Each while loop adds one branch point."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        """Each except clause adds one branch point."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        """Each item in a with statement adds one branch point.

        A single 'with a, b:' statement has two items and adds 2.
        """
        self.complexity += len(node.items)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
        """Each assert statement adds one branch point."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
        """Each AND or OR operator adds one branch point per additional operand.

        'a and b' has 2 values → +1. 'a and b and c' has 3 values → +2.
        """
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:  # noqa: N802
        """Each if-filter in a list comprehension adds one branch point."""
        self._count_comprehension_ifs(node.generators)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:  # noqa: N802
        """Each if-filter in a set comprehension adds one branch point."""
        self._count_comprehension_ifs(node.generators)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:  # noqa: N802
        """Each if-filter in a dict comprehension adds one branch point."""
        self._count_comprehension_ifs(node.generators)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:  # noqa: N802
        """Each if-filter in a generator expression adds one branch point."""
        self._count_comprehension_ifs(node.generators)
        self.generic_visit(node)

    def _count_comprehension_ifs(self, generators: list[ast.comprehension]) -> None:
        """Increment complexity for each if-filter across all generators.

        Args:
            generators: List of comprehension generator nodes, each of which
                may have zero or more if-filter expressions.
        """
        for gen in generators:
            self.complexity += len(gen.ifs)
