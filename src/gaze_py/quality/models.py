"""Internal models for the O1 quality assessment pipeline.

TestFunc wraps an ast.FunctionDef node and is used only within the quality
pipeline. It is never serialized to JSON — use QualityReport (in taxonomy/models.py)
for all output types.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class TestFunc:
    """Internal representation of a test function.

    Not frozen — contains ast.FunctionDef which is a mutable type.
    Never serialized; used only within the quality pipeline.

    Attributes:
        name: Simple function name (e.g., "test_process").
        filename: Absolute path to the source file containing this function.
        lineno: Line number where the function is defined (1-indexed).
        node: The parsed AST node for this function. Read-only in practice;
            MUST NOT be mutated. Stored as a mutable type, so the dataclass
            cannot be frozen.
    """

    name: str
    filename: str
    lineno: int
    node: ast.FunctionDef  # read-only; mutable type, so @dataclass (not frozen)
