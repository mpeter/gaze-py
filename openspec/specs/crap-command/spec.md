# Spec: crap-command

`gazepy crap <path>` — detect side effects, classify them, and compute CRAP
and GazeCRAP scores. Optionally runs pytest automatically for coverage
collection. Supports CI threshold gates.

---

### Requirement: path-argument
`gazepy crap` SHALL accept a single positional `PATH` argument (file or
directory). The path SHALL be resolved and validated before any subprocess
or analysis work begins.

#### Scenario: valid path
- **WHEN** PATH exists
- **THEN** analysis proceeds

#### Scenario: path does not exist
- **WHEN** PATH does not exist
- **THEN** the command emits `Error: path does not exist: <path>` to stderr
  and exits 2

---

### Requirement: output-format
`gazepy crap` SHALL support `--format=text` (default, matching Go gaze) and
`--format=json`.

#### Scenario: default format is text
- **WHEN** `--format` is not specified
- **THEN** output is human-readable plain text

#### Scenario: json format
- **WHEN** `--format=json` is specified
- **THEN** output is valid JSON conforming to the `AnalysisResult` schema

---

### Requirement: include-unexported-default-on
`gazepy crap` SHALL include underscore-prefixed (private) functions by
default. There is no `--include-unexported` flag on `crap`; private
functions are always analyzed.

#### Scenario: private functions included
- **WHEN** `gazepy crap <path>` is invoked
- **THEN** functions whose names start with `_` appear in the output

---

### Requirement: coverage-acquisition-coverprofile
When `--coverprofile <path>` is provided, `gazepy crap` SHALL load coverage
data from that pre-generated coverage.py JSON report instead of running
pytest.

#### Scenario: valid coverprofile
- **WHEN** `--coverprofile coverage.json` is provided and the file is valid
- **THEN** coverage data is loaded from that file and used for CRAP scoring

#### Scenario: coverprofile file missing
- **WHEN** `--coverprofile /nonexistent.json` is provided
- **THEN** the command emits an error to stderr and exits 2

#### Scenario: coverprofile malformed JSON
- **WHEN** `--coverprofile` points to a file with invalid JSON
- **THEN** the command emits an error to stderr and exits 2

#### Scenario: coverprofile missing required keys
- **WHEN** `--coverprofile` points to a JSON file without a `files` key
- **THEN** the command emits an error to stderr and exits 2

---

### Requirement: coverage-acquisition-auto-pytest
When `--coverprofile` is not provided, `gazepy crap` SHALL automatically
invoke `pytest` (using the same interpreter as the running `gazepy` process,
via `sys.executable`) with `--cov=<path>` and `--cov-report json:<tmpfile>`.
Coverage failures SHALL be non-fatal — the command SHALL continue without
coverage data and emit a warning to stderr.

#### Scenario: pytest succeeds
- **WHEN** `--coverprofile` is omitted and pytest runs successfully
- **THEN** coverage data from the temporary JSON report is used for scoring

#### Scenario: pytest not installed
- **WHEN** `--coverprofile` is omitted and pytest is not installed
- **THEN** a warning is emitted to stderr
- **AND** analysis continues with `null` line coverage
- **AND** the command exits 0 (coverage failure is non-fatal)

#### Scenario: pytest exits non-zero
- **WHEN** `--coverprofile` is omitted and pytest exits with a non-zero code
- **THEN** a warning is emitted to stderr
- **AND** analysis continues with `null` line coverage

#### Scenario: coverage json parse failure
- **WHEN** pytest writes malformed JSON to the temporary file
- **THEN** a warning is emitted to stderr
- **AND** analysis continues with `null` line coverage

#### Scenario: temporary file cleanup
- **WHEN** pytest coverage collection completes (success or failure)
- **THEN** the temporary JSON file is deleted

---

### Requirement: tests-flag
`gazepy crap` SHALL support `--tests <path>` to specify a test directory or
file. When provided, the O1 quality pipeline runs after CRAP scoring to
populate GazeCRAP, quadrant, and contract coverage fields. When omitted,
the command auto-discovers a tests directory; if none is found, GazeCRAP
fields remain `null`.

#### Scenario: tests path provided
- **WHEN** `--tests tests/` is passed and the path exists
- **THEN** the O1 quality pipeline runs and GazeCRAP fields are populated

#### Scenario: tests auto-discovered
- **WHEN** `--tests` is omitted and a `tests/` or `test/` directory exists
  relative to PATH or cwd
- **THEN** the O1 quality pipeline runs automatically

#### Scenario: no tests found
- **WHEN** `--tests` is omitted and no tests directory can be discovered
- **THEN** GazeCRAP fields in the output are `null` (OC-003 compliant)
- **AND** the command exits 0

---

### Requirement: crap-threshold-flag
`gazepy crap` SHALL support `--crap-threshold <float>` (default: 15.0) to
set the CRAP score threshold used for CRAPload computation.

#### Scenario: custom threshold
- **WHEN** `--crap-threshold 30.0` is passed
- **THEN** functions with CRAP score ≥ 30.0 count toward crapload

---

### Requirement: gaze-crap-threshold-flag
`gazepy crap` SHALL accept `--gaze-crap-threshold <float>` (default: 15.0).
This flag is accepted for flag-surface parity with Go gaze.

#### Scenario: flag accepted
- **WHEN** `--gaze-crap-threshold 20.0` is passed
- **THEN** the command accepts the flag without error

---

### Requirement: max-crapload-gate
`gazepy crap` SHALL support `--max-crapload <int>` (default: 0 = no limit).
When the computed `crapload` exceeds this value, the command SHALL emit a
CI gate message to stderr and exit 1. Output SHALL be emitted before the
gate check fires.

#### Scenario: gate not triggered
- **WHEN** `--max-crapload 10` and `crapload` ≤ 10
- **THEN** the command exits 0

#### Scenario: gate triggered
- **WHEN** `--max-crapload 5` and `crapload` > 5
- **THEN** output is emitted first
- **AND** a CI gate message is emitted to stderr
- **AND** the command exits 1

#### Scenario: zero means no limit
- **WHEN** `--max-crapload 0` (default)
- **THEN** no crapload gate is enforced regardless of crapload value

---

### Requirement: max-gaze-crapload-gate
`gazepy crap` SHALL support `--max-gaze-crapload <int>` (default: 0 = no
limit). When `gaze_crapload` in the summary is not `null` and exceeds this
value, the command SHALL emit a CI gate message to stderr and exit 1.
The gate SHALL be skipped (not triggered) when `gaze_crapload` is `null`
(i.e., when no quality pipeline data is available).

#### Scenario: gate triggered when data available
- **WHEN** `--max-gaze-crapload 3`, `gaze_crapload` is not null, and
  `gaze_crapload` > 3
- **THEN** a CI gate message is emitted to stderr and the command exits 1

#### Scenario: gate skipped when data unavailable
- **WHEN** `--max-gaze-crapload 3` and `gaze_crapload` is `null`
- **THEN** no gate is triggered and the command exits 0

---

### Requirement: min-contract-coverage-gate
`gazepy crap` SHALL support `--min-contract-coverage <float>`. When
`avg_contract_coverage` in the summary is below this value, the command
SHALL emit a CI gate message to stderr and exit 1. The gate SHALL be
skipped when no contract coverage data is available.

#### Scenario: gate triggered
- **WHEN** `--min-contract-coverage 80` and `avg_contract_coverage` < 80
- **THEN** a CI gate message is emitted to stderr and the command exits 1

#### Scenario: gate skipped when no data
- **WHEN** `--min-contract-coverage 80` and no quality pipeline ran
- **THEN** no gate is triggered

---

### Requirement: baseline-flag-stub
`gazepy crap` SHALL accept `--baseline <path>` but SHALL exit 1 with a
clear "not yet implemented" message when it is provided.

#### Scenario: baseline provided
- **WHEN** `--baseline baseline.json` is passed
- **THEN** the command emits an error to stderr and exits 1

---

### Requirement: json-output-shape
When `--format=json`, the output SHALL be a JSON object with:
- `functions`: array of `FunctionTarget` objects, each with `score` populated
- `summary`: object containing `crapload`, `gaze_crapload`,
  `avg_contract_coverage`, `avg_line_coverage`, `quadrant_counts`,
  `fix_strategy_counts`, `recommended_actions`, `crap_threshold`,
  `gaze_crap_threshold`, `function_count`

All GazeCRAP-derived fields (`gaze_crapload`, `avg_contract_coverage`,
`quadrant_counts`) SHALL be `null` when `--tests` is not provided and no
tests directory is auto-discovered (OC-003).

#### Scenario: full output with tests
- **WHEN** `--format=json` and `--tests` is provided
- **THEN** `summary.gaze_crapload` is an integer (not null)
- **AND** `summary.avg_contract_coverage` is a float (not null)

#### Scenario: output without tests
- **WHEN** `--format=json` and no tests path is found
- **THEN** `summary.gaze_crapload` is `null`
- **AND** `summary.avg_contract_coverage` is `null`
- **AND** `summary.quadrant_counts` is `null`

---

### Requirement: exit-codes
`gazepy crap` SHALL exit 0 on success, 1 when a CI gate is violated, and
2 on user-input errors (path not found, invalid coverprofile).

#### Scenario: success
- **WHEN** analysis completes and no CI gates are violated
- **THEN** the command exits 0

#### Scenario: CI gate violation
- **WHEN** crapload or gaze_crapload exceeds its threshold
- **THEN** the command exits 1

#### Scenario: user input error
- **WHEN** PATH does not exist or coverprofile is invalid
- **THEN** the command exits 2
