# Spec: quality-assessment

Capability: `gazepy quality` and `assess()` — contract coverage assessment
with private-function inclusion by default.

Sources: `src/gaze_py/cli/main.py` (quality command), `CHANGELOG.md`.

---

### Requirement: Private functions included by default

`gazepy quality` and the underlying `assess()` function SHALL include
underscore-prefixed (private) functions by default. The `--include-unexported`
flag defaults to `True` for the quality command.

This is the **opposite** of `gazepy analyze`, which defaults
`--include-unexported` to `False` (private functions excluded unless
explicitly requested).

**Rationale**: The majority of functions in real-world Python codebases have
underscore prefixes. Excluding them by default caused the quality pipeline to
miss most of the functions that most need quality assessment. The quality
command's purpose is to surface contract coverage gaps — excluding private
functions defeats that purpose.

#### Scenario: Private functions included by default
- **WHEN** `gazepy quality src/mypackage/` is run without any flags
- **THEN** underscore-prefixed functions (e.g. `_parse_config`, `_validate`)
  are included in the quality assessment output

#### Scenario: analyze excludes private by default
- **WHEN** `gazepy analyze src/mypackage/` is run without `--include-unexported`
- **THEN** underscore-prefixed functions are NOT included in the output
  (original behavior preserved)

---

### Requirement: --no-include-unexported restores old behavior

Passing `--no-include-unexported` to `gazepy quality` SHALL restrict the
quality assessment to public (non-underscore-prefixed) functions only,
restoring the pre-change behavior.

#### Scenario: Old behavior restored
- **WHEN** `gazepy quality src/mypackage/ --no-include-unexported` is run
- **THEN** underscore-prefixed functions are excluded from the quality
  assessment output

---

### Requirement: assess() include_unexported parameter

The `assess()` function in `quality/pipeline.py` SHALL accept
`include_unexported: bool = True` as a parameter. When `True`, private
functions are included in the analysis. When `False`, they are excluded.

The `gazepy quality` command passes `include_unexported` directly from the
Click flag value.

#### Scenario: assess() called with include_unexported=True
- **WHEN** `assess(src, tests, include_unexported=True)` is called
- **THEN** underscore-prefixed production functions are included in the
  returned `AssessResult`

#### Scenario: assess() called with include_unexported=False
- **WHEN** `assess(src, tests, include_unexported=False)` is called
- **THEN** underscore-prefixed production functions are excluded from the
  returned `AssessResult`

---

### Requirement: gazepy crap --tests uses private-inclusive default

When `gazepy crap --tests PATH` is run, the quality pipeline portion SHALL
also use the private-inclusive default (`include_unexported=True`) for the
`assess()` call. This ensures consistency between `gazepy quality` and
`gazepy crap --tests` for private function coverage.

#### Scenario: crap --tests includes private functions
- **WHEN** `gazepy crap src/ --tests tests/` is run
- **THEN** underscore-prefixed functions receive `contract_coverage` and
  `gaze_crap` enrichment in the output (not silently skipped)

---

### Requirement: gazepy analyze retains original default

`gazepy analyze` SHALL retain `--include-unexported` defaulting to `False`.
The flag is opt-in for `analyze`. This requirement is unchanged from v0.2.0.

Only the quality pipeline (`gazepy quality`, `assess()`, and the quality
enrichment path in `gazepy crap --tests`) uses the private-inclusive default.

#### Scenario: analyze unchanged
- **WHEN** `gazepy analyze src/mypackage/` is run
- **THEN** underscore-prefixed functions are not included unless
  `--include-unexported` is explicitly passed

---

### Requirement: Quality command flag surface

`gazepy quality PATH` SHALL support the following flags:

- `--format [json|text]` — output format (default: `text`)
- `--tests PATH` — test directory or file; auto-discovered if omitted
- `--target NAME` — restrict to tests exercising a specific production
  function name
- `--verbose` / `-v` — full signal breakdown
- `--include-unexported` / `--no-include-unexported` — include private
  functions (default: on)
- `--config PATH` — explicit config file path
- `--contractual-threshold N` — override contractual confidence threshold
- `--incidental-threshold N` — override incidental confidence threshold
- `--min-contract-coverage N` — CI gate: exit 1 when average contract
  coverage is below `N` percent

#### Scenario: min-contract-coverage gate
- **WHEN** `--min-contract-coverage=80` is set and average coverage is 65%
- **THEN** per-function failures are emitted to stderr and the command exits 1

#### Scenario: Output emitted before gate
- **WHEN** the `--min-contract-coverage` gate fires
- **THEN** the quality report (JSON or text) is emitted to stdout first,
  then the gate error is emitted to stderr

---

### Requirement: Test auto-discovery

When `--tests` is not provided, `gazepy quality` SHALL auto-discover the
test directory by searching in order:

1. `tests/` relative to `src_path.parent`
2. `test/` relative to `src_path.parent`
3. `test_*.py` files relative to `src_path.parent`
4. `tests/` relative to `Path.cwd()`
5. `test/` relative to `Path.cwd()`
6. `test_*.py` files relative to `Path.cwd()`

When no test directory is found, the command SHALL exit 2 with:
`"Error: no tests directory found — use --tests"`

#### Scenario: Auto-discovery finds tests/
- **WHEN** a `tests/` directory exists adjacent to the source path
- **THEN** it is used as the test path without requiring `--tests`

#### Scenario: No tests found
- **WHEN** no test directory or file is found by auto-discovery
- **THEN** the command exits 2 with a message directing the user to
  use `--tests`

---

### Requirement: assess() returns AssessResult

`assess()` SHALL return an `AssessResult` object with:
- `.reports` — test-keyed `list[QualityReport]`
- `.untested` — production-function-keyed data for functions with no paired test

Direct Python callers MUST use `result = assess(...); reports = result.reports`
(not `reports = assess(...)` — the return type changed from `list[QualityReport]`
in a prior release).

#### Scenario: AssessResult structure
- **WHEN** `assess()` completes successfully
- **THEN** the return value has `.reports` (list) and `.untested` attributes

---

### Requirement: Known limitations

The following limitations are documented and deferred to future changes:

1. **Private function contract_coverage_reason enrichment**: Private
   (underscore-prefixed) functions do not receive `contract_coverage_reason`
   enrichment in `gazepy crap --tests` output. Deduplication of the double
   `detect_and_classify()` call is deferred to a follow-up change.

2. **Astroid cache clearing**: `MANAGER.clear_cache()` evicts astroid's
   process-global AST cache on each `assess()` call. Tools sharing the
   process that also use astroid (e.g. pylint) will have their cache cleared.

These limitations SHALL be documented in the CHANGELOG and SHALL NOT be
treated as bugs requiring immediate resolution.
