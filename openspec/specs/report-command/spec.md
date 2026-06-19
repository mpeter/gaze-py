# Spec: report-command

Capability: `gazepy report` — AI-powered narrative reports and JSON payload emission.

Sources: `openspec/changes/archive/2026-06-18-report-command/proposal.md`,
`openspec/changes/archive/2026-06-18-report-command/design.md`,
`src/gaze_py/report/ai.py`, `src/gaze_py/cli/main.py`, `CHANGELOG.md`.

---

### Requirement: JSON-only mode (no --ai)

When `gazepy report PATH` is invoked without a configured AI provider,
the command SHALL:

1. Run the CRAP analysis pipeline on `PATH`
2. Optionally enrich with quality data when `--tests` is provided or
   auto-discovered
3. Emit the raw JSON analysis payload to stdout (same format as
   `gazepy crap --format=json`)
4. Print `"Tip: pass --ai opencode to get a narrative report."` to stderr
5. Enforce CI gates (`--max-crapload`, `--max-gaze-crapload`,
   `--min-contract-coverage`) **after** emitting the payload
6. Exit 0 when no gate is violated

The JSON payload is always written before any CI gate exit, so the payload
is available even when the gate fires.

#### Scenario: No provider configured
- **WHEN** `gazepy report src/mypackage/` is run with no `ai:` config and
  no `GAZEPY_AI_PROVIDER` env var
- **THEN** stdout contains the JSON analysis payload, stderr contains the
  tip message, and the command exits 0

#### Scenario: CI gate fires after payload
- **WHEN** `--max-gaze-crapload=5` is set and the result exceeds 5
- **THEN** the JSON payload is written to stdout first, then the gate
  error is emitted to stderr, and the command exits 1

---

### Requirement: AI mode (provider configured)

When an AI provider is configured (via `.gaze.yaml` `ai:` section or
`GAZEPY_AI_*` environment variables), `gazepy report PATH` SHALL:

1. Run the same analysis pipeline as JSON-only mode
2. Assemble the JSON payload string
3. Load the system prompt via `_load_report_prompt()`
4. Call the configured AI provider with the prompt and payload
5. Emit the AI response to stdout
6. Enforce CI gates after emitting the response
7. Exit 0 when no gate is violated

#### Scenario: AI provider produces narrative
- **WHEN** a provider is configured and reachable
- **THEN** stdout contains the AI narrative report (plain text), not raw JSON

#### Scenario: --format ignored in AI mode
- **WHEN** `--format=json` is explicitly set alongside a configured provider
- **THEN** a warning is emitted to stderr: `"Warning: --format is ignored in
  AI mode; output is always plain text."` and the AI response is still emitted

---

### Requirement: Supported AI providers

The `report` command SHALL support the following AI providers:

**`ollama`** — HTTP REST to a local Ollama server:
- Communicates via `ollama run <model>` subprocess with prompt+payload on stdin
- Model is **required** for ollama; omitting `--model` with no configured model
  raises a clear error
- Binary detected via `shutil.which("ollama")`; if not found, raises
  `ClickException` with install hint: `"Install it from: https://ollama.com"`

**`vertex`** — Google Vertex AI via rawPredict (Anthropic Messages format):
- Calls the Vertex AI REST endpoint directly via HTTP (no subprocess)
- Requires `ai.project` and `ai.region` (or `GAZEPY_AI_PROJECT`,
  `GAZEPY_AI_REGION`)
- Uses `GOOGLE_APPLICATION_CREDENTIALS` or Application Default Credentials

**`opencode`** — opencode CLI subprocess (legacy, from Change 1):
- Invokes `opencode run [--model MODEL] "<prompt>\n\n<payload>"`
- Binary detected via `shutil.which("opencode")`; if not found, raises
  `ClickException` with install hint: `"Install it with: npm install -g opencode-ai"`
- Model is optional; when omitted, opencode uses its configured default

**`claude`** — deferred to Change 4B:
- Passing `--ai claude` (or `ai.provider: claude` in config) raises
  `ClickException`: `"claude adapter is available in Change 4B. Use
  --ai opencode or --ai ollama."`

All subprocess adapters MUST use list form (never `shell=True`) to prevent
shell injection.

#### Scenario: ollama model required
- **WHEN** `ai.provider: ollama` is configured but no model is set
- **THEN** the command exits non-zero with a clear error message requesting
  `--model` or `ai.model` in config

#### Scenario: Provider binary not found
- **WHEN** the configured provider binary is not on PATH
- **THEN** the command exits non-zero with a clear error message and an
  install hint for that provider

#### Scenario: claude deferred
- **WHEN** `ai.provider: claude` is configured
- **THEN** the command exits non-zero with a message directing the user to
  use `opencode` or `ollama` instead

---

### Requirement: Provider configuration

The AI provider SHALL be configured via `.gaze.yaml` `ai:` section or
`GAZEPY_AI_*` environment variables. Environment variables override config
file values. The `--model` CLI flag overrides both.

Config file fields (`ai:` section):
- `provider` — string: `"ollama"`, `"vertex"`, or `"opencode"`
- `model` — string: provider-specific model identifier
- `endpoint` — string: custom endpoint URL (overrides provider default)
- `project` — string: GCP project ID (Vertex AI)
- `region` — string: GCP region (Vertex AI)
- `timeout` — int: seconds (default: 120)

Environment variable overrides:
- `GAZEPY_AI_PROVIDER` → `ai.provider`
- `GAZEPY_AI_MODEL` → `ai.model`
- `GAZEPY_AI_ENDPOINT` → `ai.endpoint`
- `GAZEPY_AI_PROJECT` → `ai.project`
- `GAZEPY_AI_REGION` → `ai.region`
- `GAZEPY_AI_TIMEOUT` → `ai.timeout`

#### Scenario: Env var overrides config
- **WHEN** `ai.provider: ollama` is in `.gaze.yaml` and `GAZEPY_AI_PROVIDER=vertex`
  is set
- **THEN** the vertex provider is used

#### Scenario: --model overrides all
- **WHEN** `ai.model: llama3` is in config and `--model mistral` is passed
- **THEN** `mistral` is used for this invocation

---

### Requirement: System prompt loading

`_load_report_prompt(workdir: Path) -> str` SHALL:

1. Check `workdir / ".opencode" / "agents" / "gaze-reporter.md"` for a local
   user override. The file MUST resolve to a path contained within `workdir`
   (path traversal guard).
2. If the local override exists and passes the guard: read it, strip YAML
   frontmatter, return.
3. Otherwise: read the bundled asset at
   `src/gaze_py/cli/assets/agents/gaze-reporter.md` via `importlib.resources`,
   strip frontmatter, return.

YAML frontmatter stripping: remove the block between the first `---\n` and
the next `\n---` line. If no frontmatter is present, return content unchanged.
This matches Go's `stripFrontmatter()` algorithm.

#### Scenario: Local override used
- **WHEN** `.opencode/agents/gaze-reporter.md` exists in the working directory
- **THEN** that file is used as the system prompt (with frontmatter stripped)

#### Scenario: Bundled asset fallback
- **WHEN** no local override exists
- **THEN** the bundled `gaze-reporter.md` asset is used (with frontmatter stripped)

#### Scenario: Path traversal blocked
- **WHEN** a symlink in `.opencode/agents/gaze-reporter.md` resolves outside
  `workdir`
- **THEN** the local file is ignored and the bundled asset is used instead

---

### Requirement: Payload assembly

`_assemble_report_payload(result: AnalysisResult) -> str` SHALL return
`to_json(result)` — the same JSON that `gazepy crap --format=json` produces.
This includes CRAP scores, GazeCRAP scores, quadrants, contract coverage,
fix strategies, and recommended actions. No additional transformation is
applied; the existing serializer is reused.

#### Scenario: Payload matches crap JSON output
- **WHEN** `gazepy report PATH` is run in JSON-only mode
- **THEN** the stdout payload is byte-for-byte equivalent to
  `gazepy crap PATH --format=json` for the same input

---

### Requirement: Quality enrichment via --tests

`--tests PATH` on the `report` command SHALL enable the O1 quality pipeline,
adding GazeCRAP scores and contract coverage data to the payload. When
`--tests` is omitted and auto-discovery finds no test directory, the quality
enrichment step is skipped; the report still runs with CRAP-only data.

#### Scenario: Tests provided
- **WHEN** `gazepy report src/ --tests tests/` is run
- **THEN** the payload includes `gaze_crap`, `contract_coverage`, and
  `gap_hints` fields populated from the O1 pipeline

#### Scenario: No tests found
- **WHEN** `--tests` is omitted and no test directory is auto-discovered
- **THEN** the report runs with CRAP-only data; `gaze_crap` and
  `contract_coverage` fields are `null` in the payload

---

### Requirement: CI gates on report command

The `report` command SHALL enforce the same CI gates as `gazepy crap`:

- `--max-crapload=N` — exit 1 when `summary.crapload > N` (0 = no limit)
- `--max-gaze-crapload=N` — exit 1 when `summary.gaze_crapload > N`
  (0 = no limit; requires quality enrichment for `gaze_crapload` to be
  non-null)
- `--min-contract-coverage=N` — exit 1 when average contract coverage
  percentage is below `N`

Gates fire **after** output is emitted in both JSON-only and AI modes.

#### Scenario: max-gaze-crapload gate
- **WHEN** `--max-gaze-crapload=3` and `summary.gaze_crapload` is 5
- **THEN** the command emits output first, then exits 1 with a message:
  `"CI gate: gaze_crapload=5 exceeds --max-gaze-crapload=3"`

---

### Requirement: call_ai injectable subprocess

`call_ai(prompt, payload, *, provider, model, timeout, _subprocess_run)` SHALL
accept `_subprocess_run` as an injectable parameter (default: `subprocess.run`)
so tests can mock subprocess calls without patching. No real subprocess is
spawned during unit tests.

#### Scenario: Test injection
- **WHEN** `_subprocess_run` is replaced with a mock returning a fake result
- **THEN** `call_ai` returns the mock's stdout without spawning a real process
