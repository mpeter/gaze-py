# Proposal: effect-confidence-range

## Summary

Populate the `effect_confidence_range` field in `Score` (currently always
`None`) and formally specify the cyclomatic complexity algorithm with the
missing round-trip tests. Two gaps closed in one patch-level change:

- **A.6**: `Score.effect_confidence_range` carries `[min, max]` confidence
  when all effects on a function are ambiguously classified. Follows the Go
  reference implementation exactly — null in all other cases.
- **B.1–B.2**: The complexity algorithm is formally specified and locked by
  7 missing round-trip tests that detect specific regression scenarios.

## Motivation

`effect_confidence_range` has been `None` since the O1 pipeline landed. The
field exists in the JSON schema and is specified in taxonomy-reference.md, but
was deferred. The Go reference shows the exact population condition:
`reason == "all_effects_ambiguous"` — when a function has effects but none
are contractual, the confidence range surfaces for diagnostic purposes.

The complexity algorithm is documented in code but lacks formal spec and
round-trip tests: `test_high_complexity_function_greater_than_1` asserts
`> 1` instead of `== 8`, meaning a regression returning `5` or `3` would
silently pass. Seven specific cases (assert, multi-item with, multiple except,
chained BoolOp, multi-filter comprehension, nested function independent scoring,
exact high-complexity value) have no coverage.

## Acceptance Criteria

**A.6:**
1. When a function's all effects are classified ambiguous (`reason == "all_effects_ambiguous"`),
   `Score.effect_confidence_range` is `(min_score, max_score)` where both are
   ints in `[0, 100]`.
2. When `reason` is anything else (including `no_effects_detected`, `None`, etc.),
   `effect_confidence_range` is `None`.
3. The field serializes to `[min, max]` in JSON, or `null` when `None`.
4. All existing tests continue to pass.

**B.1–B.2:**
5. `ruff check`, `ruff format --check`, `mypy --strict` all pass.
6. `pytest --cov-fail-under=85` passes with 7 new complexity tests added.
7. Each new test asserts an exact expected value (not just `> 1`).
8. `test_high_complexity_function_greater_than_1` is updated to assert `== 8`.
