# Spec: quality-coverage

Contract coverage computation for the O1 quality assessment pipeline.
Classifies each side effect individually using `ClassificationEngine`, then
computes what fraction of contractual effects have at least one mapped
assertion.

---

### Requirement: per-effect-classification

`compute_contract_coverage()` MUST classify each `SideEffect` on the target
function individually using `ClassificationEngine`. Classification MUST NOT
use the function-level `FunctionTarget.classification` field (which reflects
only the primary effect). Each effect is classified independently as
`"contractual"`, `"incidental"`, or `"ambiguous"`.

#### Scenario: mixed effects classified individually
- **WHEN** a function has one contractual effect and one incidental effect
- **THEN** coverage is computed using only the contractual effect as the
  denominator; the incidental effect contributes to `over_specification_count`

---

### Requirement: coverage-formula

Contract coverage MUST be computed as:

```
percentage = (count of distinct contractual effect types with ≥1 mapped assertion)
           / (count of distinct contractual effect types)
           × 100.0
```

Coverage uses **distinct effect types** (a `set[SideEffectType]`), not the
raw count of `SideEffect` objects. One `ReturnValue` effect counts as covered
if ANY assertion maps to `SideEffectType.ReturnValue`.

The result MUST be stored as `ContractCoverageResult.percentage` in the range
`[0.0, 100.0]`. Callers passing this value to `gaze_crap()` or `quadrant()`
MUST divide by 100.0 (those functions take fractions in `[0.0, 1.0]`).

#### Scenario: 100% coverage
- **WHEN** all contractual effect types have at least one mapped assertion
- **THEN** `percentage == 100.0`

#### Scenario: 50% coverage
- **WHEN** 2 contractual effect types exist and 1 has a mapped assertion
- **THEN** `percentage == 50.0`

#### Scenario: 0% coverage
- **WHEN** contractual effects exist but no assertion maps to any of them
- **THEN** `percentage == 0.0`

#### Scenario: duplicate effect types counted once
- **WHEN** a function has two `ReturnValue` effects and one assertion maps
  to `ReturnValue`
- **THEN** `covered_count == 1` and `total_contractual == 1`
  (distinct types, not raw count)

---

### Requirement: null-not-zero

Per OC-003, `ContractCoverageResult.percentage` MUST be `None` (not `0.0`)
when there are no contractual effects. The four reason codes are mutually
exclusive and MUST be checked in this order:

1. `"no_effects_detected"` — `target.effects` is empty (function has no
   detected side effects at all).
2. `"no_test_coverage"` — `no_test_coverage=True` was passed AND
   `target.effects` is non-empty (effects exist but no test targets this
   function). Takes precedence over `"all_effects_ambiguous"`.
3. `"all_effects_ambiguous"` — effects exist, none are contractual, none
   are incidental (all classified as ambiguous).
4. `"no_contractual_effects"` — effects exist but all are incidental
   (none contractual).

When `percentage` is `None`, `covered_effects` MUST be `0`.

#### Scenario: no effects detected
- **WHEN** `target.effects` is empty
- **THEN** `percentage=None`, `reason="no_effects_detected"`

#### Scenario: no contractual effects (all incidental)
- **WHEN** effects exist but all classify as incidental
- **THEN** `percentage=None`, `reason="no_contractual_effects"`

#### Scenario: all effects ambiguous
- **WHEN** effects exist but all classify as ambiguous (neither contractual
  nor incidental)
- **THEN** `percentage=None`, `reason="all_effects_ambiguous"`

---

### Requirement: no-test-coverage-reason

`compute_contract_coverage()` MUST accept a `no_test_coverage: bool = False`
parameter. When `no_test_coverage=True` AND `target.effects` is non-empty,
the function MUST return immediately with:
- `percentage=None`
- `reason="no_test_coverage"`
- `covered_effects=0`
- `total_contractual` set to the count of contractual effects (computed
  from classification, not assumed zero)

This matches the Go porting contract (`contract.go:148`): "no test = no
coverage data, not 0% coverage." GazeCRAP MUST remain `null` for functions
with `"no_test_coverage"` reason.

`"no_test_coverage"` is distinct from `0.0%` coverage:
- `0.0%` means a test ran but no assertion mapped to any contractual effect.
- `"no_test_coverage"` means no test targeted this function at all.

When `no_test_coverage=True` but `target.effects` is empty, the function
falls through to normal computation (returns `"no_effects_detected"`).

#### Scenario: no_test_coverage with effects
- **WHEN** `no_test_coverage=True` and function has detected side effects
- **THEN** `percentage=None`, `reason="no_test_coverage"`, `covered_effects=0`

#### Scenario: no_test_coverage with no effects falls through
- **WHEN** `no_test_coverage=True` and `target.effects` is empty
- **THEN** `percentage=None`, `reason="no_effects_detected"`

#### Scenario: no_test_coverage supersedes all_effects_ambiguous
- **WHEN** `no_test_coverage=True` and all effects are ambiguous
- **THEN** `reason="no_test_coverage"` (not `"all_effects_ambiguous"`)

---

### Requirement: over-specification-count

`ContractCoverageResult.over_specification_count` MUST count the number of
assertions in `mapped` whose matched `SideEffectType` is classified as
incidental on the target function. These are assertions that verify
implementation details rather than contractual behaviour.

#### Scenario: assertion on incidental effect counted
- **WHEN** an assertion maps to a `SideEffectType` that classifies as
  incidental on the target
- **THEN** `over_specification_count` is incremented

---

### Requirement: unmapped-assertions-count

`ContractCoverageResult.unmapped_assertions` MUST count the number of
assertions in `mapped` whose matched `SideEffectType` is `None` (the
assertion could not be mapped to any effect).

#### Scenario: unmapped assertion counted
- **WHEN** an assertion maps to `None` in the mapped list
- **THEN** `unmapped_assertions` is incremented

---

### Requirement: private-functions-included

Private (underscore-prefixed) functions MUST be included in contract coverage
computation by default. `assess()` passes `include_unexported=True` to
`detect_and_classify()`, so private functions appear in `source_targets` and
receive coverage computation.

#### Scenario: private function receives coverage result
- **WHEN** `_validate` has detected effects and a paired test
- **THEN** `compute_contract_coverage()` is called for `_validate` and
  produces a `ContractCoverageResult` with a non-None `percentage`

---

### Requirement: all-effects-ambiguous-confidence-range

When `reason="all_effects_ambiguous"`, `ContractCoverageResult` MUST
populate `min_confidence` and `max_confidence` with the minimum and maximum
`ClassificationResult.score` values across all ambiguous effects. These
fields MUST be `None` in all other cases.

#### Scenario: confidence range populated for ambiguous effects
- **WHEN** all effects are ambiguous with scores 30 and 60
- **THEN** `min_confidence=30`, `max_confidence=60`

#### Scenario: confidence range is None for normal coverage
- **WHEN** coverage is computed normally (contractual effects exist)
- **THEN** `min_confidence=None`, `max_confidence=None`
