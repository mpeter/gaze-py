"""Tests for quality/hints.py — hint_for_effect() pure function.

Per CR-007: all assertions directly reference the variable bound to the
production function's return value (result = hint_for_effect(...); assert result ...).
"""

from __future__ import annotations

import pytest

from gaze_py.quality.hints import hint_for_effect
from gaze_py.taxonomy.effects import TIER_MAP, SideEffectType
from gaze_py.taxonomy.models import SideEffect

# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------


def _make_effect(effect_type: SideEffectType) -> SideEffect:
    """Create a minimal SideEffect for the given type."""
    return SideEffect(
        id="se-00000000",
        type=effect_type,
        tier=TIER_MAP[effect_type],
        location="test.py:1:0",
        description="test",
        target="test_func",
    )


# ---------------------------------------------------------------------------
# Tailored hint tests — P0
# ---------------------------------------------------------------------------


def test_hint_for_return_value() -> None:
    """ReturnValue hint contains 'result' and 'assert'."""
    result = hint_for_effect(_make_effect(SideEffectType.ReturnValue))
    assert "result" in result
    assert "assert" in result


def test_hint_for_error_return() -> None:
    """ErrorReturn hint contains 'pytest.raises'."""
    result = hint_for_effect(_make_effect(SideEffectType.ErrorReturn))
    assert "pytest.raises" in result


def test_hint_for_sentinel_error() -> None:
    """SentinelError hint contains 'pytest.raises'."""
    result = hint_for_effect(_make_effect(SideEffectType.SentinelError))
    assert "pytest.raises" in result


def test_hint_for_receiver_mutation() -> None:
    """ReceiverMutation hint contains 'assert'."""
    result = hint_for_effect(_make_effect(SideEffectType.ReceiverMutation))
    assert "assert" in result


def test_hint_for_pointer_arg_mutation() -> None:
    """PointerArgMutation hint contains 'assert'."""
    result = hint_for_effect(_make_effect(SideEffectType.PointerArgMutation))
    assert "assert" in result


# ---------------------------------------------------------------------------
# Tailored hint tests — P1
# ---------------------------------------------------------------------------


def test_hint_for_writer_output() -> None:
    """WriterOutput hint contains 'BytesIO' or 'buf'."""
    result = hint_for_effect(_make_effect(SideEffectType.WriterOutput))
    assert "BytesIO" in result or "buf" in result


# ---------------------------------------------------------------------------
# Tailored hint tests — P2
# ---------------------------------------------------------------------------


def test_hint_for_filesystem_write() -> None:
    """FileSystemWrite hint contains 'Path' or 'exists'."""
    result = hint_for_effect(_make_effect(SideEffectType.FileSystemWrite))
    assert "Path" in result or "exists" in result


def test_hint_for_callback_invocation() -> None:
    """CallbackInvocation hint contains 'Mock' or 'assert_called'."""
    result = hint_for_effect(_make_effect(SideEffectType.CallbackInvocation))
    assert "Mock" in result or "assert_called" in result


def test_hint_for_log_write() -> None:
    """LogWrite hint contains 'caplog'."""
    result = hint_for_effect(_make_effect(SideEffectType.LogWrite))
    assert "caplog" in result


# ---------------------------------------------------------------------------
# Tailored hint tests — P3 exceptions
# ---------------------------------------------------------------------------


def test_hint_for_stdout_write() -> None:
    """StdoutWrite hint contains 'capsys'."""
    result = hint_for_effect(_make_effect(SideEffectType.StdoutWrite))
    assert "capsys" in result


def test_hint_for_stderr_write() -> None:
    """StderrWrite hint contains 'capsys'."""
    result = hint_for_effect(_make_effect(SideEffectType.StderrWrite))
    assert "capsys" in result


def test_hint_for_process_exit() -> None:
    """ProcessExit hint contains 'SystemExit'."""
    result = hint_for_effect(_make_effect(SideEffectType.ProcessExit))
    assert "SystemExit" in result


# ---------------------------------------------------------------------------
# Exhaustive coverage — all 38 types must return non-empty strings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("effect_type", list(SideEffectType))
def test_hint_for_all_38_types_non_empty(effect_type: SideEffectType) -> None:
    """hint_for_effect() returns a non-empty string for every SideEffectType.

    Guards against missing match arms and empty-string returns.
    Parametrized over all 38 SideEffectType values (EC-001).
    """
    result = hint_for_effect(_make_effect(effect_type))
    assert result, f"hint_for_effect returned empty string for {effect_type!r}"
    assert isinstance(result, str)
