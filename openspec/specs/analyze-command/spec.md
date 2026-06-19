# Spec: analyze-command

`gazepy analyze <path>` — detect side effects in Python source files and
optionally classify them. CRAP scoring is not performed by this command;
all CRAP-derived output fields are `null`. Use `gazepy crap` for scoring.

---

### Requirement: path-argument
`gazepy analyze` SHALL accept a single positional `PATH` argument that
resolves to either a `.py` file or a directory. When PATH is a directory,
the command SHALL recursively collect all `.py` files within it.

#### Scenario: file path
- **WHEN** PATH points to a single `.py` file that exists
- **THEN** the command analyzes that file and exits 0

#### Scenario: directory path
- **WHEN** PATH points to a directory
- **THEN** the command recursively collects all `.py` files and analyzes them

#### Scenario: path does not exist
- **WHEN** PATH does not exist on the filesystem
- **THEN** the command emits `Error: path does not exist: <path>` to stderr
  and exits 2

---

### Requirement: output-format
`gazepy analyze` SHALL support `--format=json` (default) and `--format=text`
output formats. The default of `json` is an intentional divergence from Go
gaze (which defaults to `text`); the difference SHALL be documented in the
command help text.

#### Scenario: default format is json
- **WHEN** `--format` is not specified
- **THEN** output is valid JSON conforming to the `AnalysisResult` schema

#### Scenario: text format
- **WHEN** `--format=text` is specified
- **THEN** output is human-readable plain text (no JSON)

#### Scenario: help text notes the divergence
- **WHEN** `gazepy analyze --help` is invoked
- **THEN** the `--format` help text includes a note that the default differs
  from Go gaze which defaults to `text`

---

### Requirement: crap-fields-null
`gazepy analyze` SHALL NOT compute CRAP scores. All CRAP-derived fields in
the JSON output (`line_coverage`, `crap`, `gaze_crap`, `fix_strategy`,
`quadrant`, `contract_coverage`) SHALL be `null` per OC-003 (Null Not Zero).
`Summary.crapload` SHALL also be `null`.

#### Scenario: json output has null crap fields
- **WHEN** `gazepy analyze <path> --format=json` is invoked
- **THEN** every `FunctionTarget.score` field in the output is `null`
- **AND** `summary.crapload` is `null`
- **AND** `summary.gaze_crapload` is `null`
- **AND** `summary.avg_line_coverage` is `null`

---

### Requirement: include-unexported-flag
`gazepy analyze` SHALL support `--include-unexported` (default: off). When
off, underscore-prefixed functions SHALL be excluded from output. When on,
they SHALL be included.

#### Scenario: default excludes private functions
- **WHEN** `--include-unexported` is not passed
- **THEN** functions whose names start with `_` are absent from the output

#### Scenario: flag includes private functions
- **WHEN** `--include-unexported` is passed
- **THEN** functions whose names start with `_` appear in the output

---

### Requirement: classify-flag
`gazepy analyze` SHALL support `--classify` / `-c` (flag, default: off).
When set, the classification engine SHALL run on each detected effect,
annotating it as contractual or incidental per the configured thresholds.

#### Scenario: classify off
- **WHEN** `--classify` is not passed
- **THEN** effects in the output have no classification annotation

#### Scenario: classify on
- **WHEN** `--classify` is passed
- **THEN** each detected effect is annotated with its classification result

---

### Requirement: verbose-flag
`gazepy analyze` SHALL support `--verbose` / `-v` (flag, default: off).
`--verbose` SHALL imply `--classify` — the full signal breakdown is emitted.

#### Scenario: verbose implies classify
- **WHEN** `--verbose` is passed without `--classify`
- **THEN** the classification engine runs as if `--classify` were also passed

---

### Requirement: config-flag
`gazepy analyze` SHALL support `--config <path>` to specify an explicit
`.gaze.yaml` configuration file. When omitted, the command SHALL walk up
from PATH to find `.gaze.yaml` automatically.

#### Scenario: explicit config path
- **WHEN** `--config /path/to/.gaze.yaml` is provided and the file exists
- **THEN** that config file is loaded

#### Scenario: config file not found
- **WHEN** `--config /nonexistent.yaml` is provided
- **THEN** the command emits an error to stderr and exits 2

#### Scenario: config auto-discovery
- **WHEN** `--config` is omitted
- **THEN** the command walks up from PATH searching for `.gaze.yaml`

---

### Requirement: threshold-override-flags
`gazepy analyze` SHALL support `--contractual-threshold <int>` and
`--incidental-threshold <int>` to override the corresponding values from
the loaded config. These overrides apply after config load.

#### Scenario: threshold override applied
- **WHEN** `--contractual-threshold 80` is passed
- **THEN** the classification engine uses 80 as the contractual threshold
  regardless of the value in `.gaze.yaml`

---

### Requirement: function-filter-flag
`gazepy analyze` SHALL support `--function <name>` / `-f <name>` to restrict
analysis to a single function matching the given name exactly.

#### Scenario: function filter
- **WHEN** `--function my_func` is passed
- **THEN** only the function named `my_func` appears in the output

---

### Requirement: exit-codes
`gazepy analyze` SHALL exit 0 on success. It SHALL exit 2 on user-input
errors (path not found, config not found). Parse errors on individual files
SHALL be emitted as warnings to stderr and SHALL NOT cause a non-zero exit.

#### Scenario: parse error is non-fatal
- **WHEN** a `.py` file in the target directory contains a syntax error
- **THEN** a warning is emitted to stderr for that file
- **AND** analysis continues for remaining files
- **AND** the command exits 0

#### Scenario: success
- **WHEN** all files parse successfully
- **THEN** the command exits 0

---

### Requirement: output-schema-compatibility
The JSON output from `gazepy analyze` SHALL use the same `AnalysisResult`
envelope as `gazepy crap`, maintaining schema compatibility. CRAP-derived
fields SHALL be `null` rather than absent, so callers can detect the
difference between "not computed" and "computed zero."

#### Scenario: schema envelope present
- **WHEN** `gazepy analyze <path> --format=json` is invoked
- **THEN** the output is a JSON object with `functions` (array) and
  `summary` (object) keys
- **AND** the output validates against the schema printed by `gazepy schema`
