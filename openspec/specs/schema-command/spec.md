# Spec: schema-command

`gazepy schema` — print the JSON output schema for the `AnalysisResult`
envelope used by `gazepy analyze` and `gazepy crap --format=json`.

---

### Requirement: no-arguments
`gazepy schema` SHALL accept no positional arguments and no flags (other
than `--help`). Any unexpected arguments SHALL produce a Click usage error.

#### Scenario: bare invocation
- **WHEN** `gazepy schema` is invoked with no arguments
- **THEN** the schema is printed to stdout and the command exits 0

#### Scenario: unexpected argument
- **WHEN** `gazepy schema some-arg` is invoked
- **THEN** Click emits a usage error and exits 2

---

### Requirement: stdout-output
`gazepy schema` SHALL print the JSON schema to stdout. No other output
SHALL be emitted to stdout. The schema SHALL be the same constant embedded
in `gaze_py.report.json_formatter.SCHEMA`.

#### Scenario: output is valid JSON
- **WHEN** `gazepy schema` is invoked
- **THEN** the output is parseable as valid JSON

#### Scenario: output describes AnalysisResult
- **WHEN** `gazepy schema` is invoked
- **THEN** the output describes the structure of the `AnalysisResult`
  envelope produced by `gazepy analyze` and `gazepy crap --format=json`

---

### Requirement: always-exits-zero
`gazepy schema` SHALL always exit 0. There are no error conditions for this
command — the schema is a compile-time constant embedded in the package.

#### Scenario: always succeeds
- **WHEN** `gazepy schema` is invoked in any environment
- **THEN** the command exits 0

---

### Requirement: schema-consistency
The schema printed by `gazepy schema` SHALL be consistent with the actual
JSON output produced by `gazepy crap --format=json`. Callers MAY use the
schema to validate `crap` output.

#### Scenario: schema matches crap output
- **WHEN** `gazepy crap <path> --format=json` is invoked
- **THEN** the output validates against the schema printed by `gazepy schema`

---

### Requirement: no-stderr-output
`gazepy schema` SHALL NOT emit anything to stderr under normal operation.

#### Scenario: clean stderr
- **WHEN** `gazepy schema` is invoked
- **THEN** stderr is empty
