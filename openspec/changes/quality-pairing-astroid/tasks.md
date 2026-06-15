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

## 1. Dependency

- [ ] 1.1 Add `astroid>=3.0,<4` to `[project] dependencies` in
      `pyproject.toml`. Run `uv sync` to update lockfile.
      Verify: `uv run python -c "import astroid; print(astroid.__version__)"`.

## 2. Pairing — Strategy 3 (Astroid transitive call graph)

- [ ] 2.1 Add `_build_astroid_graph(test_files: list[Path], src_files: list[Path]) -> dict[str, set[str]]`
      to `src/gaze_py/quality/pairing.py`.
      - Import `astroid` and `astroid.MANAGER` defensively inside
        the function body (D7). On `ImportError`, emit
        `warnings.warn("astroid not available — Strategy 3 disabled", stacklevel=2)`
        and return `{}`.
      - Load all files via `astroid.MANAGER.ast_from_file(str(path))`.
      - For each `FunctionDef` node (walk with `nodes_of_class`), walk
        all `Call` nodes within the body.
      - For each `Call`, resolve callee via `call.func.infer()` (returns
        a generator). For each inferred value:
        - `BoundMethod`: use `inferred._proxied.qname()`
        - `FunctionDef`: use `inferred.qname()`
        - `Uninferable` sentinel (`astroid.util.Uninferable`): skip
      - Build and return adjacency dict
        `{caller_qname: set(callee_qname)}`.

- [ ] 2.2 Add `_pair_astroid(test_func: TestFunc, source_names: set[str], graph: dict[str, set[str]], *, depth_limit: int = 5) -> str | None`
      to `src/gaze_py/quality/pairing.py`.
      - Determine the test function's FQN: derive module name from
        `test_func.filename` relative to the project root, append
        `.test_func.name`.
      - BFS from that FQN over `graph` up to `depth_limit` hops.
      - At each callee FQN, extract the short name (last segment after
        final `.`) and check if it is in `source_names`.
      - Return the first matching short name, or `None` if none found
        within the depth limit.

- [ ] 2.3 Update `pair_to_targets()` signature in
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
      return `TestTargetPair(..., inference_method="call_graph_transitive",
      confidence=0.75)`. Existing callers that pass no `astroid_graph`
      are unaffected (default `None` preserves backward compatibility).

- [ ] 2.4 Update `assess()` in `src/gaze_py/quality/pipeline.py`:
      - Collect `test_files: list[Path]` (from `_collect_test_functions`
        before iterating) and `src_files: list[Path]` (from
        `collect_py_files(src_path)`).
      - Call `_build_astroid_graph(test_files, src_files)` once before
        the per-test-function loop.
      - Pass `astroid_graph=graph` to every `pair_to_targets()` call.

- [ ] 2.5 [P] New tests in `tests/test_quality_pairing.py`
      (no modification to existing tests):
      - `test_pair_astroid_resolves_method_call` — test function body
        contains `engine = _engine(); result = engine.classify(...)`;
        `_engine()` is annotated `-> ClassificationEngine`; with a real
        Astroid graph built from the test file and engine source file,
        `pair_to_targets()` resolves to `"classify"`.
      - `test_pair_astroid_transitive_reaches_signal_func` — test calls
        `engine.classify()` which internally calls `caller_signal()`;
        Astroid graph includes the transitive edge; pairing resolves to
        `"caller_signal"` (or `"classify"` depending on BFS order —
        assert the result is in `{"classify", "caller_signal"}`).
      - `test_pair_astroid_depth_limit` — graph with chain of 6 hops;
        function at hop 6 is NOT returned when `depth_limit=5`.
      - `test_pair_astroid_empty_graph_falls_through_to_unmatched` —
        `astroid_graph={}`, no name match, no ast.Name call match →
        `inference_method="unmatched"`, `confidence=0.0`.
      - `test_pair_astroid_confidence_and_method` — matched via Strategy
        3 → `inference_method="call_graph_transitive"`,
        `confidence=0.75`.

## 3. Coverage — no_test_coverage reason

- [ ] 3.1 Update `compute_contract_coverage()` in
      `src/gaze_py/quality/coverage.py`:
      Add `*, no_test_coverage: bool = False` keyword parameter.
      When `no_test_coverage=True` and `target.effects` is non-empty,
      compute and return:
      ```python
      ContractCoverageResult(
          percentage=0.0,
          covered_effects=0,
          total_contractual=<count of contractual effects via engine>,
          over_specification_count=0,
          unmapped_assertions=0,
          reason="no_test_coverage",
      )
      ```
      When `no_test_coverage=True` but `target.effects` is empty,
      fall through to normal computation (returns `"no_effects_detected"`).

- [ ] 3.2 Update `ContractCoverageResult.reason` docstring in
      `src/gaze_py/taxonomy/models.py` to add:
      `"no_test_coverage"` — effects were detected but no test targets
      this function; percentage is 0.0 (not None).

- [ ] 3.3 Update `assess()` in `src/gaze_py/quality/pipeline.py`:
      After processing all test functions, identify every production
      function in `source_targets` that was **never** the
      `target_function` of any emitted `QualityReport`. For each such
      function, call `compute_contract_coverage(target, [], config=config,
      no_test_coverage=True)` and emit a `QualityReport`:
      ```python
      QualityReport(
          test_function="",          # no test
          target_function=target.name,
          assertions=(),
          contract_coverage=coverage,
          warnings=("No test targets this function — "
                    "GazeCRAP computed at 0% contract coverage.",),
          complexity=target.complexity,
      )
      ```
      These reports are included in the return value so the caller can
      score all production functions correctly.

- [ ] 3.4 [P] New tests in `tests/test_quality_coverage.py`
      (no modification to existing tests):
      - `test_no_test_coverage_emits_zero_percentage` — `no_test_coverage=True`,
        target has `ReturnValue` effect → `percentage=0.0`,
        `reason="no_test_coverage"`, `percentage is not None`.
      - `test_no_test_coverage_total_contractual_populated` — same setup →
        `total_contractual >= 1`.
      - `test_no_test_coverage_gaze_crap_computable` — verify
        `gaze_crap(complexity=5, contract_coverage=0.0)` equals
        `5**2 * (1 - 0.0)**3 + 5 == 30.0` (confirms the score is real).
      - `test_no_test_coverage_empty_effects_falls_through` —
        `no_test_coverage=True`, target has no effects → reason is
        `"no_effects_detected"` (not `"no_test_coverage"`).

## 4. Rendering — no_test_coverage display

- [ ] 4.1 Update `_format_function()` in
      `src/gaze_py/report/text_formatter.py`:
      When `target.score` is not None and
      `target.score.contract_coverage_reason == "no_test_coverage"`,
      append `"*"` to the GazeCRAP value string (e.g. `"2652.0*"`
      instead of `"2652.0"`). When `gaze_crap` is null and reason is
      `"no_test_coverage"`, show `"null*"`.

- [ ] 4.2 Update `_emit_quality_text()` in `src/gaze_py/cli/main.py`:
      Apply the same `*` suffix rule to the GazeCRAP column in the
      quality command text table.
      Add a footnote line after the table whenever any row has the
      `"no_test_coverage"` reason:
      ```
      * GazeCRAP computed at 0% contract coverage — no test targets this function
      ```

- [ ] 4.3 [P] New rendering tests (add to `tests/test_output.py` or
      `tests/test_cli.py` as appropriate — no modification to existing):
      - `test_no_test_coverage_text_appends_asterisk` — build a
        `FunctionTarget` with a `Score` where
        `contract_coverage_reason="no_test_coverage"` and `gaze_crap=30.0`;
        `to_text()` output contains `"30.0*"`.
      - `test_no_test_coverage_json_emits_raw_float_with_reason` — same
        setup; JSON output contains `"gaze_crap": 30.0` (raw float, no
        asterisk) and `"contract_coverage_reason": "no_test_coverage"`.

## 5. CRAP command — quality pipeline integration

- [ ] 5.1 Add `_build_contract_coverage_map(src_path: Path, tests_path: Path, config: GazeConfig) -> dict[str, ContractCoverageResult]`
      to `src/gaze_py/cli/main.py`.
      - Calls `assess(src_path, tests_path, config=config)`.
      - Builds `{function_name: ContractCoverageResult}` — when multiple
        reports exist for the same function name, keep the one with the
        highest `percentage` (or any if all are `0.0`).
      - Returns the map; returns `{}` if `assess()` raises or tests path
        is not found.

- [ ] 5.2 Update `_run_crap()` in `src/gaze_py/cli/main.py`:
      - After acquiring `coverage_data`, attempt to auto-discover a tests
        path using the same logic as the `quality` command (search for
        `tests/`, `test/`, `test_*.py` relative to `path.parent`, then
        relative to `Path.cwd()`).
      - If a `tests_path` option is explicitly provided (from the new
        `--tests` flag in task 5.3), use that instead.
      - If a tests path is resolved, call `_build_contract_coverage_map()`
        and, for each target, look up its `ContractCoverageResult` by
        name and pass to `_score_target(quality_result=...)`.
      - If no tests path is found, proceed as today (no `quality_result`
        passed, GazeCRAP remains null — OC-003 compliant).

- [ ] 5.3 Add `--tests` option to the `crap` command in
      `src/gaze_py/cli/main.py`:
      ```python
      @click.option("--tests", "tests_path", default=None,
                    help="Path to test directory or file. Auto-discovered if not provided.")
      ```
      Thread the value through to `_run_crap()`.

- [ ] 5.4 [P] New tests in `tests/test_cli.py`
      (no modification to existing tests):
      - `test_crap_with_tests_populates_gaze_crap` — run `crap` on
        `tests/testdata/quality/src/` with
        `--tests tests/testdata/quality/tests/`; assert at least one
        function has non-null `gaze_crap` in JSON output.
      - `test_crap_no_test_coverage_reason_in_json` — same invocation;
        assert at least one function has
        `contract_coverage_reason: "no_test_coverage"` and non-null
        `gaze_crap`.
      - `test_crap_without_tests_gaze_crap_null` — run `crap` on a path
        with no auto-discoverable tests directory; all `gaze_crap` values
        in JSON output are null.

## 6. Baseline measurement + CI gate

- [ ] 6.1 Run `uv run gazepy quality src/gaze_py/ --tests tests/ --format=json`
      and record in `openspec/changes/quality-pairing-astroid/results.md`:
      - Total public functions paired (target ≥ 28, stretch ≥ 31)
      - Count with `"no_test_coverage"` reason
      - Count with `"no_effects_detected"` reason (should be 0 for
        functions with any detected effects)
      - Wall-clock time (target ≤ 4s; current baseline ~1.5s)
      Also run `gazepy crap src/gaze_py/ --tests tests/
      --coverprofile=coverage.json --format=json` and record:
      - Count of non-null `gaze_crap` values
      - `gaze_crapload` value
      - `visit_Call` entry (expected: non-null `gaze_crap` ≈ 2652,
        `contract_coverage_reason: "no_test_coverage"`)

- [ ] 6.2 [P] `uv run ruff check .`
- [ ] 6.3 [P] `uv run ruff format --check .`
- [ ] 6.4 [P] `uv run mypy --strict src/`
- [ ] 6.5 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
