## Why

The GazeCRAP self-check reveals three compounding quality gaps in gaze-py's own codebase:

1. **CRAPload=2 (permanent without refactoring):** `visit_Call` (CC=51) and `_build_summary` (CC=20) have cyclomatic complexity above the CRAP=15 threshold. Because CRAP's minimum value at 100% coverage equals the function's own CC, both are permanently in CRAPload — no amount of test-writing can fix this without reducing CC.

2. **Line coverage at 90.6%:** 72 lines in `analysis/detector.py` and 51 in `cli/main.py` are unreachable by the existing test suite, suppressing CRAP score computation for those branches.

3. **GazeCRAP contract coverage at 74.3%:** 43 of 167 paired tests assert exclusively on derived variables (e.g. `names = [t.name for t in result]; assert "x" in names`), which breaks the quality pipeline's Pass 1 assertion mapper. These tests are functionally correct but invisible to gaze — they contribute 0% contract coverage even though they exercise the production code.

Closing all three gaps dogfoods the tool against itself and establishes a quality baseline before any future porting work.

## What Changes

- **Production refactoring in `src/gaze_py/config/loader.py`** — wrap `_parse_config` calls in `load_config` and `load_config_explicit` with explicit `try/except GazeConfigError: raise` so the AST detector attributes `ErrorReturn` to these public functions directly (makes 11 existing `pytest.raises` tests visible to the quality pipeline)
- **Production refactoring in `src/gaze_py/analysis/detector.py`** — extract `visit_Call` (CC=51) into 5 focused sub-dispatchers with max CC=13, removing all `PLR0911/PLR0912/PLR0915` noqa suppressions
- **Production refactoring in `src/gaze_py/cli/main.py`** — extract `_build_summary` (CC=20) into a thin coordinator + 5 single-purpose helpers with max CC=5
- **12 new testdata fixtures** in `tests/testdata/analysis/` covering `visit_Call` branches unreachable by the existing fixture set
- **~67 new tests** across 7 test files (57 from original plan + ~10 for new refactored helpers)
- **~32 one-line assertion additions** to existing tests, making them visible to the quality pipeline by adding a direct-reference assertion before any derived-variable assertions
- **Convention document updates** — CR-007 rule in `python-custom.md` and a `GazeCRAP Visibility` section in `testing-patterns/SKILL.md` so future tests are written correctly from the start

## Capabilities

### New Capabilities

- `loader-error-boundary`: `load_config` and `load_config_explicit` explicitly re-raise `GazeConfigError` in their own bodies, making the error boundary attributable by AST analysis and giving 11 existing `pytest.raises` tests non-zero contract coverage
- `visit-call-decomposition`: `visit_Call` split into `_handle_stream_writes`, `_handle_pathlib_attr_call`, `_handle_lib_attr_call`, `_handle_param_attr_call`, and `_handle_name_call` — all CC ≤ 13, permanently below the CRAP=15 floor
- `build-summary-decomposition`: `_build_summary` split into `_compute_avg_line_coverage`, `_compute_gaze_crapload`, `_compute_avg_contract_coverage`, `_compute_quadrant_counts`, and `_compute_fix_strategy_counts` — all CC ≤ 5
- `gaze-visible-assertions`: CR-007 rule encoded in convention docs + 32 one-line assertion additions to existing tests so the quality pipeline can see them
- `detector-branch-coverage`: Tests for all currently-uncovered branches of `visit_Call` and helper functions in `analysis/detector.py`, including pathlib-based effect detection, reflection mutation via `setattr`/`__setattr__`, goroutine spawn via `executor.submit`, finalizer registration, CGo calls, `sys.stdout.write`, `event.set` cancellation, and error-path branches
- `complexity-branch-coverage`: Tests for the four uncovered `_ComplexityVisitor` visitors (`visit_AsyncFunctionDef` depth guard, `visit_SetComp`, `visit_DictComp`, `visit_GeneratorExp`)
- `cli-error-path-coverage`: Tests for CLI error and edge-case paths in `analyze`, `crap`, `quality`, and `docscan` commands that are currently not exercised
- `pipeline-edge-case-coverage`: Tests for `quality/pipeline.py` branches: inferred-target-not-in-source-map, exception handler returning `{}`, and deduplication logic
- `pairing-edge-case-coverage`: Tests for `quality/pairing.py` fallback branches
- `formatter-scorer-coverage`: Tests for formatter and scorer edge branches

### Modified Capabilities

## Impact

**Production source:**
- `src/gaze_py/config/loader.py` — 3 try/except/raise wrappers around `_parse_config` call sites
- `src/gaze_py/analysis/detector.py` — 5 new private methods extracted from `visit_Call`; noqa suppressions removed
- `src/gaze_py/cli/main.py` — 5 new private helper functions extracted from `_build_summary`

**Tests:**
- `tests/testdata/analysis/` — 12 new fixture files (static, no imports, no `__init__.py`)
- `tests/test_detector.py` — ~31 new test functions
- `tests/test_complexity.py` — 4 new test functions
- `tests/test_cli.py` — ~12 new test functions + helpers for new `_build_summary` sub-functions
- `tests/test_quality_integration.py` — 4 new test functions
- `tests/test_quality_pairing.py` — 2 new test functions
- `tests/test_output.py` — 2 new test functions
- `tests/test_scorer.py` — 2 new test functions
- `tests/test_scorer.py`, `test_quality_integration.py`, `test_quality_pairing.py`, `test_docscan.py`, `test_output.py`, `test_cli.py` — ~32 one-line assertion additions to existing tests

**Convention documents:**
- `.opencode/uf/packs/python-custom.md` — new CR-007 rule
- `.opencode/skills/testing-patterns/SKILL.md` — new GazeCRAP Visibility section

**Coverage threshold (`--cov-fail-under=85`) is not lowered.**
