## Context

`src/gaze_py/report/ai.py` currently dispatches to three subprocess adapters via `call_ai()`.
The `opencode` and `ollama` adapters shell out to external binaries; the `claude` adapter
raises immediately and has never been implemented. Provider selection is done at CLI invocation
time via `--ai <provider>`, making it impossible to configure once in a project and use
consistently.

The reference implementation is Dewey (https://github.com/unbound-force/dewey/tree/main/llm/), which uses a
`Synthesizer` interface backed by direct HTTP calls, a factory keyed on a `ProviderConfig`
struct, and config-file + env-var precedence for provider selection. This design mirrors
that pattern in Python.

## Goals / Non-Goals

**Goals:**
- Direct HTTP REST calls to Ollama and Vertex AI — no subprocess for the actual synthesis
- Typed `Synthesizer` Protocol injectable for testing (replaces `_subprocess_run` injection)
- Config-driven provider selection via `.gaze.yaml` `ai:` section and env vars
- Vertex auth via `gcloud auth print-access-token` subprocess with TTL token cache
- Exponential backoff on Vertex HTTP 429 (up to 5 retries, base 1s, max 60s, ±25% jitter)
- Prompt-only mode when no provider configured (emit raw JSON, tip to stderr)
- `--model` CLI flag retained as override for config model

**Non-Goals:**
- Streaming output (`--stream`) — deferred to BI-001
- Anthropic SDK or google-auth Python SDK — gcloud CLI handles Vertex auth
- `--baseline` delta reporting — deferred to BI-001
- Ollama auto-start subprocess — Dewey does this; gaze-py does not (out of scope)
- The `--baseline` stub in `gazepy report` is preserved unchanged — removal is out of scope
- Adding a `ai_narrative` field to the JSON output schema — AI output is plain text, not a schema field (no OC-002 change)

## Decisions

**D1 — Direct HTTP over subprocess for synthesis**

Subprocess adapters (`opencode run`, `ollama run`) have no stable machine-readable protocol,
add ~300ms process startup overhead each call, and require mocking `subprocess.run` in tests.
Direct HTTP POST to Ollama `/api/generate` and Vertex `rawPredict` is explicit, testable via
`unittest.mock` patching `urllib.request.urlopen`, and mirrors Dewey exactly.

*Alternative considered*: Keep subprocess for Ollama, only switch Vertex. Rejected — the
inconsistency adds complexity without benefit.

**D2 — `Synthesizer` Protocol (structural subtyping) over ABC** *(AP-007 deviation, pre-approved)*

Python `Protocol` allows test doubles (`NoopSynthesizer`) without inheriting from a base
class. Mirrors Dewey's Go interface pattern. No runtime ABC overhead. AP-007 prefers ABC
for owned interfaces; this deviation is pre-approved for this change because the test double
ergonomics outweigh the convention benefit and the interface is small (3 methods).

**D3 — gcloud CLI for Vertex auth, not google-auth SDK**

`google-auth` adds a required dependency for a capability most users won't use. `gcloud auth
print-access-token` is already present on any machine configured for Vertex. Token cached
in-process with a TTL of `expiry - 60s` to avoid clock-skew races; re-fetched on expiry.
Cache is per-process (not persisted). If `gcloud` is not on PATH, raise a clear
`click.ClickException` pointing to install docs.

*Alternative considered*: `gaze-py[vertex]` optional dep with `google-auth`. Rejected per
user decision — subprocess auth avoids any Python dependency for Vertex.

**D4 — Config in `.gaze.yaml` `ai:` section, env vars as overrides**

Precedence (highest to lowest):
1. `--model` CLI flag (model only)
2. Env vars: `GAZEPY_AI_PROVIDER`, `GAZEPY_AI_MODEL`, `GAZEPY_AI_ENDPOINT` (Ollama only),
   `GAZEPY_AI_PROJECT`, `GAZEPY_AI_REGION`, `GAZEPY_AI_TIMEOUT`
3. `.gaze.yaml` `ai:` flat fields (`ai_provider`, `ai_model`, etc. in `GazeConfig`)
4. No synthesizer (prompt-only mode)

`GAZEPY_AI_ENDPOINT` applies to Ollama only; it is ignored for Vertex. When
`GAZEPY_AI_MODEL` is set without `GAZEPY_AI_PROVIDER`, the provider remains empty and the
factory selects Ollama via the model-only dispatch rule (D8 below).

**D8 — Flat fields on `GazeConfig` instead of nested `AiConfig` dataclass**

The existing `GazeConfig` uses flat primitives for all config (`doc_scan_timeout: float`,
`doc_scan_exclude: list[str]`, etc.). A nested `AiConfig` dataclass would introduce a new
structural pattern, require `_build_config` changes beyond key extraction, and add
cross-package import complexity. Flat `ai_*` fields are consistent, directly accessible
from `read_ai_config()`, and require only extending the existing `_build_config` parsing
pattern.

**D9 — `timeout` carried in `ProviderConfig`**

`ProviderConfig` includes `timeout: int = 120` so the factory can pass it directly to
synthesizer constructors. `read_ai_config()` populates `ProviderConfig.timeout` from
`GazeConfig.ai_timeout` (with env var override via `GAZEPY_AI_TIMEOUT`). This avoids
the CLI having to read `config.ai_timeout` separately from the factory path.

**D10 — `ai.timeout` is per-request, not total-operation**

`urllib.request.urlopen(timeout=N)` applies per HTTP call. For Vertex with 5 retries, the
worst-case wall-clock time is `timeout × 6 + cumulative_backoff` (up to ~800s at default
120s timeout). This is intentional: a rate-limited Vertex call should be allowed to
succeed eventually. Users who want shorter total time should set `ai.timeout` to a smaller
value or reduce retries. The error message for timeout includes the per-request nature:
"timed out after {timeout}s per request; try reducing ai.timeout in .gaze.yaml".

**D5 — Vertex wire format: Anthropic Messages via rawPredict**

Vertex AI hosts Claude models using the Anthropic Messages API format via the `rawPredict`
endpoint, identical to Dewey's `VertexSynthesizer`. Request body includes
`"anthropic_version": "vertex-2023-10-16"` and `"max_tokens": 4096`.

**D6 — Remove `--ai` and `--ai-timeout` flags, keep `--model`**

`--ai` is replaced by config. `--ai-timeout` moves to `.gaze.yaml` `ai.timeout` with a
120s default. `--model` is kept as a one-shot override (useful for experimentation without
editing config). No backward-compat shim — these flags are undocumented in the README and
the feature has never shipped as stable.

**D7 — New files: `provider.py` and `config.py` alongside `ai.py`**

`src/gaze_py/report/ai.py` — Protocol + implementations (Ollama, Vertex)
`src/gaze_py/report/provider.py` — `ProviderConfig` dataclass + factory
`src/gaze_py/report/config.py` — `read_ai_config()` reading GazeConfig + env vars

Mirrors Dewey's `llm/llm.go`, `llm/provider.go`, `llm/config.go` split exactly.

## Risks / Trade-offs

**gcloud not installed** → `VertexSynthesizer.__init__` does NOT check at construction time
(to allow config to be loaded without requiring gcloud). Check is deferred to
`available()` and `synthesize()`. Error message: "vertex provider requires gcloud CLI.
Install: https://cloud.google.com/sdk/docs/install and run: gcloud auth application-default
login". Mitigation: clear error, not a silent failure.

**Token cache per-process** → Long-running processes (future TUI/server mode) may need
cache invalidation. Mitigation: TTL is conservative (expiry - 60s); re-fetch is cheap.

**Vertex endpoint construction** → URL format is:
`https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/publishers/anthropic/models/{model}:rawPredict`
Region and project are required fields; missing either raises at factory time, not at call
time. Mitigation: validated in `new_synthesizer_from_config()`.

**HTTP timeout** → Ollama generation can be slow for large models. Default timeout 120s,
configurable via `.gaze.yaml` `ai.timeout`. Vertex has the same default. Mitigation:
timeout error message includes "try increasing ai.timeout in .gaze.yaml".

**Ollama availability check** → `OllamaSynthesizer.available()` calls GET `/api/tags` with
a 5s timeout and checks for the configured model in the response. Does not cache (unlike
Dewey) to keep implementation simple — `available()` is only called once per `report`
invocation. If Ollama is not running, `available()` returns `False` and the command falls
back to prompt-only mode with a warning.

## Migration Plan

1. Implement on branch `opsx/ai-http-adapters`
2. No data migration — `.gaze.yaml` `ai:` section is additive; existing configs without it
   continue to work (prompt-only mode)
3. Users who relied on `--ai opencode` or `--ai ollama` must migrate to `.gaze.yaml`:
   ```yaml
   ai:
     provider: ollama
     model: llama3.2:3b
   ```
   Since `--ai` was never in a stable release and is not in the README, migration burden
   is minimal
4. Rollback: revert branch; no schema changes to existing files

## Porting Contract Compliance

**Principle V sign-off: CLEAR**

This change modifies the O2 AI reporting pipeline only. Per `requirements.md` O2:
"Contracts honored: None specific. AI reports consume the output of R1–R5 but do not
define behavioral contracts of their own. A port MAY use any AI integration approach."
No EC-001 through OC-003 contracts are affected. No taxonomy, scoring, or classification
changes are introduced.

**Supply Chain (Principle VII)**: No new Python dependencies are added. `gcloud` is an
external system tool — its absence causes a clear user-facing error, not a silent failure.
`urllib.request` and `http.client` are stdlib. The `gcloud` subprocess cannot be pinned in
`uv.lock` (it is not a Python package); this supply chain gap is acknowledged. Users should
document their `gcloud` version in deployment runbooks if using Vertex in CI.
