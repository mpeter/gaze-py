## Why

The current `gazepy report --ai` integration shells out to external binaries (`opencode run`,
`ollama run`) rather than calling provider APIs directly. This is fragile, slow, and
untestable without mocking subprocesses. The `claude` adapter always raises immediately —
it was never implemented. Dewey, the reference implementation in this ecosystem, uses
direct HTTP REST calls with a typed `Synthesizer` interface and config-file-driven provider
selection. gaze-py should mirror that pattern.

## What Changes

- **Remove** the subprocess-based `_call_opencode`, `_call_ollama`, `_call_claude` adapters
  from `src/gaze_py/report/ai.py`
- **Remove** the `--ai` and `--ai-timeout` CLI flags from `gazepy report`
- **Add** `Synthesizer` Protocol with `synthesize(prompt) -> str`, `available() -> bool`,
  `model_id() -> str`
- **Add** `OllamaSynthesizer` — direct HTTP POST to Ollama `/api/generate` (no subprocess)
- **Add** `VertexSynthesizer` — direct HTTPS POST to Vertex AI `rawPredict` endpoint,
  Anthropic Messages wire format; auth via `gcloud auth print-access-token` subprocess
  with TTL token cache; exponential backoff on HTTP 429
- **Add** `ProviderConfig` dataclass and `new_synthesizer_from_config()` factory
- **Add** `ai:` section to `.gaze.yaml` and `GazeConfig` for provider selection
- **Add** env var overrides: `GAZEPY_AI_PROVIDER`, `GAZEPY_AI_MODEL`, `GAZEPY_AI_ENDPOINT`
- **Modify** `gazepy report` to wire config → factory → `synth.synthesize()`; if no provider
  configured, emit raw JSON to stdout (prompt-only mode) with a tip to stderr
- **Keep** `--model` flag as a CLI override for the config model

## Capabilities

### New Capabilities

- `ai-synthesizer`: Typed `Synthesizer` Protocol, `OllamaSynthesizer` (HTTP), and
  `VertexSynthesizer` (HTTPS + gcloud auth + retry) implementations in
  `src/gaze_py/report/ai.py`
- `ai-provider-config`: `ProviderConfig` dataclass, `new_synthesizer_from_config()` factory,
  and `read_ai_config()` function reading `.gaze.yaml` `ai:` section and env vars in
  `src/gaze_py/report/provider.py` and `src/gaze_py/report/config.py`

### Modified Capabilities

- `gazepy-report-command`: CLI surface changes — `--ai` and `--ai-timeout` flags removed,
  `--model` retained; provider now config-driven not flag-driven

## Impact

- `src/gaze_py/report/ai.py` — full replacement
- `src/gaze_py/report/provider.py` — new file
- `src/gaze_py/report/config.py` — new file
- `src/gaze_py/config/loader.py` — add `ai:` section to `GazeConfig`
- `src/gaze_py/cli/main.py` — remove `--ai`/`--ai-timeout`, wire synthesizer
- `tests/test_report_ai.py` — replace subprocess-mock tests with HTTP-mock tests
- `tests/test_report_provider.py` — new file
- No new required dependencies; `gcloud` CLI is an external tool (not a Python dep);
  Ollama uses stdlib `urllib`/`http.client`
