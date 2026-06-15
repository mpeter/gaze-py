## Why

`gazepy report` has been a stub since v0.1 with the message "use Go
gaze for full AI reports." O1 is shipped. O1 Astroid pairing is
shipped. Gap hints will be shipped (Change 1). The raw data now exists:
CRAP scores, GazeCRAP scores, quadrant assignments, contract coverage
percentages, gap effects, and assertion snippets. An AI-powered
narrative report translates that raw data into actionable prose —
severity assessments, remediation priorities, architectural risk
observations — without requiring the user to parse JSON.

The `gaze-reporter.md` agent prompt is already bundled at
`src/gaze_py/cli/assets/agents/gaze-reporter.md`. The existing
analysis pipeline (`_run_crap` + `_enrich_with_quality`) already
produces the payload. This change wires them together and calls an LLM
subprocess.

This also resolves the stale "not enforced until O1" warning on
`--max-gaze-crapload` (O5). O1 is shipped; enforcement is a one-line
wire-up included here.

## What Changes

### New Capabilities

- `report-command`: `gazepy report` produces AI-powered narrative
  reports. Subprocess-based adapters for `opencode`, `ollama`, and
  `claude` CLI. No new Python dependencies. AI is optional — without
  `--ai`, the command emits the JSON payload to stdout (useful for
  piping to external tools).

### Modified Capabilities

- `crap` command: `--max-gaze-crapload` now enforced (was stale warn).
  Help text updated from "enforcement deferred until O1" to
  "CI gate: fail (exit 1) when gaze_crapload exceeds this value."
- `self-check` command: same `--max-gaze-crapload` fix.
- `report` command: stub body replaced with real pipeline.

### Removed Capabilities

None.

## Capabilities not in scope (deferred to Change 4B)

- Anthropic SDK, Google Generative AI SDK, OpenAI SDK adapters
- Streaming output (`--stream` flag)
- `--baseline` delta reporting
- AI-assisted assertion mapping

## Impact

- `src/gaze_py/report/ai.py` — new subprocess adapter module
- `src/gaze_py/cli/main.py` — report command body; O5 enforcement;
  `_load_report_prompt()`; `_assemble_report_payload()`
- `tests/test_report_ai.py` — new
- `tests/test_cli.py` — appended tests

## Constitution Alignment

Assessed against `.specify/memory/constitution.md`.

### I. Autonomous Collaboration

**Assessment**: PASS

The report command produces machine-readable JSON by default (`--ai`
is optional). When `--ai` is provided, the narrative output is
human-readable prose. Both modes are self-contained outputs.

### II. Minimal Assumptions

**Assessment**: PASS

No assumptions about which LLM is available. Provider detection uses
`shutil.which()` — if the provider CLI is not on PATH, the command
fails with a clear error and install hint. No fallback guessing.

### III. Observable Quality

**Assessment**: PASS

The `--ai` flag makes AI involvement explicit. Without it, the command
produces JSON — observable, parseable, pipeable. The system prompt
source is logged to stderr when `--verbose`.

### IV. Testability

**Assessment**: PASS

`call_ai()` accepts `subprocess_run` as an injectable parameter
(default `subprocess.run`) so tests can mock the subprocess call
without patching. `_load_report_prompt()` is a pure file-reading
function with a deterministic fallback.

### V. Porting Contract Supremacy

**Assessment**: PASS

O2 is an optional capability with no behavioral contracts in the
porting docs. The implementation follows the Go reference architecture
(prompt loading, payload assembly, subprocess adapter pattern) without
being bound to it. The O5 enforcement fix strictly follows the
porting contract (SC-003: GazeCRAPload defined, thresholds
configurable, CI exit on violation).

### VI. Composability First

**Assessment**: PASS

`src/gaze_py/report/ai.py` is a library module — importable without
the CLI. No new runtime dependencies. AI is opt-in via `--ai` flag.
The JSON payload mode works standalone without any external tool.
