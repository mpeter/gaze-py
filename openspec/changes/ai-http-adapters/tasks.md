## Coverage Strategy

All new production code in `ai.py` (replacement), `provider.py`, and `config.py` MUST be
covered by HTTP-mock tests. All `urllib.request.urlopen` calls are patched via
`unittest.mock.patch`. All `gcloud` subprocess calls use injectable `_gcloud`. Time-dependent
paths use injectable `_clock` and `_sleep`. `NoopSynthesizer` lives in `src/gaze_py/report/ai.py`
(not in `tests/`). The project-wide 85% coverage gate applies. No `@pytest.mark.slow` tests
are required — all tests must run without network access or real sleeping.

## 1. Config layer

- [x] 1.1 Add flat `ai_*` fields to `GazeConfig` in `src/gaze_py/config/loader.py`: `ai_provider: str = ""`, `ai_model: str = ""`, `ai_endpoint: str = ""`, `ai_project: str = ""`, `ai_region: str = ""`, `ai_timeout: int = 120`
- [x] 1.2 Parse `ai:` YAML block in `_build_config` using existing key-extraction pattern (consistent with `classification:` and `scoring:` blocks); silently ignore unknown keys
- [x] 1.3 Add `ai_timeout` validation to `_validate`: must be `> 0`; error message format: `"ai.timeout must be > 0, got X in /path/.gaze.yaml"`; coerce float input to int via existing `_to_int` helper
- [x] 1.4 Add tests for ai field parsing, defaults, timeout validation, float coercion, and unknown key handling to `tests/test_config.py`

## 2. Provider config and factory

- [x] 2.1 Create `src/gaze_py/report/provider.py` with `ProviderConfig` dataclass: fields `provider: str = ""`, `model: str = ""`, `endpoint: str = ""`, `project: str = ""`, `region: str = ""`, `timeout: int = 120`
- [x] 2.2 Implement `new_synthesizer_from_config(cfg: ProviderConfig) -> Synthesizer | None` factory with dispatch: both empty → None; `""` or `"ollama"` + model → OllamaSynthesizer (with endpoint default and timeout); `"vertex"` → validate project/region/model chars then VertexSynthesizer; unknown → ClickException
- [x] 2.3 Create `src/gaze_py/report/config.py` with `read_ai_config(gaze_config: GazeConfig, cli_model: str | None) -> ProviderConfig` applying precedence: cli_model (model only) > env vars (`GAZEPY_AI_PROVIDER`, `GAZEPY_AI_MODEL`, `GAZEPY_AI_ENDPOINT`, `GAZEPY_AI_PROJECT`, `GAZEPY_AI_REGION`, `GAZEPY_AI_TIMEOUT`) > gaze_config.ai_* fields > empty ProviderConfig; parse `GAZEPY_AI_TIMEOUT` as int, raise ClickException on invalid value
- [x] 2.4 Create `tests/test_report_provider.py` covering: all factory dispatch scenarios, unknown provider, missing project/region for Vertex, input validation for path-traversal chars, all config precedence scenarios including env var model-only, CLI model override, full Vertex env config, nothing configured

## 3. Synthesizer implementations

- [x] 3.1 Replace `src/gaze_py/report/ai.py` content: define `Synthesizer` Protocol, `NoopSynthesizer` (exported; constructor: `response=""`, `err=None`, `avail=True`, `model="noop"`)
- [x] 3.2 Implement `OllamaSynthesizer(base_url, model, timeout=120, _http_open=urllib.request.urlopen)`: `synthesize` via POST `/api/generate` (stream=false), return `response` field; raise ClickException on non-200, malformed JSON, missing `response` key, or URLError timeout; `available` via GET `/api/tags` (exact match on `name` field in `models` array, 5s timeout), return False on any error; `model_id` returns model
- [x] 3.3 Implement `VertexSynthesizer(project, region, model, timeout=120, _http_open=urllib.request.urlopen, _gcloud=subprocess.run, _clock=time.time, _sleep=time.sleep)`: token fetch via `["gcloud", "auth", "print-access-token", "--format=json"]` (list form, never shell=True), parse `{"token": "...", "token_expiry": "..."}`, cache with TTL = expiry_epoch - 60s; `available` checks `shutil.which("gcloud")` and non-empty project/region (no API call, trusts factory validation); `synthesize` builds rawPredict URL, sends Anthropic Messages request, returns `content[0].text`; raise ClickException on: gcloud not found (install URL), gcloud non-zero exit (include stderr + `gcloud auth application-default login` tip), HTTP 4xx/5xx (not 429, no retry), malformed JSON, missing content; HTTP 401 invalidates token cache and retries once
- [x] 3.4 Add 429 retry loop to `VertexSynthesizer.synthesize`: up to 5 retries (6 total attempts); exponential backoff base=1s max=60s ±25% jitter using `_sleep`; respect `Retry-After` header (integer seconds); raise ClickException after exhaustion mentioning "rate limited" and "5 retries"
- [x] 3.5 Replace `tests/test_report_ai.py` with HTTP-mock tests for: OllamaSynthesizer (success, non-200, timeout/URLError, malformed JSON, missing response key, tags match/miss/malformed); VertexSynthesizer (success, gcloud-not-found, gcloud-non-zero-exit, token cache hit/miss via mock _clock, 429-retry-then-success, 429-exhausted with call count assert, 429-success-on-attempt-N, non-429 4xx/5xx, malformed JSON, missing content, 401-refresh-retry); NoopSynthesizer (happy path, error path)

## 4. CLI wiring

- [x] 4.1 Remove `--ai` and `--ai-timeout` flags from `gazepy report` in `src/gaze_py/cli/main.py`; retain `--model`; preserve `_load_report_prompt()` and `_assemble_report_payload()` helpers unchanged
- [x] 4.2 Wire `read_ai_config(config, cli_model)` → `new_synthesizer_from_config(cfg)` → check `synth.available()` → `synth.synthesize(_load_report_prompt(Path.cwd()) + "\n\n" + _assemble_report_payload(result))`
- [x] 4.3 Implement prompt-only mode: if `synth is None` → emit JSON to stdout + tip to stderr; if `synth.available()` is False → emit warning `"Warning: {provider} provider configured but not available ({model} not found) — falling back to prompt-only mode"` to stderr + emit JSON to stdout; exit code 0 in both cases
- [x] 4.4 Update CLI tests in `tests/test_cli.py`: assert `--ai` and `--ai-timeout` return exit code 2; test config-driven flow by patching `new_synthesizer_from_config` to return `NoopSynthesizer`; test `--model` override; test prompt-only mode (no provider); test unavailable provider fallback
- [x] 4.5 Update `src/gaze_py/report/__init__.py` module docstring to reflect the new module structure (ai.py: Protocol + implementations; provider.py: factory; config.py: config loading)

## 5. Documentation and housekeeping

- [x] 5.1 Add `CHANGELOG.md` entry documenting removal of `--ai` and `--ai-timeout` with migration note: configure provider via `.gaze.yaml` `ai:` section or `GAZEPY_AI_*` env vars
- [x] 5.2 Update `README.md` with `## AI Reports` section: configuration via `.gaze.yaml` `ai:` block, all env vars with descriptions, Ollama prerequisites (model pulled), Vertex prerequisites (`gcloud` installed + `gcloud auth application-default login`), and troubleshooting
- [x] 5.3 Update `pyproject.toml` project URLs to `github.com/unbound-force/gaze-py`

## 6. Gate check

- [x] 6.1 `uv run ruff check .` passes
- [x] 6.2 `uv run ruff format --check .` passes
- [x] 6.3 `uv run mypy --strict src/` passes
- [x] 6.4 `uv run pytest -m "not slow" --no-cov` passes (all tests green, no network access, no real sleeping)
- [x] 6.5 `uv run pytest` passes (pyproject.toml addopts enforce `--cov=gaze_py --cov-fail-under=85`)
- [x] 6.6 Verify `test.yml` requires no changes — no new secrets, services, or env vars needed in CI

<!-- spec-review: passed -->
