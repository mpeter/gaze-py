# Spec: quality-output

JSON serialization and CLI output wiring for the O1 quality assessment
pipeline. Covers how quality data flows from `assess()` into JSON output,
the `crap` command, and summary fields.

---

### Requirement: quality-json-structure

`quality_to_json()` MUST produce a JSON object with two top-level keys:
- `"reports"` — object keyed by test function name, each value being a
  report entry for a paired test function.
- `"untested"` — object keyed by production function name, each value being
  a report entry for a production function with no paired test.

Each report entry MUST include:
- `"function"` — function name (string)
- `"contract_coverage"` — percentage `[0.0, 100.0]` or `null`
- `"reason"` — reason code string or `null`
- `"gaps"` — array of effect objects (empty array when no gaps)
- `"gap_hints"` — array of hint strings (empty array when no hints)
- `"gaze_crap"` — GazeCRAP score (float) or `null`
- `"complexity"` — McCabe complexity (int) or `null`

#### Scenario: full report entry structure
- **WHEN** `quality_to_json()` serializes a paired report with 50% coverage
- **THEN** the JSON entry contains all required fields with correct types

#### Scenario: null fields when no target found
- **WHEN** a test function has no paired production target
- **THEN** `"contract_coverage": null`, `"reason": null`, `"gaze_crap": null`

---

### Requirement: null-not-zero-in-output

Per OC-003, all quality fields that depend on optional capabilities MUST
serialize as `null` (not `0` or `0.0` or `""`) when the capability has not
run or has no data.

Specifically:
- `"contract_coverage"` MUST be `null` when `percentage is None`
- `"gaze_crap"` MUST be `null` when `no_test_coverage` reason applies or
  when quality pipeline has not run
- `"quadrant"` MUST be `null` when GazeCRAP is not available
- `"avg_contract_coverage"` MUST be `null` when O1 has not run
- `"gaze_crapload"` MUST be `null` when O1 has not run

#### Scenario: no_test_coverage serializes as null
- **WHEN** a function has `reason="no_test_coverage"`
- **THEN** `"contract_coverage": null` and `"gaze_crap": null` in JSON

#### Scenario: quality fields null without --tests
- **WHEN** `gazepy crap` is run without `--tests`
- **THEN** all quality fields (`gaze_crap`, `contract_coverage`,
  `contract_coverage_reason`, `quadrant`) are `null` in JSON output

---

### Requirement: gaze-crap-computation

GazeCRAP MUST be computed using the formula (SC-002):

```
gaze_crap = complexity² × (1 − contract_frac)³ + complexity
```

where `contract_frac` is `ContractCoverageResult.percentage / 100.0`
(a fraction in `[0.0, 1.0]`). The division by 100 MUST be performed before
passing to `gaze_crap()` and `quadrant()` — those functions take fractions,
not percentages.

At 100% coverage (`contract_frac=1.0`): cubic term is 0, GazeCRAP equals
`complexity` (NOT 0.0).
At 0% coverage (`contract_frac=0.0`): GazeCRAP equals `complexity² + complexity`.

GazeCRAP MUST be `null` when `contract_coverage_result.percentage is None`
(any reason code, including `"no_test_coverage"`).

#### Scenario: GazeCRAP at 100% coverage
- **WHEN** `complexity=3` and `contract_frac=1.0`
- **THEN** `gaze_crap == 3.0` (not 0.0)

#### Scenario: GazeCRAP at 0% coverage
- **WHEN** `complexity=3` and `contract_frac=0.0`
- **THEN** `gaze_crap == 12.0` (9 × 1 + 3)

#### Scenario: GazeCRAP null for no_test_coverage
- **WHEN** function has `reason="no_test_coverage"`
- **THEN** `gaze_crap` is `null` in output

---

### Requirement: crap-command-quality-integration

The `crap` command MUST accept a `--tests` option specifying a path to test
files. When `--tests` is provided, the command MUST:
1. Call `build_contract_coverage_map(src_path, tests_path, config)` to run
   the O1 pipeline.
2. Use the resulting `dict[str, ContractCoverageResult]` to populate
   `contract_coverage_reason` on each `Score` object.
3. Populate `gaze_crap` and `quadrant` on functions where
   `ContractCoverageResult.percentage is not None`.

When `--tests` is NOT provided, the `crap` command MUST NOT run the O1
pipeline. All quality fields remain `null`. This keeps `crap` fast (no test
discovery or Astroid inference).

#### Scenario: crap with --tests populates quality fields
- **WHEN** `gazepy crap src/ --tests tests/` is run
- **THEN** JSON output includes `"contract_coverage_reason"` for all functions
  and non-null `"gaze_crap"` for paired functions with contractual effects

#### Scenario: crap without --tests has null quality fields
- **WHEN** `gazepy crap src/` is run without `--tests`
- **THEN** `"gaze_crap": null` and `"contract_coverage_reason": null` for
  all functions

---

### Requirement: summary-quality-fields

When quality data is available, the JSON summary MUST include:
- `"gaze_crapload"` — count of functions where `gaze_crap >= gaze_crap_threshold`
- `"avg_contract_coverage"` — average contract coverage percentage across all
  functions with non-null `percentage`
- `"quadrant_counts"` — dict mapping quadrant label to count of functions
  in that quadrant
- `"fix_strategy_counts"` — dict mapping fix strategy to count of functions
  with that strategy (populated whenever CRAP scores are available, does NOT
  require O1)

All four fields MUST be `null` when O1 has not run (OC-003).

#### Scenario: summary fields populated with quality data
- **WHEN** `gazepy quality` runs against a source with 5 functions
- **THEN** JSON summary includes non-null `gaze_crapload` and
  `avg_contract_coverage`

#### Scenario: fix_strategy_counts populated from CRAP scores
- **WHEN** CRAP scores are computed (even without O1)
- **THEN** `fix_strategy_counts` is non-null in summary

---

### Requirement: quality-command-text-output

The `quality` command text output MUST display a table with columns:
- Function name (with paired test name in parentheses)
- Contract coverage percentage (or reason code)
- GazeCRAP score (or `null`)

The text output MUST NOT include a quadrant column — the `quality` command
does not run line coverage collection, so `line_coverage_frac` is `None` for
all targets, and `quadrant()` requires both line and contract coverage fractions.

The footer MUST show average contract coverage and GazeCRAPload count.

#### Scenario: text output shows coverage and GazeCRAP
- **WHEN** `gazepy quality src/ --tests tests/ --format=text` is run
- **THEN** output contains function names, coverage percentages, and GazeCRAP
  scores in a tabular format

#### Scenario: no quadrant column in text output
- **WHEN** `gazepy quality` runs
- **THEN** text output does not include a "Quadrant" column

---

### Requirement: quality-command-json-output

The `quality` command with `--format=json` MUST emit a JSON array of
`QualityReport` objects (NOT wrapped in `AnalysisResult`). Each entry is
serialized via `dataclasses.asdict()` through the existing JSON encoder.

#### Scenario: JSON output is array of QualityReport
- **WHEN** `gazepy quality src/ --tests tests/ --format=json` is run
- **THEN** output is a JSON array where each element is a QualityReport object

---

### Requirement: build-contract-coverage-map

`build_contract_coverage_map(src_path, tests_path, config)` MUST be a
public function in `quality/pipeline.py` (not in `cli/`). It MUST:
1. Call `assess()` to run the full O1 pipeline.
2. Consolidate `AssessResult.reports` and `AssessResult.untested` into a
   flat `dict[str, ContractCoverageResult]` keyed by production function name.
3. When multiple test functions target the same production function, keep
   the entry with the highest `percentage` (or the first entry when both
   are `None`).
4. On any exception from `assess()`, emit a warning to `sys.stderr` and
   return an empty dict (graceful degradation per OC-003).

#### Scenario: best coverage kept for multiply-tested function
- **WHEN** two tests target `compute` with 30% and 70% coverage respectively
- **THEN** `build_contract_coverage_map()` returns `{"compute": <70% result>}`

#### Scenario: assess failure returns empty dict
- **WHEN** `assess()` raises an exception
- **THEN** `build_contract_coverage_map()` returns `{}` and writes a warning
  to stderr

---

### Requirement: ci-threshold-enforcement

The `quality` command MUST support a `--min-contract-coverage` option
specifying a minimum average contract coverage percentage. When the average
falls below the threshold, the command MUST:
1. Print a failure message identifying which functions are below threshold.
2. Exit with a non-zero exit code.

#### Scenario: threshold exceeded causes non-zero exit
- **WHEN** `--min-contract-coverage=80` and average coverage is 50%
- **THEN** the command exits with a non-zero exit code and prints the
  failing function names and their coverage percentages
