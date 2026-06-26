## MODIFIED Requirements

### Requirement: report command AI provider selection
The `gazepy report` command SHALL select the AI provider via `.gaze.yaml` `ai:` section
and environment variables, NOT via a `--ai` CLI flag. The `--ai` and `--ai-timeout` flags
SHALL be removed. The `--model` flag SHALL be retained as a per-invocation model override.
The `_load_report_prompt()` helper (loads `gaze-reporter.md` system prompt) and
`_assemble_report_payload()` helper (serializes analysis result to JSON) SHALL be retained
unchanged. The AI narrative is emitted as plain text to stdout — it is NOT added as a new
field to the JSON schema (no OC-002 schema change). In AI mode, the JSON payload is
consumed by the synthesizer; in prompt-only mode, the JSON payload is emitted to stdout.

#### Scenario: Provider from config
- **WHEN** `.gaze.yaml` has `ai: {provider: ollama, model: llama3.2:3b}` and `--model` is not passed
- **THEN** `gazepy report` synthesizes using `OllamaSynthesizer` with model `llama3.2:3b`

#### Scenario: Model CLI override
- **WHEN** `.gaze.yaml` has `ai: {provider: ollama, model: llama3.2:3b}` and `--model gemma3:4b` is passed
- **THEN** synthesis uses model `gemma3:4b` with provider `ollama`

#### Scenario: --ai flag rejected
- **WHEN** `gazepy report --ai ollama` is invoked
- **THEN** exit code is 2 and stderr contains "No such option: --ai" (flag removed)

#### Scenario: --ai-timeout flag rejected
- **WHEN** `gazepy report --ai-timeout 60` is invoked
- **THEN** exit code is 2 and stderr contains "No such option: --ai-timeout" (flag removed)

#### Scenario: synthesize() raises after available() returns True
- **WHEN** `synthesizer.available()` returns `True` but `synthesizer.synthesize()` raises `click.ClickException`
- **THEN** the exception propagates and click prints the error to stderr with exit code 1

### Requirement: report command prompt-only mode
The `gazepy report` command SHALL emit the raw analysis JSON to stdout and a tip to stderr
when no AI provider is configured, or when the configured provider is not available. The
exit code SHALL be 0 in both cases (prompt-only is a valid output mode, not an error).

#### Scenario: No provider configured
- **WHEN** no `ai:` section in `.gaze.yaml` and no `GAZEPY_AI_*` env vars
- **THEN** the JSON analysis payload is written to stdout; stderr contains a tip mentioning how to configure a provider via `.gaze.yaml` `ai:` section; exit code is 0

#### Scenario: Provider configured but unavailable
- **WHEN** `.gaze.yaml` has `ai: {provider: ollama, model: llama3.2:3b}` but `available()` returns `False`
- **THEN** stderr contains a warning in the format: `"Warning: ollama provider configured but not available (model llama3.2:3b not found) — falling back to prompt-only mode"`; the JSON analysis payload is written to stdout; exit code is 0

### Requirement: report command backward-compat migration
The removal of `--ai` and `--ai-timeout` SHALL be documented in `CHANGELOG.md` with a
migration note. The project URLs in `pyproject.toml` SHALL be updated to point to
`github.com/unbound-force/gaze-py` (not `github.com/mpeter/gaze-py`).

#### Scenario: CHANGELOG entry exists
- **WHEN** `CHANGELOG.md` is read
- **THEN** it contains an entry for the removal of `--ai` and `--ai-timeout` with migration guidance pointing to the `.gaze.yaml` `ai:` section

#### Scenario: CLI test injection mechanism
- **WHEN** `gazepy report` CLI tests are written using `CliRunner`
- **THEN** `new_synthesizer_from_config` is patched (via `unittest.mock.patch`) to return a `NoopSynthesizer`, enabling tests to run without a live Ollama or Vertex instance
