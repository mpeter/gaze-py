## 1. Taxonomy additions (output types → taxonomy/models.py)

- [x] 1.1 Add to `src/gaze_py/taxonomy/models.py`:
      `AssertionKind` (StrEnum), `AssertionSite` (frozen dataclass),
      `TestTargetPair` (frozen dataclass), `ContractCoverageResult`
      (frozen dataclass with `percentage: float | None` and `reason: str | None`),
      `QualityReport` (frozen dataclass with tuple fields).
      See design.md "taxonomy/models.py additions" for exact signatures.
- [x] 1.2 Create `src/gaze_py/quality/__init__.py` with module docstring only
      (CR-001 — no re-exports, no imports)
- [x] 1.3 Create `src/gaze_py/quality/models.py` with `TestFunc` dataclass only
      (mutable @dataclass, not frozen — contains ast.FunctionDef).

## 2. Test fixtures (tests/testdata/quality/)

- [x] 2.1 Create `tests/testdata/quality/src/simple.py` — single function
      returning a computed value; its only effect is ReturnValue
- [x] 2.2 Create `tests/testdata/quality/tests/test_simple.py` — `def test_simple():`
      calls the function, asserts on the return value (100% coverage expected).
      Add `# ruff: noqa: F821` header and AST-fixture comment (CR-002).
- [x] 2.3 Create `tests/testdata/quality/src/raises_fn.py` — function that
      raises a specific exception type
- [x] 2.4 Create `tests/testdata/quality/tests/test_raises.py` — uses
      `pytest.raises(...)` to assert the exception is raised (covers
      RaiseException effect). Add CR-002 noqa header.
- [x] 2.5 Create `tests/testdata/quality/src/attribute_mutation.py` — function
      that mutates an attribute on a passed-in object (AttributeMutation effect;
      more reliably detectable than GlobalMutation via AST)
- [x] 2.6 Create `tests/testdata/quality/tests/test_attribute_mutation.py` —
      asserts on the mutated attribute after calling the function. CR-002 header.
- [x] 2.7 Create `tests/testdata/quality/src/undertested.py` — function with
      a contractual ReturnValue effect
- [x] 2.8 Create `tests/testdata/quality/tests/test_undertested.py` — calls
      the function but makes zero assertions (0% contract coverage expected).
      CR-002 header.
- [x] 2.9 Confirm that existing `norecursedirs = ["tests/testdata"]` in
      `pyproject.toml` already recursively covers `tests/testdata/quality/`
      — no `pyproject.toml` change needed. Verify using exit code 5
      (EXIT_NOTESTSCOLLECTED): `uv run pytest --collect-only tests/testdata/;
      [ $? -eq 5 ] && echo "PASS: no tests collected"`. Exit code 5 means
      pytest found no test items — version-stable check.

## 3. A.1 — Pairing (quality/pairing.py)

- [x] 3.1 Create `src/gaze_py/quality/pairing.py` with:
      - `find_test_functions(filepath: Path) -> list[TestFunc]`
      - `_extract_call_name(node: ast.Call) -> str | None`
      - `pair_to_targets(test_func: TestFunc, source_functions: list[FunctionTarget]) -> TestTargetPair`
        (three strategies per design.md; empty source_functions → immediate unmatched return)
- [x] 3.2 Tests in `tests/test_quality_pairing.py`:
      - `test_pair_empty_source_functions` — source_functions=[] →
        target_name=None, method="unmatched", confidence=0.0
      - `test_pair_name_convention_exact` — test_foo → foo → confidence=0.9
      - `test_pair_name_convention_case_insensitive` → confidence=0.7
      - `test_pair_call_graph_no_name_match` — no name match, but call to
        source function found in body → confidence=0.8
      - `test_pair_unmatched` — no name match, no call found → None
      - `test_pair_class_method` — class TestFoo method → correct target
      - `test_pair_underscore_name` — test_process_items → process_items (exact match)
      - `test_find_test_functions` — returns only test_* prefixed functions,
        not helpers

## 4. A.2 — Assertion detection (quality/assertions.py)

- [x] 4.1 Create `src/gaze_py/quality/assertions.py` with:
      - `detect_assertions(test_func: TestFunc, *, pkg_ast: dict[str, ast.Module] | None = None, max_depth: int = 3) -> list[AssertionSite]`
      - `_extract_referenced_names(expr: ast.expr) -> frozenset[str]`
        (handles Name, Attribute, Subscript, Call — see design.md)
      - Location format: `"file:line:col"` — use `col=0` when unavailable
- [x] 4.2 Tests in `tests/test_quality_assertions.py`:
      - `assert x == y` → STDLIB_EQUALITY, referenced_names={"x","y"}
      - `assert f() == g()` → STDLIB_EQUALITY, referenced_names includes
        "f" and "g" (call names extracted)
      - `assert result[0] == expected` → STDLIB_EQUALITY, referenced_names
        includes "result" (base of subscript)
      - `assert obj.value == 42` → STDLIB_EQUALITY, referenced_names
        includes "obj" (base of attribute)
      - `assert x is None` → STDLIB_NONE_CHECK
      - `assert err is None` → STDLIB_ERROR_CHECK (name contains "err")
      - `assert x` → STDLIB_TRUTH
      - `with pytest.raises(ValueError):` → STDLIB_RAISES
      - `self.assertEqual(a, b)` → UNITTEST_EQUAL
      - `self.assertIsNone(x)` → UNITTEST_NONE
      - `self.assertRaises(Err, fn)` → UNITTEST_RAISES
      - helper function recursion: assert_helper called from test body →
        assertions inside helper detected at depth=1
      - depth limit: assert_* at depth=3 not recursed into further
      - no assertions → empty list
      - location uses three-part "file:line:col" format

## 5. A.3 — Assertion mapping (quality/mapper.py)

- [x] 5.1 Create `src/gaze_py/quality/mapper.py` with:
      - `build_call_bindings(test_func: TestFunc, target_name: str) -> dict[str, str]`
      - `map_assertions_to_effects(assertions: list[AssertionSite], target: FunctionTarget, call_bindings: dict[str, str]) -> list[tuple[AssertionSite, SideEffectType | None]]`
        using first-match-wins across three passes (see design.md)
- [x] 5.2 Tests in `tests/test_quality_mapper.py`:
      - return value binding → maps to ReturnValue (Pass 1)
      - error return binding → maps to ErrorReturn (Pass 1)
      - pytest.raises → maps to ErrorReturn (Pass 2)
      - assertion referencing name matching a contractual GlobalMutation
        effect target → maps to that effect (Pass 3 positive, contractual)
      - assertion referencing name matching an incidental effect target →
        maps to incidental effect, counted as over-spec (Pass 3, incidental)
      - assertion that would match both Pass 1 (binding) and Pass 2 (raises):
        e.g., kind=STDLIB_RAISES AND name in call_bindings → matched by
        Pass 1 only (first-match-wins); NOT yielded twice
      - assertion with no binding, no raises kind, no name match → None (unmapped)
      - function with no effects → all assertions unmapped
      - multiple bindings in same test (result, err) → two separate entries
      - 3-element tuple unpack: `a, b, c = fn()` → `{"a": "return_value",
        "b": "error_return"}`; index 2+ ignored (spec: first two named only)
      - output length equals input length: `assert len(result) == len(assertions)`
        for EVERY test case, including "no effects" and "all unmapped"

## 6. A.4 — Contract coverage (quality/coverage.py)

- [x] 6.1 Create `src/gaze_py/quality/coverage.py` with:
      - `compute_contract_coverage(target: FunctionTarget, mapped: list[tuple[AssertionSite, SideEffectType | None]], *, config: GazeConfig) -> ContractCoverageResult`
        (uses ClassificationEngine internally to classify each effect; correct field
        name is `effect.type` not `effect.effect_type`; see design.md A.4)
- [x] 6.2 Tests in `tests/test_quality_coverage.py`:
      - all contractual effects covered → percentage=100.0, covered_effects=N,
        total_contractual=N, over_specification_count=0, reason=None
      - zero assertions, contractual effects exist → percentage=0.0,
        covered_effects=0, total_contractual=N (N>0), unmapped_assertions=0
      - partial: 1 of 2 contractual covered → percentage=50.0,
        covered_effects=1, total_contractual=2
      - no contractual effects (effects exist but all incidental) →
        `percentage is None` (not 0.0!), reason="no_contractual_effects",
        total_contractual=0
      - no effects at all → `percentage is None`, reason="no_effects_detected",
        total_contractual=0, covered_effects=0
      - over-specification: assertion maps to incidental effect →
        over_specification_count=1
      - unmapped: assertion maps to None → unmapped_assertions=1
      - contractual effects with assertion on same effect type as both
        covered and incidental → covered counts covered, over_spec not double-counted

## 7. assess() — pipeline.py

- [x] 7.1 Create `src/gaze_py/quality/pipeline.py` with:
      `assess(src_path: Path, tests_path: Path, *, config: GazeConfig, target_func: str | None = None) -> list[QualityReport]`
      - Run `_run_detect_classify()` on src_path
      - Discover test functions in tests_path via `find_test_functions()`
      - For each test function: `pair_to_targets()`, `detect_assertions()`,
        `build_call_bindings()`, `map_assertions_to_effects()`,
        `compute_contract_coverage()`
      - If `target_func` is set, filter to reports whose target matches
      - Return list of QualityReport
- [x] 7.2 Integration tests in `tests/test_quality_integration.py` using
      testdata fixtures from task 2:
      - simple fixture: `percentage == 100.0`, `contract_coverage` non-None
      - raises fixture: RaiseException effect covered, `percentage > 0`
      - undertested fixture: `percentage == 0.0` AND `percentage is not None`
        (zero assertions → zero coverage, but contractual effects exist so
        null-not-zero rule does not apply; this is NOT the same as None)
      - attribute_mutation fixture: coverage > 0% (AttributeMutation covered)
      - `target_func` filtering: only reports for the specified function returned
      - empty tests_path (no test functions found): `assess()` returns `[]`
        without error (documented edge case)

## 8. Output wiring (A.5)

- [x] 8.1 Update `_score_target()` signature in `src/gaze_py/cli/main.py` to:
      `_score_target(target, *, line_coverage_frac, config, quality_result=None)`
      Populate `Score.gaze_crap`, `Score.contract_coverage`, `Score.quadrant`,
      `Score.contract_coverage_reason` per design.md A.5 wiring.
      CRITICAL: divide `quality_result.percentage` by 100.0 before passing
      to `gaze_crap()` and `quadrant()`.
      Existing callers pass no `quality_result` — default None preserves
      backward compatibility.
- [x] 8.2 Update `_build_summary()` in `src/gaze_py/cli/main.py` to populate:
      - `gaze_crapload`: count where `score.gaze_crap >= config.gaze_crap_threshold`
      - `avg_contract_coverage`: mean of non-None `score.contract_coverage` values
      - `quadrant_counts`: dict counting each quadrant label
      - `fix_strategy_counts`: count `score.fix_strategy` per value across all
        targets with non-None scores (does NOT require O1; populated from existing
        CRAP scoring whenever scores are available)
      - Update `Summary.fix_strategy_counts` docstring in `taxonomy/models.py`
        to reflect it is populated whenever CRAP scores are available (not only
        when O1 has run)
- [x] 8.3 Implement the `quality` CLI command in `src/gaze_py/cli/main.py`:
      - Remove stub body and stub error message
      - `PATH` positional (required; use `click.Path(exists=False)` and validate
        manually, emitting exit 2 with error if not found)
      - `--tests` option (optional; auto-discover if not provided: search `tests/`,
        `test/`, `test_*.py` relative to `Path(path).parent` first, then fall back
        to the same relative to `Path.cwd()`; emit error and exit 2 if not found)
      - `--target` option maps to `assess(target_func=<name>)` — it is a
        **production function name** (e.g., `process`), not a package/module filter;
        update the CLI help text to say "restrict to tests exercising this function"
      - Full flag surface per design.md A.5: `--format`, `--target`, `--verbose`,
        `--include-unexported`, `--config`, `--contractual-threshold`,
        `--incidental-threshold`, `--min-contract-coverage`,
        `--max-over-specification`, `--ai-mapper` (accepted, ignored),
        `--ai-mapper-model` (accepted, ignored)
      - Run `assess()`, emit `QualityReport` list via text formatter or JSON
      - CI threshold: `--min-contract-coverage` exits 1 if avg coverage below threshold
      - Text output format per design.md (table with Function, Coverage, Status)
      - JSON output: array of QualityReport dicts (NOT wrapped in AnalysisResult)
- [x] 8.4 Update `SCHEMA` constant in `src/gaze_py/report/json_formatter.py`
      to add quality-related fields (gaze_crap, contract_coverage, quadrant,
      gaze_crapload, avg_contract_coverage, quadrant_counts, fix_strategy_counts)
- [x] 8.5 Tests for `quality` command in `tests/test_cli.py`:
      - `test_quality_runs_pipeline` — with testdata/quality/src/simple.py fixture,
        exits 0; assert `contract_coverage == 100.0` (not just non-null);
        assert `gaze_crap == complexity` (SC-002: at 100% coverage the cubic
        term vanishes, leaving exactly complexity). For the undertested fixture,
        assert `gaze_crap == complexity**2 + complexity` (0% coverage).
      - `test_quality_auto_discovers_tests` — no --tests flag; set cwd to
        `tests/testdata/quality/`; auto-discovery finds `tests/` relative to
        Path(path).parent; assert result non-empty
      - `test_quality_json_serializable` — for each report from assess() on
        the simple fixture, assert `json.dumps(dataclasses.asdict(report))`
        succeeds without TypeError (guards against TestFunc leaking into output)
      - `test_quality_min_contract_coverage_gate` — threshold exceeded → exit 1,
        stderr contains "FAIL" and the specific function name
      - `test_quality_format_text` — exits 0, text output contains "Contract
        Coverage" header and at least one function row with a percentage value;
        assert NO "Q1_Safe" / "Q4_Dangerous" quadrant labels appear (quality
        command has no line coverage → quadrants are always null)
      - `test_quality_target_flag_filters` — `--target=simple_function` →
        only reports for that function returned; other functions excluded
      - `test_quality_target_flag_no_match` — `--target=nonexistent_fn` →
        empty result, exit 0, no error
      - `test_quality_path_not_exists` — PATH doesn't exist → exit 2

## 9. CI gate

- [x] 9.1 `uv run ruff check .`
- [x] 9.2 `uv run ruff format --check .`
- [x] 9.3 `uv run mypy --strict src/`
- [x] 9.4 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`

<!-- spec-review: passed -->
<!-- code-review: passed -->