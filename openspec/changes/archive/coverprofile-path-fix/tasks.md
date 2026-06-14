## 1. Fix path resolution

- [x] 1.1 In `src/gaze_py/cli/main.py`, update `_resolve_line_coverage` to
      add the cwd-relative lookup between the root-relative and filename-only
      attempts, exactly as specified in design.md

## 2. Regression tests — all three lookup branches

- [x] 2.1 Add parametrized unit tests for `_resolve_line_coverage` directly
      (import and call it; do not go through CLI), covering all three branches:
      - Branch 1 (root-relative): key = `analysis/complexity.py`; assert match
      - Branch 2 (cwd-relative): key = `src/gaze_py/analysis/complexity.py`; assert match
      - Branch 3 (filename-only): key = `complexity.py`; assert match
      Also test the non-match (absent key) case returns None.
- [x] 2.2 Confirm that `test_crap_coverprofile_path` (existing, branch 3 /
      root-relative depending on fixture layout) and
      `test_crap_max_crapload_threshold_exceeded` (existing, filename-only)
      still pass after the change — these are the branch-1 and branch-3
      regression baselines. No new code needed; noted here for traceability.
- [x] 2.3 Update `_resolve_line_coverage` docstring to describe all three
      attempts and note that the cwd-relative attempt is silently skipped
      (falls through to filename-only) when `py_file` is not under `Path.cwd()`

## 3. CI gate

- [x] 3.1 `uv run ruff check . && uv run ruff format --check .`
- [x] 3.2 `uv run mypy --strict src/`
- [x] 3.3 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`

<!-- code-review: passed -->