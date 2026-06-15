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

<!--
  IMPLEMENTER NOTES — non-blocking advisories from the
  victory-lap review council run (all 8 reviewers approved):

  1. BFS must use graph.get(fqn, set()) not graph[fqn] —
     a callee that was never itself a caller has no key in
     the adjacency dict; KeyError without the .get() guard.

  2. _process_test_func() needs astroid_graph threaded
     through as a parameter — task 5.4 says "pass
     astroid_graph=graph to every pair_to_targets() call"
     but the only call site is inside _process_test_func(),
     not directly in assess(). Update _process_test_func()
     signature accordingly.

  3. build_contract_coverage_map export in __init__.py
     should be deferred to after task 6.1 — task 2.1
     specifies both AssessResult and build_contract_coverage_map
     in the __init__.py update, but build_contract_coverage_map
     doesn't exist until 6.1. Do the __init__.py export for
     build_contract_coverage_map as part of task 6.1, not 2.1.

  4. "Zero transitive deps" in proposal.md is slightly
     imprecise — astroid has lazy_object_proxy, wrapt,
     typing_extensions, and platformdirs as transitive deps.
     They are all benign and widely deployed; the supply chain
     argument is still valid. Do not repeat the zero-deps claim
     in user-facing docs or --help text.
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
      Also update the early-return guard at `pipeline.py:59` (currently
      `return []` when no test functions found) to:
      `return AssessResult(reports=(), untested=())`.

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
        uses `result.reports + result.untested` — it is written knowing
        the new type.

      Update `tests/test_quality_integration.py` — all existing tests
      that call `assess()` and treat the return value as a list must be
      migrated to `AssessResult`. Pattern for each:
      ```python
      # Before:
      reports = assess(src_path, tests_path, config=config)
      assert reports == []
      assert len(reports) >= 1
      for r in reports: ...

      # After:
      result = assess(src_path, tests_path, config=config)
      reports = result.reports
      assert reports == ()  # or len(reports) == 0
      assert len(reports) >= 1
      for r in reports: ...
      ```
      This is an exception to the "no existing tests modified" goal —
      these are mechanical migrations, not behavioral changes. The
      existing test assertions remain valid once migrated.

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
      - When `target_func is None` (unfiltered run), call
        `_untested_reports(tuple(source_targets), seen_names, config)`.
      - When `target_func is not None` (filtered run), set
        `untested = ()` — do not call `_untested_reports()`, since
        `seen_names` is filtered and would incorrectly mark tested-but-
        filtered functions as untested (B-03).
      - Return `AssessResult(reports=tuple(reports), untested=untested)`.

- [ ] 4.3 Create new fixture for genuinely-untested functions:
      `tests/testdata/quality/src/uncovered.py`:
      ```python
      # ruff: noqa
      # AST fixture — never executed. No test file targets this function.

      def orphan_compute(items: list) -> int:
          """Return sum of items."""
          return sum(items)
      ```
      **No corresponding test file** — this function has effects but no
      test in the test suite calls it by name or via call graph. This
      makes `orphan_compute` genuinely untested by ALL strategies (1, 2,
      and 3): Strategy 1 fails (no test named `test_orphan_compute`);
      Strategy 2 fails (no test calls `orphan_compute` as a Name);
      Strategy 3 fails (no test reaches it via call graph).

      The existing `undertested.py` / `test_undertested.py` fixture
      (`compute_total` called without assertions) is paired by Strategy
      2 (`compute_total` is a bare ast.Name call) and belongs in
      `result.reports` with `percentage=0.0` — it is NOT suitable for
      `result.untested` tests.

- [ ] 4.4 New integration tests in `tests/test_quality_integration.py`
      — requires tasks 2.1, 2.2, and 4.3 to be complete first;
      do NOT mark [P]:
      - `test_assess_returns_assess_result` — `assess()` returns an
        `AssessResult` with `.reports` and `.untested` attributes.
      - `test_assess_untested_has_no_test_coverage_reason` — run
        `assess(src_path=QUALITY_FIXTURES/"src", tests_path=QUALITY_FIXTURES/"tests")`
        where `QUALITY_FIXTURES = tests/testdata/quality/`. The
        `uncovered.py` fixture (task 4.3) contains `orphan_compute` with
        no corresponding test. Assert `result.untested` is non-empty and
        at least one entry has `target_function == "orphan_compute"`,
        `contract_coverage.reason == "no_test_coverage"`, and
        `contract_coverage.percentage is None`.
      - `test_assess_untested_test_function_is_empty_string` — same run;
        all entries in `result.untested` have `test_function == ""`.
      - `test_assess_paired_functions_not_in_untested` — same run; no
        function name appears in both `{r.target_function for r in result.reports
        if r.target_function}` and `{r.target_function for r in result.untested}`.
      - `test_assess_no_effects_function_not_in_untested` — run `assess()`
        on `tests/testdata/quality/src/simple.py` (single file, not a
        directory) with `tests/testdata/quality/tests/test_simple.py`.
        `simple.py` has one function with `ReturnValue` effect, fully
        covered by `test_simple.py`. Assert `result.untested` is empty
        (tuple length == 0).

## 5. Pairing — Strategy 3 (Astroid transitive call graph)

- [ ] 5.1 Add `_build_astroid_graph(test_files: list[Path], src_files: list[Path]) -> dict[str, set[str]]`
      to `src/gaze_py/quality/pairing.py`.
      - Add at **module level** in `pairing.py` (CS-002 MUST):
        `import collections`, `import sys`
        `import astroid`, `from astroid import MANAGER`
        `import astroid.exceptions`, `import astroid.util`
        (All are required production dependencies — no defensive
        ImportError handlers; D7.)
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

      All tests in this section use **hand-built graph dicts** — no
      `_build_astroid_graph()` call on real files, no fixture file loading.
      This avoids cross-file import resolution issues entirely. The
      fixture files (above) are only used by `test_build_astroid_graph_*`
      tests (intra-file only).

      **FQN alignment**: `_pair_astroid()` computes the start FQN from
      `test_func.filename` using D8. In tests, use a synthetic
      `TestFunc` with `filename` set to a fake path whose D8 output
      matches the graph key exactly:
      - If D8 produces `"<module>.<func>"` from the filename, the
        graph key must use that same string.
      - Simplest approach: mock or monkeypatch `_pair_astroid()`'s FQN
        computation, OR construct the graph key to match the D8 output
        for the specific fake path used in the test. Use a helper:
        ```python
        def _make_test_func(name: str, fqn_key: str) -> TestFunc:
            # Create a TestFunc with a synthetic filename whose D8 output
            # equals fqn_key (minus the function name suffix)
            # Implementation: patch _get_fqn() if extracted, or use
            # a filename that produces the expected key via D8
            ...
        ```
        The exact mechanism is left to the implementer, but the test
        must be deterministic and not dependent on pyproject.toml location.

      - `test_pair_astroid_resolves_method_call` — use a hand-built graph
        and a `TestFunc` whose FQN resolves to a key in the graph:
        ```python
        graph = {
            "test_mod.test_engine_integration": {"src_mod.Engine.classify"},
            "src_mod.Engine.classify": set(),
        }
        source_funcs = [make_target("classify"), make_target("Engine")]
        # source_names = {"classify", "Engine"}
        ```
        Use `source_names={"classify"}`. Call `_pair_astroid(tf, source_names, graph)`.
        Assert result is `"classify"`.
        Then test `inference_method` and `confidence` by calling
        `pair_to_targets(tf, source_funcs, astroid_graph=graph)` and
        asserting the returned `TestTargetPair.inference_method ==
        "call_graph_transitive"` and `confidence == 0.75`. (`_pair_astroid`
        returns `str | None`; `pair_to_targets` returns `TestTargetPair`
        — use the right function for each assertion.)
      - `test_pair_astroid_transitive_reaches_caller_signal` — hand-built
        graph with 3-hop chain:
        ```python
        graph = {
            "test_mod.test_foo": {"src_mod._make_engine"},
            "src_mod._make_engine": {"src_mod.Engine.classify"},
            "src_mod.Engine.classify": {"src_mod.caller_signal"},
        }
        ```
        Call `_pair_astroid(tf, {"caller_signal"}, graph)`.
        Assert result is `"caller_signal"`.
      - `test_pair_astroid_depth_limit` — hand-built 6-hop chain;
        `depth_limit=5`; function at hop 6 is NOT returned.
      - `test_pair_astroid_empty_graph_falls_through_to_unmatched` —
        `astroid_graph={}`, no name match, no ast.Name call match →
        assert `pair_to_targets(...)` returns
        `TestTargetPair(inference_method="unmatched", confidence=0.0)`.
      - `test_pair_astroid_confidence_and_method` — hand-built graph
        producing a match; assert `pair_to_targets(...).inference_method
        == "call_graph_transitive"` and `.confidence == 0.75`.
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
        `result.reports + result.untested` (concatenate tuples):
        - For each report with non-None `target_function` and non-None
          `contract_coverage`, update the dict keeping the entry with
          the highest `percentage` (or first if both are `None`).
      - On exception from `assess()`, emit a stderr warning before
        returning `{}`:
        ```python
        except Exception as exc:  # noqa: BLE001
            import sys
            sys.stderr.write(f"warning: quality pipeline failed: {exc}\n")
            return {}
        ```
        (The `import sys` is inside the `except` block here because this
        is a `cli/` adjacent module — see D7. Actually: `pipeline.py` is
        a library module; add `import sys` at module level of
        `pipeline.py` if not already present.)

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
      Use a **lazy inline import** inside the crap command body (same
      pattern as `from gaze_py.quality.pipeline import assess` in the
      quality command at line 512 — avoids loading quality/pipeline.py
      on every `gazepy crap` invocation that doesn't pass `--tests`):
      ```python
      from gaze_py.quality.pipeline import build_contract_coverage_map
      ```
      Place this import inside the `if resolved_tests:` block, not at
      module level.

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

- [ ] 6.4 New tests in `tests/test_cli.py` — requires tasks 4.3, 6.2,
      and 6.3 to be complete first; do NOT mark [P] within section 6:
      - `test_crap_with_tests_populates_contract_coverage_reason` — run
        `crap` on `tests/testdata/quality/src/` with
        `--tests tests/testdata/quality/tests/`; assert at least one
        function has `contract_coverage_reason` non-null in JSON output.
      - `test_crap_no_test_coverage_reason_gaze_crap_still_null` — same
        invocation; the `uncovered.py` fixture (task 4.3) contains
        `orphan_compute` with no test — this function appears with
        `contract_coverage_reason: "no_test_coverage"` in crap output;
        assert its `gaze_crap` is `null` (not a float). If the fixture
        is analysed by crap but the source path doesn't include
        `uncovered.py`, adjust the invocation to ensure it's included.
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

      ### Changed
      - `assess()` now returns `AssessResult` instead of
        `list[QualityReport]`. Direct Python callers must update:
        `reports = assess(...)` → `result = assess(...); reports = result.reports`

      ### Known Limitations
      - Private (underscore-prefixed) functions do not receive
        `contract_coverage_reason` enrichment in `gazepy crap --tests`
        output (assess() uses include_unexported=False by default;
        deduplication of the double detect_and_classify() call is
        deferred to a follow-up change)
      - Astroid 3.x compatibility is asserted but CI-verified at 4.1.2
        only (astroid>=3.0 with no upper bound)
      - `MANAGER.clear_cache()` evicts astroid's process-global AST
        cache on each `assess()` call; tools sharing the process that
        also use astroid (e.g. pylint) will have their cache cleared
      ```

- [ ] 7.3 [P] `uv run ruff check .`
- [ ] 7.4 [P] `uv run ruff format --check .`
- [ ] 7.5 [P] `uv run mypy --strict src/`
- [ ] 7.6 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`

<!-- spec-review: passed -->
