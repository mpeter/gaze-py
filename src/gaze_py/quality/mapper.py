"""A.3 — Assertion-to-effect mapping for the O1 quality assessment pipeline.

Maps each assertion site to the side effect type it most likely exercises,
using first-match-wins precedence:

Context-aware evidence — one ordered analyzer owns live return roles and
    captured-stream provenance. Explicitly blocked capture evidence wins.
Exception match — assertion is a raises-kind assertion.
Name/semantic match — assertion references a name that appears in the target
    attribute of a detected side effect.

Callers without test AST context retain the legacy binding pass before exception
and semantic matching.

Output length always equals input length (one entry per assertion).
"""

from __future__ import annotations

import ast
from pathlib import Path

from gaze_py.quality.capture import _map_assertion_evidence
from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.models import AssertionKind, AssertionSite, FunctionTarget


def build_call_bindings(test_func: TestFunc, target_name: str) -> dict[str, str]:
    """Scan the test body for assignments where the RHS calls target_name.

    Binding rules:
    - ``result = target_name(...)``        → {"result": "return_value"}
    - ``result: T = target_name(...)``     → {"result": "return_value"}
    - ``x, err = target_name(...)``        → {"x": "return_value", "err": "error_return"}
    - ``a, b, c = target_name(...)``       → {"a": "return_value", "b": "error_return"}
      (index 0 → return_value, index 1 → error_return; indices 2+ ignored)
    - ``target_name(...)`` (void call)     → {} (no binding)

    Matches both plain calls (``target_name(...)``) and module-aliased calls
    (``alias.target_name(...)``). Also handles annotated assignments
    (``ast.AnnAssign``) in addition to plain assignments (``ast.Assign``).

    Args:
        test_func: The test function to scan.
        target_name: The production function name to look for on the RHS.

    Returns:
        Dict mapping variable name → role ("return_value" or "error_return").
    """
    result: dict[str, str] = {}

    for stmt in ast.walk(test_func.node):
        if isinstance(stmt, ast.Assign):
            if not _is_call_to(stmt.value, target_name):
                continue
            # Single target: result = target_name(...)
            if len(stmt.targets) == 1:
                _bind_assignment_target(stmt.targets[0], result)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            if not _is_call_to(stmt.value, target_name):
                continue
            # Annotated assignment: result: T = target_name(...)
            # AnnAssign.target is always a single Name (no tuple unpacking).
            _bind_assignment_target(stmt.target, result)

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
    """Return True if node is a call to target_name (plain or module-aliased).

    Matches both ``target_name(...)`` (plain ``ast.Name`` call) and
    ``alias.target_name(...)`` (``ast.Attribute`` call where the attribute
    name matches ``target_name``).

    Args:
        node: The expression node to inspect.
        target_name: The function name to match.

    Returns:
        True when node is an ast.Call whose function name matches target_name.
    """
    if not isinstance(node, ast.Call):
        return False
    # Plain call: target_name(...)
    if isinstance(node.func, ast.Name) and node.func.id == target_name:
        return True
    # Module-aliased call: alias.target_name(...)
    if isinstance(node.func, ast.Attribute) and node.func.attr == target_name:
        return True
    return False


def map_assertions_to_effects(
    assertions: list[AssertionSite],
    target: FunctionTarget,
    call_bindings: dict[str, str],
    *,
    test_func: TestFunc | None = None,
    target_path: Path | None = None,
    import_root: Path | None = None,
) -> list[tuple[AssertionSite, SideEffectType | None]]:
    """Map each assertion to the side effect type it most likely exercises.

    Uses first-match-wins precedence. Once an assertion is matched
    in an earlier pass, it is not re-evaluated in later passes. This prevents
    double-counting when multiple passes could match the same assertion.

    Output length always equals input length — every assertion gets an entry.

    Context-aware evidence:
        Ordered live return roles and capture provenance, including blocked evidence.
        Without test_func, legacy call_bindings provide ReturnValue or ErrorReturn.
    Exception match:
        Assertion kind is STDLIB_RAISES or UNITTEST_RAISES → ErrorReturn.
    Name/semantic match:
        Assertion references a name that appears in a side effect's target field.
        Maps to that effect's type (contractual or incidental).

    Args:
        assertions: All assertion sites from detect_assertions().
        target: The production FunctionTarget with its detected side effects.
        call_bindings: Mapping from variable name → role, from build_call_bindings().
        test_func: Optional AST context for ordered capture provenance.
        target_path: Exact production file path for qualified-call identity.
        import_root: Authoritative root for the target's canonical module name.

    Returns:
        List of (AssertionSite, SideEffectType | None) tuples, one per assertion.
        None means the assertion could not be mapped to any effect.
    """
    result: list[tuple[AssertionSite, SideEffectType | None]] = []
    matched: set[int] = set()  # indices of already-matched assertions

    if test_func is None:
        _pass1_binding(assertions, call_bindings, result=result, matched=matched)
    else:
        _pass_ordered_evidence(
            assertions,
            target,
            test_func,
            target_path=target_path,
            import_root=import_root,
            result=result,
            matched=matched,
        )
    _pass2_exception(assertions, result, matched)
    _pass3_semantic(assertions, target, result=result, matched=matched)

    return result


def _pass_ordered_evidence(
    assertions: list[AssertionSite],
    target: FunctionTarget,
    test_func: TestFunc,
    *,
    target_path: Path | None,
    import_root: Path | None,
    result: list[tuple[AssertionSite, SideEffectType | None]],
    matched: set[int],
) -> None:
    """Map assertion-time return roles and captured-stream provenance."""
    evidence = _map_assertion_evidence(
        test_func,
        target.function,
        target_path=target_path,
        import_root=import_root,
        receiver=target.receiver,
    )
    available_effects = {effect.type for effect in target.effects}
    for index, assertion in enumerate(assertions):
        if index in matched or assertion.depth != 0:
            continue
        position = _assertion_position(assertion.location, test_func.filename)
        if position is None:
            continue
        if position not in evidence:
            continue
        effect_type = evidence[position]
        result.append((assertion, effect_type if effect_type in available_effects else None))
        matched.add(index)


def _assertion_position(location: str, expected_filename: str) -> tuple[int, int] | None:
    """Extract a same-file line/column suffix, tolerating legacy locations."""
    parts = location.rsplit(":", maxsplit=2)
    if len(parts) != 3 or parts[0] != expected_filename:
        return None
    if not parts[1].isdigit() or not parts[2].isdigit():
        return None
    return int(parts[1]), int(parts[2])


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
