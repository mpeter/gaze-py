# Tasks: gaze-py 1:1 Parity with Go gaze

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Story 1: JSON Schema Compatibility — branch `opsx/schema-compat`

### Phase 1.1: New and updated model types

- [ ] T101 Add `Metadata` frozen dataclass to `models.py`: `gaze_version: str`, `warnings: list[str]`, `duration_ms: int`, `timestamp: str`
- [ ] T102 Add `package: str`, `receiver: str | None`, `signature: str` to `FunctionTarget` (no defaults — populated at construction; all existing call sites in `detector.py` updated in T108/T109)
- [ ] T103 Add `OverSpecification` frozen dataclass: `count: int`, `ratio: float`, `incidental_assertions: list`, `suggestions: list[str]`
- [ ] T104 Add `QualitySummary` dataclass: `total_tests: int`, `average_contract_coverage: float | None`, `total_over_specifications: int`, `worst_coverage_tests: list[str]` (test function names, bottom 5 by coverage), `assertion_detection_confidence: int` (mean of per-report values rounded)
- [ ] T105 Add `covered_count: int`, `total_contractual: int` to `ContractCoverageResult`
- [ ] T106 Add `discarded_returns: tuple[SideEffect, ...]`, `discarded_return_hints: tuple[str, ...]` to `ContractCoverageResult` (empty tuples — OC-003 compliant)
- [ ] T107 Add `test_location: str`, `over_specification: OverSpecification`, `ambiguous_effects: tuple[SideEffect, ...]`, `assertion_count: int`, `assertion_detection_confidence: int` to `QualityReport`
- [ ] T107b Change `QualityReport.target_function` from `str | None` to `FunctionTarget | None`; update all quality pipeline code that sets this field (pairing, mapper, assess modules)
- [ ] T108 Rename `AnalysisResult.functions` → `AnalysisResult.results` in the Python model; update all internal callers (cli, formatters, tests)

### Phase 1.2: Populate new fields in the pipeline

- [ ] T109 Populate `FunctionTarget.package` (= `file_path`), `receiver` (enclosing class name for methods, `None` for module-level), `signature` (AST reconstruction) in `detector.py` at construction time; update all `FunctionTarget(...)` call sites to pass the three new fields
- [ ] T110 Implement `signature` reconstruction from AST `arguments` node: handle positional params, `*args`, `**kwargs`, positional-only (`/`), keyword-only (`*`), return annotation; fall back to `f"def {name}(...)"` ONLY when annotation reconstruction raises (not for variadic params)
- [ ] T111 Populate `QualityReport.test_location` from test function AST node `lineno` in the quality pipeline
- [ ] T112 Populate `QualityReport.over_specification`: `count` from existing `over_specification_count`, `ratio = count / assertion_count` (0.0 when 0), `incidental_assertions = []`, `suggestions = []`
- [ ] T113 Populate `QualityReport.assertion_count` and `assertion_detection_confidence` (mapped / total * 100, 100 when 0 assertions)
- [ ] T114 Populate `ContractCoverageResult.covered_count` and `total_contractual` from existing effect-counting logic in mapper

### Phase 1.3: JSON formatter

- [ ] T115 Update `analysis_to_json()` in `json_formatter.py`: emit `{"results": [...], "summary": {...}}`; each result as `{"target": <FunctionTarget dict>, "side_effects": [...], "metadata": <Metadata dict>, <scoring fields...>}`
- [ ] T116 Inject `Metadata` at serialization time: `gaze_version` from `gaze_py.__version__`, `duration_ms` from run timer (caller-supplied `time.monotonic()` delta), `timestamp` from `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`, `warnings = []`
- [ ] T117 Update `quality_to_json()`: emit `{"quality_reports": [...], "quality_summary": <QualitySummary dict>}`; `target_function` is a `FunctionTarget` dict (not a bare string)
- [ ] T118 Update `SCHEMA` constant in `json_formatter.py` to reflect `results`-keyed structure with `target`, `side_effects`, `metadata` per entry

### Phase 1.4: CLI wiring

- [ ] T119 Update `main.py` serialization call sites: thread run-start `time.monotonic()` into `analysis_to_json()` for `duration_ms`; update all references to `result.functions` → `result.results`

### Phase 1.5: Tests

- [ ] T120 Update all `test_cli.py` assertions referencing `"functions"` top-level key → `"results"` (34 occurrences)
- [ ] T121 Update `test_output.py` (7 occurrences), `test_report_ai.py`, `test_config.py`, and any other files with old schema key assertions
- [ ] T122 Add tests: assert `results[0]["target"]` has all five sub-keys (`package`, `function`, `receiver`, `signature`, `location`) with correct types (`str`, `str`, `str|None`, `str`, `str`)
- [ ] T122b Add schema regression guard test: parse `gazepy analyze` JSON output and assert top-level key is `"results"` (not `"functions"`), `results[0]` has `"target"` key (not flat), `results[0]["target"]` has `"package"` key — this test would catch a revert to the old schema
- [ ] T123 Add tests: assert `results[0]["metadata"]["gaze_version"]` == `gaze_py.__version__`; `duration_ms` is a non-negative int; `timestamp` matches `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`
- [ ] T124 Add tests: assert `quality_reports` and `quality_summary` top-level keys on quality JSON output; `quality_summary` has `total_tests`, `average_contract_coverage`, `worst_coverage_tests` (list of str), `assertion_detection_confidence` (int)
- [ ] T125 Add tests: `over_specification`, `assertion_count`, `assertion_detection_confidence`, `test_location` present in each quality report; `over_specification.ratio` is a float in [0.0, 1.0]
- [ ] T126 Add tests: `covered_count`, `total_contractual`, `discarded_returns` (empty list), `discarded_return_hints` (empty list) present in `contract_coverage`
- [ ] T126b Add tests for `FunctionTarget` new fields: parametrize with (a) method → `receiver` == class name, (b) module-level function → `receiver` is `null`; (c) function with `*args`/`**kwargs` → `signature` contains `*args` / `**kwargs` (not fallback); (d) function with simple return annotation → annotation appears in `signature`
- [ ] T127 Add test: `gazepy schema` output contains `"results"` key and does not contain `"functions"` key
- [ ] T128 Run full test suite: `uv run pytest --cov=gaze_py --cov-fail-under=85`
- [ ] T129 Run lint/type gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/`

### Phase 1.6: Docs + CI

- [ ] T130 Update `docs/reference/cli/analyze.md` and `docs/reference/cli/crap.md` output format descriptions to reflect `results`-keyed schema with `target`/`metadata` wrapper
- [ ] T131 Update `docs/reference/cli/quality.md` output format description to reflect `quality_reports`/`quality_summary` envelope
- [ ] T132 Open PR `opsx/schema-compat` → CI green → merge

---

## Story 2: `--baseline` implementation — branch `opsx/baseline` (requires S1 merged)

### Phase 2.1: Pure comparison module

- [ ] T201 Create `src/gaze_py/crap/compare.py` with `FunctionStatus(enum.StrEnum)`: `REGRESSION = "regression"`, `IMPROVEMENT = "improvement"`, `UNCHANGED = "unchanged"`, `NEW = "new"`, `NEW_VIOLATION = "new_violation"`, `REMOVED = "removed"`
- [ ] T202 Add `CompareOptions` dataclass: `epsilon: float = 0.0`, `new_function_threshold: float = 15.0`
- [ ] T203 Add `FunctionDelta` frozen dataclass: `baseline: dict`, `current: dict`, `crap_delta: float`, `gaze_crap_delta: float | None`, `status: FunctionStatus`
- [ ] T204 Add `ComparisonSummary` dataclass: `regressions: int`, `improvements: int`, `unchanged: int`, `new_functions: int`, `new_violations: int`, `removed_functions: int`, `passed: bool`, `epsilon: float`, `new_function_threshold: float`
- [ ] T205 Add `ComparisonResult` dataclass: `deltas: list[FunctionDelta]`, `new_functions: list[dict]`, `removed_functions: list[dict]`, `summary: ComparisonSummary`
- [ ] T206 Implement `load_baseline(path: Path) -> list[dict]`: (a) read file; wrap `FileNotFoundError` → `ValueError("baseline not found: {path}; re-generate with: gazepy crap --format=json > baseline.json")`; (b) `json.load()` wrapping both `json.JSONDecodeError` and `RecursionError` → `ValueError` with actionable message; (c) validate `results` key is present and is a `list`; raise `ValueError("baseline uses incompatible schema (missing 'results' key); re-generate with: gazepy crap --format=json > baseline.json")` if not; (d) validate each entry has `target.package` and `target.function` keys, raise `ValueError` with entry index on failure; (e) empty `results` list is valid (return empty list, matches Go behavior)
- [ ] T207 Implement `score_key(entry: dict) -> str`: returns `entry["target"]["package"] + ":" + entry["target"]["function"]`
- [ ] T208 Implement `classify_delta(crap_delta: float, gaze_crap_delta: float | None, has_gaze_delta: bool, epsilon: float) -> FunctionStatus`: regression wins on conflict; `has_gaze_delta=False` when baseline had no GazeCRAP data (null or 0)
- [ ] T209 Implement `compare(baseline: list[dict], current: list[dict], opts: CompareOptions) -> ComparisonResult`: pure function; build lookup map via `score_key`; classify each current entry; collect new/removed
- [ ] T209b In `compare()`: after building results, if unmatched baseline entries > 50% of baseline count, add a warning string to a returned `warnings: list[str]` field on `ComparisonResult`; caller emits this to stderr
- [ ] T210 Implement `build_comparison_summary(result: ComparisonResult, opts: CompareOptions) -> ComparisonSummary`: count statuses; `passed = regressions == 0 and new_violations == 0`

### Phase 2.2: Config

- [ ] T211 Add `BaselineConfig` dataclass to `loader.py`: `file: str | None = None`, `epsilon: float = 0.0`, `new_function_threshold: float | None = None`
- [ ] T212 Add `baseline: BaselineConfig = field(default_factory=BaselineConfig)` to `GazeConfig`
- [ ] T213 Add validation in `load_config()`: `baseline.epsilon >= 0`, `baseline.new_function_threshold > 0` when set

### Phase 2.3: Output formatters

- [ ] T214 Add `comparison_to_json(comparison_result: ComparisonResult, crap_summary: dict) -> str` in `json_formatter.py`: emit `{"results": [...enriched...], "new_functions": [...], "removed_functions": [...], "comparison": <summary dict>, "summary": <crap_summary>}`; each matched entry in `results` gets optional `baseline_crap`, `crap_delta`, `baseline_gaze_crap`, `gaze_crap_delta`, `status` fields; `new_functions` and `removed_functions` entries include `status`
- [ ] T215 Add `comparison_to_text(crap_text: str, result: ComparisonResult) -> str`: crap text + `\n--- Baseline Comparison: PASS/FAIL ---\n` + counts line + regressions table + improvements table + new violations list + removed list; empty sections omitted

### Phase 2.4: CLI wiring

- [ ] T216 Add `resolve_baseline_path(flag_path: str | None, config: GazeConfig, project_root: Path) -> tuple[Path | None, bool]`: (1) `--baseline` flag → `(Path(flag_path), True)` (explicit); (2) `config.baseline.file` not None → `(Path(config.baseline.file), True)` (explicit); (3) auto-discovery: check `project_root / ".gaze" / "baseline.json"` — return `(path, False)` if it exists as a regular file, `(None, False)` if absent or directory. For explicit paths: if file not found → caller exits 2; if path is a directory → caller exits 2.
- [ ] T217 Update `crap` command: update `--baseline` help (remove "stub: not yet implemented"); after running CRAP, call `resolve_baseline_path()`; if `None`, skip; else `load_baseline()` wrapping errors → exit 2 on `ValueError` (explicit) or stderr warning + skip (auto-discovered); compare and emit; apply gate (exit 1 if `not passed`)
- [ ] T218 Wire `CompareOptions`: `epsilon = config.baseline.epsilon`, `new_function_threshold = config.baseline.new_function_threshold or config.crap_threshold`

### Phase 2.5: Tests

- [ ] T219 Create `tests/test_crap_compare.py`: unit tests for `compare()`, `classify_delta()`, `build_comparison_summary()`, `load_baseline()`
- [ ] T220 Test `classify_delta()` parametrized with all cases: (a) CRAP regression only → `regression`; (b) GazeCRAP regression only → `regression`; (c) CRAP regression + GazeCRAP improvement → `regression` (regression wins); (d) CRAP improvement + GazeCRAP regression → `regression` (regression wins); (e) both improve → `improvement`; (f) CRAP within epsilon → `unchanged`; (g) `has_gaze_delta=False` (baseline had no GazeCRAP) → classify based on CRAP only
- [ ] T221 Test `compare()`: new function below threshold → `new`; new function above threshold → `new_violation`; removed function in `removed_functions`; matched regression; `passed` true/false logic; > 50% unmatched → warning in `result.warnings`
- [ ] T222 Test `load_baseline()` error paths: (a) missing file → `ValueError` with "re-generate" in message; (b) malformed JSON → `ValueError` with "parsing baseline" in message; (c) `{"functions": [...]}` old schema → `ValueError` with "incompatible schema" in message; (d) `{"results": null}` → `ValueError`; (e) `{"results": []}` → empty list (no error); (f) entry missing `target.function` → `ValueError` with entry index
- [ ] T223 CLI integration tests using `tmp_path`: write minimal Python source + synthetic baseline JSON; `--baseline` missing file → exit 2; regression (CRAP increased) → exit 1 + `comparison.passed == false`; no regression → exit 0 + `comparison.passed == true`; auto-discovery: write `.gaze/baseline.json` in `tmp_path`, invoke CLI with `cwd=tmp_path` → comparison runs
- [ ] T224 Test `baseline.epsilon` config from `.gaze.yaml`: delta ≤ epsilon → `unchanged`; delta > epsilon → `regression`
- [ ] T225 Test `baseline.new_function_threshold` config: new function CRAP = 18.0, threshold = 20.0 → status `new` (not `new_violation`); new function CRAP = 25.0, threshold = 20.0 → `new_violation`; verify flow from `.gaze.yaml` through `CompareOptions`
- [ ] T226 Test `comparison_to_text()`: assert `"--- Baseline Comparison: PASS ---"` when `passed=True`; `"FAIL"` when `passed=False`; regression table present when regressions > 0; "Improvements" section absent when improvements == 0
- [ ] T227 Run full test suite: `uv run pytest --cov=gaze_py --cov-fail-under=85`
- [ ] T228 Run lint/type gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/`

### Phase 2.6: Docs + CI

- [ ] T229 Update `docs/reference/cli/crap.md`: document `--baseline` as implemented; add auto-discovery behavior; add `.gaze.yaml` config keys table (`baseline.file: str|null`, `baseline.epsilon: float`, `baseline.new_function_threshold: float|null`); add baseline edge cases (file-rename false positives, corrupt file behavior)
- [ ] T230 Open PR `opsx/baseline` → CI green → merge

---

## Story 3: Stale content / docs cleanup — branch `opsx/parity-cleanup`

- [ ] T301 Delete stale comment in `main.py`: `# report command (not yet implemented — requires O2)` (search by content, not line number — line may have shifted)
- [ ] T302 Rewrite `docs/reference/cli/report.md`: remove `--ai`/`--ai-timeout` option rows, remove "requires O1+O2" note, add `.gaze.yaml` `ai:` section config reference, add `GAZEPY_AI_*` env var table, correct description to "direct HTTP" (not "subprocess")
- [ ] T303 Consolidate `CHANGELOG.md [Unreleased]` → `## [0.7.0]`: one each of `### Added`, `### Changed`, `### Removed`, `### Breaking Changes` (omitting empty sections); no duplicate headers; no `Spec:` references; `### Breaking Changes` includes JSON schema migration notice (FR-001, FR-004) with before/after examples; missing entries: docs tree, `_matches_cache_decorator` refactor, python-native detection patterns, AI HTTP adapters
- [ ] T304 Bump `pyproject.toml` `version` → `0.7.0`
- [ ] T305 Bump `src/gaze_py/__init__.py` `__version__` → `0.7.0`
- [ ] T306 Remove `pip` ecosystem entry from `.github/dependabot.yml` (retain `github-actions`); per constitution v1.1.3 SYNC IMPACT REPORT
- [ ] T307 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` — all clean
- [ ] T308 Open PR `opsx/parity-cleanup` → CI green → merge

---

## Story 4: Release v0.7.0

- [ ] T300.5 Verify PyPI history: `curl -s https://pypi.org/pypi/gaze-py/json | python3 -c "import sys,json; vers=json.load(sys.stdin)['releases']; print(sorted(vers.keys()))"` — confirm no version ≥ 0.5.0 published; if found, escalate to 1.0.0 and update all version references
- [ ] T401 Update `release.yml`: add a `test` job that runs `uv run pytest --cov=gaze_py --cov-fail-under=85` on the release commit; make `publish` job depend on `test` job passing (FR-012)
- [ ] T402 Confirm `main` has S1 + S2 + S3 all merged; confirm `pyproject.toml` = `0.7.0`, `__init__.py` `__version__` = `0.7.0`
- [ ] T403 Trigger `release.yml`: GitHub Actions → Release → Run workflow → tag `v0.7.0`
- [ ] T404 Approve `pypi` environment gate when prompted
- [ ] T405 Confirm smoke test passes in workflow: `gazepy --version` outputs `0.7.0`
- [ ] T406 Confirm PyPI listing: `https://pypi.org/project/gaze-py/0.7.0/`
- [ ] T407 Install locally: `uv tool install --force "gaze-py==0.7.0" && gazepy --version`
- [ ] T408 Archive `openspec/changes/002-deferred-capabilities` — note: C.3 (O6 full — `.coverage` binary format), G.1 (return-None annotation evaluation), G.2 (37 vs 38 type count verification with Go maintainers) remain open and must be tracked in a new spec before archiving
