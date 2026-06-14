<!--
  [P] marks tasks eligible for parallel execution.
  Tasks without [P] run sequentially. [P] tasks run in parallel after
  sequential tasks in the same phase complete.
-->

## Phase 1 — Model change

- [ ] 1.1 In `src/gaze_py/taxonomy/models.py`, add two new nullable fields to
      `ContractCoverageResult` (frozen dataclass):
      ```python
      min_confidence: int | None = None
      max_confidence: int | None = None
      ```
      Place them after `reason: str | None = None`. Update the class docstring
      to document both fields.
      Also update the `Score.effect_confidence_range` docstring — remove
      "Reserved for a future change. Always None." and replace with accurate
      description of when it is populated.
      Also update the `ContractCoverageResult.reason` docstring to include
      `"all_effects_ambiguous"` as a valid value alongside the existing two.
      Verify: `uv run mypy --strict src/` passes with zero errors.

## Phase 2 — Coverage computation

- [ ] 2.1       In `src/gaze_py/quality/coverage.py`, modify `compute_contract_coverage()`
      to (a) add the `"all_effects_ambiguous"` reason and (b) collect
      `ClassificationResult.score` values for that path.

      The current `if not contractual:` branch produces only
      `"no_effects_detected"` or `"no_contractual_effects"`. It must be split
      into three cases:
      1. `not target.effects` → `"no_effects_detected"` (unchanged)
      2. `target.effects` non-empty, some incidental → `"no_contractual_effects"` (unchanged)
      3. `target.effects` non-empty, zero incidental (all ambiguous) →
         `"all_effects_ambiguous"` with `min_confidence`/`max_confidence` set

      For case 3: collect the `.score` from each `engine.classify()` call
      (already called in the existing loop — save both `.label` and `.score`
      in one pass, no double-call). Set:
      ```python
      min_confidence=min(ambiguous_scores),
      max_confidence=max(ambiguous_scores),
      ```

      The change MUST NOT call `classify()` twice per effect.

      Verify: `uv run pytest tests/test_quality_coverage.py -v --no-cov` passes
      (or equivalent coverage test file). If no dedicated coverage test file
      exists, verify with the full suite.

## Phase 3 — CLI wiring

- [ ] 3.1 In `src/gaze_py/cli/main.py`, update `_score_target()` (~line 1042)
      to populate `effect_confidence_range` from the quality result.

      Replace:
      ```python
      effect_confidence_range=None,  # deferred to future change
      ```
      With:
      ```python
      effect_confidence_range=(
          (quality_result.min_confidence, quality_result.max_confidence)
          if (
              quality_result is not None
              and quality_result.reason == "all_effects_ambiguous"
              and quality_result.min_confidence is not None
              and quality_result.max_confidence is not None
          )
          else None
      ),
      ```
      Note: `quality_result` in `_score_target()` is already typed as
      `ContractCoverageResult | None` (confirmed at `cli/main.py:972`). No
      rename needed.

      Verify: `uv run mypy --strict src/` passes.

## Phase 4 — Tests [P]

- [ ] 4.1 [P] In `tests/test_quality_integration.py` (or a new dedicated test),
      add a test that exercises the `all_effects_ambiguous` path end-to-end via
      `_score_target()` in `cli/main.py`, or via the `assess()` pipeline.

      The `undertested`/`compute_total` fixture MUST NOT be used — its
      `ReturnValue` effect (P0 tier, +25 boost) will be classified as contractual,
      not ambiguous. Use an inline source function with only low-tier effects
      (e.g., a `LogWrite` or `StdoutWrite` effect) that are reliably ambiguous
      at default thresholds.

      Alternatively, construct a `ContractCoverageResult` directly with
      `reason="all_effects_ambiguous"` and `min_confidence=60`,
      `max_confidence=85`, call `_score_target()` with it, and assert the
      `Score.effect_confidence_range == (60, 85)`. This approach tests the
      CLI wiring independently of the classification engine.

      Either approach is acceptable. Assert:
      - `score.effect_confidence_range is not None`
      - `score.effect_confidence_range[0] <= score.effect_confidence_range[1]`
      - `0 <= score.effect_confidence_range[0] <= 100`
      - `0 <= score.effect_confidence_range[1] <= 100`

- [ ] 4.2 [P] In `tests/test_complexity.py`, add 7 new round-trip tests and fix
      the existing weak assertion:

      a. Fix `test_high_complexity_function_greater_than_1`:
         Change `assert result > 1` to `assert result == 9` and add a comment:
         ```python
         # 1 base + 6 if/elif (lines 3,4,6,10,12,19)
         #        + 1 for (line 11) + 1 while (line 17) = 9
         # Verified by running cyclomatic_complexity() against the fixture.
         ```

      b. Add `test_assert_statement_increments_complexity`:
         ```python
         source = "def f(x):\n    assert x > 0\n    return x\n"
         # expected: 2 (1 base + 1 assert)
         ```

      c. Add `test_with_multi_item_increments_per_item`:
         ```python
         source = "def f():\n    with a() as x, b() as y:\n        pass\n"
         # expected: 3 (1 base + 2 with-items)
         ```

      d. Add `test_multiple_except_handlers`:
         ```python
         source = (
             "def f():\n"
             "    try:\n"
             "        pass\n"
             "    except ValueError:\n"
             "        pass\n"
             "    except TypeError:\n"
             "        pass\n"
         )
         # expected: 3 (1 base + 2 except handlers)
         ```

      e. Add `test_chained_bool_op`:
         ```python
         source = "def f(a, b, c):\n    return a and b and c\n"
         # expected: 3
         # 'a and b and c' is ONE BoolOp node with values=[a,b,c]
         # → len(values)-1 = 2 → +2 complexity. Base 1 + 2 = 3.
         ```

      f. Add `test_comprehension_multiple_if_filters`:
         ```python
         source = (
             "def f(items):\n"
             "    return [x for x in items if x > 0 if x < 10]\n"
         )
         # expected: 3 (1 base + 2 comprehension if-filters)
         ```

      g. Add `test_nested_function_scored_independently`:
         Construct inline source with outer function containing a nested
         function that has 2 if-statements. Assert:
         - `cyclomatic_complexity(outer_node) == 1` (outer body has no branches)
         - `cyclomatic_complexity(inner_node) == 3` (1 base + 2 if)
         Use `ast.parse` and walk to find the inner `FunctionDef`.

      Verify: `uv run pytest tests/test_complexity.py -v --no-cov` all pass.

## Phase 5 — CI gate

- [ ] 5.1 Run full CI gate:
      ```bash
      uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85
      ```
      All commands must exit 0.

- [ ] 5.2 Verify effect_confidence_range is None for normal coverage cases
      (regression check):
      ```bash
      uv run pytest tests/test_output.py -v --no-cov -k "effect_confidence"
      ```
      Must pass.

<!-- spec-review: passed -->
