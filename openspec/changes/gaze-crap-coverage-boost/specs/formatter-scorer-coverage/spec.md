## ADDED Requirements

### Requirement: _json_default raises TypeError for unrecognized types
Tests MUST verify that `_json_default` raises `TypeError` when called with an object that is neither an `enum.Enum`, `tuple`, nor `frozenset`.

#### Scenario: _json_default raises TypeError for plain object
- **WHEN** `_json_default(object())` is called
- **THEN** `TypeError` is raised
- **AND** the error message contains the type name

### Requirement: to_text renders non-null fix_strategy correctly
Tests MUST verify that when a `FunctionTarget` has a non-null `fix_strategy`, `to_text()` includes that strategy value in the output string.

#### Scenario: to_text renders fix_strategy when set
- **WHEN** `to_text()` is called with a result containing a target whose `score.fix_strategy == "add_tests"`
- **THEN** the output string contains `"add_tests"`

### Requirement: crapload skips targets with score=None
Tests MUST verify that `crapload()` silently skips `FunctionTarget` objects where `target.score is None`.

#### Scenario: crapload skips no-score target
- **WHEN** `crapload([target_with_no_score], threshold=0.5)` is called
- **THEN** the result is an empty list

### Requirement: recommended_actions skips targets with score=None
Tests MUST verify that `recommended_actions()` silently skips `FunctionTarget` objects where `target.score is None`.

#### Scenario: recommended_actions skips no-score target
- **WHEN** `recommended_actions([target_with_no_score])` is called
- **THEN** the result is an empty list
