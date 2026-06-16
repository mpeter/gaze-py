## ADDED Requirements

### Requirement: _build_summary becomes a thin coordinator with CC ≤ 5
After decomposition, `_build_summary` MUST delegate aggregate computations to private helpers and contain no more than 5 cyclomatic complexity points of its own.

#### Scenario: _build_summary output unchanged
- **WHEN** `_build_summary` is called with any valid `all_targets` and `config`
- **THEN** the returned `Summary` is byte-for-byte identical to the pre-decomposition output for all existing tests

### Requirement: _compute_avg_line_coverage with CC ≤ 3
`_compute_avg_line_coverage(targets: list[FunctionTarget], coverage_data: dict[str, float] | None) -> float | None` MUST return `None` when `coverage_data` is `None` or when no targets have `score.line_coverage` set, and the average of non-None `score.line_coverage` values otherwise (per OC-003).

#### Scenario: Returns None when coverage_data is None
- **WHEN** `_compute_avg_line_coverage(targets, coverage_data=None)` is called
- **THEN** returns `None`

#### Scenario: Returns None when no line data available
- **WHEN** `_compute_avg_line_coverage(targets, coverage_data={})` is called and no target has `score.line_coverage`
- **THEN** returns `None`

#### Scenario: Returns average of non-None values
- **WHEN** some targets have `score.line_coverage` set
- **THEN** returns the mean of those values

### Requirement: _compute_gaze_crapload with CC ≤ 4
`_compute_gaze_crapload(targets: list[FunctionTarget], config: GazeConfig) -> int | None` MUST return `None` when no targets have `score.gaze_crap` set, and the count of targets where `score.gaze_crap >= config.gaze_crap_threshold` otherwise.

#### Scenario: Returns None when no gaze_crap data
- **WHEN** no targets have `score.gaze_crap` set
- **THEN** returns `None`

### Requirement: _compute_avg_contract_coverage with CC ≤ 3
`_compute_avg_contract_coverage(targets: list[FunctionTarget]) -> float | None` MUST return `None` when no targets have `score.contract_coverage` set, and the mean of non-None values otherwise.

### Requirement: _compute_quadrant_counts with CC ≤ 3
`_compute_quadrant_counts(targets: list[FunctionTarget]) -> dict[str, int] | None` MUST return `None` when no targets have `score.quadrant` set, and a `{label: count}` dict otherwise.

#### Scenario: Returns None when no quadrant data
- **WHEN** no targets have `score.quadrant` set
- **THEN** returns `None`

#### Scenario: Returns count dict when quadrant data present
- **WHEN** some targets have `score.quadrant` set
- **THEN** returns a dict mapping each distinct quadrant label to its count

### Requirement: _compute_fix_strategy_counts with CC ≤ 3
`_compute_fix_strategy_counts(targets: list[FunctionTarget]) -> dict[str, int] | None` MUST return `None` when no targets have `score.fix_strategy` set, and a `{strategy: count}` dict otherwise.

### Requirement: All existing crap/quality CLI tests pass unchanged
- **WHEN** any existing test that exercises `_build_summary` via the CLI (`gazepy crap` or `gazepy quality`) is run after decomposition
- **THEN** all tests pass with no changes to test code
