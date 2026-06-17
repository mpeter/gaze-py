<!--
  [P] marks tasks eligible for parallel execution.
-->

## Phase 1 — Config

- [x] 1.1 In `src/gaze_py/config/loader.py`, add three new fields to `GazeConfig`.
      Already implemented. Fields at lines 56–67. YAML parsing at line 242.
      Validation in `_validate()`. Docstring updated.
      Verified: `uv run mypy --strict src/` passes. ✓

## Phase 2 — Scanner module

- [x] 2.1 Create `src/gaze_py/analysis/docscan.py` with `DocEntry`, `_find_repo_root()`,
      `_matches_any()`, and `scan_docs()`.
      Already implemented. Note: Python's `fnmatch` treats `*` as matching any
      characters including `/`, so `vendor/**` correctly excludes nested paths —
      no `pathlib.Path.match()` substitution needed.
      `_find_repo_root()` returns `start` when no sentinel found (silent fallback
      per design; no warning emitted — acceptable for the no-git-repo edge case).
      `OSError` on individual file reads: `warnings.warn()` + skip (implemented).
      Verified: `uv run mypy --strict src/gaze_py/analysis/docscan.py` passes. ✓

## Phase 3 — Engine and runner wiring [P]

- [x] 3.1 [P] In `src/gaze_py/classify/engine.py`, `project_docs_text: str | None = None`
      added to `ClassificationEngine.__init__()`. Signal 5 augmentation implemented.
      Verified: `uv run mypy --strict src/` passes. ✓

- [x] 3.2 [P] In `src/gaze_py/analysis/runner.py`, `docs_text: str | None = None`
      added as keyword-only parameter to `detect_and_classify()`.
      Verified: `uv run mypy --strict src/` passes. ✓

## Phase 4 — CLI changes

- [x] 4.1 In `src/gaze_py/cli/main.py`, real `docscan` command implemented.
      `scan_docs` imported at module level (top-level import, not inline).
      JSON output: `path` relative to cwd, `content`, `priority`. ✓
      Text output: `[P{priority}] {relative_path}` + `  ({word_count} words)` line. ✓
      `--exclude`/`--include` REPLACE (not extend) config lists (documented in
      DS-007 and AC-6). Verified: `uv run mypy --strict src/` passes. ✓

- [x] 4.2 In `src/gaze_py/cli/main.py`, doc scanning wired into `_run_analyze()`
      and `_run_crap()`.
      Note: `scan_docs` is imported at **module level** (`cli/main.py:35`); the
      `except Exception` (not `except ImportError`) wraps the **call** to
      `scan_docs`, not the import. This is runtime graceful degradation, not
      a conditional import guard. BLE001 suppression is justified: scan failure
      must never abort analysis (Constitution Principle VI — graceful degradation).
      Verified: `uv run mypy --strict src/` passes. ✓

## Phase 5 — Tests and testdata [P]

- [x] 5.1 [P] Testdata fixtures under `tests/testdata/docscan/`:
      `README.md`, `CHANGELOG.md`, `sub/guide.md` — all created. ✓

- [x] 5.2 [P] `tests/test_docscan.py` created with 17 tests covering:
      DS-002 discovery, DS-003 priority, DS-004 config fields,
      timeout (test_timeout_returns_partial), OSError handling,
      exclude/include filters, CLI command (docscan exits 0 JSON/text). ✓

- [x] 5.3 [P] `tests/test_cli.py` updated — docscan CLI tests added. The
      `test_docscan_json_keys` test asserts `path`, `content`, `priority` keys
      with correct types (str, str, int). Path is a string — relative to cwd
      when the scanned directory is inside cwd, absolute as graceful fallback
      otherwise (this is the documented DS-007 behavior: "relative to cwd"). ✓

- [x] 5.4 [P] `test_analyze_classify_calls_scan_docs` added to `tests/test_cli.py`.
      Patches `scan_docs` at the CLI module level, runs `analyze --classify`,
      asserts `scan_docs` was called. Verified: passes. ✓

- [x] 5.5 [P] `test_detect_and_classify_passes_docs_text` added to `tests/test_docscan.py`.
      Patches `ClassificationEngine.__init__`, calls `detect_and_classify()` with
      `docs_text="test doc content"`, asserts it reached the engine. Verified: passes. ✓

- [x] 5.6 [P] `test_engine_combines_docstring_and_project_docs` added to `tests/test_docscan.py`.
      Patches `docstring_signal`, creates engine with `project_docs_text`, calls
      `classify()` with docstring kwarg, asserts combined string contains both. Verified: passes. ✓

- [x] 5.7 [P] `test_scan_handles_oserror` added to `tests/test_docscan.py`.
      Patches `Path.read_text` to raise `OSError` for one file, asserts 1 entry
      returned and warning emitted. Verified: passes. ✓

## Phase 6 — CI gate

- [x] 6.1 Run full CI gate:
      ```bash
      uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85
      ```
      Verified: ruff ✓ mypy --strict ✓ pytest 528 passed 91.82% coverage ✓
      (After additional fixes: DRY extraction via _SENTINELS import, error message aligned
      with DS-004 spec, timeout test made deterministic with monkeypatch, graceful
      degradation test added.)

<!-- spec-review: passed -->

<!-- code-review: passed -->
