"""Assertion mapper and contract coverage engine for gaze-py.

This module implements User Story 2 (S2) of the gaze-py analysis engine:

1. ``AssertionVisitor`` — ``ast.NodeVisitor`` that walks a test function body
   and detects assertion patterns, mapping them to ``SideEffectType`` values.
2. ``map_assertions`` — public entry point that parses a test source file,
   locates the test function body, runs the visitor, and returns a
   ``QualityReport`` with contract coverage and over-specification metrics.

Design decisions:
- S2 is isolated from S1: ``map_assertions`` accepts pre-constructed
  ``SideEffect`` objects and does NOT call ``analyze_function()``.  A bug in
  ``analysis.py`` will not cause misleading failures in ``test_quality.py``.
- Classification is delegated to ``taxonomy.is_contractual()`` — not
  reimplemented here (SOLID Single Responsibility; Open/Closed: extend the
  taxonomy, not this module).
- ``GazeParseError`` is re-raised from ``analysis.py`` so callers have a
  single typed exception surface for all parse failures across S1 and S2.
- Coverage formula: ``covered_contractual / total_contractual * 100``.
  When ``total_contractual == 0`` the result is vacuously 100.0 (no effects
  to cover).
- Gap hints are parallel to ``gaps``: ``len(gap_hints) == len(gaps)`` always.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from gaze_py.analysis import GazeParseError
from gaze_py.taxonomy import (
    AssertionMapping,
    ContractCoverage,
    FunctionTarget,
    OverSpecificationScore,
    QualityReport,
    SideEffect,
    SideEffectType,
    is_contractual,
)

# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------


@dataclass
class _AssertionResult:
    """Raw output of the AssertionVisitor for one test function body.

    Attributes:
        return_value_covered: True when at least one assertion maps to
            ``ReturnValue`` (assignment+assert, inline call, isinstance, etc.).
        error_return_covered: True when a ``pytest.raises`` context manager
            is detected for the target function.
        total_assert_count: Total number of ``assert`` statements found.
        incidental_count: Number of assertions classified as over-specified
            (e.g., ``isinstance`` type checks that are not the primary value
            assertion).
        incidental_texts: Source text of each incidental assertion, used to
            populate ``OverSpecificationScore.incidental_assertions``.
    """

    return_value_covered: bool = False
    error_return_covered: bool = False
    total_assert_count: int = 0
    incidental_count: int = 0
    incidental_texts: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AssertionVisitor
# ---------------------------------------------------------------------------


class AssertionVisitor(ast.NodeVisitor):
    """Walk a test function body and detect assertion patterns.

    The visitor recognises the following patterns (per plan.md S2 design):

    - ``result = target_func(...); assert result == x``  → ReturnValue
    - ``result = target_func(...); assert result is not None`` → ReturnValue
    - ``result = target_func(...); assert isinstance(result, T)``
      → ReturnValue (primary), but also flagged as incidental type-check
      when a value assertion already covers ReturnValue.
    - ``assert target_func() == x`` (inline call)  → ReturnValue
    - ``with pytest.raises(E): target_func(...)``   → ErrorReturn

    Args:
        target_func: Name of the source function under test.
    """

    def __init__(self, target_func: str) -> None:
        """Initialise the visitor for the given target function name.

        Args:
            target_func: The name of the source function being tested.
        """
        self._target_func = target_func
        # Names of local variables that were assigned from a call to
        # target_func.  Populated by _scan_assignments().
        self._result_vars: set[str] = set()
        # Whether a plain value assertion (==, is not None) was found —
        # used to classify isinstance as incidental when a value assert
        # already covers ReturnValue.
        self._has_value_assert = False
        self.result = _AssertionResult()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def visit_body(self, stmts: list[ast.stmt]) -> None:
        """Scan a list of statements (the test function body).

        Performs two passes:
        1. Assignment scan — identifies variables bound to ``target_func()``
           calls.
        2. Statement walk — detects assertion and context-manager patterns.

        Args:
            stmts: The ``body`` attribute of an ``ast.FunctionDef`` node.
        """
        self._scan_assignments(stmts)
        for stmt in stmts:
            self.visit(stmt)

    # ------------------------------------------------------------------
    # Pass 1: assignment scan
    # ------------------------------------------------------------------

    def _scan_assignments(self, stmts: list[ast.stmt]) -> None:
        """Populate ``_result_vars`` with names assigned from target_func().

        Recognises simple assignment: ``result = target_func(...)``

        Args:
            stmts: Statement list to scan.
        """
        for stmt in stmts:
            if not isinstance(stmt, ast.Assign):
                continue
            if not isinstance(stmt.value, ast.Call):
                continue
            if not self._is_target_call(stmt.value):
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    self._result_vars.add(target.id)

    # ------------------------------------------------------------------
    # Pass 2: statement visitors
    # ------------------------------------------------------------------

    def visit_Assert(self, node: ast.Assert) -> None:
        """Detect assertion patterns and update coverage flags.

        Recognised patterns:
        - ``assert result == x`` / ``assert result is not None``
          where ``result`` is in ``_result_vars`` → ReturnValue
        - ``assert target_func() == x`` (inline call) → ReturnValue
        - ``assert isinstance(result, T)`` → ReturnValue (primary),
          incidental when a value assert already covered it.

        Args:
            node: The ``ast.Assert`` node to inspect.
        """
        self.result.total_assert_count += 1
        test = node.test

        # Pattern: assert isinstance(result, T)
        if self._is_isinstance_assert(test):
            if self._has_value_assert:
                # A value assertion already covers ReturnValue; this
                # isinstance check is over-specifying the type.
                self.result.incidental_count += 1
                self.result.incidental_texts.append(ast.unparse(node))
            else:
                # isinstance is the only assertion — treat as ReturnValue
                # coverage (per spec edge case: "assert isinstance(result,
                # MyClass): treated as a return value assertion").
                self.result.return_value_covered = True
                self._has_value_assert = True
            return

        # Pattern: assert result == x  /  assert result is not None
        if self._is_result_var_assert(test):
            self.result.return_value_covered = True
            self._has_value_assert = True
            return

        # Pattern: assert target_func() == x  (inline call)
        if self._is_inline_call_assert(test):
            self.result.return_value_covered = True
            self._has_value_assert = True
            return

        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """Detect ``with pytest.raises(E): target_func(...)`` pattern.

        Args:
            node: The ``ast.With`` node to inspect.
        """
        for item in node.items:
            if self._is_pytest_raises(item.context_expr) and self._body_calls_target(node.body):
                self.result.error_return_covered = True
                return
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Pattern helpers
    # ------------------------------------------------------------------

    def _is_target_call(self, node: ast.expr) -> bool:
        """Return True if ``node`` is a call to ``target_func``.

        Args:
            node: An AST expression node.

        Returns:
            ``True`` when the node is ``ast.Call`` with func name matching
            ``self._target_func``.
        """
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == self._target_func
        if isinstance(func, ast.Attribute):
            return func.attr == self._target_func
        return False

    def _is_result_var_assert(self, test: ast.expr) -> bool:
        """Return True if ``test`` asserts on a known result variable.

        Recognised forms:
        - ``result == x`` (Compare with Eq)
        - ``result is not None`` (Compare with IsNot)
        - ``result`` (bare name — truthy check)

        Args:
            test: The test expression of an ``ast.Assert`` node.

        Returns:
            ``True`` when the left-hand side of the comparison is a name
            in ``_result_vars``.
        """
        if isinstance(test, ast.Compare):
            left = test.left
            if isinstance(left, ast.Name) and left.id in self._result_vars:
                return True
        return isinstance(test, ast.Name) and test.id in self._result_vars

    def _is_inline_call_assert(self, test: ast.expr) -> bool:
        """Return True if ``test`` contains an inline call to target_func.

        Recognised forms:
        - ``target_func(...) == x``
        - ``target_func(...)`` (bare call — truthy check)

        Args:
            test: The test expression of an ``ast.Assert`` node.

        Returns:
            ``True`` when the expression contains a direct call to
            ``self._target_func`` as the left-hand side of a comparison or
            as a standalone expression.
        """
        if isinstance(test, ast.Compare) and self._is_target_call(test.left):
            return True
        return bool(self._is_target_call(test))

    def _is_isinstance_assert(self, test: ast.expr) -> bool:
        """Return True if ``test`` is ``isinstance(result_var, T)``.

        Args:
            test: The test expression of an ``ast.Assert`` node.

        Returns:
            ``True`` when the expression is an ``isinstance`` call whose
            first argument is a name in ``_result_vars``.
        """
        if not isinstance(test, ast.Call):
            return False
        func = test.func
        if not (isinstance(func, ast.Name) and func.id == "isinstance"):
            return False
        if not test.args:
            return False
        first_arg = test.args[0]
        return isinstance(first_arg, ast.Name) and first_arg.id in self._result_vars

    def _is_pytest_raises(self, node: ast.expr) -> bool:
        """Return True if ``node`` is a ``pytest.raises(...)`` call.

        Args:
            node: The context expression of a ``with`` statement item.

        Returns:
            ``True`` when the expression is ``pytest.raises(...)`` or
            ``raises(...)`` (bare import form).
        """
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        # pytest.raises(E)
        if isinstance(func, ast.Attribute):
            return func.attr == "raises"
        # raises(E) — bare import: from pytest import raises
        if isinstance(func, ast.Name):
            return func.id == "raises"
        return False

    def _body_calls_target(self, stmts: list[ast.stmt]) -> bool:
        """Return True if any statement in ``stmts`` calls ``target_func``.

        Args:
            stmts: Statement list (body of a ``with`` block).

        Returns:
            ``True`` when at least one ``ast.Call`` to ``self._target_func``
            is found anywhere in the statement list.
        """
        for stmt in stmts:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call) and self._is_target_call(node):
                    return True
        return False


# ---------------------------------------------------------------------------
# Coverage computation helpers
# ---------------------------------------------------------------------------


def _compute_contract_coverage(
    visitor_result: _AssertionResult,
    target_effects: list[SideEffect],
    target_func: str,
) -> ContractCoverage:
    """Compute contract coverage from visitor output and target effects.

    Coverage formula::

        percentage = covered_contractual / total_contractual * 100

    When ``total_contractual == 0`` the result is vacuously 100.0.

    Gap hints are parallel to ``gaps``: one hint string per uncovered
    contractual effect.

    Args:
        visitor_result: Output of ``AssertionVisitor.visit_body()``.
        target_effects: The contractual side effects of the source function.
        target_func: Name of the source function (used in hint strings).

    Returns:
        A ``ContractCoverage`` instance with percentage, counts, gaps, and
        gap hints.
    """
    contractual = [e for e in target_effects if is_contractual(e.type)]
    total = len(contractual)

    if total == 0:
        return ContractCoverage(
            percentage=100.0,
            covered_count=0,
            total_contractual=0,
            gaps=[],
            gap_hints=[],
        )

    covered: list[SideEffect] = []
    gaps: list[SideEffect] = []

    for effect in contractual:
        if _effect_is_covered(effect.type, visitor_result):
            covered.append(effect)
        else:
            gaps.append(effect)

    covered_count = len(covered)
    percentage = (covered_count / total) * 100.0

    gap_hints = [_gap_hint(e.type, target_func) for e in gaps]

    return ContractCoverage(
        percentage=percentage,
        covered_count=covered_count,
        total_contractual=total,
        gaps=gaps,
        gap_hints=gap_hints,
    )


def _effect_is_covered(
    effect_type: SideEffectType,
    visitor_result: _AssertionResult,
) -> bool:
    """Return True if the given effect type was covered by the visitor.

    Args:
        effect_type: The ``SideEffectType`` to check.
        visitor_result: Output of ``AssertionVisitor.visit_body()``.

    Returns:
        ``True`` when the effect type was detected as covered.
    """
    if effect_type == SideEffectType.ReturnValue:
        return visitor_result.return_value_covered
    if effect_type == SideEffectType.ErrorReturn:
        return visitor_result.error_return_covered
    # For other contractual types (ReceiverMutation, PointerArgMutation,
    # GlobalMutation, SentinelError) we conservatively report not covered
    # in v1 — the mapper only handles the most common patterns.
    return False


def _gap_hint(effect_type: SideEffectType, target_func: str) -> str:
    """Return a suggested assert snippet for an uncovered contractual effect.

    The hint is actionable: it shows the developer exactly what kind of
    assertion to add (per plan.md S2 design, ``gap_hints`` field).

    Args:
        effect_type: The uncovered ``SideEffectType``.
        target_func: Name of the source function under test.

    Returns:
        A plain-English assert snippet string.
    """
    if effect_type == SideEffectType.ReturnValue:
        return f"result = {target_func}(...); assert result == <expected>"
    if effect_type in (SideEffectType.ErrorReturn, SideEffectType.SentinelError):
        return f"with pytest.raises(<ExcType>): {target_func}(...)"
    if effect_type == SideEffectType.ReceiverMutation:
        return f"obj.{target_func}(...); assert obj.<attr> == <expected>"
    if effect_type == SideEffectType.PointerArgMutation:
        return f"arg = {{}}; {target_func}(arg); assert arg == <expected>"
    if effect_type == SideEffectType.GlobalMutation:
        return f"{target_func}(...); assert <global_var> == <expected>"
    return f"# assert the {effect_type.value} effect of {target_func}(...)"


def _compute_over_specification(
    visitor_result: _AssertionResult,
) -> OverSpecificationScore:
    """Compute over-specification score from visitor output.

    Over-specification ratio::

        ratio = incidental_count / total_assert_count

    When ``total_assert_count == 0`` the ratio is 0.0.

    Args:
        visitor_result: Output of ``AssertionVisitor.visit_body()``.

    Returns:
        An ``OverSpecificationScore`` instance.
    """
    count = visitor_result.incidental_count
    total = visitor_result.total_assert_count
    ratio = (count / total) if total > 0 else 0.0

    incidental_assertions = [
        AssertionMapping(
            assertion_text=text,
            location="test.py:?",
            confidence=70,
            mapped_effect=None,
            unmapped_reason="incidental_type_check",
        )
        for text in visitor_result.incidental_texts
    ]

    suggestions = [
        "This assertion over-specifies an implementation detail. "
        "Consider asserting the return value or observable behaviour instead."
        for _ in visitor_result.incidental_texts
    ]

    return OverSpecificationScore(
        count=count,
        ratio=ratio,
        incidental_assertions=incidental_assertions,
        suggestions=suggestions,
    )


def _iter_test_functions(tree: ast.Module) -> list[tuple[str, list[ast.stmt]]]:
    """Return (name, body) for every test function in the module.

    Handles three layouts:
    - Top-level ``def test_foo``: collected directly.
    - Class methods ``class TestFoo: def test_bar``: collected with name
      ``TestFoo.test_bar`` so the caller can display the full path.
    - Nested definitions are NOT descended into (matches analysis.py scoping).

    Args:
        tree: Parsed AST module.

    Returns:
        List of ``(qualified_name, body)`` tuples in source order.
    """
    results: list[tuple[str, list[ast.stmt]]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            results.append((node.name, node.body))
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    results.append((f"{node.name}.{item.name}", item.body))
    return results


def _extract_called_names(body: list[ast.stmt]) -> set[str]:
    """Return all function/attribute names called anywhere in the body.

    Handles:
    - ``foo(...)``           → ``"foo"``
    - ``mod.foo(...)``       → ``"foo"``
    - ``result = foo(...)``  → ``"foo"``
    - ``with pytest.raises(E): foo(...)`` → ``"foo"``

    Does not descend into nested function definitions.

    Args:
        body: Statement list from a function body.

    Returns:
        Set of plain function names (without module prefix) called in the body.
    """
    names: set[str] = []

    class _CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            if isinstance(node.func, ast.Name):
                names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.append(node.func.attr)
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            pass  # don't recurse into nested functions

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            pass

    visitor = _CallVisitor()
    for stmt in body:
        visitor.visit(stmt)
    return set(names)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def map_assertions(
    test_source: str,
    target_effects: list[SideEffect],
    target_func: str,
) -> QualityReport:
    """Map test assertions to side effects and compute contract coverage.

    This is the primary entry point for S2.  It:

    1. Parses ``test_source`` with ``ast.parse()`` (raises ``GazeParseError``
       on ``SyntaxError``).
    2. Iterates ALL test functions in the module (top-level and class methods).
    3. Runs ``AssertionVisitor`` over the combined bodies of tests that call
       ``target_func``.
    4. Computes ``ContractCoverage`` and ``OverSpecificationScore``.
    5. Returns a ``QualityReport``.

    S2 isolation: ``target_effects`` are passed in by the caller — this
    function does NOT call ``analyze_function()`` or ``analyze_module()``.

    Args:
        test_source: Full source text of the test file.
        target_effects: Pre-constructed ``SideEffect`` objects for the
            source function under test.
        target_func: Name of the source function being tested.  Used for
            gap hint generation and call detection.

    Returns:
        A ``QualityReport`` with contract coverage and over-specification
        metrics.

    Raises:
        GazeParseError: When ``test_source`` cannot be parsed as valid Python.
    """
    # Parse — wrap SyntaxError in GazeParseError (CS-006: specific exceptions).
    try:
        tree = ast.parse(test_source)
    except SyntaxError as exc:
        raise GazeParseError(
            path="<test_source>",
            line=exc.lineno,
            msg=str(exc.msg),
            code="PARSE_ERROR",
        ) from exc

    # Collect ALL test function bodies, filter to those that call target_func.
    test_functions = _iter_test_functions(tree)
    relevant_bodies: list[list[ast.stmt]] = []
    relevant_names: list[str] = []
    for fn_name, fn_body in test_functions:
        if target_func in _extract_called_names(fn_body):
            relevant_bodies.append(fn_body)
            relevant_names.append(fn_name)

    # Fall back to all test bodies if none specifically call target_func
    # (preserves v1 behaviour for tests without explicit call patterns).
    if not relevant_bodies and test_functions:
        relevant_bodies = [b for _, b in test_functions]
        relevant_names = [n for n, _ in test_functions]

    # Merge all relevant bodies and run the assertion visitor once.
    merged_body: list[ast.stmt] = []
    for b in relevant_bodies:
        merged_body.extend(b)

    test_fn_name = ", ".join(relevant_names) if relevant_names else "<unknown>"
    confidence = 90 if relevant_bodies else 0

    visitor = AssertionVisitor(target_func)
    visitor.visit_body(merged_body)

    # Compute coverage metrics.
    contract_coverage = _compute_contract_coverage(visitor.result, target_effects, target_func)
    over_specification = _compute_over_specification(visitor.result)

    # Build the target FunctionTarget for the report.
    target_function = FunctionTarget(
        package="<unknown>",
        function=target_func,
        location="<unknown>",
    )

    return QualityReport(
        test_function=test_fn_name,
        test_location="<test_source>",
        target_function=target_function,
        contract_coverage=contract_coverage,
        over_specification=over_specification,
        ambiguous_effects=[],
        unmapped_assertions=[],
        assertion_count=visitor.result.total_assert_count,
        assertion_detection_confidence=confidence,
    )
