# Spec: self-check-command

`gazepy self-check` — run CRAP analysis on gaze-py's own source code
(dogfooding). Walks up from cwd to locate the project root, then runs the
`crap` pipeline on `src/gaze_py/`. Supports the same CI gate flags as
`gazepy crap`.

---

### Requirement: project-root-discovery
`gazepy self-check` SHALL walk up from the current working directory,
checking each ancestor directory for a `pyproject.toml` sentinel file.
The first directory containing `pyproject.toml` is the project root.

#### Scenario: pyproject.toml found in cwd
- **WHEN** `pyproject.toml` exists in the current working directory
- **THEN** cwd is used as the project root

#### Scenario: pyproject.toml found N levels up
- **WHEN** `pyproject.toml` exists in an ancestor directory
- **THEN** that ancestor directory is used as the project root

#### Scenario: pyproject.toml not found anywhere
- **WHEN** no `pyproject.toml` exists in cwd or any ancestor up to the
  filesystem root
- **THEN** a warning is emitted to stderr
- **AND** cwd is used as the fallback project root
- **AND** analysis continues

---

### Requirement: gaze-py-source-path
After locating the project root, `gazepy self-check` SHALL run the CRAP
pipeline on `<root>/src/gaze_py/`. If that path does not exist, the command
SHALL emit an error and exit 2.

#### Scenario: src/gaze_py/ exists
- **WHEN** `<root>/src/gaze_py/` exists
- **THEN** the CRAP pipeline runs on that directory

#### Scenario: src/gaze_py/ missing
- **WHEN** `<root>/src/gaze_py/` does not exist
- **THEN** the command emits:
  `Error: self-check only works within the gaze-py repository (src/gaze_py/ not found).`
  to stderr and exits 2

---

### Requirement: output-format
`gazepy self-check` SHALL support `--format=text` (default) and
`--format=json`, matching the `crap` command output format.

#### Scenario: default text format
- **WHEN** `--format` is not specified
- **THEN** output is human-readable plain text

#### Scenario: json format
- **WHEN** `--format=json` is specified
- **THEN** output is valid JSON conforming to the `AnalysisResult` schema

---

### Requirement: max-crapload-gate
`gazepy self-check` SHALL support `--max-crapload <int>` (default: 0 = no
limit). When the computed `crapload` exceeds this value, the command SHALL
emit a CI gate message to stderr and exit 1. Output SHALL be emitted before
the gate check fires.

#### Scenario: gate triggered
- **WHEN** `--max-crapload 5` and `crapload` > 5
- **THEN** output is emitted first
- **AND** a CI gate message is emitted to stderr
- **AND** the command exits 1

#### Scenario: zero means no limit
- **WHEN** `--max-crapload 0` (default)
- **THEN** no crapload gate is enforced

---

### Requirement: max-gaze-crapload-gate
`gazepy self-check` SHALL support `--max-gaze-crapload <int>` (default: 0 =
no limit). When `gaze_crapload` is not `null` and exceeds this value, the
command SHALL emit a CI gate message to stderr and exit 1. The gate SHALL be
skipped when `gaze_crapload` is `null`.

#### Scenario: gate triggered when data available
- **WHEN** `--max-gaze-crapload 3`, `gaze_crapload` is not null, and
  `gaze_crapload` > 3
- **THEN** a CI gate message is emitted to stderr and the command exits 1

#### Scenario: gate skipped when data unavailable
- **WHEN** `--max-gaze-crapload 3` and `gaze_crapload` is `null`
- **THEN** no gate is triggered and the command exits 0

---

### Requirement: no-coverage-by-default
`gazepy self-check` SHALL NOT run pytest automatically. It runs the CRAP
pipeline without coverage data (line coverage fields are `null`). This is
intentional — self-check is a quick dogfooding check, not a full CI run.

#### Scenario: no coverage data
- **WHEN** `gazepy self-check` is invoked without any coverage flags
- **THEN** `summary.avg_line_coverage` is `null` in the output
- **AND** no pytest subprocess is spawned

---

### Requirement: exit-codes
`gazepy self-check` SHALL exit 0 on success, 1 when a CI gate is violated,
and 2 on user-input errors (src/gaze_py/ not found).

#### Scenario: success
- **WHEN** analysis completes and no CI gates are violated
- **THEN** the command exits 0

#### Scenario: CI gate violation
- **WHEN** crapload or gaze_crapload exceeds its threshold
- **THEN** the command exits 1

#### Scenario: gaze-py source missing
- **WHEN** `src/gaze_py/` is not found under the project root
- **THEN** the command exits 2

---

### Requirement: dogfooding-scope
`gazepy self-check` is a dogfooding command that targets gaze-py's own
source. It SHALL NOT be a general-purpose CRAP runner. Users running it
outside the gaze-py repository SHOULD receive the `src/gaze_py/ not found`
error. This behavior SHALL be documented in the command help text.

#### Scenario: run outside gaze-py repo
- **WHEN** invoked in a directory that has `pyproject.toml` but no
  `src/gaze_py/` subdirectory
- **THEN** the command emits the "only works within the gaze-py repository"
  error and exits 2
