"""Docstring keyword signal analyzer — Signal 5.

Parses the function's docstring for behavioral keywords and returns a signal
based on whether the keyword directly implies the detected effect type (direct
match, +15) or is found but doesn't match the effect type (indirect match, +5).
Incidental keywords produce a negative signal (-15).

Per CC-005 and EC-005: source IDs MUST be 'godoc' and 'godoc_keyword_indirect'
(NOT 'docstring' or 'pydoc') to preserve schema compatibility with Go gaze.

Keyword → effect type mapping follows contracts.md CC-005 and tasks.md 5.4.
"""

from __future__ import annotations

from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.models import Signal

# Contractual keywords and the effect types each directly implies.
# A direct match (keyword implies the specific effect type) → +15, source='godoc'.
# An indirect match (keyword found, effect type not implied) → +5, source='godoc_keyword_indirect'.
_CONTRACTUAL_KEYWORDS: dict[str, frozenset[SideEffectType]] = {
    "returns": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "return": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "mutates": frozenset(
        {
            SideEffectType.ReceiverMutation,
            SideEffectType.PointerArgMutation,
            SideEffectType.SliceMutation,
            SideEffectType.MapMutation,
            SideEffectType.GlobalMutation,
        }
    ),
    "modifies": frozenset(
        {
            SideEffectType.ReceiverMutation,
            SideEffectType.PointerArgMutation,
            SideEffectType.SliceMutation,
            SideEffectType.MapMutation,
            SideEffectType.GlobalMutation,
            SideEffectType.DatabaseWrite,
        }
    ),
    "sets": frozenset(
        {
            SideEffectType.ReceiverMutation,
            SideEffectType.PointerArgMutation,
            SideEffectType.EnvVarMutation,
        }
    ),
    "creates": frozenset(
        {
            SideEffectType.ReturnValue,
            SideEffectType.DatabaseWrite,
            SideEffectType.FileSystemWrite,
        }
    ),
    "deletes": frozenset({SideEffectType.FileSystemDelete, SideEffectType.DatabaseWrite}),
    "writes": frozenset(
        {
            SideEffectType.WriterOutput,
            SideEffectType.HTTPResponseWrite,
            SideEffectType.FileSystemWrite,
            SideEffectType.DatabaseWrite,
            SideEffectType.StdoutWrite,
            SideEffectType.StderrWrite,
        }
    ),
    "persists": frozenset({SideEffectType.DatabaseWrite, SideEffectType.FileSystemWrite}),
    "stores": frozenset({SideEffectType.DatabaseWrite, SideEffectType.FileSystemWrite}),
    "removes": frozenset(
        {
            SideEffectType.FileSystemDelete,
            SideEffectType.SliceMutation,
            SideEffectType.MapMutation,
        }
    ),
    "updates": frozenset(
        {
            SideEffectType.ReceiverMutation,
            SideEffectType.PointerArgMutation,
            SideEffectType.DatabaseWrite,
        }
    ),
    "saves": frozenset({SideEffectType.DatabaseWrite, SideEffectType.FileSystemWrite}),
    "loads": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
}

# Incidental keywords → -15, source='godoc'.
_INCIDENTAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "logs",
        "log",
        "prints",
        "print",
        "debug",
        "trace",
    }
)

_DIRECT_WEIGHT: int = 15
_INDIRECT_WEIGHT: int = 5
_INCIDENTAL_WEIGHT: int = -15


def docstring_signal(
    docstring: str | None,
    effect_type: SideEffectType,
) -> Signal | None:
    """Compute the docstring keyword signal for a function and effect type.

    Scans the docstring for contractual and incidental keywords. For each
    keyword found, determines whether it directly implies the detected effect
    type (direct match → +15) or is present but doesn't match (indirect → +5).
    Incidental keywords produce -15.

    When multiple keywords are found, takes the highest-weight match per
    keyword. The highest-weight signal across all keywords is returned.

    Args:
        docstring: The function's docstring text, or None when absent.
        effect_type: The SideEffectType being classified.

    Returns:
        A Signal with source='godoc' or 'godoc_keyword_indirect', or None
        when no docstring is provided or no keywords are found.
    """
    if not docstring:
        return None

    doc_lower = docstring.lower()
    best: Signal | None = None

    # Check incidental keywords first — they produce negative signals.
    for keyword in _INCIDENTAL_KEYWORDS:
        if keyword in doc_lower:
            candidate = Signal(source="godoc", weight=_INCIDENTAL_WEIGHT)
            if best is None or candidate.weight > best.weight:
                best = candidate

    # Check contractual keywords.
    for keyword, implied_types in _CONTRACTUAL_KEYWORDS.items():
        if keyword not in doc_lower:
            continue

        if effect_type in implied_types:
            # Direct match: keyword implies this specific effect type.
            candidate = Signal(source="godoc", weight=_DIRECT_WEIGHT)
        else:
            # Indirect match: keyword found but doesn't imply this effect type.
            candidate = Signal(source="godoc_keyword_indirect", weight=_INDIRECT_WEIGHT)

        # Take the highest-weight match per keyword (direct beats indirect).
        if best is None or candidate.weight > best.weight:
            best = candidate

    return best
