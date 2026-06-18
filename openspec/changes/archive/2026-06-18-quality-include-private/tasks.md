## 1. Core fix — assess() and build_contract_coverage_map()

- [x] 1.1 In `src/gaze_py/quality/pipeline.py`, add `include_unexported: bool = True`
      to `assess()` signature (after `target_func`); pass it to
      `detect_and_classify()` call at line ~78:
      ```python
      source_targets = detect_and_classify(
          src_path.resolve(),
          config=config,
          include_unexported=include_unexported,
      )
      ```
      Update `assess()` docstring to document the new parameter.

- [x] 1.2 In `src/gaze_py/quality/pipeline.py`, add `include_unexported: bool = True`
      to `build_contract_coverage_map()` signature as keyword-only argument;
      pass it to the `assess()` call inside.

## 2. CLI wiring — quality command

- [x] 2.1 In `src/gaze_py/cli/main.py`, change the `--include-unexported` option
      on the `quality` command from `default=False` to `default=True`. Update
      help text to:
      `"Include underscore-prefixed functions (default: on). Pass --no-include-unexported to restrict to public functions only."`

- [x] 2.2 In the `quality` command body (`src/gaze_py/cli/main.py`, the
      `assess()` call approximately at line 561), add
      `include_unexported=include_unexported` as a keyword argument:
      ```python
      result = assess(
          src_path.resolve(),
          resolved_tests,
          config=config,
          target_func=target,
          include_unexported=include_unexported,   # ← add this
      )
      ```
      Note: the quality command's JSON output path goes through
      `_emit_quality_json(result.reports)`, which uses the `result` from
      `assess()` — so wiring `include_unexported` into `assess()` covers both
      text and JSON output paths with no additional changes. Note:
      `_enrich_with_quality()` calls `build_contract_coverage_map()` without
      `include_unexported`; after task 1.2 it inherits `default=True`, which
      is correct (the `crap` path already hardcodes `True` at line 1758).

## 3. Tests — fix expectations

- [x] 3.1 Run `uv run pytest -m "not slow" -x --tb=short -q` to identify
      which tests fail with the new default. Record the failures.
      Result: 0 failures — all 678 tests pass without modification.

- [x] 3.2 For each failing test, apply one of two fixes — choose based on what
      the test is asserting:
      a) **Expected-value update**: If the test asserts a count or list of
         function names that will grow (e.g., `assert len(reports) == 25`),
         update the expected value to match the new count. Confirm by running
         the test.
      b) **Logic inversion**: If the test asserts that a private function is
         ABSENT (e.g., `assert "_helper" not in names`), it is verifying the
         old exclusion behaviour. Invert the assertion to verify the new
         inclusion behaviour (`assert "_helper" in names`). Do NOT delete it.
      In both cases: do NOT remove assertions, do NOT add `pass` or `assert True`,
      do NOT change what the test is exercising. Key files likely affected:
      - `tests/test_quality_coverage.py`
      - `tests/test_quality_integration.py`
      - `tests/test_quality_pairing.py`
      - `tests/test_cli.py` (quality command tests)
      Result: No test changes needed — all existing tests used `>=` comparisons
      for report counts, so they accommodate the increased function set naturally.

## 4. CHANGELOG

- [x] 4.1 Add entry under `## [Unreleased]`:
      ```
      ### Changed
      - `gazepy quality` and `assess()` now include underscore-prefixed
        (private) functions by default. Previously these were excluded,
        causing the quality pipeline to miss the majority of functions in
        most Python codebases. Use `--no-include-unexported` to restore the
        old behaviour.
      ```
      Add `- Spec: openspec/changes/quality-include-private/` at the end of
      the entry.

## 5. Verification

- [x] 5.1 Run `uv run gazepy quality src/gaze_py/ --tests tests/ --format=json
      2>/dev/null | python3 -c "import json,sys; r=json.load(sys.stdin);
      print(len(r), 'pairings')"` — should be significantly more than 25
      (the pre-fix baseline per proposal.md; exact post-fix count depends on
      the current test suite size).
      Result: **469 pairings** (vs 25 baseline — 18.8× improvement).

- [x] 5.2 Run full CI gate:
      `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
      Result: All pass. 678 tests, 95.19% coverage.

## Convention Pack Compliance

Before implementing any task, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`

<!-- spec-review: passed -->

<!-- code-review: passed -->
