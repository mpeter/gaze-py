"""A.3 — Assertion-to-effect mapping for the O1 quality assessment pipeline.

Maps each assertion site to the side effect type it most likely exercises,
using three passes in first-match-wins order:

Pass 1 — Binding match: assertion references a name bound to the target's
    return value or error return (from call_bindings).
Pass 2 — Exception match: assertion is a raises-kind assertion.
Pass 3 — Name/semantic match: assertion references a name that appears in
    the target attribute of a detected side effect.

Output length always equals input length (one entry per assertion).
"""

from __future__ import annotations

import ast

from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.models import AssertionKind, AssertionSite, FunctionTarget


def build_call_bindings(test_func: TestFunc, target_name: str) -> dict[str, str]:
    """Scan the test body for assignments where the RHS calls target_name.

    Binding rules:
    - ``result = target_name(...)``        → {"result": "return_value"}
    - ``x, err = target_name(...)``        → {"x": "return_value", "err": "error_return"}
    - ``a, b, c = target_name(...)``       → {"a": "return_value", "b": "error_return"}
      (index 0 → return_value, index 1 → error_return; indices 2+ ignored)
    - ``target_name(...)`` (void call)     → {} (no binding)

    Args:
        test_func: The test function to scan.
        target_name: The production function name to look for on the RHS.

    Returns:
        Dict mapping variable name → role ("return_value" or "error_return").
    """
    result: dict[str, str] = {}

    for stmt in ast.walk(test_func.node):
        if not isinstance(stmt, ast.Assign):
            continue
        if not _is_call_to(stmt.value, target_name):
            continue

        # Single target: result = target_name(...)
        if len(stmt.targets) == 1:
            _bind_assignment_target(stmt.targets[0], result)

    return result


def _bind_assignment_target(target: ast.expr, result: dict[str, str]) -> None:
    """Populate result with bindings from a single assignment target.

    Handles:
    - ``ast.Name`` → {"name": "return_value"}
    - ``ast.Tuple`` → first element → "return_value", second → "error_return"

    Args:
        target: The LHS assignment target node.
        result: Mutable dict to populate with bindings.
    """
    if isinstance(target, ast.Name):
        result[target.id] = "return_value"
    elif isinstance(target, ast.Tuple):
        for idx, elt in enumerate(target.elts):
            if idx == 0 and isinstance(elt, ast.Name):
                result[elt.id] = "return_value"
            elif idx == 1 and isinstance(elt, ast.Name):
                result[elt.id] = "error_return"
            elif idx >= 2:
                break  # only first two bindings named per spec


def _is_call_to(node: ast.expr, target_name: str) -> bool:
    """Return True if node is a direct call to target_name.

    Args:
        node: The expression node to inspect.
        target_name: The function name to match.

    Returns:
        True when node is ast.Call with func being ast.Name matching target_name.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == target_name
    )


def map_assertions_to_effects(
    assertions: list[AssertionSite],
    target: FunctionTarget,
    call_bindings: dict[str, str],
) -> list[tuple[AssertionSite, SideEffectType | None]]:
    """Map each assertion to the side effect type it most likely exercises.

    Uses three passes in first-match-wins order. Once an assertion is matched
    in an earlier pass, it is not re-evaluated in later passes. This prevents
    double-counting when multiple passes could match the same assertion.

    Output length always equals input length — every assertion gets an entry.

    Pass 1 — Binding match:
        Assertion references a name in call_bindings → ReturnValue or ErrorReturn.
    Pass 2 — Exception match:
        Assertion kind is STDLIB_RAISES or UNITTEST_RAISES → ErrorReturn.
    Pass 3 — Name/semantic match:
        Assertion references a name that appears in a side effect's target field.
        Maps to that effect's type (contractual or incidental).

    Args:
        assertions: All assertion sites from detect_assertions().
        target: The production FunctionTarget with its detected side effects.
        call_bindings: Mapping from variable name → role, from build_call_bindings().

    Returns:
        List of (AssertionSite, SideEffectType | None) tuples, one per assertion.
        None means the assertion could not be mapped to any effect.
    """
    result: list[tuple[AssertionSite, SideEffectType | None]] = []
    matched: set[int] = set()  # indices of already-matched assertions

    _pass1_binding(assertions, call_bindings, result=result, matched=matched)
    _pass2_exception(assertions, result, matched)
    _pass3_semantic(assertions, target, result=result, matched=matched)

    return result


def _pass1_binding(
    assertions: list[AssertionSite],
    call_bindings: dict[str, str],
    *,
    result: list[tuple[AssertionSite, SideEffectType | None]],
    matched: set[int],
) -> None:
    """Pass 1: match assertions whose referenced names appear in call_bindings.

    Args:
        assertions: All assertion sites.
        call_bindings: Variable name → role mapping from build_call_bindings().
        result: Mutable output list to append matched pairs to.
        matched: Mutable set of already-matched assertion indices.
    """
    for i, assertion in enumerate(assertions):
        for name in assertion.referenced_names:
            if name in call_bindings and i not in matched:
                role = call_bindings[name]
                if role == "return_value":
                    result.append((assertion, SideEffectType.ReturnValue))
                elif role == "error_return":
                    result.append((assertion, SideEffectType.ErrorReturn))
                else:
                    result.append((assertion, None))
                matched.add(i)
                break


def _pass2_exception(
    assertions: list[AssertionSite],
    result: list[tuple[AssertionSite, SideEffectType | None]],
    matched: set[int],
) -> None:
    """Pass 2: match raises-kind assertions to ErrorReturn.

    pytest.raises() and self.assertRaises() assert that the target raises an
    exception, which corresponds to the ErrorReturn effect type in the taxonomy.
    (The design.md refers to this as "RaiseException" but the canonical taxonomy
    value is ErrorReturn — the detector emits ErrorReturn for all raise statements.)

    Args:
        assertions: All assertion sites.
        result: Mutable output list to append matched pairs to.
        matched: Mutable set of already-matched assertion indices.
    """
    for i, assertion in enumerate(assertions):
        if i in matched:
            continue
        if assertion.kind in (AssertionKind.STDLIB_RAISES, AssertionKind.UNITTEST_RAISES):
            result.append((assertion, SideEffectType.ErrorReturn))
            matched.add(i)


def _pass3_semantic(
    assertions: list[AssertionSite],
    target: FunctionTarget,
    *,
    result: list[tuple[AssertionSite, SideEffectType | None]],
    matched: set[int],
) -> None:
    """Pass 3: match assertions by name overlap with effect target strings.

    Args:
        assertions: All assertion sites.
        target: The production FunctionTarget with detected side effects.
        result: Mutable output list to append matched pairs to.
        matched: Mutable set of already-matched assertion indices.
    """
    for i, assertion in enumerate(assertions):
        if i in matched:
            continue
        matched_effect: SideEffectType | None = None
        for effect in target.effects:
            if effect.target and any(name in effect.target for name in assertion.referenced_names):
                matched_effect = effect.type  # SideEffect.type (not effect_type)
                break
        result.append((assertion, matched_effect))
        matched.add(i)
