# Spec: quality-command

`gazepy quality <path>` — run the O1 quality assessment pipeline on Python
source files paired with their tests. Computes contract coverage, GazeCRAP
scores, gap hints, and reason codes per function.

---

### Requirement: path-argument
`gazepy quality` SHALL accept a single positional `PATH` argument (file or
directory). The path SHALL be validated before the pipeline runs.

#### Scenario: valid path
- **WHEN** PATH exists
- **THEN** analysis proceeds

#### Scenario: path does not exist
- **WHEN** PATH does not exist
- **THEN** the command emits `Error: path does not exist: <path>` to stderr
  and exits 2

---

### Requirement: tests-flag
`gazepy quality` SHALL support `--tests <path>` to specify the test
directory or file. When omitted, the command SHALL auto-discover a tests
directory by searching for `tests/`, `test/`, or `test_*.py` relative to
PATH's parent and then relative to cwd.

#### Scenario: explicit tests path
- **WHEN** `--tests tests/` is provided and the path exists
- **THEN** the quality pipeline uses that directory

#### Scenario: tests path does not exist
- **WHEN** `--tests /nonexistent/` is provided
- **THEN** the command emits an error to stderr and exits 2

#### Scenario: auto-discovery succeeds
- **WHEN** `--tests` is omitted and a `tests/` directory exists relative to
  PATH's parent or cwd
- **THEN** that directory is used automatically

#### Scenario: auto-discovery fails
- **WHEN** `--tests` is omitted and no tests directory can be found
- **THEN** the command emits `Error: no tests directory found — use --tests`
  to stderr and exits 2

---

### Requirement: include-unexported-default-on
`gazepy quality` SHALL include underscore-prefixed (private) functions by
default. This is a deliberate Python-specific divergence from Go gaze: the
`_` prefix is a convention, not an access boundary, and private helpers are
often the most complex and least directly tested parts of a codebase.

The `--include-unexported` flag defaults to `True`. To restrict analysis to
public functions only, pass `--no-include-unexported`.

#### Scenario: default includes private functions
- **WHEN** neither `--include-unexported` nor `--no-include-unexported` is
  passed
- **THEN** functions whose names start with `_` are included in the output

#### Scenario: opt-out excludes private functions
- **WHEN** `--no-include-unexported` is passed
- **THEN** functions whose names start with `_` are excluded from the output

---

### Requirement: output-format
`gazepy quality` SHALL support `--format=text` (default) and `--format=json`.

#### Scenario: text format (default)
- **WHEN** `--format` is not specified
- **THEN** output is a plain-text table with columns: Function, Contract
  Coverage, GazeCRAP

#### Scenario: json format
- **WHEN** `--format=json` is specified
- **THEN** output is a JSON array of `QualityReport` objects (NOT wrapped in
  an `AnalysisResult` envelope)

---

### Requirement: output-content
The quality pipeline output SHALL include per-function:
- `target_function`: the production function name
- `test_function`: the paired test function name
- `contract_coverage`: percentage (0–100) and reason code
- `gap_hints`: list of `{effect_hint, test_hint}` objects identifying
  untested effect types
- `complexity`: cyclomatic complexity of the production function
- GazeCRAP score (computed from complexity and contract coverage fraction)

#### Scenario: paired function output
- **WHEN** a production function is paired with a test function
- **THEN** the output includes `contract_coverage.percentage` (not null)
- **AND** `gap_hints` lists any effect types not covered by assertions

#### Scenario: unpaired function output
- **WHEN** a production function has no paired test
- **THEN** `contract_coverage.reason` is `"no_test_coverage"`
- **AND** GazeCRAP is `null` per porting contract D5

---

### Requirement: reason-codes
Contract coverage results SHALL include a `reason` field explaining why
coverage is at its computed value. Valid reason codes include:
- `"all_effects_covered"` — all detected effects have matching assertions
- `"partial_coverage"` — some effects lack assertions
- `"no_effects_detected"` — the function has no detectable side effects
- `"no_test_coverage"` — no test function was paired
- `"all_effects_ambiguous"` — all effects are classified as ambiguous

#### Scenario: reason code present
- **WHEN** `--format=json` is used
- **THEN** every `contract_coverage` object has a non-null `reason` field

---

### Requirement: config-flag
`gazepy quality` SHALL support `--config <path>` to specify an explicit
`.gaze.yaml` configuration file. When omitted, the command walks up from
PATH to find `.gaze.yaml` automatically.

#### Scenario: explicit config
- **WHEN** `--config /path/to/.gaze.yaml` is provided and the file exists
- **THEN** that config file is loaded

---

### Requirement: threshold-override-flags
`gazepy quality` SHALL support `--contractual-threshold <int>` and
`--incidental-threshold <int>` to override the corresponding config values.

#### Scenario: threshold override
- **WHEN** `--contractual-threshold 70` is passed
- **THEN** the classification engine uses 70 as the contractual threshold

---

### Requirement: target-flag
`gazepy quality` SHALL support `--target <name>` to restrict the quality
pipeline to tests that exercise a specific production function name.

#### Scenario: target filter
- **WHEN** `--target my_func` is passed
- **THEN** only quality reports for `my_func` are included in the output

---

### Requirement: verbose-flag
`gazepy quality` SHALL support `--verbose` / `-v` for full signal breakdown.

#### Scenario: verbose flag accepted
- **WHEN** `--verbose` is passed
- **THEN** the command accepts the flag without error

---

### Requirement: min-contract-coverage-gate
`gazepy quality` SHALL support `--min-contract-coverage <float>`. When the
average contract coverage across all paired functions is below this value,
the command SHALL emit a CI gate summary to stderr and exit 1. The gate
SHALL be checked after output is emitted.

#### Scenario: gate triggered
- **WHEN** `--min-contract-coverage 80` and average coverage < 80%
- **THEN** output is emitted first
- **AND** a CI gate summary is emitted to stderr listing failing functions
- **AND** the command exits 1

#### Scenario: gate passes
- **WHEN** `--min-contract-coverage 80` and average coverage ≥ 80%
- **THEN** the command exits 0

#### Scenario: no paired functions
- **WHEN** `--min-contract-coverage 80` but no functions have coverage data
- **THEN** no gate is triggered

---

### Requirement: max-over-specification-flag
`gazepy quality` SHALL accept `--max-over-specification <float>` for flag-
surface parity with Go gaze. The flag is accepted without error.

#### Scenario: flag accepted
- **WHEN** `--max-over-specification 20.0` is passed
- **THEN** the command accepts the flag without error

---

### Requirement: exit-codes
`gazepy quality` SHALL exit 0 on success, 1 when a CI gate is violated, and
2 on user-input errors (path not found, tests not found, config error).

#### Scenario: success
- **WHEN** pipeline completes and no CI gates are violated
- **THEN** the command exits 0

#### Scenario: CI gate violation
- **WHEN** average contract coverage is below `--min-contract-coverage`
- **THEN** the command exits 1

#### Scenario: user input error
- **WHEN** PATH or tests path does not exist
- **THEN** the command exits 2
