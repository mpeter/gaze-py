## Coverage Strategy

All public methods of `OllamaSynthesizer` and `VertexSynthesizer` SHALL be covered by
HTTP-mock tests using `unittest.mock.patch("urllib.request.urlopen", ...)`. No live network
calls are permitted in tests. The `gcloud` subprocess SHALL be mocked via an injectable
`_gcloud` callable. Time-dependent behavior (token TTL, retry backoff) SHALL use injectable
`_clock` and `_sleep` callables. `NoopSynthesizer` lives in `src/gaze_py/report/ai.py`
(production code, exported for use in tests). The 85% project-wide coverage gate applies.

## Test Infrastructure

All synthesizer implementations MUST accept the following injectable parameters for testing.
These parameters default to their production equivalents and MUST NOT be used except in tests.

- `_http_open: Callable = urllib.request.urlopen` — HTTP client for all REST calls. Mock
  shape: a callable that returns a context-manager object with `.status: int`,
  `.read() -> bytes`, and `.getheader(name: str) -> str | None`. For connection errors,
  raise `urllib.error.URLError`. For timeouts, raise `urllib.error.URLError` wrapping
  `socket.timeout`.
- `_gcloud: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run` — used by
  `VertexSynthesizer` to invoke `gcloud auth print-access-token --format=json`. Mock shape:
  `CompletedProcess(args=..., returncode=0, stdout='{"token":"tok","token_expiry":"..."}')`.
  For gcloud not found, raise `FileNotFoundError`. For auth failure, return
  `CompletedProcess(returncode=1, stdout="", stderr="error")`.
- `_clock: Callable[[], float] = time.time` — used by `VertexSynthesizer` for TTL
  comparison. Mock by returning fixed timestamps.
- `_sleep: Callable[[float], None] = time.sleep` — used by `VertexSynthesizer` retry
  backoff. Mock to verify backoff values without real delay.

## Security Requirements

### Requirement: Input validation before URL construction
The system SHALL validate `project`, `region`, and `model` field values in
`VertexSynthesizer.__init__` before constructing the endpoint URL. Each field MUST contain
only alphanumeric characters, hyphens (`-`), dots (`.`), underscores (`_`), or colons (`:`).
Any other character SHALL cause `new_synthesizer_from_config` to raise `click.ClickException`
at factory time. The `gcloud` subprocess MUST always be invoked using list form
(`["gcloud", "auth", "print-access-token", "--format=json"]`). Shell form (`shell=True`)
is prohibited.

#### Scenario: Path-traversal characters in project rejected
- **WHEN** `cfg.project` contains `/` or `..`
- **THEN** `new_synthesizer_from_config` raises `click.ClickException` mentioning "project"

#### Scenario: Invalid model name rejected
- **WHEN** `cfg.model` contains characters outside `[a-zA-Z0-9\-._:]`
- **THEN** `new_synthesizer_from_config` raises `click.ClickException` mentioning "model"

#### Scenario: gcloud subprocess always uses list form
- **WHEN** `gcloud` is invoked for token fetching
- **THEN** the subprocess call uses list form, never `shell=True`

## ADDED Requirements

### Requirement: Synthesizer Protocol
The system SHALL define a `Synthesizer` Protocol in `src/gaze_py/report/ai.py` with three
methods: `synthesize(prompt: str) -> str`, `available() -> bool`, and `model_id() -> str`.
`available()` MAY perform I/O. Callers MUST NOT assume it is O(1). Implementations MUST
document their I/O behavior. The Protocol is used (rather than ABC) because test doubles
must be constructible without inheriting from a base class — this is a documented deviation
from AP-007 (which prefers ABC for owned interfaces), pre-approved for this change.

#### Scenario: Protocol structural subtyping
- **WHEN** a class implements `synthesize`, `available`, and `model_id` with matching signatures
- **THEN** it is accepted as a `Synthesizer` without explicit inheritance

### Requirement: NoopSynthesizer test double
The system SHALL define `NoopSynthesizer` in `src/gaze_py/report/ai.py` (exported, not
test-only) with constructor: `NoopSynthesizer(response: str = "", err: Exception | None = None, avail: bool = True, model: str = "noop")`.
`synthesize()` SHALL raise `self.err` directly if set, otherwise return `self.response`.
`available()` SHALL return `self.avail`. `model_id()` SHALL return `self.model`.

#### Scenario: NoopSynthesizer happy path
- **WHEN** `NoopSynthesizer(response="ok")` is used and `synthesize("prompt")` is called
- **THEN** `"ok"` is returned

#### Scenario: NoopSynthesizer error path
- **WHEN** `NoopSynthesizer(err=click.ClickException("boom"))` is used
- **THEN** `synthesize()` raises `click.ClickException("boom")`

### Requirement: OllamaSynthesizer
The system SHALL implement `OllamaSynthesizer` that calls Ollama's HTTP API via
`urllib.request.urlopen` (injectable as `_http_open`). It MUST NOT spawn a subprocess for
synthesis. Constructor: `OllamaSynthesizer(base_url: str = "http://localhost:11434", model: str, timeout: int = 120, _http_open=urllib.request.urlopen)`.

#### Scenario: Successful generation
- **WHEN** `synthesize(prompt)` is called and `_http_open` returns HTTP 200 with body `{"response": "text", "done": true}`
- **THEN** `"text"` is returned (stripped of leading/trailing whitespace)

#### Scenario: Non-200 from Ollama
- **WHEN** `_http_open` returns a non-200 HTTP status
- **THEN** `synthesize` raises `click.ClickException` containing the status code

#### Scenario: Request timeout
- **WHEN** `_http_open` raises `urllib.error.URLError` wrapping `socket.timeout`
- **THEN** `synthesize` raises `click.ClickException` mentioning "timed out" and "ai.timeout"

#### Scenario: Malformed JSON from Ollama
- **WHEN** `_http_open` returns HTTP 200 but the body is not valid JSON
- **THEN** `synthesize` raises `click.ClickException` mentioning "unexpected response format"

#### Scenario: Missing response key
- **WHEN** `_http_open` returns HTTP 200 with valid JSON but the `response` key is absent
- **THEN** `synthesize` raises `click.ClickException` mentioning "unexpected response format"

#### Scenario: Model availability check — model present
- **WHEN** `available()` is called and `_http_open` GET `/api/tags` returns HTTP 200 with `{"models": [{"name": "<model>"}]}` containing the configured model (exact match on the `name` field)
- **THEN** `available()` returns `True`; `_http_open` was called with `timeout=5` (hardcoded constant, not `self.timeout`)

#### Scenario: Ollama not running
- **WHEN** `available()` is called and `_http_open` raises `urllib.error.URLError` (connection refused)
- **THEN** `available()` returns `False` without raising

#### Scenario: Model not pulled
- **WHEN** `available()` is called and `/api/tags` returns 200 but the configured model is absent from the `name` fields in the `models` array
- **THEN** `available()` returns `False`

#### Scenario: Malformed tags response
- **WHEN** `available()` is called and `/api/tags` returns 200 but the body is not valid JSON or lacks the `models` key
- **THEN** `available()` returns `False`

### Requirement: VertexSynthesizer
The system SHALL implement `VertexSynthesizer` that calls the Vertex AI `rawPredict`
endpoint using the Anthropic Messages wire format. Constructor:
`VertexSynthesizer(project: str, region: str, model: str, timeout: int = 120, _http_open=urllib.request.urlopen, _gcloud=subprocess.run, _clock=time.time, _sleep=time.sleep)`.
Auth tokens are obtained via `gcloud auth print-access-token --format=json` (list form,
never `shell=True`). The gcloud output is parsed as JSON: `{"token": "...", "token_expiry": "..."}`.
The token is cached in-process; the cache is considered valid when `_clock() < expiry_epoch - 60`.
`expiry_epoch` is parsed from the `token_expiry` field (ISO 8601 string). `available()`
does NOT make a Vertex API call — it only checks that `gcloud` is on PATH (via `shutil.which`)
and that `project` and `region` are non-empty. It trusts the factory has already validated
field values. HTTP timeout is per-request (each HTTP call to Vertex gets `timeout` seconds).
Total wall-clock time for a rate-limited call can exceed `timeout` by the cumulative backoff.

#### Scenario: Successful generation
- **WHEN** `synthesize(prompt)` is called and `_http_open` returns HTTP 200 with a valid Anthropic Messages response containing `content[0].type == "text"`
- **THEN** `content[0].text` is returned

#### Scenario: gcloud not on PATH
- **WHEN** `synthesize(prompt)` is called and `shutil.which("gcloud")` returns `None`
- **THEN** `click.ClickException` is raised with a message containing "gcloud CLI" and the install URL `https://cloud.google.com/sdk/docs/install`

#### Scenario: gcloud auth failure (non-zero exit)
- **WHEN** `_gcloud` returns `CompletedProcess(returncode=1)`
- **THEN** `synthesize` raises `click.ClickException` mentioning "gcloud auth print-access-token" and the stderr output; the user is directed to run `gcloud auth application-default login`

#### Scenario: Token cache hit
- **WHEN** `synthesize` is called and `_clock()` returns a value less than `expiry_epoch - 60`
- **THEN** `_gcloud` call count is 0 (verified via mock); the cached token is used

#### Scenario: Token cache expiry
- **WHEN** `synthesize` is called and `_clock()` returns a value greater than `expiry_epoch - 60`
- **THEN** `_gcloud` is called exactly once to obtain a fresh token

#### Scenario: HTTP 429 retry with backoff
- **WHEN** `_http_open` returns HTTP 429 on the first call then HTTP 200 on the second
- **THEN** `_sleep` is called once with a value between `0.75` and `1.25` (base 1s ±25% jitter); the final response is returned

#### Scenario: 429 exhausted after 5 retries
- **WHEN** `_http_open` returns HTTP 429 on all 6 calls (1 original + 5 retries)
- **THEN** `synthesize` raises `click.ClickException` mentioning "rate limited" and "5 retries"; exactly 6 HTTP calls were made (verified via mock call count); `_sleep` was called exactly 5 times

#### Scenario: 429 succeeds on retry N
- **WHEN** `_http_open` returns HTTP 429 on calls 1–3 then HTTP 200 on call 4
- **THEN** the response is returned; exactly 4 HTTP calls were made; `_sleep` was called exactly 3 times with increasing values

#### Scenario: Non-429 HTTP error from Vertex
- **WHEN** `_http_open` returns HTTP 4xx (not 429) or 5xx
- **THEN** `synthesize` raises `click.ClickException` containing the status code and the first 512 bytes of the response body; no retry is attempted

#### Scenario: Malformed JSON from Vertex
- **WHEN** `_http_open` returns HTTP 200 but the body is not valid JSON
- **THEN** `synthesize` raises `click.ClickException` mentioning "unexpected response format"

#### Scenario: Missing content in Vertex response
- **WHEN** `_http_open` returns HTTP 200 with valid JSON but `content[0].text` is absent or `content` is empty
- **THEN** `synthesize` raises `click.ClickException` mentioning "unexpected response format"

#### Scenario: Vertex availability check — gcloud present
- **WHEN** `available()` is called and `shutil.which("gcloud")` returns a path and `project` and `region` are non-empty
- **THEN** `available()` returns `True` without making a Vertex API call or invoking `_gcloud`

#### Scenario: Vertex unavailable — missing gcloud
- **WHEN** `available()` is called and `shutil.which("gcloud")` returns `None`
- **THEN** `available()` returns `False`

#### Scenario: Retry-After header respected
- **WHEN** `_http_open` returns HTTP 429 with a `Retry-After: 5` header (integer seconds)
- **THEN** `_sleep` is called with `5.0` (not the jitter-based exponential backoff value); the mock shape for `_http_open` MUST support `.getheader(name: str) -> str | None` on the response object
- **WHEN** the `Retry-After` header is absent or contains a non-integer value (e.g., an HTTP-date string)
- **THEN** the jitter-based exponential backoff is used instead

#### Scenario: 401 mid-flight (expired token)
- **WHEN** `_http_open` returns HTTP 401 (token expired mid-request)
- **THEN** the cached token is invalidated; `_gcloud` is called exactly once to refresh; the request is retried exactly once; exactly 2 HTTP calls were made total (verified via mock call count); `_gcloud` call count is 1 (verified via mock); if the retry also returns 401, `synthesize` raises `click.ClickException` mentioning "authentication failed" and "gcloud auth application-default login"
