"""API visibility signal analyzer — Signal 2.

Checks whether the function and its types are part of the public API surface.
Three independent dimensions contribute:
  - Exported function name (+8): no leading underscore
  - Exported return type annotation (+6): not None, not starting with '_'
  - Exported receiver/class name (+6): not starting with '_'

Total is clamped to +20 per CC-005.

Per contracts.md CC-005: Python exported names are those without a leading
underscore (no __all__ inspection required — underscore convention is the
canonical Python visibility marker).
"""

from __future__ import annotations

from gaze_py.taxonomy.models import Signal

_FUNC_WEIGHT: int = 8
_RETURN_TYPE_WEIGHT: int = 6
_RECEIVER_WEIGHT: int = 6
_MAX_WEIGHT: int = 20


def visibility_signal(
    func_name: str,
    *,
    return_type_hint: str | None = None,
    receiver_name: str | None = None,
) -> Signal | None:
    """Compute the API visibility signal for a function.

    Adds weights for each public dimension (no leading underscore):
    - Public function name: +8
    - Public return type annotation: +6
    - Public receiver/class name: +6

    Total is clamped to +20. Returns None when the function is private
    (leading underscore) — a private function contributes no visibility signal.

    Args:
        func_name: Simple function name (not qualified). A leading underscore
            marks the function as private.
        return_type_hint: String representation of the return type annotation,
            or None when no annotation is present. 'None' (the string) and
            names starting with '_' are treated as non-public.
        receiver_name: Name of the containing class (receiver type), or None
            for standalone functions. Names starting with '_' are non-public.

    Returns:
        A Signal with source='visibility' and weight in [8, 20], or None when
        the function is private (no visibility contribution).
    """
    # A private function contributes nothing — return None immediately.
    if func_name.startswith("_"):
        return None

    total = _FUNC_WEIGHT  # public function name: +8

    if return_type_hint is not None and _is_public_type(return_type_hint):
        total += _RETURN_TYPE_WEIGHT

    if receiver_name is not None and not receiver_name.startswith("_"):
        total += _RECEIVER_WEIGHT

    # Clamp to maximum allowed weight.
    clamped = min(total, _MAX_WEIGHT)
    return Signal(source="visibility", weight=clamped)


def _is_public_type(type_hint: str) -> bool:
    """Return True when a type hint string represents a public (exported) type.

    A type is considered non-public when:
    - It is the literal string 'None' (no meaningful return type)
    - Its first non-whitespace character is '_' (private name)

    Args:
        type_hint: String representation of a type annotation.

    Returns:
        True when the type is considered public/exported.
    """
    stripped = type_hint.strip()
    if stripped == "None":
        return False
    # Check the first identifier component for a leading underscore.
    # Handles simple names ('_Private'), unions ('_Private | None'), etc.
    first_token = stripped.split()[0].lstrip("(")
    return not first_token.startswith("_")
