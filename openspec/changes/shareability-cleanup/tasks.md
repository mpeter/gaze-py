<!--
  [P] marks tasks eligible for parallel execution.
  Tasks without [P] run sequentially first, then [P] tasks run in parallel.
-->

## Phase 1 — Source code comment cleanup

- [x] 1.1 In `src/gaze_py/cli/main.py`, remove the two `# H4 fix` comment lines
      near the `_discover_tests_path` function. Already done.
      Verified: `grep -n "H4 fix" src/gaze_py/cli/main.py` returns no output. ✓

- [x] 1.2 In `src/gaze_py/cli/main.py`, strip `(H6 fix)` from inline comments.
      Already done.
      Verified: `grep -n "H6 fix" src/gaze_py/cli/main.py` returns no output. ✓

- [x] 1.3 In `src/gaze_py/cli/main.py`, remove the `# Summary line — M6:` comment.
      Already done.
      Verified: `grep -n "M6" src/gaze_py/cli/main.py` returns no output. ✓

- [x] 1.4 In `src/gaze_py/cli/main.py`, strip `(H2 fix)` from the docstring of
      `_run_analyze`. Already done.
      Verified: `grep -n "H2 fix" src/gaze_py/cli/main.py` returns no output. ✓

- [x] 1.5 In `src/gaze_py/taxonomy/models.py`, strip `(H6 fix)` from the docstring
      of `QualityReport`. Already done.
      Verified: `grep -n "H6 fix" src/gaze_py/taxonomy/models.py` returns no output. ✓

- [x] 1.6 In `src/gaze_py/cli/main.py`, fix the three stale stub-comment headers.
      Already done.
      Verified: `grep -n "task 3\|task 4\|task 5" src/gaze_py/cli/main.py` returns
      no output. ✓

## Phase 2 — Test fix

- [x] 2.1 In `tests/test_quality_integration.py`, the tautological assertion has been
      replaced. The test `test_attribute_mutation_fixture_coverage` (note: correct
      function name — NOT `test_attribute_mutation_coverage`) now asserts the
      concrete pipeline output with full specificity:
      ```python
      assert report.contract_coverage is not None
      assert report.contract_coverage.percentage is None
      assert report.contract_coverage.reason == "no_effects_detected"
      assert report.contract_coverage.total_contractual == 0
      ```
      The `or report.target_function is not None` tautology is gone.
      The docstring is updated to reflect the actual contract:
      "attribute mutation classified as incidental → percentage=None, reason='no_effects_detected'"
      Verified: `uv run pytest tests/test_quality_integration.py::test_attribute_mutation_fixture_coverage -v` passes. ✓

## Phase 3 — README update [P]

- [x] 3.1 [P] Three badges already present at lines 3–5 of `README.md`:
      CI badge, PyPI badge, Python badge (all pointing to `mpeter/gaze-py`). ✓

- [x] 3.2 [P] README already updated: "GazeCRAP scoring deferred" bullet gone,
      output field table updated, `gazepy quality` usage section present with all
      three examples (`src/`, `--tests tests/`, `--min-contract-coverage 80`). ✓

- [x] 3.3 [P] `### One-time setup (already done)` block already removed from
      `## Releasing` section. ✓

## Phase 4 — CHANGELOG [P]

- [x] 4.1 [P] `## [0.1.0] — 2026-06-13` entry already present in `CHANGELOG.md`
      with all specified content (38 SideEffectType values, CRAP/GazeCRAP formulas,
      five-signal classification, JSON output, CLI commands, Python 3.11+,
      AST-only). ✓

## Phase 5 — Housekeeping [P]

- [x] 5.1 [P] All six completed OpenSpec changes already archived. Current state of
      `openspec/changes/archive/`: `001-initial-port/`, `cli-parity/`,
      `constitution-v1-1-0-pr/`, `coverprofile-path-fix/`, `o1-quality-pipeline/`,
      `pypi-release/`, `upgrade-setup-uv/` (seven entries total including
      `constitution-v1-1-0-pr/` which was archived in a prior session).
      Current state of `openspec/changes/`: `002-deferred-capabilities/`,
      `archive/`, `effect-confidence-range/`, `o3-docscan/`, `shareability-cleanup/`.
      Note: `effect-confidence-range/` and `o3-docscan/` are open changes — do NOT
      archive them. ✓

- [x] 5.2 [P] `docs/.gitkeep` already removed. `docs/` directory does not exist. ✓

- [x] 5.3 [P] Stage `uv.lock` (version bump 0.3.1 → 0.4.0, includes mypy 1.x → 2.1.0
      major upgrade with new transitive deps ast-serialize and librt):
      ```bash
      git add uv.lock
      ```
      Verified: `git diff uv.lock` shows no output after staging. ✓
      Verified: `grep 'version = "0.4.0"' uv.lock` returns the gaze-py package entry. ✓

## Phase 6 — CI gate

- [x] 6.1 Run full CI gate and confirm all pass:
      ```bash
      uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85
      ```
      Verified: ruff ✓ mypy --strict ✓ pytest 523 passed 91.50% coverage ✓
      (After additional fixes: README "Effect confidence range deferred" removed,
      scorer.py stale O1 comment removed, test docstring corrected.)

- [x] 6.2 Confirm no review marker strings remain in src/:
      ```bash
      grep -rn "# H4 fix\|# H6 fix\|# H2 fix\|# M6\|stub — task [345]" src/
      ```
      Verified: returns no output. ✓

<!-- spec-review: passed -->

<!-- code-review: passed -->
