"""Subprocess-based AI adapters for gazepy report.

Provides call_ai() which dispatches to one of three subprocess
adapters: opencode, ollama, or claude CLI. No Python SDK
dependencies — each adapter shells out to an external binary.

The _subprocess_run parameter is injectable for testing.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, cast

import click


def call_ai(
    prompt: str,
    payload: str,
    *,
    provider: str,
    model: str | None = None,
    timeout: int = 120,
    _subprocess_run: Any = subprocess.run,
) -> str:
    """Call an AI provider via subprocess and return the response.

    Args:
        prompt: System/instruction prompt (from gaze-reporter.md).
        payload: Analysis JSON to interpret.
        provider: One of "opencode", "ollama", "claude".
        model: Provider-specific model identifier. Required for
            ollama. Optional for opencode (uses configured default)
            and claude (uses API default).
        timeout: Subprocess timeout in seconds.
        _subprocess_run: Injection point for testing (default:
            subprocess.run).

    Returns:
        AI response text.

    Raises:
        click.ClickException: Provider binary not found, subprocess
            failed, or timed out.
    """
    match provider:
        case "opencode":
            return _call_opencode(prompt, payload, model, timeout, _subprocess_run)
        case "ollama":
            return _call_ollama(prompt, payload, model, timeout, _subprocess_run)
        case "claude":
            return _call_claude(prompt, payload, model, timeout, _subprocess_run)
        case _:
            raise click.ClickException(
                f"Unknown AI provider: {provider!r}. Supported: opencode, ollama, claude."
            )


def _call_opencode(
    prompt: str,
    payload: str,
    model: str | None,
    timeout: int,
    _subprocess_run: Any,
) -> str:
    """Call opencode run with the combined prompt and payload.

    Uses subprocess list form (never shell=True) per D4.
    Passes prompt+payload as a single positional argument.

    Args:
        prompt: System/instruction prompt.
        payload: Analysis JSON to interpret.
        model: Model identifier, or None to use opencode's configured default.
        timeout: Subprocess timeout in seconds.
        _subprocess_run: Injection point for testing.

    Returns:
        opencode response text (stdout, stripped).

    Raises:
        click.ClickException: Binary not found, timed out, or non-zero exit.
    """
    if shutil.which("opencode") is None:
        raise click.ClickException(
            "opencode binary not found. Install it with: npm install -g opencode-ai"
        )

    combined = f"{prompt}\n\n{payload}"
    cmd: list[str] = ["opencode", "run"]
    if model is not None:
        cmd += ["--model", model]
    # opencode run takes `message` as a positional array argument (not stdin).
    # `opencode run --help` confirms: "message  message to send [array]".
    # Unlike ollama, opencode does not read from stdin, so we pass the combined
    # prompt+payload as a single positional argument. This is the correct
    # invocation pattern for the opencode CLI.
    cmd.append(combined)

    try:
        result = _subprocess_run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise click.ClickException(
            f"opencode timed out after {timeout}s — try --ai-timeout with a larger value"
        ) from exc

    if result.returncode != 0:
        raise click.ClickException(f"opencode failed (exit {result.returncode}): {result.stderr}")

    return cast(str, result.stdout).strip()


def _call_ollama(
    prompt: str,
    payload: str,
    model: str | None,
    timeout: int,
    _subprocess_run: Any,
) -> str:
    """Call ollama run with prompt+payload via stdin.

    Uses subprocess list form (never shell=True) per D4.
    Model is required for ollama — raises ClickException when None.

    Args:
        prompt: System/instruction prompt.
        payload: Analysis JSON to interpret.
        model: Model identifier (required for ollama).
        timeout: Subprocess timeout in seconds.
        _subprocess_run: Injection point for testing.

    Returns:
        ollama response text (stdout, stripped).

    Raises:
        click.ClickException: model is None, binary not found, timed out,
            or non-zero exit.
    """
    if model is None:
        raise click.ClickException(
            "ollama requires a model name. Pass --model <model> (e.g. --model llama3)."
        )

    if shutil.which("ollama") is None:
        raise click.ClickException("ollama binary not found. Install it from: https://ollama.com")

    combined = f"{prompt}\n\n{payload}"
    cmd = ["ollama", "run", model]

    try:
        result = _subprocess_run(
            cmd,
            input=combined,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise click.ClickException(
            f"ollama timed out after {timeout}s — try --ai-timeout with a larger value"
        ) from exc

    if result.returncode != 0:
        raise click.ClickException(f"ollama failed (exit {result.returncode}): {result.stderr}")

    return cast(str, result.stdout).strip()


def _call_claude(
    _prompt: str,
    _payload: str,
    _model: str | None,
    _timeout: int,
    _subprocess_run: Any,
) -> str:
    """Raise ClickException — claude adapter is deferred to Change 4B.

    The Anthropic CLI's invocation interface is not yet stable enough to
    specify correctly. No binary check is performed; the error is raised
    immediately.

    Args:
        _prompt: Unused (deferred).
        _payload: Unused (deferred).
        _model: Unused (deferred).
        _timeout: Unused (deferred).
        _subprocess_run: Unused (deferred).

    Raises:
        click.ClickException: Always — adapter not yet implemented.
    """
    raise click.ClickException(
        "claude adapter is available in Change 4B. Use --ai opencode or --ai ollama."
    )
