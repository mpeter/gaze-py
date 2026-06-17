"""Tests for gaze_py.report.ai — subprocess-based AI adapters.

Uses _subprocess_run parameter injection to avoid spawning real subprocesses.
All tests are isolated: no network calls, no binary dependencies.
"""

from __future__ import annotations

import subprocess
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gaze_py.report.ai import call_ai


def _make_completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> CompletedProcess[str]:
    """Build a CompletedProcess for use as a mock return value."""
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# opencode adapter
# ---------------------------------------------------------------------------


def test_call_ai_opencode_success() -> None:
    """call_ai with opencode provider returns stdout from subprocess."""
    mock_run = MagicMock(return_value=_make_completed(stdout="report text\n"))

    with patch("gaze_py.report.ai.shutil.which", return_value="/usr/bin/opencode"):
        result = call_ai(
            "prompt",
            "payload",
            provider="opencode",
            _subprocess_run=mock_run,
        )

    assert result == "report text"


def test_call_ai_opencode_with_model() -> None:
    """call_ai with opencode and --model passes --model flag in subprocess args."""
    mock_run = MagicMock(return_value=_make_completed(stdout="ok"))

    with patch("gaze_py.report.ai.shutil.which", return_value="/usr/bin/opencode"):
        call_ai(
            "prompt",
            "payload",
            provider="opencode",
            model="claude-3-opus",
            _subprocess_run=mock_run,
        )

    call_args = mock_run.call_args[0][0]  # positional list arg
    assert "--model" in call_args
    assert "claude-3-opus" in call_args


# ---------------------------------------------------------------------------
# ollama adapter
# ---------------------------------------------------------------------------


def test_call_ai_ollama_requires_model() -> None:
    """call_ai with ollama and model=None raises ClickException mentioning 'model'.

    LOW-2 fix: the shutil.which patch was removed — model=None raises before
    the binary check is reached, so patching which() was dead code.
    """
    import click

    with pytest.raises(click.ClickException) as exc_info:
        call_ai("prompt", "payload", provider="ollama", model=None)

    assert "model" in str(exc_info.value.format_message()).lower()


# ---------------------------------------------------------------------------
# Provider not found
# ---------------------------------------------------------------------------


def test_call_ai_provider_not_found() -> None:
    """call_ai raises ClickException when the provider binary is not found."""
    import click

    with patch("gaze_py.report.ai.shutil.which", return_value=None):
        with pytest.raises(click.ClickException) as exc_info:
            call_ai("prompt", "payload", provider="opencode")

    # Should mention the binary or an install hint.
    assert "opencode" in str(exc_info.value.format_message()).lower()


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


def test_call_ai_timeout() -> None:
    """call_ai raises ClickException mentioning 'timed out' on TimeoutExpired."""
    import click

    def _raise_timeout(*args: Any, **kwargs: Any) -> CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=[], timeout=30)

    with patch("gaze_py.report.ai.shutil.which", return_value="/usr/bin/opencode"):
        with pytest.raises(click.ClickException) as exc_info:
            call_ai("prompt", "payload", provider="opencode", _subprocess_run=_raise_timeout)

    assert "timed out" in str(exc_info.value.format_message()).lower()


# ---------------------------------------------------------------------------
# Non-zero exit
# ---------------------------------------------------------------------------


def test_call_ai_nonzero_exit() -> None:
    """call_ai raises ClickException containing stderr on non-zero returncode."""
    import click

    mock_run = MagicMock(return_value=_make_completed(returncode=1, stderr="err msg"))

    with patch("gaze_py.report.ai.shutil.which", return_value="/usr/bin/opencode"):
        with pytest.raises(click.ClickException) as exc_info:
            call_ai("prompt", "payload", provider="opencode", _subprocess_run=mock_run)

    assert "err msg" in str(exc_info.value.format_message())


# ---------------------------------------------------------------------------
# Unknown provider
# ---------------------------------------------------------------------------


def test_call_ai_unknown_provider() -> None:
    """call_ai raises ClickException for an unknown provider name."""
    import click

    with pytest.raises(click.ClickException) as exc_info:
        call_ai("prompt", "payload", provider="unknown")

    assert "unknown" in str(exc_info.value.format_message()).lower()
