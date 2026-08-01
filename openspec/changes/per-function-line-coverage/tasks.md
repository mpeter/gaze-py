<!--
  All tasks are sequential by nature; no [P] markers are used.
  Sections 2 and 3 touch different files but 3 depends on 2's field.
-->

## 1. Verification Baseline

- [x] 1.1 Confirm the bug: pre-fix, every function in a file shares one `line_coverage` value
- [x] 1.2 Record gaze-py's own pre-fix figures, measured in a clean worktree at `main` against identical coverage input: **crapload 5**, `avg_line_coverage` **0.9557**

## 2. Model and Detector

- [x] 2.1 `taxonomy/models.py`: add `owned_lines: frozenset[int] | None = None` to `FunctionTarget` with a docstring entry. Defaulted rather than required — `FunctionTarget(` is constructed at 26 sites in `tests/`, and dataclass ordering forbids a required field after the defaults block. (The handoff's premise that it appears 0 times in tests was incorrect; verified by grep.)
- [x] 2.2 `analysis/detector.py`: add `_owned_lines(scope, start, end)` implementing rule B, and `_fn_owned_lines(fn_node)` implementing rule A
- [x] 2.3 `analysis/detector.py`: populate `owned_lines` at the `<module>` sentinel site (whole file minus all function bodies) and the per-function site
- [x] 2.4 Confirm no leak into JSON: `json_formatter.py` builds `FunctionTarget` output manually and emits only `line`; `asdict()` is used on `Summary`/`SideEffect` only

## 3. Coverage Resolution (`cli/main.py` — sequential)

- [x] 3.1 Add `_FileCoverage` carrying `percent_covered`, `executed_lines`, `missing_lines`
- [x] 3.2 Rewrite `_load_coverage_json` to populate it; `GazeConfigError` messages and `files`-key validation unchanged
- [x] 3.3 Rewrite `_resolve_line_coverage` to take the `FunctionTarget` and return its own fraction. Three-key lookup preserved verbatim — only the value type and fraction derivation changed
- [x] 3.4 Zero-statement case returns 1.0
- [x] 3.5 Degraded case (either line array absent, or `owned_lines is None`) returns file-level `percent_covered`
- [x] 3.6 Update the call site to pass `target`; make the parameter required so a forgotten argument cannot silently reproduce the bug
- [x] 3.7 Update the `coverage_data` annotation at all seven remaining sites; `_compute_avg_line_coverage` needed no logic change

## 4. Fixtures and Tests

- [x] 4.1 Add `tests/testdata/analysis/coverage_ownership.py` — a fixture pinning each rule (never-called, nested def, uncalled nested, docstring-only, partial)
- [x] 4.2 Generate and commit `tests/testdata/coverage_ownership.json` — a **real coverage.py 7.14.1 reference** for that fixture, including the per-function map
- [x] 4.3 Add `tests/test_coverage_ownership.py` (16 tests) asserting ownership reproduces coverage.py's statement **sets**, and that resolving from file-level arrays reproduces coverage.py's per-function percentages
- [x] 4.4 Rule A guard: never-called function resolves to exactly 0.0
- [x] 4.5 Rule B guard: parent owns the nested `def` line, ownership is disjoint
- [x] 4.6 Zero-statement guard: docstring-only body resolves to 1.0
- [x] 4.7 Degraded-input guards: absent line arrays and unknown extent both fall back to file-level
- [x] 4.8 Adapt the five existing `_resolve_line_coverage` branch tests — signature only; lookup order untouched. They now use explicitly degraded entries so they test path resolution in isolation
- [x] 4.9 Existing summary-only fixtures across `test_cli.py`, `test_quality_coverage.py`, `test_crap_compare.py` keep working unchanged via the documented fallback — no regeneration needed

### Mutation verification (that the guards are load-bearing)

- [x] 4.10 Break rule A (own the `def` line) → **6 tests fail**, including all four resolution guards
- [x] 4.11 Break rule B (steal the nested `def` line from the parent) → **2 tests fail**, including the coverage.py set comparison
- [x] 4.12 Restore and confirm 16/16 pass

## 5. Gates

- [x] 5.1 `uv run ruff check .` — all checks passed; `ruff format --check .` — 62 files already formatted
- [x] 5.2 `uv run mypy src/` — success, 42 source files
- [x] 5.3 `uv run pytest --cov=gaze_py --cov-fail-under=85` — **1063 passed, 95.46%** (up from 95.31%). Threshold untouched
- [x] 5.4 Self-gate: this repo enforces **no** crapload gate (only `--cov-fail-under=85`), so nothing protected is breached
- [ ] 5.5 `/review-council` — all Divisor reviewers must APPROVE

## 6. Docs

- [x] 6.1 `docs/reference/cli/crap.md` — new "How coverage is attributed" section covering both rules, the zero-statement case, the fallback, and an upgrade note
- [x] 6.2 `docs/reference/cli/report.md` — `avg_line_coverage` is a per-function unweighted mean, not a line-weighted project total
- [x] 6.3 `docs/getting-started/quickstart.md` — `cov` column is the function's own coverage
- [x] 6.4 `docs/concepts/scoring.md` — `line_coverage` is per function (found during a docs sweep; not in the original plan)

## 7. Release 0.8.3

- [x] 7.1 CHANGELOG entry describing the correction and warning that saved baselines MUST be regenerated
- [ ] 7.2 Bump `pyproject.toml`, `src/gaze_py/__init__.py`, refresh `uv.lock` — separate commit, mirroring 0.8.2's release commit (31b0fd7)
- [ ] 7.3 PR, green CI, merge, tag

## 8. Findings for follow-up (not fixed here)

- [ ] 8.1 **gaze-py's own crapload moves 5 → 9.** The handoff predicted it would stay at 5; that was wrong. Four genuinely under-tested functions were concealed behind well-covered file-mates: `_enforce_min_contract_coverage_from_result` (16.67%), `_acquire_coverage` (16.67%), `_check_nonlocal_assignment` (0%), `comparison_to_text` (71.79%). Writing those tests is separate work — bundling it would confound the measurement correction with the debt it exposes.
- [ ] 8.2 `crapload` counts `crap >= 15.0` (`scorer.py:66`) but the baseline comparator's `new_violations` uses `crap > 15.0` (`compare.py:415`). A function at exactly 15.0 counts toward crapload yet is not a new violation. Pre-existing; per-function attribution makes it observable more often.
