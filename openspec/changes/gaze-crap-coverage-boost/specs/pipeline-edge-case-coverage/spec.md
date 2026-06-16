## ADDED Requirements

### Requirement: _process_test_func returns report with null coverage when inferred target not in source map
Tests MUST verify that when a test function is paired (by name convention) to a production function name that does not exist in the source analysis, the resulting `QualityReport` has `target_function` set to the inferred name and `contract_coverage=None`.

#### Scenario: Inferred target absent from source map produces null-coverage report
- **WHEN** `assess()` is called with a test file containing `test_nonexistent_fn` and a source file with no function named `nonexistent_fn`
- **THEN** the resulting `QualityReport` has `target_function == "nonexistent_fn"` and `contract_coverage is None`
- **AND** `warnings` contains a message about the inferred target not being found

### Requirement: build_contract_coverage_map returns empty dict on assess() exception
Tests MUST verify that when `assess()` raises any exception, `build_contract_coverage_map()` returns an empty dict and emits a warning to stderr.

#### Scenario: assess() exception produces empty dict
- **WHEN** `assess()` is monkeypatched to raise `RuntimeError("boom")`
- **THEN** `build_contract_coverage_map()` returns `{}`
- **AND** a warning message is written to stderr

### Requirement: build_contract_coverage_map keeps higher contract coverage percentage for duplicate targets
Tests MUST verify that when multiple test functions target the same production function, the entry with the higher `percentage` is kept in the result map.

#### Scenario: Higher percentage wins deduplication
- **WHEN** `assess()` returns two `QualityReport` objects for the same `target_function` — one with 0% and one with 100%
- **THEN** `build_contract_coverage_map()` returns a map where the entry for that function has `percentage == 100.0`

#### Scenario: New entry with None percentage does not displace existing percentage
- **WHEN** `assess()` returns a `QualityReport` with 50% coverage followed by one with `None` percentage for the same function
- **THEN** the resulting map entry retains `percentage == 50.0`
