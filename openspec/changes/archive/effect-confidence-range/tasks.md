<!--
  [P] marks tasks eligible for parallel execution.
  Tasks without [P] run sequentially. [P] tasks run in parallel after
  sequential tasks in the same phase complete.
-->

## Phase 1 — Model change

- [x] 1.1 In `src/gaze_py/taxonomy/models.py`, add two new nullable fields to
      `ContractCoverageResult` (frozen dataclass):
      ```python
      min_confidence: int | None = None
      max_confidence: int | None = None
      ```
      Already implemented. Fields at lines 291–292. Docstrings updated.
      Verified: `uv run mypy --strict src/` passes. ✓

## Phase 2 — Coverage computation

- [x] 2.1 In `src/gaze_py/quality/coverage.py`, modify `compute_contract_coverage()`
      to (a) add the `"all_effects_ambiguous"` reason and (b) collect
      `ClassificationResult.score` values for that path.
      Already implemented at lines 75–86. `classify()` called once per effect.
      Verified: full test suite passes. ✓

## Phase 3 — CLI wiring

- [x] 3.1 In `src/gaze_py/cli/main.py`, update `_score_target()` to populate
      `effect_confidence_range` from the quality result.
      Already implemented at lines 1113–1122.
      Verified: `uv run mypy --strict src/` passes. ✓

## Phase 4 — Tests [P]

- [x] 4.1 [P] Test for `all_effects_ambiguous` path in `tests/test_quality_integration.py`.
      Already implemented: `test_effect_confidence_range_populated_when_all_effects_ambiguous`
      at line 185 (ECR-001). Constructs `ContractCoverageResult` directly with
      `reason="all_effects_ambiguous"`, `min_confidence=60`, `max_confidence=85`.
      Asserts `score.effect_confidence_range == (60, 85)` and range bounds. ✓

- [x] 4.2 [P] In `tests/test_output.py`, added `test_oc003_effect_confidence_range_serializes_as_list`.
      Constructs `Score(effect_confidence_range=(60, 85))`, passes through `to_json()`,
      asserts `fn["effect_confidence_range"] == [60, 85]` and `isinstance(..., list)`.
      Verified: `uv run pytest tests/test_output.py -v --no-cov -k "effect_confidence"` passes. ✓

- [x] 4.3 [P] JSON serialization of `None` case already tested in `tests/test_output.py`
      at line 214: `test_oc003_effect_confidence_range_is_null_key_present` asserts
      `fn["effect_confidence_range"] is None`. ✓

- [x] 4.4 [P] In `tests/test_complexity.py`, all 7 round-trip tests added:

      a. `test_high_complexity_function_exact_value` — asserts `== 9` with
         full breakdown comment (1 base + 8 decision points). ✓

      b. `test_assert_statement_increments_complexity` — asserts `== 2`. ✓

      c. `test_with_multi_item_increments_per_item` — asserts `== 3`. ✓

      d. `test_multiple_except_handlers` — asserts `== 3`. ✓

      e. `test_chained_bool_op` — asserts `== 3`. ✓

      f. `test_comprehension_multiple_if_filters` — asserts `== 3`. ✓

      g. `test_nested_function_complexity_is_independent` — existing test at
         line 74, asserts outer `== 1`. The spec name `test_nested_function_scored_independently`
         differs but covers the outer assertion. Task 4.5 adds the inner assertion.

- [x] 4.5 Added `test_nested_function_scored_independently` to `tests/test_complexity.py`.
      Asserts both `cyclomatic_complexity(outer_node) == 1` and
      `cyclomatic_complexity(inner_node) == 3` (CX-002: if + elif = 2 ast.If nodes + 1 base).
      Verified: passes. ✓

## Phase 5 — CI gate

- [x] 5.1 Run full CI gate:
      ```bash
      uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85
      ```
      Verified: ruff ✓ mypy --strict ✓ pytest 525 passed 91.50% coverage ✓

- [x] 5.2 Verify effect_confidence_range is None for normal coverage cases
      (regression check):
      ```bash
      uv run pytest tests/test_output.py -v --no-cov -k "effect_confidence"
      ```
      Verified: 2 passed (null case + new list-serialization case). ✓

<!-- spec-review: passed -->

<!-- code-review: passed -->
