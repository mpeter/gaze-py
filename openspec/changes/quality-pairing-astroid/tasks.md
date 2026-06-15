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
          reports: tuple[QualityReport, ...]   # one per test function (paired)
          untested: tuple[QualityReport, ...]  # one per unmatched prod func with effects
      ```
      Use `tuple` fields to match the project convention (all other frozen
      dataclasses use `tuple[..., ...]` for sequences — see `QualityReport`,
      `ContractCoverageResult`).
      Add to `src/gaze_py/quality/__init__.py`:
      ```python
      from gaze_py.quality.pipeline import AssessResult, build_contract_coverage_map
      ```
      Both public names are importable as
      `from gaze_py.quality import AssessResult, build_contract_coverage_map`.

- [ ] 2.2 Update `assess()` signature and return type in
      `src/gaze_py/quality/pipeline.py`:
      ```python
      def assess(...) -> AssessResult:
      ```
      Update all callers in `cli/main.py`:
      - Change `reports = assess(...)` to `result = assess(...)`; pass
        `result.reports` (a `tuple[QualityReport, ...]`) where `reports`
        was used.
      - Update `_emit_quality_json()`, `_emit_quality_text()`, and
        `_check_min_contract_coverage()` signatures to accept
        `Sequence[QualityReport]` (from `collections.abc`) instead of
        `list[QualityReport]` — `tuple` is a `Sequence` so no call-site
        changes are needed beyond the variable rename above.
      - `build_contract_coverage_map()` (task 6.1) calls `assess()` and
        uses `result.reports + result.untested` — this is a consuming
        caller of `AssessResult`; it is written knowing the new type.

- [ ] 2.3 Update `QualityReport` docstring in `src/gaze_py/taxonomy/models.py`
      to document the `test_function=""` sentinel:
      ```
      test_function: Name of the test function. Empty string ("") when
          this report represents an unmatched production function with
          no paired test (part of AssessResult.untested).
      ```

- [ ] 2.4 Update `TestTargetPair.inference_method` docstring in
      `src/gaze_py/taxonomy/models.py` to add `"call_graph_transitive"`:
      ```
      inference_method: "name_convention" | "call_graph" |
          "call_graph_transitive" | "unmatched".
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
      Note: `"no_test_coverage"` supersedes `"all_effects_ambiguous"` —
      when `no_test_coverage=True` and effects exist (even if all
      ambiguous), the function returns `"no_test_coverage"`. This matches
      Go behaviour where `effectsSet` membership (any effects) triggers
      `"no_test_coverage"` regardless of classification state.

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

- [ ] 4.1 Add `_untested_reports(source_targets: tuple[FunctionTarget, ...], seen_names: set[str], config: GazeConfig) -> tuple[QualityReport, ...]`
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
      - Return `tuple(results)`; empty tuple if all production functions
        are paired.

- [ ] 4.2 Update `assess()` in `src/gaze_py/quality/pipeline.py`:
      - After the main per-test-function loop, collect `seen_names` (set
        of non-None `target_function` values from emitted reports).
      - Call `_untested_reports(tuple(source_targets), seen_names, config)`.
      - Return `AssessResult(reports=tuple(reports), untested=untested)`.

- [ ] 4.3 Identify the correct existing fixture for `_untested_reports()`
      integration tests. Use
      `tests/testdata/quality/src/undertested.py` — this file already
      exists (created in the O1 quality pipeline change, task 2.7) and
      contains a function with a `ReturnValue` contractual effect and
      `tests/testdata/quality/tests/test_undertested.py` which calls the
      function but makes zero assertions. Verify these files exist before
      writing the tests:
      `ls tests/testdata/quality/src/undertested.py tests/testdata/quality/tests/test_undertested.py`
      If either is missing, create it per the O1 task 2.7/2.8 spec
      before writing the integration tests.

- [ ] 4.4 New integration tests in `tests/test_quality_integration.py`
      — requires tasks 2.1 and 2.2 to be complete first (AssessResult
      must exist and assess() must return it); do NOT mark [P] within
      section 4 for this reason:
      - `test_assess_returns_assess_result` — `assess()` returns an
        `AssessResult` with `.reports` and `.untested` attributes.
      - `test_assess_untested_has_no_test_coverage_reason` — using the
        `undertested` fixture (`tests/testdata/quality/src/` with
        `tests/testdata/quality/tests/`), `result.untested` is non-empty;
        at least one entry has `contract_coverage.reason == "no_test_coverage"`
        and `contract_coverage.percentage is None`.
      - `test_assess_untested_test_function_is_empty_string` — all
        entries in `result.untested` have `test_function == ""`.
      - `test_assess_paired_functions_not_in_untested` — no function
        name appears in both `result.reports` (with non-None
        `target_function`) and `result.untested`.
      - `test_assess_no_effects_function_not_in_untested` — using the
        `simple` fixture where the source function has `ReturnValue` and
        is fully tested (100% coverage), assert `result.untested` is
        empty (length == 0). No OR-branch: for this fixture, all
        production functions with effects ARE paired, so `untested`
        must be empty, not "empty OR only no_effects_detected".

## 5. Pairing — Strategy 3 (Astroid transitive call graph)

- [ ] 5.1 Add `_build_astroid_graph(test_files: list[Path], src_files: list[Path]) -> dict[str, set[str]]`
      to `src/gaze_py/quality/pairing.py`.
      - Add `import sys` at **module level** in `pairing.py` (CS-002
        MUST — all imports at module level; no inline imports).
      - Import `astroid`, `astroid.MANAGER`, `astroid.exceptions`, and
        `astroid.util` at module level (required production dependency —
        no defensive ImportError handler needed; D7).
      - Call `astroid.MANAGER.clear_cache()` before loading any files
        (D2 — prevents stale data across multiple `assess()` calls in
        the same process; this evicts all cached modules from the global
        MANAGER, a known trade-off documented in D2 and CHANGELOG).
      - Deduplicate input paths: build a `unique_files: list[Path]` from
        `dict.fromkeys(test_files + src_files)` — preserves insertion
        order, eliminates duplicates so files with multiple test
        functions are not loaded more than once.
      - For each file in `unique_files`:
        ```python
        try:
            module = astroid.MANAGER.ast_from_file(str(path))
        except astroid.exceptions.AstroidBuildingError as exc:
            sys.stderr.write(f"warning: astroid could not load {path}: {exc}\n")
            continue
        ```
        (`sys` is imported at module level; `sys.stderr.write()` not
        `click.echo()` — library module must not import Click; D9.)
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
      - Collect `test_funcs` from `_collect_test_functions(tests_path)`.
      - Build `test_files: list[Path]` as deduplicated file paths:
        `list(dict.fromkeys(Path(tf.filename) for tf in test_funcs))`
        (one path per file, not one per test function).
      - Collect `src_files: list[Path]` via `collect_py_files(src_path)`.
      - Call `_build_astroid_graph(test_files, src_files)` once before
        the per-test-function loop.
      - Pass `astroid_graph=graph` to every `pair_to_targets()` call.

- [ ] 5.5 [P] New tests in `tests/test_quality_pairing.py` using
      dedicated testdata fixtures in `tests/testdata/quality/astroid/`
      (no modification to existing tests):

      Create fixture files (NO relative imports — Astroid loads files
      individually by path and cannot resolve relative imports without a
      full package structure; use absolute names only):
      - `tests/testdata/quality/astroid/src/signals.py`:
        ```python
        # ruff: noqa
        def caller_signal(x):  # type: ignore[override]
            return x * 2
        ```
      - `tests/testdata/quality/astroid/src/engine.py`:
        ```python
        # ruff: noqa
        def caller_signal(x):  # local stub — Astroid resolves within same load
            return x * 2

        class Engine:
            def classify(self, x):
                return caller_signal(x)

        def _make_engine():
            # type: () -> Engine
            return Engine()
        ```
        Note: both functions are defined in the same file to avoid
        cross-file import resolution issues. Astroid resolves intra-file
        calls reliably. Cross-file call graph edges are still covered by
        the depth-limit and empty-graph tests which use hand-built dicts.
      - `tests/testdata/quality/astroid/tests/test_engine.py`:
        ```python
        # ruff: noqa
        # This is a testdata fixture; it is not collected by pytest.
        # See pyproject.toml norecursedirs = ["tests/testdata"] (CR-002).
        from engine import _make_engine  # noqa: F821

        def test_classify():
            e = _make_engine()
            assert e.classify(1) == 2
        ```

      Tests (use `_build_astroid_graph()` directly with fixture file paths;
      do NOT use live project source):
      - `test_pair_astroid_resolves_method_call` — graph built from
        `engine.py` only (NOT `test_engine.py` — the test file's cross-
        file import will cause `AstroidBuildingError` on load; the
        method-call resolution test is done with a hand-built graph):
        Manually construct a graph dict:
        `graph = {"tests.test_engine.test_engine_integration": {"engine._make_engine"},
                  "engine._make_engine": {"engine.Engine.classify"},
                  "engine.Engine.classify": {"engine.caller_signal"}}`
        Create a `TestFunc` with `name="test_engine_integration"` (NOT
        `"test_classify"` — Strategy 1 would strip prefix to `"classify"`
        which matches a source function by name convention, bypassing
        Strategy 3). With `source_names={"classify"}` and this graph,
        `_pair_astroid()` reaches `Engine.classify` → short name
        `"classify"` → match. Assert result is `"classify"` AND
        `inference_method == "call_graph_transitive"` AND
        `confidence == 0.75` (verifies Strategy 3, not Strategy 1).
      - `test_pair_astroid_transitive_reaches_caller_signal` — same
        hand-built graph; call `_pair_astroid()` with
        `source_names={"caller_signal"}`; assert result is
        `"caller_signal"` (transitive match through 3 hops).
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
      - `test_build_astroid_graph_clears_cache_between_calls` — use
        `unittest.mock.patch.object(astroid.MANAGER, "clear_cache")` to
        assert `clear_cache` is called exactly once per invocation of
        `_build_astroid_graph()`. Call the function twice; assert the mock
        was called twice total. This verifies the clear_cache contract
        without relying on observable cache state (which would be
        unfalsifiable without mock).

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

- [ ] 6.2 Add `--tests` option to the `crap` command (must be done
      BEFORE task 6.3 so the option exists when `_run_crap()` is updated):
      ```python
      @click.option("--tests", "tests_path", default=None,
                    help="Test directory or file. Auto-discovered if omitted.")
      ```
      Add `tests_path: str | None = None` to the `crap` function
      signature. Thread it through as a `Path | None` to the inner
      quality integration step (task 6.3).

- [ ] 6.3 Integrate quality pipeline into the `crap` command body
      (NOT inside `_run_crap()` — `_run_crap()` signature is unchanged):
      In the `crap` command body, after `result = _run_crap(src, coverage_data, config=config)`:
      - Resolve `tests_path`: if `tests_path` option is provided, use it;
        otherwise auto-discover (search `tests/`, `test/`, `test_*.py`
        relative to `src.parent`, then `Path.cwd()`).
      - If a tests path is resolved:
        - Call `build_contract_coverage_map(src, resolved_tests, config)`.
        - For each `target` in `result.functions`, look up
          `ContractCoverageResult` by `target.name` in the map.
        - If found, call `_score_target(target, line_coverage_frac=
          target.score.line_coverage if target.score else None,
          config=config, quality_result=ccr)` to re-score in-place
          with contract coverage. (Note: `_run_crap()` already scored
          the target once without quality data; this re-scores with it.
          The re-score overwrites the `target.score` attribute.)
        - Verify that the existing `_score_target()` guard
          `if quality_result is not None and quality_result.percentage is not None:`
          already handles `"no_test_coverage"` correctly (`percentage=None`
          → else branch → `gaze_crap_score=None`). No new guard needed.
          Add code comment: `# "no_test_coverage": percentage=None →
          else branch → gaze_crap stays null per Go contract (D5)`.
      - **Known Limitation**: `build_contract_coverage_map()` uses
        `include_unexported=False`. Private functions always show
        `contract_coverage_reason: null` in crap output (D10).
      - If no tests path found, proceed as today (GazeCRAP null,
        OC-003 compliant).

- [ ] 6.4 New tests in `tests/test_cli.py` — requires tasks 6.2 and
      6.3 to be complete first (--tests option and quality integration
      must exist); do NOT mark [P] within section 6 for this reason:
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
        (`inference_method: "call_graph_transitive"`, confidence 0.75)
      - `"no_test_coverage"` contract coverage reason code for functions
        with effects but no paired test (GazeCRAP remains null per Go
        porting contract — "no test = no coverage data, not 0%")
      - `--tests` option on `gazepy crap` command
      - `AssessResult` return type from `assess()` with `.reports`
        (test-keyed) and `.untested` (production-function-keyed) fields
      - `build_contract_coverage_map()` in `quality/pipeline.py`

      ### Known Limitations
      - Private (underscore-prefixed) functions do not receive
        `contract_coverage_reason` enrichment in `gazepy crap --tests`
        output (assess() uses include_unexported=False by default;
        deduplication of the double detect_and_classify() call is
        deferred to a follow-up change)
      - Astroid 3.x compatibility is asserted but CI-verified at 4.1.2
        only (astroid>=3.0 with no upper bound)
      ```

- [ ] 7.3 [P] `uv run ruff check .`
- [ ] 7.4 [P] `uv run ruff format --check .`
- [ ] 7.5 [P] `uv run mypy --strict src/`
- [ ] 7.6 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
