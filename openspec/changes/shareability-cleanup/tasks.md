<!--
  [P] marks tasks eligible for parallel execution.
  Tasks without [P] run sequentially first, then [P] tasks run in parallel.
-->

## Phase 1 — Source code comment cleanup

- [ ] 1.1 In `src/gaze_py/cli/main.py`, remove the two `# H4 fix` comment lines
      near the `_discover_tests_path` function (lines ~583 and ~592). These are
      internal review markers with no value for external readers.
      Verify with: `grep -n "H4 fix" src/gaze_py/cli/main.py` → must return no output.

- [ ] 1.2 In `src/gaze_py/cli/main.py`, strip `(H6 fix)` from the inline comment
      near the GazeCRAP computation (line ~652) and from the docstring of
      `_build_summary` (line ~673). Keep the substantive text; remove only
      the `(H6 fix)` marker.
      Verify with: `grep -n "H6 fix" src/gaze_py/cli/main.py` → must return no output.

- [ ] 1.3 In `src/gaze_py/cli/main.py`, remove the `# Summary line — M6: use typed
      access instead of hasattr().` comment (line ~659). It is noise.
      Verify with: `grep -n "M6" src/gaze_py/cli/main.py` → must return no output.

- [ ] 1.4 In `src/gaze_py/cli/main.py`, strip `(H2 fix)` from the docstring of
      `_run_analyze` (line ~1160). Keep the substantive text.
      Verify with: `grep -n "H2 fix" src/gaze_py/cli/main.py` → must return no output.

- [ ] 1.5 In `src/gaze_py/taxonomy/models.py`, strip `(H6 fix)` from the docstring
      of `QualityReport` (line ~294). Keep the substantive sentence; remove only
      the review-marker suffix.
      Verify with: `grep -n "H6 fix" src/gaze_py/taxonomy/models.py` → must return no output.

- [ ] 1.6 In `src/gaze_py/cli/main.py`, fix the three stale stub-comment headers:
      - `# quality command (stub — task 3)` → `# quality command`
      - `# docscan command (stub — task 4)` → `# docscan command (not yet implemented — requires O3)`
      - `# report command (stub — task 5, replaces old (src, tests) signature)` → `# report command (not yet implemented — requires O2)`
      Verify with: `grep -n "task 3\|task 4\|task 5" src/gaze_py/cli/main.py` → must return no output.
      Note: task 1.5 in this list now covers `taxonomy/models.py`; the old 1.5 is
      now 1.6 — numbering updated accordingly.

## Phase 2 — Test fix

- [ ] 2.1 In `tests/test_quality_integration.py`, replace the tautological assertion.
      The current code reads approximately:
      ```python
      assert report.contract_coverage is not None or report.target_function is not None
      ```
      The right-hand `or` arm is always True (target_function was asserted non-None
      two lines earlier), making the entire expression a no-op.

      **Before writing the replacement**: run the test with `-s` to observe the actual
      pipeline output for this fixture:
      ```bash
      uv run pytest tests/test_quality_integration.py::test_attribute_mutation_coverage -sv 2>&1 | grep "contract_coverage"
      ```
      If `contract_coverage` is reliably `> 0.0` for this fixture (the test asserts
      on the mutated attribute, which the mapper should pair to the effect), use:
      ```python
      assert report.contract_coverage is not None
      assert report.contract_coverage > 0.0
      ```
      If `contract_coverage` is reliably `0.0`, assert `== 0.0` with a comment
      explaining why (e.g., the mapper did not pair the assertion). If it is
      non-deterministic, assert `>= 0.0` and add a comment flagging the uncertainty.
      Choose the strongest assertion the pipeline can reliably satisfy.

      Verify: `uv run pytest tests/test_quality_integration.py -v` → all tests pass.

## Phase 3 — README update [P]

- [ ] 3.1 [P] Add three badges to `README.md` immediately after the `# gaze-py`
      title (before the first paragraph):
      ```markdown
      [![CI](https://github.com/mpeter/gaze-py/actions/workflows/test.yml/badge.svg)](https://github.com/mpeter/gaze-py/actions/workflows/test.yml)
      [![PyPI](https://img.shields.io/pypi/v/gaze-py)](https://pypi.org/project/gaze-py/)
      [![Python](https://img.shields.io/pypi/pyversions/gaze-py)](https://pypi.org/project/gaze-py/)
      ```
      Verify: `head -6 README.md` shows the title followed by the three badge lines.

- [ ] 3.2 [P] In `README.md`, remove the "GazeCRAP scoring deferred" bullet from the
      `## Current limitations` section. Update the output field table: the `gaze_crap`
      and `quadrant` rows currently say `null (O1 deferred)` — update them to
      accurately describe that these fields are populated by `gazepy quality`.
      Keep the "Effect confidence range deferred" bullet (still true).
      Add a `gazepy quality` usage example to the Basic usage section showing:
      - basic invocation: `gazepy quality src/`
      - with explicit tests dir: `gazepy quality src/ --tests tests/`
      - CI gate: `gazepy quality src/ --min-contract-coverage 80`

- [ ] 3.3 [P] In `README.md`, remove the `### One-time setup (already done)` block
      from the `## Releasing` section. Keep only the numbered "Releasing a new
      version" steps. This section documents internal ops knowledge that is not
      useful to contributors or users.

## Phase 4 — CHANGELOG [P]

- [ ] 4.1 [P] Add a `## [0.1.0]` entry to `CHANGELOG.md` at the bottom of the file
      (after the 0.2.0 entry). The 0.1.0 release was the initial port. Document:
      - Initial side-effect detection engine (38 SideEffectType values, P0–P4 tiers)
      - CRAP and GazeCRAP scoring formulas
      - Five-signal confidence classification engine
      - JSON output schema (schema-compatible with Go gaze)
      - CLI commands available in 0.1.0: `analyze`, `report` (with two-argument
        positional signature that was later broken in 0.2.0)
      - Python 3.11+ requirement
      - AST-only analysis (no code execution)
      Date: 2026-06-13 (the 001-initial-port merge date).

## Phase 5 — Housekeeping [P]

- [ ] 5.1 [P] Archive completed OpenSpec changes using `git mv`:
      ```bash
      git mv openspec/changes/001-initial-port openspec/changes/archive/001-initial-port
      git mv openspec/changes/cli-parity openspec/changes/archive/cli-parity
      git mv openspec/changes/coverprofile-path-fix openspec/changes/archive/coverprofile-path-fix
      git mv openspec/changes/o1-quality-pipeline openspec/changes/archive/o1-quality-pipeline
      git mv openspec/changes/pypi-release openspec/changes/archive/pypi-release
      git mv openspec/changes/upgrade-setup-uv openspec/changes/archive/upgrade-setup-uv
      ```
      Verify: `ls openspec/changes/archive/` shows all six directories.
      Verify: `ls openspec/changes/` shows only `002-deferred-capabilities/`,
      `archive/`, `constitution-v1-1-0-pr/`, `shareability-cleanup/`.

- [ ] 5.2 [P] Remove the empty docs/ directory:
      ```bash
      git rm docs/.gitkeep
      ```
      Verify: `ls docs/` produces "No such file or directory".

- [ ] 5.3 [P] Stage and commit the uv.lock version bump (0.2.0 → 0.3.0):
      ```bash
      git add uv.lock
      ```
      This should be included in the final commit for this change, not as a
      standalone commit. No separate commit needed — it will be staged with
      everything else at the end.
      Verify: `git diff uv.lock` shows no output after staging.

## Phase 6 — CI gate

- [ ] 6.1 Run full CI gate and confirm all pass:
      ```bash
      uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85
      ```
      All commands must exit 0.

- [ ] 6.2 Confirm no review marker strings remain in src/:
      ```bash
      grep -rn "H4 fix\|H6 fix\|H2 fix\|M6\|task 3\|task 4\|task 5" src/
      ```
      Must return no output.

<!-- spec-review: passed -->

<!-- code-review: passed -->
