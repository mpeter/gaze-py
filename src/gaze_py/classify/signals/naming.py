"""Naming convention signal analyzer — Signal 4.

Checks the function name against contractual and incidental naming prefixes.
Returns a Signal with weight +10 (contractual prefix, implied effect type),
+30 (sentinel special case), or -10 (incidental prefix).

Per CC-005: the contractual prefix signal fires ONLY when the effect type is
implied by the prefix. For example, 'Get*' implies ReturnValue — it does NOT
fire for a LogWrite effect on a function named 'GetUser'.
"""

from __future__ import annotations

from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.models import Signal

# Contractual prefixes and the effect types each implies.
# A prefix with an empty set implies ALL effect types (fires for any effect).
# Per contracts.md CC-005 and tasks.md 5.2.
CONTRACTUAL_PREFIXES: dict[str, frozenset[SideEffectType]] = {
    "Get": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Fetch": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Load": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Read": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Save": frozenset(
        {
            SideEffectType.ReceiverMutation,
            SideEffectType.PointerArgMutation,
            SideEffectType.ErrorReturn,
            SideEffectType.DatabaseWrite,
            SideEffectType.FileSystemWrite,
        }
    ),
    "Write": frozenset(
        {
            SideEffectType.WriterOutput,
            SideEffectType.HTTPResponseWrite,
            SideEffectType.FileSystemWrite,
            SideEffectType.DatabaseWrite,
            SideEffectType.ErrorReturn,
        }
    ),
    "Update": frozenset(
        {
            SideEffectType.ReceiverMutation,
            SideEffectType.PointerArgMutation,
            SideEffectType.DatabaseWrite,
            SideEffectType.ErrorReturn,
        }
    ),
    "Set": frozenset(
        {
            SideEffectType.ReceiverMutation,
            SideEffectType.PointerArgMutation,
            SideEffectType.ErrorReturn,
        }
    ),
    "Delete": frozenset(
        {
            SideEffectType.FileSystemDelete,
            SideEffectType.DatabaseWrite,
            SideEffectType.ErrorReturn,
        }
    ),
    "Remove": frozenset(
        {
            SideEffectType.FileSystemDelete,
            SideEffectType.SliceMutation,
            SideEffectType.MapMutation,
            SideEffectType.ErrorReturn,
        }
    ),
    "Create": frozenset(
        {
            SideEffectType.ReturnValue,
            SideEffectType.DatabaseWrite,
            SideEffectType.FileSystemWrite,
            SideEffectType.ErrorReturn,
        }
    ),
    "New": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Open": frozenset(
        {
            SideEffectType.ReturnValue,
            SideEffectType.FileSystemWrite,
            SideEffectType.ErrorReturn,
        }
    ),
    "Close": frozenset(
        {
            SideEffectType.ChannelClose,
            SideEffectType.ErrorReturn,
        }
    ),
    "Start": frozenset(
        {
            SideEffectType.GoroutineSpawn,
            SideEffectType.ErrorReturn,
        }
    ),
    "Stop": frozenset(
        {
            SideEffectType.ContextCancellation,
            SideEffectType.ErrorReturn,
        }
    ),
    # Broad prefixes — fire for any effect type (empty set = all)
    "Handle": frozenset(),
    "Process": frozenset(),
    "Compute": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Analyze": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Classify": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Parse": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
    "Build": frozenset({SideEffectType.ReturnValue, SideEffectType.ErrorReturn}),
}

# Incidental prefixes — fire for any effect type with weight -10.
# Per contracts.md CC-005 and tasks.md 5.2.
INCIDENTAL_PREFIXES: frozenset[str] = frozenset(
    {
        "log",
        "Log",
        "print",
        "Print",
        "debug",
        "Debug",
        "trace",
        "Trace",
        "warn",
        "Warn",
    }
)

_CONTRACTUAL_WEIGHT: int = 10
_INCIDENTAL_WEIGHT: int = -10
_SENTINEL_WEIGHT: int = 30

# Sentinel name patterns: ends with "Error" or "Err", or starts with "Err".
_SENTINEL_SUFFIXES: tuple[str, ...] = ("Error", "Err")
_SENTINEL_PREFIX: str = "Err"


def naming_signal(
    func_name: str,
    effect_type: SideEffectType,
) -> Signal | None:
    """Compute the naming convention signal for a function and effect type.

    Checks the function name against contractual and incidental prefix tables.
    The sentinel special case (+30) fires when the effect is SentinelError AND
    the name ends with 'Error'/'Err' or starts with 'Err'.

    The contractual prefix signal (+10) fires ONLY when the effect type is
    implied by the prefix. An empty implied-types set means the prefix fires
    for all effect types.

    Args:
        func_name: Simple function or class name (not qualified).
        effect_type: The SideEffectType being classified.

    Returns:
        A Signal with source='naming' and the appropriate weight, or None
        when no naming convention applies.
    """
    # Sentinel special case: SentinelError + Err*/Error* name → +30.
    # This takes priority over all other naming checks.
    if effect_type is SideEffectType.SentinelError:
        if func_name.startswith(_SENTINEL_PREFIX) or any(
            func_name.endswith(suffix) for suffix in _SENTINEL_SUFFIXES
        ):
            return Signal(source="naming", weight=_SENTINEL_WEIGHT)

    # Incidental prefix check: fires for any effect type.
    for prefix in INCIDENTAL_PREFIXES:
        if func_name.startswith(prefix):
            return Signal(source="naming", weight=_INCIDENTAL_WEIGHT)

    # Contractual prefix check: fires only when effect type is implied.
    for prefix, implied_types in CONTRACTUAL_PREFIXES.items():
        if func_name.startswith(prefix):
            # Empty implied_types set means the prefix fires for all effect types.
            if not implied_types or effect_type in implied_types:
                return Signal(source="naming", weight=_CONTRACTUAL_WEIGHT)
            # Prefix matched but effect type not implied — no signal.
            return None

    return None
