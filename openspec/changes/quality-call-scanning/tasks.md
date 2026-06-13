# Tasks: quality-call-scanning

**Input**: `openspec/changes/quality-call-scanning/proposal.md`
**Branch**: `opsx/quality-call-scanning`
**Files**: `src/gaze_py/quality/__init__.py`, `src/gaze_py/cli/__init__.py`,
           `tests/test_quality.py`, `tests/test_cli.py`

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- Mark `[x]` immediately on completion

---

## Phase 1 — Tests first (write before implementing)

**Write tests FIRST — ensure they FAIL before implementing.**

- [x] T001 Write new tests in `tests/test_quality.py`:
  - `test_iter_test_functions_finds_class_methods` — given a source
    with `class TestFoo: def test_bar(self): ...`, verify
    `_iter_test_functions` returns `[("TestFoo.test_bar", body)]`
  - `test_iter_test_functions_finds_top_level` — given top-level
    `def test_foo(): ...`, verify `[("test_foo", body)]`
  - `test_extract_called_names_simple` — `foo()` in body → `{"foo"}`
  - `test_extract_called_names_attribute` — `module.foo()` → `{"foo"}`
  - `test_extract_called_names_nested_skipped` — calls inside nested
    `def helper(): bar()` are NOT collected (only top-level body)
  - `test_map_assertions_finds_class_method_tests` — given a test
    source with `class TestFoo: def test_bar(self): result = fn(); assert result == 1`,
    and `target_func="fn"`, verify coverage > 0%
  - `test_map_assertions_test_function_name_populated` — verify
    `QualityReport.test_function` contains the actual test method name,
    not `"<test_function>"`
  - `test_map_assertions_multi_test_merged` — given two test methods
    that both call `fn`, verify both assertion counts are combined

- [x] T002 [P] Update `tests/test_cli.py`:
  - `test_sc030_report_json_exit_0` — update assertion to expect
    `quality_reports` key (quality JSON) instead of `version`+`results`
    (analysis JSON)

**Checkpoint**: `uv run pytest tests/test_quality.py tests/test_cli.py
-m "not slow" -x --tb=short` — T001/T002 tests FAIL (expected).

---

## Phase 2 — Implement

- [x] T003 Implement in `src/gaze_py/quality/__init__.py`:
  - Add `_iter_test_functions(tree: ast.Module) -> list[tuple[str, list[ast.stmt]]]`
    — finds top-level `def test_*` and `class TestX: def test_*` methods
  - Add `_extract_called_names(body: list[ast.stmt]) -> set[str]`
    — scans `ast.Call` nodes, returns plain names (no module prefix),
    does NOT descend into nested `FunctionDef`
  - Update `map_assertions()`:
    - Call `_iter_test_functions(tree)` to get all test functions
    - Filter to those whose bodies contain `target_func` in
      `_extract_called_names(body)`
    - Merge filtered bodies; fall back to all bodies if none match
    - Set `test_function` to joined qualified names of matched tests
    - Set `assertion_detection_confidence = 90` if matches found,
      `0` if falling back to all bodies with no specific match
  - Remove `_find_test_function_body()` — replaced by above

- [x] T004 [P] Implement in `src/gaze_py/cli/__init__.py` — `report` command:
  - Phase 2: replace filename heuristic with inverted index:
    - Parse all test files once; collect called names per file
    - Build `{func_name: [test_source_text]}` index
    - For each source function with effects: look up index,
      concatenate matching sources, call `map_assertions()`
  - Phase 3: emit quality JSON (`write_quality_json`) instead of
    analysis JSON; build `PackageSummary` with `worst_coverage_tests`
  - Update imports: add `write_quality_json`, `write_quality_text`

**Checkpoint**: `uv run pytest -m "not slow" -x --tb=short` — all
100+ tests pass.

---

## Phase 3 — Verify and clean

- [x] T005 Run full quality gate:
  - `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src/`

- [x] T006 [P] Smoke test on fieldkit-cmd:
  - `gaze-py report /path/to/fieldkit-cmd/fieldkit/gmail_cache/
    /path/to/fieldkit-cmd/tests/ --format=json`
  - Verify: `quality_reports` count > 0,
    `average_contract_coverage` > 0%
  - Verify: class-based test names appear in `test_function` fields

- [x] T007 [P] Update `CHANGELOG.md` with entry for this change

## Completion Gate

- [x] All existing tests still pass (no regressions)
- [x] New tests in T001 pass
- [x] `test_sc030_report_json_exit_0` passes with updated assertion
- [x] `ruff`, `mypy` clean
- [x] Coverage ≥ 85%
- [x] fieldkit-cmd smoke test passes (quality_reports > 0)

<!-- code-review: passed -->
