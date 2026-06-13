"""Interface satisfaction signal analyzer — Signal 1.

Checks whether the function is a method on a class that inherits from ABC or
Protocol. If so, the side effect is strong evidence of contractual behavior.

Per CC-005: weight is +30 when the method satisfies an interface, 0 (no signal)
otherwise.

The class_bases list is extracted from the AST by the caller (ClassificationEngine
receives it as a parameter). This keeps the signal analyzer pure — it does not
perform AST traversal itself.
"""

from __future__ import annotations

from gaze_py.taxonomy.models import Signal

# Base class names that indicate an interface contract.
# Per contracts.md CC-005: Python protocols/ABCs are the language mapping.
_INTERFACE_BASE_NAMES: frozenset[str] = frozenset({"ABC", "Protocol"})

_INTERFACE_WEIGHT: int = 30


def interface_signal(class_bases: list[str] | None) -> Signal | None:
    """Compute the interface satisfaction signal for a method.

    Returns a Signal with weight +30 when the containing class inherits from
    ABC or Protocol. Returns None for standalone functions (no class_bases)
    or methods on plain classes.

    Args:
        class_bases: List of base class names for the containing class, or
            None when the function is not a method (standalone function).
            The list contains simple names as they appear in the class
            definition (e.g., ['ABC', 'SomeMixin']).

    Returns:
        A Signal with source='interface' and weight=30, or None when no
        interface base class is detected.
    """
    if class_bases is None:
        return None

    for base in class_bases:
        if base in _INTERFACE_BASE_NAMES:
            return Signal(source="interface", weight=_INTERFACE_WEIGHT)

    return None
