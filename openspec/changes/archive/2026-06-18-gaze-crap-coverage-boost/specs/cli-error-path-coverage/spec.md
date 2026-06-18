## ADDED Requirements

### Requirement: analyze --config with invalid YAML exits 2
Tests MUST verify that passing an invalid `.gaze.yaml` via `--config` causes `gazepy analyze` to exit with code 2 and print an error to stderr.

#### Scenario: analyze --config invalid YAML exits 2
- **WHEN** `gazepy analyze <path> --config <file-with-negative-threshold>` is invoked
- **THEN** exit code is 2
- **AND** stderr contains "Error"

### Requirement: analyze --contractual-threshold and --incidental-threshold are applied
Tests MUST verify that the threshold override flags are wired and accepted without error.

#### Scenario: analyze with threshold overrides exits 0
- **WHEN** `gazepy analyze <path> --contractual-threshold=95 --incidental-threshold=10` is invoked
- **THEN** exit code is 0

### Requirement: crap --config with invalid YAML exits 2
Tests MUST verify that passing an invalid `.gaze.yaml` via `--config` causes `gazepy crap` to exit with code 2 and print an error to stderr.

#### Scenario: crap --config invalid YAML exits 2
- **WHEN** `gazepy crap <path> --config <file-with-negative-threshold> --coverprofile <valid-cov>` is invoked
- **THEN** exit code is 2
- **AND** stderr contains "Error"

### Requirement: crap --contractual-threshold and --incidental-threshold are applied
Tests MUST verify that threshold override flags for the crap command are accepted without error.

#### Scenario: crap with threshold overrides exits 0
- **WHEN** `gazepy crap <path> --contractual-threshold=95 --incidental-threshold=10 --coverprofile <valid-cov>` is invoked
- **THEN** exit code is 0

### Requirement: quality with no discoverable tests directory exits 2
Tests MUST verify that `gazepy quality` exits 2 when no `tests/` directory is discoverable and `--tests` is not provided.

#### Scenario: quality without tests path exits 2
- **WHEN** `gazepy quality <path>` is invoked in a directory with no `tests/`, `test/`, or `test_*.py` files
- **THEN** exit code is 2
- **AND** stderr contains "no tests directory found"

### Requirement: quality discovers test_*.py files via glob when no tests/ dir exists
Tests MUST verify that `_discover_tests_path` returns a `test_*.py` file when no `tests/` or `test/` directory exists but matching files are found.

#### Scenario: quality discovers test_*.py glob fallback
- **WHEN** `gazepy quality <path>` is invoked in a directory containing `test_foo.py` but no `tests/` dir
- **THEN** the command does not exit with "no tests directory found" error

### Requirement: crap summary includes quadrant_counts when quadrant data is available
Tests MUST verify that when quality pipeline data provides quadrant labels, the JSON summary's `quadrant_counts` field is a non-null dict.

#### Scenario: crap with tests populates quadrant_counts in summary
- **WHEN** `gazepy crap <path> --tests <tests> --coverprofile <cov> --format=json` is invoked and quality data provides quadrant labels
- **THEN** the JSON summary `quadrant_counts` field is a non-null object

### Requirement: docscan --include flag replaces config include list
Tests MUST verify that `--include` is accepted and applied without error.

#### Scenario: docscan --include exits 0
- **WHEN** `gazepy docscan <path> --include=*.md` is invoked
- **THEN** exit code is 0

### Requirement: docscan --timeout flag overrides config timeout
Tests MUST verify that `--timeout` is accepted and applied without error.

#### Scenario: docscan --timeout exits 0
- **WHEN** `gazepy docscan <path> --timeout=5.0` is invoked
- **THEN** exit code is 0

### Requirement: docscan exits 1 on GazeConfigError
Tests MUST verify that when the config file has invalid content, `gazepy docscan` exits 1 with an error message.

#### Scenario: docscan with invalid config exits 1
- **WHEN** `gazepy docscan <path> --config <file-with-bad-content>` is invoked
- **THEN** exit code is 1
- **AND** stderr contains "Error"

### Requirement: docscan exits 1 on generic exception from scan_docs
Tests MUST verify that when `scan_docs` raises an unexpected exception, `gazepy docscan` exits 1 with an error message.

#### Scenario: docscan scan_docs raises RuntimeError exits 1
- **WHEN** `scan_docs` is monkeypatched to raise `RuntimeError("boom")`
- **THEN** exit code is 1
- **AND** stderr contains "Error"

### Requirement: quality --min-contract-coverage with no contractual effects exits 0
Tests MUST verify that when no functions have contractual effects, `--min-contract-coverage` does not trigger the CI gate (early return, no coverage to check).

#### Scenario: quality min-coverage gate skipped for pure functions
- **WHEN** `gazepy quality <pure-function-source> --tests <tests> --min-contract-coverage=50` is invoked
- **THEN** exit code is 0 (no FAIL, coverage check is vacuously skipped)
