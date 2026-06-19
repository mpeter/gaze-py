# Spec: config-loading

Capability: `.gaze.yaml` configuration loading and `GazeConfig` defaults.

Sources: `src/gaze_py/config/loader.py`, `CHANGELOG.md`.

---

### Requirement: Config file discovery

`load_config(start_path: Path) -> GazeConfig` SHALL walk upward from
`start_path` to find `.gaze.yaml`. The walk SHALL stop at the first ancestor
directory containing `pyproject.toml` or `.git` (project root sentinels).
Config files above the project root boundary SHALL NOT be read.

When no `.gaze.yaml` is found, a default `GazeConfig` SHALL be returned
silently (no error, no warning).

#### Scenario: Config found at project root
- **WHEN** `.gaze.yaml` exists in the same directory as `pyproject.toml`
- **THEN** that config file is loaded and returned

#### Scenario: Config found in intermediate directory
- **WHEN** `.gaze.yaml` exists in an ancestor directory between `start_path`
  and the project root
- **THEN** that config file is loaded (first match wins, walking upward)

#### Scenario: No config file exists
- **WHEN** no `.gaze.yaml` is found anywhere in the walk
- **THEN** a default `GazeConfig` is returned with no error or warning

#### Scenario: Config above project root ignored
- **WHEN** `.gaze.yaml` exists in a directory above `pyproject.toml` or `.git`
- **THEN** it is not read; the walk stops at the project root boundary

#### Scenario: start_path is a file
- **WHEN** `start_path` points to a `.py` file rather than a directory
- **THEN** the walk begins from `start_path.parent`

---

### Requirement: Explicit config loading

`load_config_explicit(config_path: Path) -> GazeConfig` SHALL load
configuration from the exact path provided, bypassing walk-up discovery.
This is used when the caller provides a `--config` CLI flag.

#### Scenario: Explicit path used
- **WHEN** `--config /path/to/.gaze.yaml` is passed
- **THEN** that exact file is loaded, regardless of the analysis path

---

### Requirement: Supported configuration fields

`.gaze.yaml` SHALL support the following fields. Unknown keys SHALL be
silently ignored for forward-compatibility.

**Classification thresholds** (`classification.thresholds.*`):
- `contractual` — int, default `80`. Minimum confidence score for the
  "contractual" label. Must be in `[0, 100]`.
- `incidental` — int, default `50`. Maximum confidence score (exclusive)
  for the "incidental" label. Must be in `[0, 100]`.

**Scoring thresholds** (`scoring.*`):
- `crap_threshold` — float, default `15.0`. CRAP score threshold for
  CRAPload computation. Must be `> 0`.
- `gaze_crap_threshold` — float, default `15.0`. GazeCRAP score threshold
  for GazeCRAPload computation. Must be `> 0`.

**Document scanning** (`classification.doc_scan.*`):
- `exclude` — list of strings, default:
  `["vendor/**", "node_modules/**", ".git/**", "testdata/**", "CHANGELOG.md", "CONTRIBUTING.md"]`.
  fnmatch glob patterns for `.md` files to exclude.
- `include` — list of strings, default `[]` (empty = no filter; all files
  included). fnmatch glob patterns for `.md` files to include.
- `timeout` — float seconds, default `30.0`. Maximum time to spend scanning
  documents. Must be `> 0`.

**AI report configuration** (`ai.*`):
- `provider` — string: `"ollama"`, `"vertex"`, or `"opencode"`
- `model` — string: provider-specific model identifier
- `endpoint` — string: custom endpoint URL
- `project` — string: GCP project ID (Vertex AI)
- `region` — string: GCP region (Vertex AI)
- `timeout` — int seconds, default `120`. Timeout for AI provider calls.

#### Scenario: All defaults applied when no config
- **WHEN** no `.gaze.yaml` exists
- **THEN** `GazeConfig()` has `contractual_threshold=80`, `incidental_threshold=50`,
  `crap_threshold=15.0`, `gaze_crap_threshold=15.0`, `doc_scan_timeout=30.0`,
  `doc_scan_exclude` matching the Go reference list, `doc_scan_include=[]`

#### Scenario: Partial config merges with defaults
- **WHEN** `.gaze.yaml` sets only `classification.thresholds.contractual: 90`
- **THEN** `contractual_threshold` is 90 and all other fields retain defaults

#### Scenario: Unknown keys silently ignored
- **WHEN** `.gaze.yaml` contains an unrecognized key (e.g. `future_feature: true`)
- **THEN** the key is ignored and config loads successfully

---

### Requirement: Environment variable overrides for AI config

The following environment variables SHALL override the corresponding
`.gaze.yaml` `ai:` fields. Env vars take precedence over config file values.
The `--model` CLI flag takes precedence over both.

| Environment variable    | Overrides config field |
|-------------------------|------------------------|
| `GAZEPY_AI_PROVIDER`    | `ai.provider`          |
| `GAZEPY_AI_MODEL`       | `ai.model`             |
| `GAZEPY_AI_ENDPOINT`    | `ai.endpoint`          |
| `GAZEPY_AI_PROJECT`     | `ai.project`           |
| `GAZEPY_AI_REGION`      | `ai.region`            |
| `GAZEPY_AI_TIMEOUT`     | `ai.timeout`           |

#### Scenario: Env var overrides config file
- **WHEN** `ai.provider: ollama` is in `.gaze.yaml` and `GAZEPY_AI_PROVIDER=vertex`
  is set in the environment
- **THEN** the vertex provider is used

#### Scenario: --model overrides env var and config
- **WHEN** `GAZEPY_AI_MODEL=llama3` is set and `--model mistral` is passed
- **THEN** `mistral` is used for the invocation

---

### Requirement: Validation

The following validation rules SHALL be enforced after parsing. Violations
SHALL raise `GazeConfigError` with a descriptive message and cause a non-zero
exit.

- `contractual_threshold` must be in `[0, 100]`
- `incidental_threshold` must be in `[0, 100]`
- `crap_threshold` must be `> 0`
- `gaze_crap_threshold` must be `> 0`
- `doc_scan_timeout` must be `> 0`; if `<= 0`, the error message SHALL be
  `"doc_scan.timeout must be positive"`

#### Scenario: Invalid contractual threshold
- **WHEN** `.gaze.yaml` sets `classification.thresholds.contractual: 150`
- **THEN** `GazeConfigError` is raised with a message citing the field name
  and the out-of-range value, and the command exits non-zero

#### Scenario: Zero doc_scan_timeout
- **WHEN** `.gaze.yaml` sets `classification.doc_scan.timeout: 0`
- **THEN** `GazeConfigError` is raised with message `"doc_scan.timeout must be positive"`

---

### Requirement: Malformed YAML handling

When `.gaze.yaml` exists but cannot be parsed as valid YAML, the loader
SHALL raise `GazeConfigError` with a message that includes the file path
and the YAML parse error. The calling command SHALL emit this error to
stderr and exit non-zero.

#### Scenario: Invalid YAML syntax
- **WHEN** `.gaze.yaml` contains a YAML syntax error (e.g. unmatched `{`)
- **THEN** the command exits non-zero with a message identifying the file
  and the parse error

#### Scenario: File unreadable
- **WHEN** `.gaze.yaml` exists but cannot be read (e.g. permission denied)
- **THEN** `GazeConfigError` is raised with a message citing the file path
  and the OS error

---

### Requirement: Null-not-zero for optional fields

Fields that depend on optional capabilities (O1 quality pipeline, O2 AI
reports) SHALL be `None`/`null` when the capability has not run — not `0.0`
or `""`. This is per porting contract OC-003.

`GazeConfig` itself does not emit JSON; this requirement applies to the
`Score` and `Summary` fields populated by commands that use the config.

#### Scenario: GazeCRAP null without O1
- **WHEN** `gazepy analyze` runs without the quality pipeline
- **THEN** `gaze_crap`, `contract_coverage`, and `quadrant` fields in the
  output are `null`, not `0` or `""`
