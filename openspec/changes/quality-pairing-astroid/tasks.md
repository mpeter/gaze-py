<!--
  [P] marks tasks eligible for parallel execution.
  Add [P] when a task: (a) touches different files from
  other [P] tasks in the group, (b) has no dependency
  on prior tasks in the group, (c) can safely execute
  without ordering constraints.
  Do NOT add [P] when tasks modify the same file —
  parallel workers will cause merge conflicts.
  Tasks without [P] run sequentially first, then [P]
  tasks run in parallel.
-->

## 1. Dependency and version bump

- [ ] 1.1 Add `astroid>=3.0` to `[project] dependencies` in
      `pyproject.toml`. No upper bound (see D11). Run `uv sync`.
      Verify: `uv run python -c "import astroid; print(astroid.__version__)"`.

- [ ] 1.2 Bump version in `pyproject.toml` from `0.4.1` to `0.5.0`
      (MINOR bump per D12 — new dependency, new inference method value,
      new reason code, changed `assess()` return type, new CLI option).

## 2. AssessResult return type

- [ ] 2.1 Add `AssessResult` dataclass to `src/gaze_py/quality/pipeline.py`:
      ```python
      @dataclass(frozen=True)
      class AssessResult:
          reports: list[QualityReport]   # one per test function (paired)
          untested: list[QualityReport]  # one per unmatched production func with effects
      ```
      Export from `quality/__init__.py` (module docstring only — no star
      import; add explicit `AssessResult` to the module's public names
      per project convention).

- [ ] 2.2 Update `assess()` signature and return type in
      `src/gaze_py/quality/pipeline.py`:
      ```python
      def assess(...) -> AssessResult:
      ```
      All existing callers in `cli/main.py` updated to use
      `result.reports` where they previously used the returned list.

- [ ] 2.3 Update `QualityReport` docstring in `src/gaze_py/taxonomy/models.py`
      to document the `test_function=""` sentinel:
      ```
      test_function: Name of the test function. Empty string ("") when
          this report represents an unmatched production function with
          no paired test (part of AssessResult.untested).
      ```

## 3. Coverage — no_test_coverage reason

- [ ] 3.1 Update `compute_contract_coverage()` in
      `src/gaze_py/quality/coverage.py`:
      Add `*, no_test_coverage: bool = False` keyword parameter.
      When `no_test_coverage=True` and `target.effects` is non-empty,
      classify effects via `ClassificationEngine` to count
      `total_contractual`, then return:
      ```python
      ContractCoverageResult(
          percentage=None,              # null per Go contract (D5)
          covered_effects=0,
          total_contractual=<contractual count>,
          over_specification_count=0,
          unmapped_assertions=0,
          reason="no_test_coverage",
      )
      ```
      When `no_test_coverage=True` but `target.effects` is empty,
      fall through to normal computation (returns `"no_effects_detected"`).

- [ ] 3.2 Update `ContractCoverageResult.reason` docstring in
      `src/gaze_py/taxonomy/models.py` to add:
      ```
      "no_test_coverage" — effects were detected but no test targets
          this function; percentage is None (null per OC-003 and Go
          porting contract — "no test = no coverage data, not 0%").
      ```

- [ ] 3.3 [P] New tests in `tests/test_quality_coverage.py`
      (no modification to existing tests):
      - `test_no_test_coverage_emits_none_percentage` —
        `no_test_coverage=True`, target has `ReturnValue` effect →
        `percentage is None`, `reason="no_test_coverage"`.
      - `test_no_test_coverage_total_contractual_populated` — same
        setup → `total_contractual >= 1`, `covered_effects == 0`.
      - `test_no_test_coverage_oc003_null_not_zero` — verify
        `percentage is None` (not `0.0`) — the specific OC-003 contract
        that "no test = no coverage data" must not be conflated with 0%.
      - `test_no_test_coverage_empty_effects_falls_through` —
        `no_test_coverage=True`, target has no effects → reason is
        `"no_effects_detected"` (not `"no_test_coverage"`).

## 4. _untested_reports() helper and pipeline wiring

- [ ] 4.1 Add `_untested_reports(source_targets: list[FunctionTarget], seen_names: set[str], config: GazeConfig) -> list[QualityReport]`
      to `src/gaze_py/quality/pipeline.py`.
      - `seen_names` is the set of `target_function` values from all
        test-keyed reports produced in the main loop.
      - For each `FunctionTarget` in `source_targets` whose `name` is
        NOT in `seen_names`:
        - Call `compute_contract_coverage(target, [], config=config,
          no_test_coverage=True)`.
        - Emit `QualityReport(test_function="", target_function=target.name,
          assertions=(), contract_coverage=coverage,
          warnings=("No test targets this function.",),
          complexity=target.complexity)`.
      - Return the list; empty list if all production functions are paired.

- [ ] 4.2 Update `assess()` in `src/gaze_py/quality/pipeline.py`:
      - After the main per-test-function loop, collect `seen_names` (set
        of non-None `target_function` values from emitted reports).
      - Call `_untested_reports(source_targets, seen_names, config)`.
      - Return `AssessResult(reports=reports, untested=untested)`.

- [ ] 4.3 [P] New integration tests in `tests/test_quality_integration.py`
      (no modification to existing tests):
      - `test_assess_returns_assess_result` — `assess()` returns an
        `AssessResult` with `.reports` and `.untested` attributes.
      - `test_assess_untested_has_no_test_coverage_reason` — using the
        `undertested` fixture (function with effects, zero assertions),
        `untested` list is non-empty; all entries have
        `contract_coverage.reason == "no_test_coverage"` and
        `contract_coverage.percentage is None`.
      - `test_assess_untested_test_function_is_empty_string` — all
        entries in `untested` have `test_function == ""`.
      - `test_assess_paired_functions_not_in_untested` — no function
        name appears in both `.reports` (with non-None `target_function`)
        and `.untested`.
      - `test_assess_no_effects_function_not_in_untested` — pure
        functions (no side effects) do NOT appear in `untested` (they
        get `"no_effects_detected"` reason and are excluded).

## 5. Pairing — Strategy 3 (Astroid transitive call graph)

- [ ] 5.1 Add `_build_astroid_graph(test_files: list[Path], src_files: list[Path], *, stderr_sink: Any = None) -> dict[str, set[str]]`
      to `src/gaze_py/quality/pairing.py`.
      - Import `astroid`, `astroid.MANAGER`, `astroid.exceptions`, and
        `astroid.util` defensively inside the function body (D7). On
        `ImportError`, emit to stderr (via `click.echo(..., err=True)` if
        click available, otherwise `sys.stderr.write(...)`) and
        return `{}`.
      - Call `astroid.MANAGER.clear_cache()` before loading any files
        (D2 — prevents stale data across multiple `assess()` calls in
        the same process).
      - For each file in `test_files + src_files`:
        ```python
        try:
            module = astroid.MANAGER.ast_from_file(str(path))
        except astroid.exceptions.AstroidBuildingError as exc:
            click.echo(f"warning: astroid could not load {path}: {exc}", err=True)
            continue
        ```
      - For each `FunctionDef` node in the module (walk with
        `module.nodes_of_class(astroid.nodes.FunctionDef)`):
        - caller_qname = `fn.qname()`
        - Walk `fn.nodes_of_class(astroid.nodes.Call)` within the body.
        - For each `Call` node, iterate `call.func.infer()`:
          ```python
          try:
              for inferred in call.func.infer():
                  if inferred is astroid.util.Uninferable:
                      continue
                  callee_qname = inferred.qname()
                  graph[caller_qname].add(callee_qname)
          except astroid.exceptions.InferenceError:
              continue
          ```
      - Return the completed adjacency dict
        `dict[str, set[str]]` (use `collections.defaultdict(set)`
        during construction, return as plain dict).

- [ ] 5.2 Add `_pair_astroid(test_func: TestFunc, source_names: set[str], graph: dict[str, set[str]], *, depth_limit: int = 5) -> str | None`
      to `src/gaze_py/quality/pairing.py`.
      - Determine the test function FQN using the project root heuristic
        (D8): walk up from `test_func.filename` until a directory
        containing `pyproject.toml` or `setup.py` is found; derive the
        dotted module name from the relative path; append
        `.{test_func.name}`.
      - BFS from that FQN over `graph` up to `depth_limit` hops using a
        `collections.deque` and a `visited: set[str]` to prevent cycles.
      - At each callee FQN, extract the short name (last segment after
        the final `.`) and check membership in `source_names`.
      - Return the first matching short name encountered, or `None`.

- [ ] 5.3 Update `pair_to_targets()` signature in
      `src/gaze_py/quality/pairing.py`:
      ```python
      def pair_to_targets(
          test_func: TestFunc,
          source_functions: list[FunctionTarget],
          *,
          astroid_graph: dict[str, set[str]] | None = None,
      ) -> TestTargetPair:
      ```
      After Strategy 2 (ast.Name call walk), add Strategy 3:
      if `astroid_graph is not None`, call `_pair_astroid()`. On match,
      return `TestTargetPair(test_name=test_func.name,
      target_name=matched_name, inference_method="call_graph_transitive",
      confidence=0.75)`. Existing callers that omit `astroid_graph` are
      unaffected.

- [ ] 5.4 Update `assess()` in `src/gaze_py/quality/pipeline.py`:
      - Collect `test_files: list[Path]` from `_collect_test_functions`
        before the loop (extract file paths from `TestFunc.filename`).
      - Collect `src_files: list[Path]` via `collect_py_files(src_path)`.
      - Call `_build_astroid_graph(test_files, src_files)` once before
        the per-test-function loop.
      - Pass `astroid_graph=graph` to every `pair_to_targets()` call.

- [ ] 5.5 [P] New tests in `tests/test_quality_pairing.py` using
      dedicated testdata fixtures in `tests/testdata/quality/astroid/`
      (no modification to existing tests):

      Create fixture files:
      - `tests/testdata/quality/astroid/src/engine.py` — minimal class:
        ```python
        from .signals import caller_signal
        class Engine:
            def classify(self, x: int) -> int:
                return caller_signal(x)
        def _make_engine() -> Engine:
            return Engine()
        ```
      - `tests/testdata/quality/astroid/src/signals.py` —
        `def caller_signal(x: int) -> int: return x * 2`
      - `tests/testdata/quality/astroid/tests/test_engine.py` —
        ```python
        from engine import _make_engine
        def test_classify():
            e = _make_engine()
            assert e.classify(1) == 2
        ```

      Tests (use `_build_astroid_graph()` directly with fixture file paths;
      do NOT use live project source):
      - `test_pair_astroid_resolves_method_call` — graph built from
        fixtures; `pair_to_targets()` for `test_classify` resolves to
        `"classify"` via Strategy 3.
      - `test_pair_astroid_transitive_reaches_signal_func` — same graph;
        BFS from `test_classify` reaches `caller_signal` transitively;
        assert result is `"classify"` or `"caller_signal"` (BFS order
        dependent — both are valid matches).
      - `test_pair_astroid_depth_limit` — manually constructed graph dict
        with 6-hop chain `A→B→C→D→E→F→target`; `depth_limit=5` →
        `"target"` is NOT returned.
      - `test_pair_astroid_empty_graph_falls_through_to_unmatched` —
        `astroid_graph={}`, no name match, no ast.Name call match →
        `inference_method="unmatched"`, `confidence=0.0`.
      - `test_pair_astroid_confidence_and_method` — matched via Strategy
        3 → `inference_method="call_graph_transitive"`,
        `confidence=0.75`.
      - `test_build_astroid_graph_skips_bad_file` — pass a `Path` to a
        non-existent file alongside valid fixtures; result is a non-empty
        dict (valid files loaded); no exception raised.
      - `test_build_astroid_graph_clears_cache_between_calls` — call
        `_build_astroid_graph()` twice with same fixture files; second
        call returns same result (no stale data); no error.

## 6. _build_contract_coverage_map() in quality/pipeline.py

- [ ] 6.1 Add `build_contract_coverage_map(src_path: Path, tests_path: Path, config: GazeConfig) -> dict[str, ContractCoverageResult]`
      to `src/gaze_py/quality/pipeline.py` (public function, exported).
      - Calls `assess(src_path, tests_path, config=config)`.
      - Builds `{function_name: ContractCoverageResult}` from
        `result.reports` + `result.untested`:
        - For each report with non-None `contract_coverage`, update the
          dict with the highest-`percentage` result for that
          `target_function` name (or first if both are `None`).
      - Returns the map; returns `{}` if `assess()` raises.

- [ ] 6.2 Update `_run_crap()` in `src/gaze_py/cli/main.py`:
      - After acquiring `coverage_data`, attempt to auto-discover a tests
        path (search `tests/`, `test/`, `test_*.py` relative to
        `path.parent`, then relative to `Path.cwd()`).
      - If `tests_path` is explicitly provided via `--tests`, use that.
      - If a tests path is resolved, call
        `build_contract_coverage_map(path, resolved_tests, config)`.
      - For each target, look up `ContractCoverageResult` by `name` and
        pass to `_score_target(quality_result=ccr)`.
      - In `_score_target()`, add a guard: when
        `quality_result.reason == "no_test_coverage"`, set
        `gaze_crap_score = None` and `quad = None` (do not compute —
        matches Go `ok=false` behaviour). The `contract_coverage_pct`
        and `contract_coverage_reason` are still recorded.
      - If no tests path found, proceed as today (GazeCRAP null,
        OC-003 compliant).

- [ ] 6.3 Add `--tests` option to the `crap` command:
      ```python
      @click.option("--tests", "tests_path", default=None,
                    help="Test directory or file. Auto-discovered if omitted.")
      ```
      Thread through to `_run_crap()`.

- [ ] 6.4 [P] New tests in `tests/test_cli.py`
      (no modification to existing tests):
      - `test_crap_with_tests_populates_contract_coverage_reason` — run
        `crap` on `tests/testdata/quality/src/` with
        `--tests tests/testdata/quality/tests/`; assert at least one
        function has `contract_coverage_reason` non-null in JSON output.
      - `test_crap_no_test_coverage_reason_gaze_crap_still_null` — same
        invocation; assert any function with
        `contract_coverage_reason: "no_test_coverage"` has
        `gaze_crap: null` (not a float) — confirms D5/Go contract.
      - `test_crap_without_tests_gaze_crap_null` — run `crap` without
        `--tests` in a temp dir with no discoverable tests; all
        `gaze_crap` remain null.
      - `test_crap_help_shows_tests_option` — `gazepy crap --help`
        output contains `--tests`.

## 7. Baseline measurement + CHANGELOG + CI gate

- [ ] 7.1 Run `uv run gazepy quality src/gaze_py/ --tests tests/ --format=json`
      and create `openspec/changes/quality-pairing-astroid/results.md`
      recording:
      - Total paired (`target_function != null` in `.reports`)
        (target ≥ 28, stretch ≥ 31)
      - Count with `"no_test_coverage"` in `.untested`
      - Count with `"no_effects_detected"` in `.untested` (should be 0
        for functions with any detected effects)
      - Wall-clock time (target ≤ 3s; baseline ~1.5s)
      Also run `gazepy crap src/gaze_py/ --tests tests/
      --coverprofile=coverage.json --format=json` and record:
      - Count of non-null `contract_coverage_reason`
      - `gaze_crapload` value (expected unchanged — GazeCRAP still null
        for `"no_test_coverage"` functions)
      - `visit_Call` entry (expected: `gaze_crap: null`,
        `contract_coverage_reason: "no_test_coverage"`)
      - Double detect_and_classify overhead (wall time with vs without
        `--tests`)

- [ ] 7.2 Add CHANGELOG entry under `## [Unreleased]`:
      ```
      ### Added
      - Strategy 3 pairing via Astroid transitive call graph inference
      - `"no_test_coverage"` contract coverage reason code for functions
        with effects but no paired test
      - `--tests` option on `gazepy crap` command
      - `AssessResult` return type from `assess()` with `.reports` and
        `.untested` lists
      ```

- [ ] 7.3 [P] `uv run ruff check .`
- [ ] 7.4 [P] `uv run ruff format --check .`
- [ ] 7.5 [P] `uv run mypy --strict src/`
- [ ] 7.6 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
