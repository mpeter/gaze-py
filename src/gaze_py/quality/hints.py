"""Assertion hint generator for uncovered contractual side effects.

Port of Go gaze internal/quality/hints.go:hintForEffect.
Maps each of the 38 SideEffectType values to a Python assertion snippet
that a developer can paste into a test to cover the gap.

Per EC-001: all 38 SideEffectType values MUST be handled — no fall-through
to empty string. The match statement covers P0/P1/P2 with tailored hints,
P3 exceptions (StdoutWrite, StderrWrite, ProcessExit) with tailored hints,
and all remaining P3/P4 types with a generic fallback.
"""

from __future__ import annotations

from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.models import SideEffect


def hint_for_effect(effect: SideEffect) -> str:  # noqa: PLR0911, PLR0912
    """Return a Python assertion snippet for an uncovered contractual effect.

    Port of Go gaze internal/quality/hints.go:hintForEffect.
    P0/P1 effects receive tailored Python-idiomatic hints.
    P2 effects receive semi-tailored hints.
    P3/P4 effects receive a generic fallback, except ProcessExit,
    StdoutWrite, and StderrWrite which receive tailored hints.

    The PLR0911/PLR0912 suppressions are intentional: this function is a
    pure dispatch table over all 38 SideEffectType values (EC-001). Each
    match arm is a single return — there is no logic to extract. Splitting
    into sub-functions would obscure the one-to-one mapping that makes this
    function easy to audit against the Go port.

    Args:
        effect: The SideEffect with no mapped assertion (a gap).

    Returns:
        A short, pasteable Python snippet suggesting how to write
        an assertion for this effect. Always a non-empty string.
    """
    match effect.type:
        # P0 — Must Detect
        case SideEffectType.ReturnValue:
            return "result = target(...)\nassert result == expected"
        case SideEffectType.ErrorReturn:
            return "with pytest.raises(ExceptionType):\n    target(...)"
        case SideEffectType.SentinelError:
            return "with pytest.raises(SpecificError):\n    target(...)"
        case SideEffectType.ReceiverMutation:
            return "target(obj, ...)\n# assert obj.<attr> changed"
        case SideEffectType.PointerArgMutation:
            return "target(arg, ...)\n# assert arg was mutated"
        # P1 — High Value
        case SideEffectType.SliceMutation:
            return "target(items, ...)\n# assert items contains expected values"
        case SideEffectType.MapMutation:
            return "target(mapping, ...)\n# assert mapping[key] == expected"
        case SideEffectType.GlobalMutation:
            return "target(...)\n# assert module.global_name == expected"
        case SideEffectType.WriterOutput:
            return "buf = io.BytesIO()\ntarget(buf, ...)\nassert buf.getvalue() == expected"
        case SideEffectType.HTTPResponseWrite:
            return "# assert HTTP response status and body after target()"
        case SideEffectType.ChannelSend:
            return "# assert value was sent to channel/queue after target()"
        case SideEffectType.ChannelClose:
            return "# assert channel/queue is closed/exhausted after target()"
        case SideEffectType.DeferredReturnMutation:
            return "result = target(...)\n# assert result (named return via captured value)"
        # P2 — Important
        case SideEffectType.FileSystemWrite:
            return "target(...)\nassert Path(expected_path).exists()"
        case SideEffectType.FileSystemDelete:
            return "target(...)\nassert not Path(expected_path).exists()"
        case SideEffectType.FileSystemMeta:
            return "target(...)\n# assert file metadata (permissions, mtime) changed"
        case SideEffectType.DatabaseWrite:
            return "target(...)\n# assert db record exists/changed after call"
        case SideEffectType.DatabaseTransaction:
            return "target(...)\n# assert transaction committed or rolled back"
        case SideEffectType.GoroutineSpawn:
            return "# assert thread/task was spawned after target()"
        case SideEffectType.Panic:
            return "with pytest.raises((SystemExit, Exception)):\n    target(...)"
        case SideEffectType.CallbackInvocation:
            return "cb = Mock()\ntarget(cb, ...)\ncb.assert_called()"
        case SideEffectType.LogWrite:
            return (
                "with caplog.at_level(logging.DEBUG):\n"
                "    target(...)\n"
                "assert 'expected' in caplog.text"
            )
        case SideEffectType.ContextCancellation:
            return "# assert context/event was cancelled after target()"
        # P3 — tailored exceptions (rest fall through to generic)
        case SideEffectType.StdoutWrite:
            return "out, _ = capsys.readouterr()\nassert 'expected' in out"
        case SideEffectType.StderrWrite:
            return "_, err = capsys.readouterr()\nassert 'expected' in err"
        case SideEffectType.ProcessExit:
            return (
                "with pytest.raises(SystemExit) as exc_info:\n"
                "    target(...)\n"
                "assert exc_info.value.code == expected"
            )
        # P3/P4 — generic fallback
        case _:
            return f"# assert {effect.type.value} side effect of target()"
