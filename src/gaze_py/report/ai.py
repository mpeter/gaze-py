"""HTTP-based AI synthesizer implementations for gazepy report.

Defines the Synthesizer Protocol and three concrete implementations:
- NoopSynthesizer: test double, exported for use in tests
- OllamaSynthesizer: calls Ollama /api/generate via HTTP
- VertexSynthesizer: calls Vertex AI rawPredict via HTTP with gcloud auth

All HTTP calls use urllib.request (stdlib). No subprocess for synthesis.
The _http_open, _gcloud, _clock, and _sleep parameters are injectable
for testing — they MUST NOT be used in production code paths.

Design decisions:
- D1: Direct HTTP over subprocess for synthesis (no process startup overhead)
- D2: Synthesizer Protocol (structural subtyping) over ABC — AP-007 deviation,
  pre-approved for this change. Allows test doubles without inheritance.
- D3: gcloud CLI for Vertex auth (no google-auth SDK dependency)
- D10: timeout is per-request, not total-operation
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

import click


@runtime_checkable
class Synthesizer(Protocol):
    """Protocol for AI text synthesizers.

    Implementations MUST document their I/O behavior in their class docstring.
    available() MAY perform I/O; callers MUST NOT assume it is O(1).

    This Protocol is used instead of ABC (AP-007 deviation, pre-approved for
    this change) because test doubles must be constructible without inheriting
    from a base class — mirrors Dewey's Go interface pattern.
    """

    def synthesize(self, prompt: str) -> str:
        """Generate a text response for the given prompt.

        Args:
            prompt: The input prompt to synthesize a response for.

        Returns:
            The synthesized response text.

        Raises:
            click.ClickException: On provider error, timeout, or malformed response.
        """
        ...

    def available(self) -> bool:
        """Check whether this synthesizer is available for use.

        MAY perform I/O (e.g., HTTP call to check model presence).
        Callers MUST NOT assume this is O(1).

        Returns:
            True if the synthesizer is ready to accept synthesize() calls.
        """
        ...

    def model_id(self) -> str:
        """Return the model identifier used by this synthesizer.

        Returns:
            The model identifier string.
        """
        ...


class NoopSynthesizer:
    """Test double synthesizer that returns a fixed response or raises a fixed error.

    Exported from production code (not test-only) so that callers can construct
    a no-op synthesizer without importing test infrastructure.

    I/O behavior: None. All methods are pure and O(1).

    Args:
        response: The string to return from synthesize(). Default: "".
        err: If set, synthesize() raises this exception directly. Default: None.
        avail: The value returned by available(). Default: True.
        model: The value returned by model_id(). Default: "noop".
    """

    def __init__(
        self,
        response: str = "",
        err: Exception | None = None,
        avail: bool = True,
        model: str = "noop",
    ) -> None:
        self.response = response
        self.err = err
        self.avail = avail
        self.model = model

    def synthesize(self, prompt: str) -> str:  # noqa: ARG002
        """Return the fixed response or raise the fixed error.

        Args:
            prompt: Ignored.

        Returns:
            self.response if self.err is None.

        Raises:
            Exception: self.err if it was set at construction time.
        """
        if self.err is not None:
            raise self.err
        return self.response

    def available(self) -> bool:
        """Return the fixed availability value.

        Returns:
            self.avail as set at construction time.
        """
        return self.avail

    def model_id(self) -> str:
        """Return the fixed model identifier.

        Returns:
            self.model as set at construction time.
        """
        return self.model


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_AVAIL_TIMEOUT = 5  # hardcoded per spec: available() uses 5s, not self.timeout


def _make_json_request(
    url: str,
    body: dict[str, Any],
    *,
    method: str = "POST",
    token: str | None = None,
    timeout: int,
    _http_open: Any,
) -> tuple[int, bytes, Any]:
    """Send a JSON HTTP request and return (status, body_bytes, response_obj).

    Args:
        url: The full URL to request.
        body: Request body to serialize as JSON.
        method: HTTP method. Default: "POST".
        token: Bearer token for Authorization header. Default: None.
        timeout: Request timeout in seconds.
        _http_open: Injectable HTTP client (default: urllib.request.urlopen).

    Returns:
        Tuple of (HTTP status code, raw response body bytes, response object).

    Raises:
        urllib.error.URLError: On connection or timeout errors.
    """
    data = json.dumps(body).encode()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with _http_open(req, timeout=timeout) as resp:
        status: int = resp.status
        body_bytes: bytes = resp.read()
        return status, body_bytes, resp


# ---------------------------------------------------------------------------
# OllamaSynthesizer
# ---------------------------------------------------------------------------


class OllamaSynthesizer:
    """Synthesizer that calls Ollama's HTTP API directly.

    I/O behavior:
    - synthesize(): POST to {base_url}/api/generate with self.timeout seconds.
    - available(): GET {base_url}/api/tags with a hardcoded 5-second timeout.
      Returns False on any error (URLError, non-200, malformed JSON, missing
      'models' key). Does NOT cache the result.

    Args:
        base_url: Ollama server base URL. Default: "http://localhost:11434".
        model: Ollama model name (required, keyword-only).
        timeout: HTTP timeout in seconds for synthesize(). Default: 120.
        _http_open: Injectable HTTP client for testing. Default:
            urllib.request.urlopen. MUST NOT be used in production code.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str,
        timeout: int = 120,
        _http_open: Any = urllib.request.urlopen,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._http_open = _http_open

    def synthesize(self, prompt: str) -> str:
        """Generate text by calling Ollama /api/generate.

        Args:
            prompt: The input prompt.

        Returns:
            The 'response' field from Ollama, stripped of whitespace.

        Raises:
            click.ClickException: On non-200 status, URLError/timeout,
                malformed JSON, or missing 'response' key.
        """
        url = f"{self._base_url}/api/generate"
        body = {"model": self._model, "prompt": prompt, "stream": False}
        try:
            status, body_bytes, _resp = _make_json_request(
                url,
                body,
                timeout=self._timeout,
                _http_open=self._http_open,
            )
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower():
                raise click.ClickException(
                    f"Ollama request timed out after {self._timeout}s per request; "
                    "try reducing ai.timeout in .gaze.yaml"
                ) from exc
            raise click.ClickException(f"Ollama request failed: {exc.reason}") from exc

        if status != 200:
            raise click.ClickException(
                f"Ollama returned HTTP {status}; check that the model is pulled "
                f"and Ollama is running at {self._base_url}"
            )

        try:
            data = json.loads(body_bytes)
        except json.JSONDecodeError as exc:
            raise click.ClickException(
                "unexpected response format from Ollama: response is not valid JSON"
            ) from exc

        if "response" not in data:
            raise click.ClickException(
                "unexpected response format from Ollama: missing 'response' key"
            )

        return str(data["response"]).strip()

    def available(self) -> bool:
        """Check whether Ollama is running and the configured model is pulled.

        Calls GET {base_url}/api/tags with a hardcoded 5-second timeout.
        Returns False on any error — does not raise.

        Returns:
            True if Ollama is reachable and the model name appears in /api/tags.
        """
        url = f"{self._base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with self._http_open(req, timeout=_AVAIL_TIMEOUT) as resp:
                if resp.status != 200:
                    return False
                body_bytes: bytes = resp.read()
        except urllib.error.URLError:
            return False

        try:
            data = json.loads(body_bytes)
        except json.JSONDecodeError:
            return False

        models = data.get("models")
        if not isinstance(models, list):
            return False

        return any(isinstance(m, dict) and m.get("name") == self._model for m in models)

    def model_id(self) -> str:
        """Return the configured Ollama model name.

        Returns:
            The model identifier string.
        """
        return self._model


# ---------------------------------------------------------------------------
# VertexSynthesizer
# ---------------------------------------------------------------------------

_VERTEX_MAX_RETRIES = 5  # 1 original + 5 retries = 6 total attempts
_BACKOFF_BASE = 1.0  # seconds
_BACKOFF_MAX = 60.0  # seconds
_BACKOFF_JITTER = 0.25  # ±25%
_TOKEN_TTL = 55 * 60  # gcloud tokens are valid 60 min; cache for 55


class VertexSynthesizer:
    """Synthesizer that calls Vertex AI rawPredict with Anthropic Messages format.

    I/O behavior:
    - synthesize(): invokes gcloud for token (cached), then POST to Vertex
      rawPredict endpoint. Retries up to 5 times on HTTP 429 with exponential
      backoff (base 1s, max 60s, ±25% jitter). Respects Retry-After header.
      On HTTP 401, invalidates token cache and retries once.
    - available(): checks shutil.which("gcloud") and non-empty project/region.
      No API call is made.

    Token cache: in-process only, per-instance. Valid when
    _clock() < expiry_epoch - 60 (conservative TTL to avoid clock-skew races).

    Args:
        project: GCP project ID (required).
        region: GCP region (required).
        model: Anthropic model name on Vertex (required).
        timeout: Per-request HTTP timeout in seconds. Default: 120.
        _http_open: Injectable HTTP client for testing. Default:
            urllib.request.urlopen. MUST NOT be used in production code.
        _gcloud: Injectable subprocess runner for testing. Default:
            subprocess.run. MUST NOT be used in production code.
        _clock: Injectable clock for TTL comparison. Default: time.time.
            MUST NOT be used in production code.
        _sleep: Injectable sleep for retry backoff. Default: time.sleep.
            MUST NOT be used in production code.

    Note:
        Field validation (character safety, non-empty) is performed by the
        factory (``new_synthesizer_from_config``) before construction.
        The constructor trusts the factory and does not re-validate. (Fix 4: DRY)
    """

    def __init__(
        self,
        *,
        project: str,
        region: str,
        model: str,
        timeout: int = 120,
        _http_open: Any = urllib.request.urlopen,
        _gcloud: Any = subprocess.run,
        _clock: Callable[[], float] = time.time,
        _sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # Validation is performed by the factory (new_synthesizer_from_config)
        # before construction. The constructor trusts the factory. (Fix 4: DRY)
        self._project = project
        self._region = region
        self._model = model
        self._timeout = timeout
        self._http_open = _http_open
        self._gcloud = _gcloud
        self._clock = _clock
        self._sleep = _sleep

        # Token cache: (token_str, expiry_epoch_float) or None
        self._cached_token: tuple[str, float] | None = None

    def _endpoint_url(self) -> str:
        """Build the Vertex AI rawPredict endpoint URL.

        Returns:
            The full rawPredict URL for this project/region/model.
        """
        return (
            f"https://{self._region}-aiplatform.googleapis.com/v1"
            f"/projects/{self._project}/locations/{self._region}"
            f"/publishers/anthropic/models/{self._model}:rawPredict"
        )

    def _fetch_token(self) -> str:
        """Fetch a fresh access token via gcloud CLI.

        Invokes gcloud using list form (never shell=True) per security requirement.
        Caches the token with its expiry.

        Returns:
            The access token string.

        Raises:
            click.ClickException: If gcloud is not on PATH, exits non-zero,
                or returns an empty token.
        """
        if shutil.which("gcloud") is None:
            raise click.ClickException(
                "vertex provider requires gcloud CLI. "
                "Install: https://cloud.google.com/sdk/docs/install "
                "and run: gcloud auth application-default login"
            )

        try:
            result = self._gcloud(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise click.ClickException(
                "vertex provider requires gcloud CLI. "
                "Install: https://cloud.google.com/sdk/docs/install "
                "and run: gcloud auth application-default login"
            ) from exc

        if result.returncode != 0:
            # Fix 1: truncate stderr to first non-empty line to avoid embedding
            # multi-kilobyte error blobs in the exception message.
            stderr_summary = (
                result.stderr.splitlines()[0] if result.stderr.strip() else "(no details)"
            )
            raise click.ClickException(
                f"gcloud auth print-access-token failed (exit {result.returncode}): "
                f"{stderr_summary}\n"
                "Run: gcloud auth application-default login"
            ) from None

        token: str = result.stdout.strip()
        if not token:
            raise click.ClickException(
                "gcloud auth print-access-token returned an empty token. "
                "Run: gcloud auth application-default login"
            )
        expiry_epoch = self._clock() + _TOKEN_TTL

        self._cached_token = (token, expiry_epoch)
        return token

    def _get_token(self) -> str:
        """Return a valid access token, using cache when possible.

        Cache is valid when _clock() < expiry_epoch - 60 (conservative TTL).

        Returns:
            A valid access token string.

        Raises:
            click.ClickException: Propagated from _fetch_token().
        """
        if self._cached_token is not None:
            token, expiry_epoch = self._cached_token
            if self._clock() < expiry_epoch - 60:
                return token
        return self._fetch_token()

    def _invalidate_token(self) -> None:
        """Invalidate the cached token (called on HTTP 401)."""
        self._cached_token = None

    def _compute_backoff(self, attempt: int) -> float:
        """Compute exponential backoff with ±25% jitter.

        Args:
            attempt: Zero-based retry attempt index (0 = first retry).

        Returns:
            Sleep duration in seconds. The base is clamped to _BACKOFF_MAX
            (60s), then ±25% jitter is applied. The returned value may be
            slightly below the base (due to negative jitter) but is floored
            to 0.0 by the caller (_sleep_for_429 via max(0.0, ...)).
        """
        base: float = min(_BACKOFF_BASE * float(2**attempt), _BACKOFF_MAX)
        jitter: float = base * _BACKOFF_JITTER
        return max(0.0, base + random.uniform(-jitter, jitter))

    def _do_request(self, token: str, prompt: str) -> tuple[int, bytes, Any]:
        """Send one rawPredict HTTP request.

        Args:
            token: Bearer token for Authorization header.
            prompt: The input prompt.

        Returns:
            Tuple of (HTTP status code, raw response body bytes, response object).

        Raises:
            urllib.error.URLError: On connection or timeout errors.
        """
        url = self._endpoint_url()
        body: dict[str, Any] = {
            "anthropic_version": "vertex-2023-10-16",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        return _make_json_request(
            url,
            body,
            token=token,
            timeout=self._timeout,
            _http_open=self._http_open,
        )

    def _sleep_for_429(self, resp_obj: Any, retry_count: int) -> None:
        """Sleep the appropriate duration for a 429 response.

        Respects the Retry-After header (integer seconds) when present.
        Falls back to jitter-based exponential backoff otherwise.

        Args:
            resp_obj: The HTTP response object (must support .getheader()).
            retry_count: Zero-based retry attempt index.
        """
        retry_after_header: str | None = resp_obj.getheader("Retry-After")
        if retry_after_header is not None:
            try:
                # Fix 2: cap Retry-After to _BACKOFF_MAX and floor to 0 to prevent
                # unbounded sleeps from a hostile or misconfigured server.
                sleep_secs = max(0.0, min(float(int(retry_after_header)), _BACKOFF_MAX))
            except ValueError:
                sleep_secs = self._compute_backoff(retry_count)
        else:
            sleep_secs = self._compute_backoff(retry_count)
        self._sleep(sleep_secs)

    def _parse_vertex_response(self, body_bytes: bytes) -> str:
        """Parse a successful Vertex AI rawPredict response body.

        Args:
            body_bytes: Raw HTTP response body bytes.

        Returns:
            content[0].text from the Anthropic Messages response.

        Raises:
            click.ClickException: On malformed JSON or missing content.
        """
        try:
            data = json.loads(body_bytes)
        except json.JSONDecodeError as exc:
            raise click.ClickException(
                "unexpected response format from Vertex AI: response is not valid JSON"
            ) from exc

        content = data.get("content")
        if not isinstance(content, list) or len(content) == 0:
            raise click.ClickException(
                "unexpected response format from Vertex AI: missing or empty 'content'"
            )

        first = content[0]
        if not isinstance(first, dict) or first.get("type") != "text" or "text" not in first:
            raise click.ClickException(
                "unexpected response format from Vertex AI: content[0].text is absent"
            )

        return str(first["text"])

    def synthesize(self, prompt: str) -> str:
        """Generate text by calling Vertex AI rawPredict.

        Fetches/caches a gcloud access token, then POSTs to the Vertex
        rawPredict endpoint. Retries up to 5 times on HTTP 429 with
        exponential backoff. On HTTP 401, invalidates the token cache and
        retries once. Non-429 4xx/5xx errors raise immediately.

        Args:
            prompt: The input prompt.

        Returns:
            content[0].text from the Anthropic Messages response.

        Raises:
            click.ClickException: On gcloud failure, HTTP error, malformed
                JSON, missing content, or 429 exhaustion.
        """
        token = self._get_token()
        retry_count = 0
        _401_retried = False

        while True:
            try:
                status, body_bytes, resp_obj = self._do_request(token, prompt)
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower():
                    raise click.ClickException(
                        f"Vertex AI request timed out after {self._timeout}s per request; "
                        "try reducing ai.timeout in .gaze.yaml"
                    ) from exc
                raise click.ClickException(f"Vertex AI request failed: {exc.reason}") from exc

            if status == 200:
                return self._parse_vertex_response(body_bytes)

            if status == 401:
                if _401_retried:
                    raise click.ClickException(
                        "Vertex AI authentication failed after token refresh. "
                        "Run: gcloud auth application-default login"
                    )
                self._invalidate_token()
                token = self._get_token()
                _401_retried = True
                continue

            if status == 429:
                if retry_count >= _VERTEX_MAX_RETRIES:
                    raise click.ClickException(
                        f"Vertex AI rate limited after {_VERTEX_MAX_RETRIES} retries. "
                        "Try again later or reduce request frequency."
                    )
                self._sleep_for_429(resp_obj, retry_count)
                retry_count += 1
                continue

            # Non-429 4xx/5xx: raise immediately.
            # Fix 9: try to extract error.message from JSON for a cleaner message.
            try:
                err_data = json.loads(body_bytes)
                err_msg = err_data.get("error", {}).get("message", "")
                detail = f": {err_msg}" if err_msg else ""
            except (json.JSONDecodeError, AttributeError):
                detail = ""
            raise click.ClickException(f"Vertex AI returned HTTP {status}{detail}")

    def available(self) -> bool:
        """Check whether Vertex AI is available for use.

        Checks that gcloud is on PATH and that project and region are non-empty.
        Does NOT make a Vertex API call — trusts the factory has validated fields.

        Returns:
            True if gcloud is on PATH and project/region are non-empty.
        """
        return shutil.which("gcloud") is not None and bool(self._project) and bool(self._region)

    def model_id(self) -> str:
        """Return the configured Vertex AI model name.

        Returns:
            The model identifier string.
        """
        return self._model
