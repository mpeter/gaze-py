"""Tests for gaze_py.report.ai — HTTP-based AI synthesizer implementations.

Uses _http_open, _gcloud, _clock, and _sleep parameter injection to avoid
real network calls, subprocess invocations, or timing dependencies.

Mock shape for _http_open:
    A callable that returns a context-manager with:
    - .status: int
    - .read() -> bytes
    - .getheader(name: str) -> str | None

For connection errors, _http_open raises urllib.error.URLError.
"""

from __future__ import annotations

import json
import urllib.error
from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock

import click
import pytest

from gaze_py.report.ai import (
    NoopSynthesizer,
    OllamaSynthesizer,
    Synthesizer,
    VertexSynthesizer,
)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_http_response(
    status: int,
    body: bytes,
    headers: dict[str, str] | None = None,
) -> Any:
    """Build a mock HTTP response context-manager.

    The returned object supports:
    - .status: int
    - .read() -> bytes
    - .getheader(name: str) -> str | None

    Args:
        status: HTTP status code.
        body: Raw response body bytes.
        headers: Optional dict of response headers.

    Returns:
        A MagicMock configured as a context-manager response.
    """
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    _headers = headers or {}
    resp.getheader.side_effect = _headers.get
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _make_http_open(
    status: int,
    body: bytes,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build a _http_open mock that returns one fixed response.

    Args:
        status: HTTP status code.
        body: Raw response body bytes.
        headers: Optional response headers dict.

    Returns:
        A callable mock that returns the configured response as a context-manager.
    """
    resp = _make_http_response(status, body, headers)
    return MagicMock(return_value=resp)


def _make_http_open_sequence(
    responses: list[tuple[int, bytes, dict[str, str] | None]],
) -> MagicMock:
    """Build a _http_open mock that cycles through a sequence of responses.

    Args:
        responses: List of (status, body, headers) tuples, consumed in order.

    Returns:
        A callable mock whose side_effect yields each response in turn.
    """
    resps = [_make_http_response(s, b, h) for s, b, h in responses]
    return MagicMock(side_effect=resps)


def _make_gcloud_ok(
    token: str = "tok",
) -> MagicMock:
    """Build a _gcloud mock that returns a successful token response.

    gcloud auth print-access-token returns a plain token string (not JSON).

    Args:
        token: The access token string.

    Returns:
        A callable mock returning CompletedProcess with the plain token string.
    """
    return MagicMock(return_value=CompletedProcess(args=[], returncode=0, stdout=token, stderr=""))


def _make_vertex_200(text: str = "synthesized text") -> tuple[int, bytes, None]:
    """Build a Vertex AI HTTP 200 response tuple.

    Args:
        text: The text content to embed in the Anthropic Messages response.

    Returns:
        Tuple of (200, body_bytes, None) for use with _make_http_open_sequence.
    """
    body = json.dumps({"content": [{"type": "text", "text": text}]}).encode()
    return (200, body, None)


def _make_vertex_429(
    retry_after: str | None = None,
) -> tuple[int, bytes, dict[str, str] | None]:
    """Build a Vertex AI HTTP 429 response tuple.

    Args:
        retry_after: Optional Retry-After header value.

    Returns:
        Tuple of (429, body_bytes, headers_or_None).
    """
    body = b'{"error": "rate limited"}'
    headers: dict[str, str] | None = (
        {"Retry-After": retry_after} if retry_after is not None else None
    )
    return (429, body, headers)


# ---------------------------------------------------------------------------
# NoopSynthesizer
# ---------------------------------------------------------------------------


class TestNoopSynthesizer:
    """Tests for NoopSynthesizer — the exported test double."""

    def test_happy_path_returns_response(self) -> None:
        """NoopSynthesizer(response='ok').synthesize() returns 'ok'."""
        noop = NoopSynthesizer(response="ok")
        result = noop.synthesize("any prompt")
        assert result == "ok"

    def test_error_path_raises_err(self) -> None:
        """NoopSynthesizer(err=ClickException('boom')).synthesize() raises the error."""
        noop = NoopSynthesizer(err=click.ClickException("boom"))
        with pytest.raises(click.ClickException) as exc_info:
            noop.synthesize("any prompt")
        assert "boom" in exc_info.value.format_message()

    def test_available_returns_avail_true(self) -> None:
        """NoopSynthesizer.available() returns True when avail=True."""
        assert NoopSynthesizer(avail=True).available() is True

    def test_available_returns_avail_false(self) -> None:
        """NoopSynthesizer.available() returns False when avail=False."""
        assert NoopSynthesizer(avail=False).available() is False

    def test_model_id_returns_model(self) -> None:
        """NoopSynthesizer.model_id() returns the model constructor argument."""
        result = NoopSynthesizer(model="my-model").model_id()
        assert result == "my-model"

    def test_default_model_is_noop(self) -> None:
        """NoopSynthesizer default model_id() is 'noop'."""
        result = NoopSynthesizer().model_id()
        assert result == "noop"

    def test_satisfies_synthesizer_protocol(self) -> None:
        """NoopSynthesizer is accepted as a Synthesizer without explicit inheritance."""
        noop: Synthesizer = NoopSynthesizer()
        assert isinstance(noop, Synthesizer)


# ---------------------------------------------------------------------------
# OllamaSynthesizer — synthesize()
# ---------------------------------------------------------------------------


class TestOllamaSynthesizerSynthesize:
    """Tests for OllamaSynthesizer.synthesize()."""

    def test_successful_generation_returns_text(self) -> None:
        """synthesize() returns the 'response' field stripped of whitespace."""
        body = json.dumps({"response": "  text  ", "done": True}).encode()
        http_open = _make_http_open(200, body)
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        result = synth.synthesize("prompt")
        assert result == "text"

    def test_non_200_raises_click_exception_with_status(self) -> None:
        """synthesize() raises ClickException containing the status code on non-200."""
        body = b'{"error": "not found"}'
        http_open = _make_http_open(404, body)
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        assert "404" in exc_info.value.format_message()

    def test_timeout_raises_click_exception_mentioning_timed_out_and_ai_timeout(
        self,
    ) -> None:
        """synthesize() raises ClickException mentioning 'timed out' and 'ai.timeout'."""

        def _raise_timeout(*args: Any, **kwargs: Any) -> Any:
            raise urllib.error.URLError(reason=TimeoutError("timed out"))

        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=_raise_timeout)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        msg = exc_info.value.format_message()
        assert "timed out" in msg.lower()
        assert "ai.timeout" in msg

    def test_malformed_json_raises_unexpected_response_format(self) -> None:
        """synthesize() raises ClickException mentioning 'unexpected response format'."""
        http_open = _make_http_open(200, b"not json at all")
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        assert "unexpected response format" in exc_info.value.format_message()

    def test_missing_response_key_raises_unexpected_response_format(self) -> None:
        """synthesize() raises ClickException when 'response' key is absent."""
        body = json.dumps({"done": True}).encode()
        http_open = _make_http_open(200, body)
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        assert "unexpected response format" in exc_info.value.format_message()

    def test_url_error_non_timeout_raises_click_exception(self) -> None:
        """synthesize() raises ClickException on non-timeout URLError."""

        def _raise_url_error(*args: Any, **kwargs: Any) -> Any:
            raise urllib.error.URLError(reason="Connection refused")

        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=_raise_url_error)
        with pytest.raises(click.ClickException):
            synth.synthesize("prompt")


# ---------------------------------------------------------------------------
# OllamaSynthesizer — available()
# ---------------------------------------------------------------------------


class TestOllamaSynthesizerAvailable:
    """Tests for OllamaSynthesizer.available()."""

    def test_model_present_returns_true(self) -> None:
        """available() returns True when model name is in /api/tags response."""
        body = json.dumps({"models": [{"name": "llama3"}]}).encode()
        http_open = _make_http_open(200, body)
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        result = synth.available()
        assert result is True

    def test_available_uses_hardcoded_timeout_5(self) -> None:
        """available() calls _http_open with timeout=5 (hardcoded, not self.timeout)."""
        body = json.dumps({"models": [{"name": "llama3"}]}).encode()
        http_open = _make_http_open(200, body)
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", timeout=120, _http_open=http_open)
        synth.available()
        call_kwargs = http_open.call_args
        assert call_kwargs is not None
        # timeout is passed as keyword argument
        assert call_kwargs.kwargs.get("timeout") == 5

    def test_ollama_not_running_returns_false(self) -> None:
        """available() returns False when _http_open raises URLError."""

        def _raise_url_error(*args: Any, **kwargs: Any) -> Any:
            raise urllib.error.URLError(reason="Connection refused")

        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=_raise_url_error)
        result = synth.available()
        assert result is False

    def test_model_not_pulled_returns_false(self) -> None:
        """available() returns False when model is absent from /api/tags."""
        body = json.dumps({"models": [{"name": "other-model"}]}).encode()
        http_open = _make_http_open(200, body)
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        result = synth.available()
        assert result is False

    def test_malformed_json_returns_false(self) -> None:
        """available() returns False when /api/tags returns malformed JSON."""
        http_open = _make_http_open(200, b"not json")
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        result = synth.available()
        assert result is False

    def test_missing_models_key_returns_false(self) -> None:
        """available() returns False when /api/tags JSON lacks 'models' key."""
        body = json.dumps({"other": []}).encode()
        http_open = _make_http_open(200, body)
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        result = synth.available()
        assert result is False

    def test_non_200_tags_response_returns_false(self) -> None:
        """available() returns False when /api/tags returns non-200 status."""
        http_open = _make_http_open(503, b"service unavailable")
        # Fix 6: keyword-only args (CS-017)
        synth = OllamaSynthesizer(model="llama3", _http_open=http_open)
        result = synth.available()
        assert result is False

    def test_model_id_returns_model(self) -> None:
        """OllamaSynthesizer.model_id() returns the configured model name."""
        synth = OllamaSynthesizer(model="llama3")
        result = synth.model_id()
        assert result == "llama3"


# ---------------------------------------------------------------------------
# VertexSynthesizer — construction / validation
# ---------------------------------------------------------------------------


class TestVertexSynthesizerValidation:
    """Tests for VertexSynthesizer field validation at construction time."""

    def test_path_traversal_slash_in_project_raises(self) -> None:
        """VertexSynthesizer raises ClickException when project contains '/'.

        Note: validation is now done by the factory (new_synthesizer_from_config),
        not by VertexSynthesizer.__init__. These tests exercise the factory path
        via provider.py's _validate_vertex_config. Direct construction with bad
        fields no longer raises — only the factory does.
        """
        from gaze_py.report.provider import ProviderConfig, new_synthesizer_from_config

        cfg = ProviderConfig(
            provider="vertex", project="my/../project", region="us-central1", model="claude-3"
        )
        with pytest.raises(click.ClickException) as exc_info:
            new_synthesizer_from_config(cfg)
        assert "project" in exc_info.value.format_message()

    def test_slash_in_project_raises(self) -> None:
        """VertexSynthesizer raises ClickException when project contains '/'."""
        from gaze_py.report.provider import ProviderConfig, new_synthesizer_from_config

        cfg = ProviderConfig(
            provider="vertex", project="proj/../../etc", region="us-central1", model="claude-3"
        )
        with pytest.raises(click.ClickException) as exc_info:
            new_synthesizer_from_config(cfg)
        assert "project" in exc_info.value.format_message()

    def test_invalid_model_name_raises(self) -> None:
        """VertexSynthesizer raises ClickException when model contains invalid characters."""
        from gaze_py.report.provider import ProviderConfig, new_synthesizer_from_config

        cfg = ProviderConfig(
            provider="vertex", project="my-project", region="us-central1", model="claude@3!"
        )
        with pytest.raises(click.ClickException) as exc_info:
            new_synthesizer_from_config(cfg)
        assert "model" in exc_info.value.format_message()

    def test_valid_fields_do_not_raise(self) -> None:
        """VertexSynthesizer accepts valid alphanumeric/hyphen/dot/underscore/colon fields."""
        # Fix 6: keyword-only args (CS-017)
        synth = VertexSynthesizer(
            project="my-project-123",
            region="us-central1",
            model="claude-3-5-sonnet-v2:latest",
        )
        assert synth.model_id() == "claude-3-5-sonnet-v2:latest"


# ---------------------------------------------------------------------------
# VertexSynthesizer — synthesize() happy path
# ---------------------------------------------------------------------------


class TestVertexSynthesizerSynthesize:
    """Tests for VertexSynthesizer.synthesize() success and error paths."""

    def _make_synth(
        self,
        http_open: Any,
        gcloud: Any | None = None,
        clock: Any | None = None,
        sleep: Any | None = None,
    ) -> VertexSynthesizer:
        """Build a VertexSynthesizer with injected test doubles."""
        return VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
            _http_open=http_open,
            _gcloud=gcloud or _make_gcloud_ok(),
            _clock=clock or (lambda: 0.0),
            _sleep=sleep or (lambda _: None),
        )

    def test_successful_generation_returns_content_text(self) -> None:
        """synthesize() returns content[0].text from a valid Anthropic Messages response."""
        body = json.dumps({"content": [{"type": "text", "text": "hello world"}]}).encode()
        http_open = _make_http_open(200, body)
        synth = self._make_synth(http_open)
        result = synth.synthesize("prompt")
        assert result == "hello world"

    def test_gcloud_not_on_path_raises_with_install_url(self) -> None:
        """synthesize() raises ClickException mentioning 'gcloud CLI' and install URL."""
        body = json.dumps({"content": [{"type": "text", "text": "x"}]}).encode()
        http_open = _make_http_open(200, body)

        def _gcloud_not_found(*args: Any, **kwargs: Any) -> Any:
            raise FileNotFoundError("gcloud not found")

        synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
            _http_open=http_open,
            _gcloud=_gcloud_not_found,
        )
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        msg = exc_info.value.format_message()
        assert "gcloud CLI" in msg
        assert "https://cloud.google.com/sdk/docs/install" in msg

    def test_gcloud_auth_failure_raises_with_stderr_and_tip(self) -> None:
        """synthesize() raises ClickException with first stderr line and gcloud auth tip.

        Fix 1: error message now contains only the first non-empty line of stderr,
        not the full blob. The fixture uses a single-line stderr so the assertion
        still holds — the first line IS the full stderr in this case.
        """
        body = json.dumps({"content": [{"type": "text", "text": "x"}]}).encode()
        http_open = _make_http_open(200, body)
        gcloud = MagicMock(
            return_value=CompletedProcess(
                args=[], returncode=1, stdout="", stderr="auth error details"
            )
        )
        # Fix 6: keyword-only args (CS-017)
        synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
            _http_open=http_open,
            _gcloud=gcloud,
        )
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        msg = exc_info.value.format_message()
        assert "gcloud auth print-access-token" in msg
        # Fix 1: assert against the first line of stderr (not the full blob).
        # The fixture has a single-line stderr so "auth error details" is the first line.
        assert "auth error details" in msg
        assert "gcloud auth application-default login" in msg

    def test_token_cache_hit_skips_gcloud(self) -> None:
        """synthesize() does not call _gcloud when cached token is still valid."""
        http_open = _make_http_open_sequence([_make_vertex_200(), _make_vertex_200()])
        gcloud = _make_gcloud_ok()
        # clock returns 0.0 — token expires at 0 + _TOKEN_TTL; 0 < TTL - 60 → still valid
        clock = MagicMock(return_value=0.0)
        synth = self._make_synth(http_open, gcloud=gcloud, clock=clock)

        synth.synthesize("first")
        synth.synthesize("second")

        # gcloud called exactly once (first call fetches token; second uses cache)
        assert gcloud.call_count == 1

    def test_token_cache_expiry_refetches_token(self) -> None:
        """synthesize() calls _gcloud again when cached token is expired."""
        http_open = _make_http_open_sequence([_make_vertex_200(), _make_vertex_200()])
        gcloud = _make_gcloud_ok()
        # Clock advances past _TOKEN_TTL between calls: first call sets expiry at
        # t=0 + TTL; second call sees t=TTL+100 which is >= expiry-60, so stale.
        from gaze_py.report.ai import _TOKEN_TTL

        clock = MagicMock(side_effect=[0.0, _TOKEN_TTL + 100, _TOKEN_TTL + 100])
        synth = self._make_synth(http_open, gcloud=gcloud, clock=clock)

        synth.synthesize("first")
        synth.synthesize("second")

        # gcloud called twice (each call sees expired token)
        assert gcloud.call_count == 2

    def test_non_429_http_error_raises_with_status_and_body(self) -> None:
        """synthesize() raises ClickException with status code on non-429 4xx/5xx.

        Fix 9: the error message now extracts error.message from JSON when available.
        When the body is not valid JSON, only the status code is included.
        When the body IS valid JSON with error.message, that message is appended.
        """
        # Case 1: non-JSON body — only status code in message.
        body = b"bad request details"
        http_open = _make_http_open(400, body)
        synth = self._make_synth(http_open)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        msg = exc_info.value.format_message()
        assert "400" in msg

        # Case 2: JSON body with error.message — message is extracted and appended.
        json_body = b'{"error": {"message": "quota exceeded", "code": 400}}'
        http_open2 = _make_http_open(400, json_body)
        synth2 = self._make_synth(http_open2)
        with pytest.raises(click.ClickException) as exc_info2:
            synth2.synthesize("prompt")
        msg2 = exc_info2.value.format_message()
        assert "400" in msg2
        assert "quota exceeded" in msg2

    def test_malformed_json_raises_unexpected_response_format(self) -> None:
        """synthesize() raises ClickException mentioning 'unexpected response format'."""
        http_open = _make_http_open(200, b"not json")
        synth = self._make_synth(http_open)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        assert "unexpected response format" in exc_info.value.format_message()

    def test_missing_content_raises_unexpected_response_format(self) -> None:
        """synthesize() raises ClickException when content is missing or empty."""
        body = json.dumps({"content": []}).encode()
        http_open = _make_http_open(200, body)
        synth = self._make_synth(http_open)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        assert "unexpected response format" in exc_info.value.format_message()

    def test_content_missing_text_raises_unexpected_response_format(self) -> None:
        """synthesize() raises ClickException when content[0].text is absent."""
        body = json.dumps({"content": [{"type": "image", "source": {}}]}).encode()
        http_open = _make_http_open(200, body)
        synth = self._make_synth(http_open)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        assert "unexpected response format" in exc_info.value.format_message()

    def test_gcloud_subprocess_uses_list_form(self) -> None:
        """_gcloud is always invoked with list form, never shell=True."""
        body = json.dumps({"content": [{"type": "text", "text": "x"}]}).encode()
        http_open = _make_http_open(200, body)
        gcloud = _make_gcloud_ok()
        synth = self._make_synth(http_open, gcloud=gcloud)
        synth.synthesize("prompt")

        call_args = gcloud.call_args
        assert call_args is not None
        cmd = call_args.args[0]
        assert isinstance(cmd, list)
        assert cmd == ["gcloud", "auth", "print-access-token"]
        assert call_args.kwargs.get("shell", False) is False


# ---------------------------------------------------------------------------
# VertexSynthesizer — 429 retry logic
# ---------------------------------------------------------------------------


class TestVertexSynthesizerRetry:
    """Tests for VertexSynthesizer 429 retry with exponential backoff."""

    def _make_synth(
        self,
        http_open: Any,
        sleep: Any | None = None,
    ) -> VertexSynthesizer:
        """Build a VertexSynthesizer with injected test doubles for retry tests."""
        return VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
            _http_open=http_open,
            _gcloud=_make_gcloud_ok(),
            _clock=lambda: 0.0,
            _sleep=sleep or MagicMock(),
        )

    def test_429_then_200_returns_response(self) -> None:
        """synthesize() retries on 429 and returns the response on subsequent 200."""
        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(),
                _make_vertex_200("retry worked"),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        result = synth.synthesize("prompt")
        assert result == "retry worked"
        assert sleep.call_count == 1

    def test_429_backoff_jitter_in_range(self) -> None:
        """synthesize() calls _sleep with a value between 0.75 and 1.25 on first retry."""
        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(),
                _make_vertex_200(),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        synth.synthesize("prompt")
        sleep_val = sleep.call_args.args[0]
        assert 0.75 <= sleep_val <= 1.25

    def test_429_exhausted_raises_after_6_calls(self) -> None:
        """synthesize() raises ClickException after 5 retries; exactly 6 HTTP calls."""
        http_open = _make_http_open_sequence([_make_vertex_429()] * 6)
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        msg = exc_info.value.format_message()
        assert "rate limited" in msg.lower()
        assert "5 retries" in msg
        assert http_open.call_count == 6
        assert sleep.call_count == 5

    def test_429_succeeds_on_retry_4(self) -> None:
        """synthesize() returns response after 3 retries; exactly 4 HTTP calls, 3 sleeps."""
        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(),
                _make_vertex_429(),
                _make_vertex_429(),
                _make_vertex_200("success on 4th"),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        result = synth.synthesize("prompt")
        assert result == "success on 4th"
        assert http_open.call_count == 4
        assert sleep.call_count == 3

    def test_429_increasing_backoff_values(self) -> None:
        """synthesize() uses increasing backoff values across retries."""
        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(),
                _make_vertex_429(),
                _make_vertex_429(),
                _make_vertex_200(),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        synth.synthesize("prompt")
        sleep_vals = [call.args[0] for call in sleep.call_args_list]
        # Base values: 1s, 2s, 4s — with ±25% jitter: [0.75,1.25], [1.5,2.5], [3,5]
        assert len(sleep_vals) == 3
        assert sleep_vals[0] <= 1.25
        assert sleep_vals[1] >= 1.5
        assert sleep_vals[2] >= 3.0

    def test_retry_after_header_integer_overrides_backoff(self) -> None:
        """synthesize() uses Retry-After: 5 header value, not jitter-based backoff."""
        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(retry_after="5"),
                _make_vertex_200(),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        synth.synthesize("prompt")
        sleep_val = sleep.call_args.args[0]
        assert sleep_val == 5.0

    def test_retry_after_absent_uses_backoff(self) -> None:
        """synthesize() uses jitter-based backoff when Retry-After header is absent."""
        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(retry_after=None),
                _make_vertex_200(),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        synth.synthesize("prompt")
        sleep_val = sleep.call_args.args[0]
        # Should be jitter-based (0.75–1.25 for first retry)
        assert 0.75 <= sleep_val <= 1.25

    def test_retry_after_non_integer_uses_backoff(self) -> None:
        """synthesize() uses jitter-based backoff when Retry-After is an HTTP-date string."""
        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(retry_after="Wed, 21 Oct 2015 07:28:00 GMT"),
                _make_vertex_200(),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        synth.synthesize("prompt")
        sleep_val = sleep.call_args.args[0]
        # Should be jitter-based (0.75–1.25 for first retry)
        assert 0.75 <= sleep_val <= 1.25

    def test_retry_after_exceeds_backoff_max_is_clamped(self) -> None:
        """synthesize() clamps Retry-After values > _BACKOFF_MAX (60s) to _BACKOFF_MAX.

        Fix 2: a hostile server sending Retry-After: 9999 must not cause an
        unbounded sleep. The value is clamped to _BACKOFF_MAX (60.0s).
        """
        from gaze_py.report.ai import _BACKOFF_MAX

        http_open = _make_http_open_sequence(
            [
                _make_vertex_429(retry_after="9999"),
                _make_vertex_200(),
            ]
        )
        sleep = MagicMock()
        synth = self._make_synth(http_open, sleep=sleep)
        synth.synthesize("prompt")
        sleep_val = sleep.call_args.args[0]
        # Fix 2: Retry-After: 9999 must be clamped to _BACKOFF_MAX (60.0).
        assert sleep_val == _BACKOFF_MAX


# ---------------------------------------------------------------------------
# VertexSynthesizer — 401 mid-flight token refresh
# ---------------------------------------------------------------------------


class TestVertexSynthesizer401:
    """Tests for VertexSynthesizer 401 handling with token cache invalidation."""

    def _make_synth_with_cached_token(
        self,
        http_open: Any,
        gcloud: Any,
    ) -> VertexSynthesizer:
        """Build a VertexSynthesizer with a pre-warmed token cache.

        Pre-warms the cache by calling synthesize() with a 200 response first,
        so the subsequent test call starts with a cached token (0 gcloud calls
        consumed for the test's HTTP sequence).

        The warm-up uses a separate http_open/gcloud that returns a 200 and
        caches the token. The test doubles are then passed to a second
        VertexSynthesizer that shares the same cached token by construction:
        we build a new synth with the test doubles but inject the cached token
        directly via _cached_token (private attribute, justified here because
        the public API cannot pre-warm the cache without consuming a gcloud call
        that would be counted in the test assertion).
        """
        # Warm the cache via a separate instance to get a valid (token, expiry) pair
        warm_body = json.dumps({"content": [{"type": "text", "text": "warm"}]}).encode()
        warm_open = _make_http_open(200, warm_body)
        warm_gcloud = _make_gcloud_ok()
        # Fix 6: keyword-only args (CS-017)
        warm_synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
            _http_open=warm_open,
            _gcloud=warm_gcloud,
            _clock=lambda: 0.0,
            _sleep=lambda _: None,
        )
        warm_synth.synthesize("warm-up")
        # CR-004: _cached_token is accessed directly because no public API exists
        # to pre-warm the cache without consuming a _gcloud call counted in assertions.
        cached = warm_synth._cached_token  # noqa: SLF001

        # Build the real test synth with the test doubles and inject the cached token
        # Fix 6: keyword-only args (CS-017)
        synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
            _http_open=http_open,
            _gcloud=gcloud,
            _clock=lambda: 0.0,
            _sleep=lambda _: None,
        )
        # CR-004: _cached_token is accessed directly because no public API exists
        # to pre-warm the cache without consuming a _gcloud call counted in assertions.
        synth._cached_token = cached  # noqa: SLF001
        return synth

    def test_401_invalidates_cache_and_retries_once(self) -> None:
        """synthesize() invalidates token on 401, refreshes, retries; 2 HTTP calls, 1 gcloud."""
        http_open = _make_http_open_sequence(
            [
                (401, b'{"error": "unauthorized"}', None),
                _make_vertex_200("refreshed"),
            ]
        )
        gcloud = _make_gcloud_ok()
        synth = self._make_synth_with_cached_token(http_open, gcloud)
        result = synth.synthesize("prompt")
        assert result == "refreshed"
        assert http_open.call_count == 2
        assert gcloud.call_count == 1

    def test_401_on_retry_raises_authentication_failed(self) -> None:
        """synthesize() raises ClickException mentioning 'authentication failed' on second 401."""
        http_open = _make_http_open_sequence(
            [
                (401, b'{"error": "unauthorized"}', None),
                (401, b'{"error": "still unauthorized"}', None),
            ]
        )
        gcloud = _make_gcloud_ok()
        synth = self._make_synth_with_cached_token(http_open, gcloud)
        with pytest.raises(click.ClickException) as exc_info:
            synth.synthesize("prompt")
        msg = exc_info.value.format_message()
        assert "authentication failed" in msg.lower()
        assert "gcloud auth application-default login" in msg
        assert http_open.call_count == 2
        assert gcloud.call_count == 1


# ---------------------------------------------------------------------------
# VertexSynthesizer — available()
# ---------------------------------------------------------------------------


class TestVertexSynthesizerAvailable:
    """Tests for VertexSynthesizer.available()."""

    def test_gcloud_present_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """available() returns True when gcloud is on PATH and project/region are non-empty."""
        monkeypatch.setattr(
            "gaze_py.report.ai.shutil.which",
            lambda name: "/usr/bin/gcloud" if name == "gcloud" else None,
        )
        synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
        )
        result = synth.available()
        assert result is True

    def test_gcloud_missing_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """available() returns False when shutil.which('gcloud') returns None."""
        monkeypatch.setattr("gaze_py.report.ai.shutil.which", lambda name: None)
        synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
        )
        result = synth.available()
        assert result is False

    def test_available_makes_no_api_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """available() does not invoke _gcloud or _http_open."""
        monkeypatch.setattr(
            "gaze_py.report.ai.shutil.which",
            lambda name: "/usr/bin/gcloud" if name == "gcloud" else None,
        )
        gcloud = MagicMock()
        http_open = MagicMock()
        synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
            _http_open=http_open,
            _gcloud=gcloud,
        )
        synth.available()
        assert gcloud.call_count == 0
        assert http_open.call_count == 0

    def test_model_id_returns_model(self) -> None:
        """VertexSynthesizer.model_id() returns the configured model name."""
        synth = VertexSynthesizer(
            project="my-project",
            region="us-central1",
            model="claude-3-5-sonnet",
        )
        result = synth.model_id()
        assert result == "claude-3-5-sonnet"


# ---------------------------------------------------------------------------
# Synthesizer Protocol structural subtyping
# ---------------------------------------------------------------------------


class TestSynthesizerProtocol:
    """Tests for the Synthesizer Protocol structural subtyping."""

    def test_class_with_matching_signatures_satisfies_protocol(self) -> None:
        """A class implementing synthesize/available/model_id is accepted as Synthesizer."""

        class MyDouble:
            def synthesize(self, prompt: str) -> str:
                return "ok"

            def available(self) -> bool:
                return True

            def model_id(self) -> str:
                return "my-model"

        obj: Synthesizer = MyDouble()
        assert isinstance(obj, Synthesizer)

    def test_noop_synthesizer_satisfies_protocol(self) -> None:
        """NoopSynthesizer satisfies the Synthesizer Protocol."""
        noop: Synthesizer = NoopSynthesizer()
        assert isinstance(noop, Synthesizer)

    def test_ollama_synthesizer_satisfies_protocol(self) -> None:
        """OllamaSynthesizer satisfies the Synthesizer Protocol."""
        synth: Synthesizer = OllamaSynthesizer(model="llama3")
        assert isinstance(synth, Synthesizer)

    def test_vertex_synthesizer_satisfies_protocol(self) -> None:
        """VertexSynthesizer satisfies the Synthesizer Protocol."""
        synth: Synthesizer = VertexSynthesizer(project="p", region="us-central1", model="claude-3")
        assert isinstance(synth, Synthesizer)
