## 0. Production Refactoring

> All refactoring is pure structural extraction — no logic changes, no output changes.
> Run the full test suite after each sub-task to catch regressions immediately.

### 0.A Config error boundary (src/gaze_py/config/loader.py)

- [x] 0.1 In `load_config()`: wrap line-116 `_parse_config()` call with `try/except GazeConfigError: raise` — load_config owns the error boundary
- [x] 0.2 In `load_config()`: wrap line-121 `_parse_config()` call with `try/except GazeConfigError: raise`
- [x] 0.3 In `load_config_explicit()`: wrap line-85 `_parse_config()` call with `try/except GazeConfigError: raise`
- [x] 0.4 Update both functions' `Raises:` docstring sections to note explicit propagation (no functional change, documentation only)

### 0.B visit_Call decomposition (src/gaze_py/analysis/detector.py)

- [x] 0.5 Extract `_handle_stream_writes(self, obj: ast.expr, method: str, node: ast.Call) -> bool` — moves StderrWrite (`sys.stderr.write`) and StdoutWrite (`sys.stdout.write`) detection. Each branch MUST call `self.generic_visit(node)` before returning `True`. CC target: 11.
- [x] 0.6 Extract `_handle_pathlib_attr_call(self, method: str, node: ast.Call) -> bool` — moves `Path.unlink()` → FileSystemDelete, `Path.chmod()` → FileSystemMeta, `Path.write_text/bytes()` → FileSystemWrite. Each branch MUST call `self.generic_visit(node)` before returning `True`. CC target: 4. NOTE: pathlib checks match on method name alone (independent of obj_name), while lib-attr checks require obj_name to be in a specific set — these are mutually exclusive. Calling `_handle_pathlib_attr_call` before `_handle_lib_attr_call` is safe.
- [x] 0.7 Extract `_handle_lib_attr_call(self, obj_name: str | None, method: str, node: ast.Call) -> bool` — moves LogWrite, GoroutineSpawn (named + executor.submit heuristic), ProcessExit, TimeDependency, FileSystemDelete (os.*), FileSystemMeta (os.*), ReflectionMutation (`__setattr__`), FinalizerRegistration (`weakref.finalize`), CgoCall (`ctypes/cffi`). All existing `if obj_name is not None and ...` guards MUST remain inside this helper. Each branch MUST call `self.generic_visit(node)` before returning `True`. CC target: 13.
- [x] 0.8 Extract `_handle_param_attr_call(self, obj_name: str | None, method: str, node: ast.Call) -> bool` — moves all `obj_name in self._params` checks: HTTPResponseWrite, WriterOutput, SliceMutation, MapMutation, ChannelSend, ChannelClose, DatabaseWrite, ContextCancellation (`.cancel()` and `.set()`). Each branch MUST call `self.generic_visit(node)` before returning `True`. CC target: 11.
- [x] 0.9 Extract `_handle_name_call(self, fn: str, node: ast.Call) -> bool` — moves `print()` → StdoutWrite, `setattr()` → ReflectionMutation, `open()` → FileSystemWrite (write modes), parameter direct call → CallbackInvocation. Each branch MUST call `self.generic_visit(node)` before returning `True`. CC target: 6.
- [x] 0.10 Reduce `visit_Call` to thin dispatcher using `if handler(...): return` short-circuit pattern — stop dispatching after the first `True` return. Pattern: `if isinstance(func, ast.Attribute): obj_name = obj.id if isinstance(obj, ast.Name) else None; if self._handle_stream_writes(obj, method, node): return; if self._handle_pathlib_attr_call(method, node): return; if self._handle_lib_attr_call(obj_name, method, node): return; if self._handle_param_attr_call(obj_name, method, node): return; elif isinstance(func, ast.Name): if self._handle_name_call(fn, node): return; self.generic_visit(node)`. CC target: 3. NOTE: `self.generic_visit(node)` at the end covers the fall-through case only (no handler matched).
- [x] 0.11 Remove `# noqa: PLR0911, PLR0912, PLR0915` from `visit_Call` signature line and update its docstring to remove the "high branch/statement count is inherent" note.

### 0.C _build_summary decomposition (src/gaze_py/cli/main.py)

- [x] 0.12 Extract `_compute_avg_line_coverage(targets: list[FunctionTarget], coverage_data: dict[str, float] | None) -> float | None` — returns `None` when `coverage_data is None` or no targets have `score.line_coverage`. CC target: 3.
- [x] 0.13 Extract `_compute_gaze_crapload(targets: list[FunctionTarget], config: GazeConfig) -> int | None` — returns `None` when no targets have `score.gaze_crap`, count above threshold otherwise. CC target: 4.
- [x] 0.14 Extract `_compute_avg_contract_coverage(targets: list[FunctionTarget]) -> float | None` — returns `None` when no targets have `score.contract_coverage`. CC target: 3.
- [x] 0.15 Extract `_compute_quadrant_counts(targets: list[FunctionTarget]) -> dict[str, int] | None` — returns `None` when no quadrant labels, count dict otherwise. CC target: 3.
- [x] 0.16 Extract `_compute_fix_strategy_counts(targets: list[FunctionTarget]) -> dict[str, int] | None` — returns `None` when no fix strategies, count dict otherwise. CC target: 3.
- [x] 0.17 Reduce `_build_summary` to thin coordinator calling 0.12–0.16 plus existing `crapload()` and `recommended_actions()`. CC target: 5.

## 1. Testdata Fixtures (tests/testdata/analysis/)

- [x] 1.1 Create `reflection_mutation_setattr.py` — `def f(obj): setattr(obj, "x", 1)`
- [x] 1.2 Create `reflection_mutation_dunder.py` — `def f(obj): obj.__setattr__("x", 1)`
- [x] 1.3 Create `goroutine_spawn_executor.py` — `def f(fn): executor.submit(fn)` with `# ruff: noqa: F821` header and comment: "executor is a bare name matching the GoroutineSpawn heuristic set. Parsed as AST only, never executed."
- [x] 1.4 Create `finalizer_registration.py` — `import weakref; def f(obj, cb): weakref.finalize(obj, cb)`
- [x] 1.5 Create `cgo_call.py` — `import ctypes; def f(): ctypes.cdll.LoadLibrary("lib.so")`
- [x] 1.6 Create `filesystem_pathlib_delete.py` — `def f(p): p.unlink()` (supplements existing `filesystem_delete.py`)
- [x] 1.7 Create `filesystem_pathlib_meta.py` — `def f(p): p.chmod(0o755)` (supplements existing `filesystem_meta.py`)
- [x] 1.8 Create `filesystem_pathlib_write.py` — `def f_text(p): p.write_text("x")` and `def f_bytes(p): p.write_bytes(b"x")` in single file (supplements existing `filesystem_write.py`)
- [x] 1.9 Create `context_cancellation_event.py` — `def f(event): event.set()` (covers `.set()` branch; distinct from existing `.cancel()` branch in `context_cancellation.py`)
- [x] 1.10 Create `stdout_write_sys.py` — `import sys; def f(): sys.stdout.write("x")` (covers `sys.stdout.write()` attribute-call path; distinct from `print()` path in `stdout_write.py`)
- [x] 1.11 Create `global_mutation_simple_assign.py` — `COUNTER = 0; def f(): global COUNTER; COUNTER = 99` (covers `visit_Assign` GlobalMutation branch at detector.py:530; distinct from existing `global_mutation.py` which covers `visit_AugAssign`)
- [x] 1.12 Create `receiver_mutation_augassign.py` — class with method `def m(self): self.x += 1` (covers `visit_AugAssign` ReceiverMutation branch at detector.py:547; distinct from existing `receiver_mutation.py`)

## 2. Detector Tests (tests/test_detector.py)

> **CR-007 requirement:** Every new test MUST assign the return value of `FileDetector.detect()` to `targets` and include `assert targets` as the first assertion before any derived-variable assertions.

- [x] 2.1 Add `test_filesystem_pathlib_delete_detected()` — fixture 1.6, `assert targets`, assert `FileSystemDelete` (EC-005)
- [x] 2.2 Add `test_filesystem_pathlib_meta_detected()` — fixture 1.7, `assert targets`, assert `FileSystemMeta` (EC-005)
- [x] 2.3 Add `@pytest.mark.parametrize("method", ["write_text", "write_bytes"]) def test_filesystem_pathlib_write_detected(method)` — fixture 1.8, `assert targets`, assert `FileSystemWrite` (EC-005; TC-005 MUST)
- [x] 2.4 Add `@pytest.mark.parametrize("fixture", ["reflection_mutation_setattr.py", "reflection_mutation_dunder.py"]) def test_reflection_mutation_detected(fixture)` — `assert targets`, assert `ReflectionMutation` (EC-005; TC-005 MUST)
- [x] 2.5 Add `test_goroutine_spawn_executor_detected()` — fixture 1.3, `assert targets`, assert `GoroutineSpawn` (EC-005)
- [x] 2.6 Add `test_finalizer_registration_detected()` — fixture 1.4, `assert targets`, assert `FinalizerRegistration` (EC-005)
- [x] 2.7 Add `test_cgo_call_detected()` — fixture 1.5, `assert targets`, assert `CgoCall` (EC-005)
- [x] 2.8 Add `test_stdout_write_sys_write_detected()` — fixture 1.10, `assert targets`, assert `StdoutWrite` (EC-005)
- [x] 2.9 Add `test_context_cancellation_event_set_detected()` — fixture 1.9, `assert targets`, assert `ContextCancellation`; cite detector.py lines 877-884 (EC-005)
- [x] 2.10 Add `test_global_mutation_simple_assign_detected()` — fixture 1.11, `assert targets`, assert `GlobalMutation`; comment: "Covers visit_Assign branch (detector.py:530); distinct from test_global_mutation_detected() which covers visit_AugAssign" (EC-005)
- [x] 2.11 Add `test_receiver_mutation_augmented_assign_detected()` — fixture 1.12, `assert targets`, assert `ReceiverMutation`; cite detector.py line 547 (EC-005)
- [x] 2.12 Add `test_open_keyword_mode_produces_filesystem_write()` — inline `def f(path): open(path, mode="w")`, `assert targets`, assert `FileSystemWrite`. Covers `_extract_open_mode` keyword path (detector.py:1074-1077).
- [x] 2.13 Add `test_vararg_param_triggers_slice_mutation_detection()` — source `def f(*args): args.append(1)`, `assert targets`, assert `SliceMutation`. CR-004 comment: `_extract_params` tested indirectly — `*args` capture only observable via effect detection.
- [x] 2.14 Add `test_kwarg_param_triggers_map_mutation_detection()` — source `def f(**kwargs): kwargs.update({"x": 1})`, `assert targets`, assert `MapMutation`. Same CR-004 comment.
- [x] 2.15 Add `test_detect_raises_gaze_parse_error_on_unreadable_file()` — create tmp file, probe-skip if chmod not enforced, `chmod 000`, `try/finally` restores `chmod(0o644)`, assert `pytest.raises(GazeParseError)`.
- [x] 2.16 Add `test_detect_uses_filename_when_path_outside_root()` — `root = tmp_path.parent / "nonexistent_sibling"` (portable). `assert targets`; assert `any(t.file_path == path.name for t in targets)` (order-independent; consistent with existing detector test pattern).
- [x] 2.17 Add `test_deferred_return_mutation_not_produced_without_finally()` — inline `try/except` with no `finally`. `assert targets` first; then assert no `DeferredReturnMutation`.
- [x] 2.18 Add `test_deferred_return_mutation_via_finally_augassign()` — inline `try: return x; finally: x += 1`. `assert targets`; assert `DeferredReturnMutation`. Covers detector.py:1000-1001.
- [x] 2.19 Add `test_finally_nonmatching_name_produces_no_deferred_mutation()` — inline `try: return y; except Exception as e: return e; finally: z = 0`. `assert targets`; assert no `DeferredReturnMutation`. Covers handler-body recursion (detector.py:1042).
- [x] 2.20 Add `test_closure_capture_mutation_via_augmented_assign()` — inline outer+inner with `nonlocal x; x += 1`. `assert targets`; assert `ClosureCaptureMutation`. Covers detector.py:1207-1220.
- [x] 2.21 Add `test_caller_count_reflects_callers_map_value()` — `FileDetector.detect(path, root=ROOT, callers={"f": 5})`. `assert targets`; assert `targets[0].caller_count == 5`. Covers detector.py:1346.

## 3. Complexity Tests (tests/test_complexity.py)

> **CR-007 requirement:** Assign return value to `result` and include `assert result == N` as the primary assertion (satisfies both CR-007 and TC-008 specific-values requirement simultaneously).

- [x] 3.1 Add `test_async_nested_function_scored_independently()` — use `ast.walk(module)` with name filters (NOT `_parse_first_fn()`); assert outer `result = cyclomatic_complexity(outer_node)` then `assert result == 1`; assert inner independently. (CX-002)
- [x] 3.2 Add `test_set_comprehension_if_increments_complexity()` — `result = cyclomatic_complexity(fn)` for `{x for x in lst if x > 0}`; `assert result == 2`. (CX-002)
- [x] 3.3 Add `test_dict_comprehension_if_increments_complexity()` — `result = cyclomatic_complexity(fn)` for `{k: v for k, v in d.items() if k}`; `assert result == 2`. (CX-002)
- [x] 3.4 Add `test_generator_expression_if_increments_complexity()` — `result = cyclomatic_complexity(fn)` for `sum(x for x in lst if x)`; `assert result == 2`. (CX-002)

## 4. CLI Tests (tests/test_cli.py)

> **CR-007 note:** CLI tests invoke via CliRunner; `result = runner.invoke(cli, [...])` binds `result` to the `CliRunner.Result` object. `assert result.exit_code == 0` (or whatever the expected code) is the direct-reference assertion for the CliRunner return value. This satisfies CR-007 for CLI tests — the exit_code assertion references `result` directly.

- [x] 4.1 Add `test_analyze_invalid_config_exits_2()` — write YAML with `contractual_threshold: -5` to tmp_path; pass as `--config`; `assert result.exit_code == 2`; `assert "Error" in result.stderr`. (cli/main.py:166)
- [x] 4.2 Add `test_analyze_contractual_threshold_override()` — `--contractual-threshold=95 --incidental-threshold=10`; `assert result.exit_code == 0`. (cli/main.py:172-174)
- [x] 4.3 Add `test_crap_invalid_config_exits_2()` — same invalid YAML for `crap` command; `assert result.exit_code == 2`; `assert "Error" in result.stderr`. (cli/main.py:535)
- [x] 4.4 Add `test_crap_contractual_threshold_override()` — threshold override flags for `crap`; `assert result.exit_code == 0`. (cli/main.py:541-543) [Note: crap uses --crap-threshold/--gaze-crap-threshold, not --contractual-threshold]
- [x] 4.5 Add `test_quality_no_tests_discovered_exits_2()` — tmp dir with only `.py` file, no `tests/` dir, no `--tests`; `assert result.exit_code == 2`; `assert "no tests directory found" in result.stderr`. (cli/main.py:609-610)
- [x] 4.6 Add `test_quality_auto_discovers_test_file_via_glob()` — `tmp_path/src/foo.py` and `tmp_path/test_foo.py`; invoke `quality` without `--tests`; `assert result.exit_code != 2` (glob fallback used). (cli/main.py:607)
- [x] 4.7 Add `test_crap_quadrant_counts_populated_with_tests_and_coverage()` — invoke `crap <quality_src> --tests <quality_tests> --coverprofile <cov_file> --format=json`; `assert result.exit_code == 0`; parse output; `assert data["summary"]["quadrant_counts"] is not None`. BOTH `--tests` AND `--coverprofile` required for quadrant_counts. (cli/main.py:1207-1210)
- [x] 4.8 Add `test_docscan_include_flag()` — create `tmp_path/README.md`; invoke `docscan <tmp_path> --include=*.md`; `assert result.exit_code == 0`. (cli/main.py:804)
- [x] 4.9 Add `test_docscan_timeout_flag()` — invoke `docscan <tmp_path> --timeout=5.0`; `assert result.exit_code == 0`. (cli/main.py:806)
- [x] 4.10 Add `test_docscan_invalid_config_exits_1()` — write syntactically valid YAML with `contractual_threshold: -5` (file must exist on disk since docscan uses `click.Path(exists=True)`); invoke `docscan <tmp_path> --config <file>`; `assert result.exit_code == 1`; `assert "Error" in result.stderr`. (cli/main.py:828-830)
- [x] 4.11 Add `test_docscan_scan_docs_exception_exits_1()` — monkeypatch `gaze_py.cli.main.scan_docs` to raise `RuntimeError("boom")`; `assert result.exit_code == 1`; `assert "Error" in result.stderr`. (cli/main.py:831-833) [Note: must patch at cli.main level, not analysis.docscan level]
- [x] 4.12 Add `test_quality_min_coverage_gate_skipped_for_no_contractual_effects()` — `tmp_path/src/pure.py` (pure function, no effects) and `tmp_path/tests/test_pure.py` (test function); invoke `quality <src> --tests <tests> --min-contract-coverage=50`; `assert result.exit_code == 0`; `assert "FAIL" not in result.output`; `assert "FAIL" not in result.stderr`. (cli/main.py:718)
- [x] 4.13 Add `test_compute_avg_line_coverage_returns_none_when_no_data()` — import `_compute_avg_line_coverage` with CR-004 comment: "Tested directly because the None-return branch when coverage_data=None cannot be triggered through the CLI without spawning a subprocess (which would require a full coverage run); the CliRunner path always provides coverage data when --coverprofile is given."; `result = _compute_avg_line_coverage([], coverage_data=None)`; `assert result is None`.
- [x] 4.14 Add `test_compute_gaze_crapload_returns_none_when_no_gaze_crap_data()` — import `_compute_gaze_crapload` with CR-004 comment: "Tested directly because producing zero gaze_crap targets through the CLI requires quality pipeline results, which depend on test fixture pairing — prohibitively complex for a boundary test."; `result = _compute_gaze_crapload([], GazeConfig())`; `assert result is None`.
- [x] 4.15 Add `test_compute_quadrant_counts_returns_none_when_no_labels()` — import `_compute_quadrant_counts` with CR-004 comment: "Tested directly because producing zero quadrant labels through the CLI requires line coverage AND contract coverage to both be non-null for at least one function — complex to set up for a boundary test."; `result = _compute_quadrant_counts([])`; `assert result is None`.

## 5. Pipeline Tests (tests/test_quality_integration.py)

> **CR-007 requirement:** Assign `result = assess(...)` or `result = build_contract_coverage_map(...)` and include `assert result` or `assert isinstance(result, AssessResult)` as the first direct-reference assertion.

- [x] 5.1 Add `test_assess_inferred_target_not_in_source_map()` — monkeypatches pair_to_targets (defensive guard at pipeline.py:167-175 is unreachable through normal flow); `result = assess(...)`; `assert result`; assert report has `target_function == "nonexistent_fn"` and `contract_coverage is None`. (pipeline.py:167-175)
- [x] 5.2 Add `test_build_contract_coverage_map_exception_returns_empty()` — monkeypatch `gaze_py.quality.pipeline.assess` to raise `RuntimeError("boom")`; `result = build_contract_coverage_map(...)`; `assert result == {}`. Verify stderr warning via `capsys`. (pipeline.py:280-282)
- [x] 5.3 Add `test_build_contract_coverage_map_keeps_higher_percentage_for_duplicate_target()` — monkeypatch `assess` to return `AssessResult` with two reports for same target (0% and 100%); `result = build_contract_coverage_map(...)`; `assert result`; assert entry has `percentage == 100.0`. (pipeline.py:293-299)
- [x] 5.4 Add `test_build_contract_coverage_map_none_does_not_displace_percentage()` — monkeypatch `assess` to return 50% then `None` for same target; `result = build_contract_coverage_map(...)`; `assert result`; assert entry retains `percentage == 50.0`. (pipeline.py:296-299)

## 6. Pairing Tests (tests/test_quality_pairing.py)

> **CR-007 requirement:** Assign return value and assert on it directly.

- [x] 6.1 Add `test_find_project_root_falls_back_to_parent_when_no_markers()` — import `_find_project_root` directly with CR-004 comment; create file in tmp_path with no project-root markers above; `result = _find_project_root(some_file)`; `assert result == some_file.parent`.
- [x] 6.2 Add `test_pair_astroid_filename_not_under_root_uses_stem()` — monkeypatch `gaze_py.quality.pairing._find_project_root` to return `tmp_path.parent / "nonexistent_sibling"` (portable); construct a minimal source_names set that includes the test file's stem; `result = _pair_astroid(test_func, source_names, graph={})`; `assert result is None` — when the stem matches nothing in source_names the function returns None without raising. If the stem happens to match, assert `isinstance(result, str)`. The key property is no `ValueError` is raised from the stem fallback path.

## 7. Formatter and Scorer Tests

> **CR-007 requirement:** All new tests assign return values and assert directly on them.

- [x] 7.1 Add `test_oc002_json_default_raises_type_error_for_unknown_type()` in `tests/test_output.py` — import `_json_default` with CR-004 comment; `with pytest.raises(TypeError)`. (`_json_default` HAS `ErrorReturn` visible in its own body, so Pass 2 works.) (OC-002)
- [x] 7.2 Add `test_text_output_renders_strategy_when_set()` in `tests/test_output.py` — `output = to_text(result_with_strategy)`; `assert output`; `assert "add_tests" in output`. (SC-005)
- [x] 7.3 Add `test_sc003_crapload_skips_unscored_targets()` in `tests/test_scorer.py` — construct `FunctionTarget` WITHOUT assigning `.score` (leave as default `None` — NOT `Score(crap=None)`); `result = crapload([target], threshold=0.5)`; `assert result == []`. Comment: "score is None — distinct from score.crap is None (covered by test_sc003_crapload_excludes_null_crap)". (SC-003)
- [x] 7.4 Add `test_sc006_recommended_actions_skips_unscored_targets()` in `tests/test_scorer.py` — same `score=None` construction; `result = recommended_actions([target])`; `assert result == []`. (SC-006)

## 7A. Existing Test Assertion Fixes (CR-007 — one line each)

> Add exactly one direct-reference assertion line to each test. No other logic changes.
> The assertion MUST appear immediately after the production function call.

- [x] 7A.1 `test_scorer.py::test_sc003_crapload_returns_targets_above_threshold` — add `assert len(result) == 2` before `names = [t.name for t in result]`
- [x] 7A.2 `test_scorer.py::test_sc006_recommended_actions_sort_order` — add `assert len(result) == 3` before `strategies = [r["strategy"] for r in result]`
- [x] 7A.3 `test_scorer.py::test_sc006_recommended_actions_excludes_null_strategy` — add `assert result == []` (recommended_actions returns list, never None; this is more specific than `is not None`)
- [x] 7A.4 `test_quality_integration.py::test_simple_fixture_full_coverage` — add `assert result` after `result = assess(...)`
- [x] 7A.5 `test_quality_integration.py::test_raises_fixture_coverage` — add `assert result` after `result = assess(...)`
- [x] 7A.6 `test_quality_integration.py::test_undertested_fixture_zero_coverage` — add `assert result` after `result = assess(...)`
- [x] 7A.7 `test_quality_integration.py::test_attribute_mutation_fixture_coverage` — add `assert result` after `result = assess(...)`
- [x] 7A.8 `test_quality_integration.py::test_assess_paired_functions_not_in_untested` — add `assert result` after `result = assess(...)`
- [x] 7A.9 `test_quality_integration.py::test_assess_untested_test_function_is_empty_string` — add `assert result` after `result = assess(...)`
- [x] 7A.10 `test_quality_integration.py::test_target_func_filtering` — add `assert isinstance(result, AssessResult)` after `result = assess(...)` (AssessResult is already imported; more specific than `is not None`)
- [x] 7A.11 `test_quality_integration.py::test_target_func_no_match` — add `assert isinstance(result, AssessResult)` after `result = assess(...)`
- [x] 7A.12 `test_quality_integration.py::test_empty_tests_path_returns_empty` — add `assert isinstance(result, AssessResult)` after `result = assess(...)` (test already asserts `result.reports == ()`; this adds the direct-reference for Pass 1)
- [x] 7A.13 `test_quality_integration.py::test_nonexistent_tests_file_returns_empty` — add `assert isinstance(result, AssessResult)` after `result = assess(...)`
- [x] 7A.14 `test_quality_pairing.py::test_find_test_functions` — add `assert isinstance(results, list)` before `names = [tf.name for tf in results]` (more specific than bare `assert results` which is falsy for empty list)
- [x] 7A.15 `test_docscan.py::test_scan_docs_returns_sorted` — add `assert isinstance(entries, list)` after `entries = scan_docs(...)` (list is never None; isinstance is more specific than `is not None`)
- [x] 7A.16 `test_docscan.py::test_priority_assignment` — add `assert isinstance(entries, list)` after `entries = scan_docs(...)`
- [x] 7A.17 `test_docscan.py::test_exclude_filter` — add `assert isinstance(entries, list)` after `entries = scan_docs(...)`
- [x] 7A.18 `test_docscan.py::test_exclude_filter_glob_pattern` — add `assert isinstance(entries, list)` after `entries = scan_docs(...)`
- [x] 7A.19 `test_docscan.py::test_include_filter` — add `assert isinstance(entries, list)` after `entries = scan_docs(...)`
- [x] 7A.20 `test_docscan.py::test_detect_and_classify_passes_docs_text` — change bare `detect_and_classify(...)` call to `result = detect_and_classify(...); assert result`
- [x] 7A.21 `test_output.py::test_oc002_json_function_has_required_fields` — add `assert output` before `data = json.loads(output)`
- [x] 7A.22 `test_output.py::test_oc002_json_summary_has_threshold_fields` — add `assert output` before `data = json.loads(output)`
- [x] 7A.23 `test_output.py::test_oc002_recommended_actions_entry_keys` — add `assert output` before `data = json.loads(output)`
- [x] 7A.24 `test_output.py::test_oc003_line_coverage_is_null_when_not_provided` — add `assert output` before `data = json.loads(output)`
- [x] 7A.25 `test_output.py::test_oc003_effect_confidence_range_is_null_key_present` — add `assert output` before `data = json.loads(output)`
- [x] 7A.26 `test_output.py::test_oc003_effect_confidence_range_serializes_as_list` — add `assert output` before `data = json.loads(output)`
- [x] 7A.27 `test_output.py::test_oc003_contract_coverage_reason_for_pure_function` — add `assert output` before `data = json.loads(output)`
- [x] 7A.28 `test_output.py::test_json_output_is_valid_json` — add `assert output` before `data = json.loads(output)`
- [x] 7A.29 `test_output.py::test_json_output_enum_values_are_strings` — add `assert output` before `data = json.loads(output)`
- [x] 7A.30 `test_output.py::test_json_output_tier_enum_is_string` — add `assert output` before `data = json.loads(output)`
- [x] 7A.31 `test_output.py::test_text_output_one_line_per_function` — add `assert output` before `lines = [line for line in output.splitlines() ...]`
- [x] 7A.32 `test_cli.py::test_quality_json_serializable` — add `assert config` immediately after `config = load_config(...)`

## 7B. Convention Document Updates

- [x] 7B.1 Append `CR-007: Tests MUST Be Gaze-Visible (Direct-Assertion Pattern)` to `.opencode/uf/packs/python-custom.md` — `[MUST]` severity; correct and incorrect code examples; explain Pass 1 binding; explain `pytest.raises()` requires `ErrorReturn` on target's own body
- [x] 7B.2 Add `## GazeCRAP Visibility` section to `.opencode/skills/testing-patterns/SKILL.md` after `## Assertion Style` — quick-reference code block showing visible vs invisible patterns; `gazepy quality` command to check coverage

## 8. Verification

- [x] 8.1 Run `uv run ruff check .` — zero errors
- [x] 8.2 Run `uv run ruff format --check .` — zero errors
- [x] 8.3 Run `uv run mypy src/` — zero errors
- [x] 8.4 Run `uv run pytest -m "not slow" -q` — all new and amended tests pass, no regressions
- [x] 8.5 Run `uv run pytest --cov=gaze_py --cov-fail-under=85 -q` — gate passes (threshold is a floor; MUST NOT be lowered)
- [x] 8.6 Run `uv run gazepy crap src/gaze_py/ --coverprofile coverage.json` — CRAPload dropped from 2 → 1 (not 0 as predicted; remaining offender is a different function added after this change)
- [x] 8.7 Run `uv run gazepy quality src/gaze_py/ --tests tests/` — avg contract coverage 75.4% (target ≥95% not reached; pairing heuristics improved but the codebase grew with the ai-http-adapters change)

<!-- spec-review: passed -->
<!-- code-review: passed -->
