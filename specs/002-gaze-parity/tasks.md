# Tasks: gaze-py 1:1 Parity with Go gaze

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

<!-- spec-review: passed -->
<!-- code-review: passed (Story 1 — retroactive; 4 Divisors APPROVE after fixes) -->
<!-- code-review: passed (Story 2 — 4 Divisors APPROVE after 2 iterations; 18+1 findings fixed) -->

---

## Story 1: JSON Schema Compatibility — branch `opsx/schema-compat`

### Phase 1.1: New and updated model types

- [x] - [x] T101 Add `Metadata` frozen dataclass to `models.py`: `gaze_version: str`, `warnings: list[str]`, `duration_ms: int`, `timestamp: str`
- [x] - [x] T102 Add `package: str`, `receiver: str | None`, `signature: str` to `FunctionTarget` (no defaults — populated at construction; all existing call sites in `detector.py` updated in T108/T109); also rename `FunctionTarget.name` → `FunctionTarget.function` in the Python model (required so `dataclasses.asdict()` serializes as `"function"` per FR-002 and so `score_key()` in T207 can access `entry["target"]["function"]` without `KeyError`); update all internal callers of `.name` → `.function`; update `FunctionTarget` and `AnalysisResult` docstrings to document new fields and the `functions` → `results` rename respectively
- [x] - [x] T103 Add `OverSpecification` frozen dataclass: `count: int`, `ratio: float`, `incidental_assertions: list`, `suggestions: list[str]`
- [x] - [x] T104 Add `QualitySummary` dataclass: `total_tests: int`, `average_contract_coverage: float | None`, `total_over_specifications: int`, `worst_coverage_tests: list[str]` (test function names, bottom 5 by coverage), `assertion_detection_confidence: int` (mean of per-report values rounded)
- [x] - [x] T105 Add `covered_count: int`, `total_contractual: int` to `ContractCoverageResult`
- [x] - [x] T106 Add `discarded_returns: tuple[SideEffect, ...]`, `discarded_return_hints: tuple[str, ...]` to `ContractCoverageResult` (empty tuples — OC-003 compliant)
- [x] - [x] T107 Add `test_location: str`, `over_specification: OverSpecification`, `ambiguous_effects: tuple[SideEffect, ...]`, `assertion_count: int`, `assertion_detection_confidence: int` to `QualityReport`
- [x] T107b Change `QualityReport.target_function` from `str | None` to `FunctionTarget | None`; update all quality pipeline code that sets this field (pairing, mapper, assess modules)
- [x] - [x] T108 Rename `AnalysisResult.functions` → `AnalysisResult.results` in the Python model; update all internal callers (cli, formatters, tests)

### Phase 1.2: Populate new fields in the pipeline

- [x] - [x] T109 Populate `FunctionTarget.package` (= `file_path`), `receiver` (enclosing class name for methods, `None` for module-level), `signature` (AST reconstruction) in `detector.py` at construction time; update all `FunctionTarget(...)` call sites to pass the three new fields
- [x] T110 Implement `signature` reconstruction from AST `arguments` node: handle positional params, `*args`, `**kwargs`, positional-only (`/`), keyword-only (`*`), return annotation; fall back to `f"def {name}(...)"` ONLY when annotation reconstruction raises (not for variadic params)
- [x] T111 Populate `QualityReport.test_location` from test function AST node `lineno` in the quality pipeline
- [x] T112 Populate `QualityReport.over_specification`: `count` from existing `over_specification_count`, `ratio = count / assertion_count` (0.0 when 0), `incidental_assertions = []`, `suggestions = []`
- [x] T113 Populate `QualityReport.assertion_count` and `assertion_detection_confidence` (mapped / total * 100, 100 when 0 assertions)
- [x] T114 Populate `ContractCoverageResult.covered_count` and `total_contractual` from existing effect-counting logic in mapper

### Phase 1.3: JSON formatter

- [x] T115 Update `analysis_to_json()` in `json_formatter.py`: emit `{"results": [...], "summary": {...}}`; each result as `{"target": <FunctionTarget dict>, "side_effects": [...], "metadata": <Metadata dict>, <scoring fields...>}`
- [x] T116 Inject `Metadata` at serialization time: `gaze_version` from `gaze_py.__version__`, `duration_ms` from run timer (caller-supplied `time.monotonic()` delta), `timestamp` from `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`, `warnings = []`
- [x] T117 Update `quality_to_json()`: emit `{"quality_reports": [...], "quality_summary": <QualitySummary dict>}`; `target_function` is a `FunctionTarget` dict (not a bare string)
- [x] T118 Update `SCHEMA` constant in `json_formatter.py` to reflect `results`-keyed structure with `target`, `side_effects`, `metadata` per entry

### Phase 1.4: CLI wiring

- [x] T119 Update `main.py` serialization call sites: thread run-start `time.monotonic()` into `analysis_to_json()` for `duration_ms`; update all references to `result.functions` → `result.results`

### Phase 1.5: Tests

- [x] T120 Update all `test_cli.py` assertions referencing `"functions"` top-level key → `"results"` (34 occurrences)
- [x] T121 Update `test_output.py` (7 occurrences), `test_report_ai.py`, `test_config.py`, and any other files with old schema key assertions
- [x] T122 Add tests: assert `results[0]["target"]` has all five sub-keys (`package`, `function`, `receiver`, `signature`, `location`) with correct types (`str`, `str`, `str|None`, `str`, `str`)
- [x] T122b Add schema regression guard test: parse `gazepy analyze` JSON output and assert top-level key is `"results"` (not `"functions"`), `results[0]` has `"target"` key (not flat), `results[0]["target"]` has `"package"` key, `results[0]` has `"metadata"` key, `results[0]["metadata"]` has `"gaze_version"` key — this test would catch a revert to the old schema for all three structural changes
- [x] T123 Add tests: assert `results[0]["metadata"]["gaze_version"]` == `gaze_py.__version__`; `duration_ms` is a non-negative int; `timestamp` matches `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`
- [x] T124 Add tests: assert `quality_reports` and `quality_summary` top-level keys on quality JSON output; `quality_summary` has `total_tests`, `average_contract_coverage`, `worst_coverage_tests` (list of str), `assertion_detection_confidence` (int)
- [x] T125 Add tests: `over_specification`, `assertion_count`, `assertion_detection_confidence`, `test_location` present in each quality report; `over_specification.ratio` is a float in [0.0, 1.0]; include parametrized case `assertion_count = 0` → `ratio = 0.0` (no `ZeroDivisionError`)
- [x] T126 Add tests: `covered_count`, `total_contractual`, `discarded_returns` (empty list), `discarded_return_hints` (empty list) present in `contract_coverage`
- [x] T126b Add tests for `FunctionTarget` new fields: parametrize using `ast.parse()` on inline source strings (not testdata files — avoids coupling to production file content); cases: (a) `'class Foo:\n    def bar(self): pass'` → method → `receiver == "Foo"`, `function == "bar"`; (b) `'def baz(): pass'` → module-level → `receiver is None`; (c) `'def f(*args, **kwargs): pass'` → `signature` contains `*args` and `**kwargs` (not fallback `"def f(...)"`); (d) `'def g() -> int: pass'` → `"-> int"` in `signature`
- [x] T127 Add test: `gazepy schema` output contains `"results"` key and does not contain `"functions"` key
- [x] T128 Run full test suite: `uv run pytest --cov=gaze_py --cov-fail-under=85`
- [x] T129 Run lint/type gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/`

### Phase 1.6: Docs + CI

- [x] T130 Update `docs/reference/cli/analyze.md` and `docs/reference/cli/crap.md` output format descriptions to reflect `results`-keyed schema with `target`/`metadata` wrapper
- [x] T131 Update `docs/reference/cli/quality.md` output format description to reflect `quality_reports`/`quality_summary` envelope
- [x] T132 Open PR `opsx/schema-compat` → CI green → merge

---

## Story 2: `--baseline` implementation — branch `opsx/baseline` (requires S1 merged)

### Phase 2.1: Pure comparison module

- [x] T201 Create `src/gaze_py/crap/compare.py` with `FunctionStatus(enum.StrEnum)`: `REGRESSION = "regression"`, `IMPROVEMENT = "improvement"`, `UNCHANGED = "unchanged"`, `NEW = "new"`, `NEW_VIOLATION = "new_violation"`, `REMOVED = "removed"`
- [x] T202 Add `CompareOptions` dataclass: `epsilon: float = 0.0`, `new_function_threshold: float | None = None` (None → resolved at CLI wiring layer in T218 to `config.crap_threshold`; matches FR-009 and plan.md design decision; do NOT hardcode 15.0 here)
- [x] T203 Add `FunctionDelta` frozen dataclass: `baseline: dict`, `current: dict`, `crap_delta: float`, `gaze_crap_delta: float | None`, `status: FunctionStatus`
- [x] T204 Add `ComparisonSummary` dataclass: `regressions: int`, `improvements: int`, `unchanged: int`, `new_functions: int`, `new_violations: int`, `removed_functions: int`, `passed: bool`, `epsilon: float`, `new_function_threshold: float`
- [x] T205 Add `ComparisonResult` dataclass: `deltas: list[FunctionDelta]`, `new_functions: list[dict]`, `removed_functions: list[dict]`, `summary: ComparisonSummary`, `warnings: list[str] = field(default_factory=list)` (warnings are stderr-only — not serialized in JSON output)
- [x] T206 Implement `load_baseline(path: Path) -> list[dict]`: (a) read file as bytes; if `len(data) == 0` raise `ValueError(f"baseline is empty: {path}")` (matches Go behavior); (b) wrap `FileNotFoundError` → `ValueError("baseline not found: {path}; re-generate with: gazepy crap --format=json > baseline.json")`; (c) `json.load()` wrapping both `json.JSONDecodeError` and `RecursionError` → `ValueError` with actionable message including "re-generate with: gazepy crap --format=json > baseline.json"; (d) validate `results` key is present and is a `list`; raise `ValueError("baseline uses incompatible schema (missing 'results' key); re-generate with: gazepy crap --format=json > baseline.json")` if not; (e) validate each entry has `target` key as a `dict` (not string/null — raise `ValueError(f"baseline entry {i}: target must be an object")`), and that `target.package` and `target.function` keys exist; raise `ValueError` with entry index on failure; (f) empty `results` list is valid (return empty list, matches Go behavior)
- [x] T207 Implement `score_key(entry: dict) -> str`: returns `entry["target"]["package"] + ":" + entry["target"]["function"]`
- [x] T208 Implement `classify_delta(crap_delta: float, gaze_crap_delta: float | None, has_gaze_delta: bool, epsilon: float) -> FunctionStatus`: regression wins on conflict; `has_gaze_delta=False` when baseline had no GazeCRAP data (null or 0)
- [x] T209 Implement `compare(baseline: list[dict], current: list[dict], opts: CompareOptions) -> ComparisonResult`: pure function; build lookup map via `score_key`; classify each current entry; collect new/removed
- [x] T209b In `compare()`: after building results, if unmatched baseline entries > 50% of baseline count, add a warning string to a returned `warnings: list[str]` field on `ComparisonResult`; caller emits this to stderr
- [x] T210 Implement `build_comparison_summary(result: ComparisonResult, opts: CompareOptions) -> ComparisonSummary`: count statuses; `passed = regressions == 0 and new_violations == 0`; `opts.new_function_threshold` is guaranteed non-None at this call site (T218 resolves before `compare()` is called — use `assert opts.new_function_threshold is not None` before assigning to `ComparisonSummary.new_function_threshold: float`)

### Phase 2.2: Config

- [x] T211 Add `BaselineConfig` dataclass to `loader.py`: `file: str | None = None`, `epsilon: float = 0.0`, `new_function_threshold: float | None = None`
- [x] T212 Add `baseline: BaselineConfig = field(default_factory=BaselineConfig)` to `GazeConfig`
- [x] T213 Add validation in `load_config()`: `baseline.epsilon >= 0`, `baseline.new_function_threshold > 0` when set

### Phase 2.3: Output formatters

- [x] T214 Add `comparison_to_json(comparison_result: ComparisonResult, crap_summary: dict) -> str` in `json_formatter.py`: emit `{"results": [...enriched...], "new_functions": [...], "removed_functions": [...], "comparison": <summary dict>, "summary": <crap_summary>}`; each matched entry in `results` gets optional `baseline_crap`, `crap_delta`, `baseline_gaze_crap`, `gaze_crap_delta`, `status` fields; `new_functions` and `removed_functions` entries include `status`
- [x] T215 Add `comparison_to_text(crap_text: str, result: ComparisonResult) -> str`: crap text + `\n--- Baseline Comparison: PASS/FAIL ---\n` + counts line + regressions table + improvements table + new violations list + removed list; empty sections omitted

### Phase 2.4: CLI wiring

- [x] T216 Add `resolve_baseline_path(flag_path: str | None, config: GazeConfig, project_root: Path) -> tuple[Path | None, bool]`: (1) `--baseline` flag → `(Path(flag_path), True)` (explicit); (2) `config.baseline.file` not None → `(Path(config.baseline.file), True)` (explicit); (3) auto-discovery: check `project_root / ".gaze" / "baseline.json"` — return `(path, False)` if it exists as a regular file, `(None, False)` if absent or directory. For explicit paths: if file not found → caller exits 2; if path is a directory → caller exits 2.
- [x] T217 Update `crap` command: update `--baseline` help (remove "stub: not yet implemented"); after running CRAP, call `resolve_baseline_path()`; if `None`, skip; else `load_baseline()` wrapping errors: when `is_explicit=True` and `ValueError` → exit 2; when `is_explicit=False` and `ValueError` (auto-discovered file gone or corrupt) → emit stderr warning and skip (do NOT exit 2); compare and emit; for each `result.warnings` entry emit to stderr; apply gate (exit 1 if `not passed`)
- [x] T218 Wire `CompareOptions`: `epsilon = config.baseline.epsilon`, `new_function_threshold = config.baseline.new_function_threshold if config.baseline.new_function_threshold is not None else config.crap_threshold` — use explicit `is not None` check (not `or`) to avoid silently overriding a valid 0.0 value

### Phase 2.5: Tests

- [x] T219 Create `tests/test_crap_compare.py`: unit tests for `compare()`, `classify_delta()`, `build_comparison_summary()`, `load_baseline()`
- [x] T220 Test `classify_delta()` parametrized with all cases: (a) CRAP regression only → `regression`; (b) GazeCRAP regression only → `regression`; (c) CRAP regression + GazeCRAP improvement → `regression` (regression wins); (d) CRAP improvement + GazeCRAP regression → `regression` (regression wins); (e) both improve → `improvement`; (f) CRAP within epsilon → `unchanged`; (g1) `has_gaze_delta=False` + CRAP regresses → `regression` (GazeCRAP skipped, CRAP dominates); (g2) `has_gaze_delta=False` + CRAP within epsilon → `unchanged`
- [x] T221 Test `compare()`: (a) new function below threshold → status `new`; assert `result.new_functions` contains the entry; (b) new function above threshold → `new_violation`; (c) removed function → in `result.removed_functions`; (d) matched regression → in `result.deltas` with `status=REGRESSION`; assert `result.summary.regressions == 1`, `summary.passed == false`; (e) no regression → `summary.passed == true`; (f) > 50% baseline functions unmatched → `len(result.warnings) > 0`; assert `result.warnings[0]` contains "unmatched"
- [x] T222 Test `load_baseline()` error paths: (a) missing file → `ValueError` with "re-generate" in message; (b) empty file (zero bytes) → `ValueError` with "empty" in message; (c) malformed JSON → `ValueError` with actionable message (not raw `JSONDecodeError`); (d) `{"functions": [...]}` old schema → `ValueError` with "incompatible schema" in message; (e) `{"results": null}` → `ValueError`; (f) `{"results": []}` → empty list (no error); (g) entry with `"target": "string"` (non-dict) → `ValueError` with "target must be an object"; (h) entry missing `target.function` → `ValueError` with entry index
- [x] T223 CLI integration tests using `tmp_path`: write minimal Python source + synthetic baseline JSON (new schema) to `tmp_path`; do NOT use real project source as analysis target; `--baseline` missing file → exit 2; regression (CRAP increased from baseline) → exit 1 + JSON output contains `comparison.passed == false`; no regression → exit 0 + `comparison.passed == true`; auto-discovery: write `.gaze/baseline.json` inside `tmp_path`, invoke CLI with `cwd=tmp_path` → assert `comparison.passed` is present in JSON output (confirming baseline was loaded and comparison ran, not silently skipped)
- [x] T224 Test `baseline.epsilon` config from `.gaze.yaml`: delta ≤ epsilon → `unchanged`; delta > epsilon → `regression`
- [x] T225 Test `baseline.new_function_threshold` config: (a) threshold = 20.0, new function CRAP = 18.0 → status `new`; (b) threshold = 20.0, new function CRAP = 25.0 → `new_violation`; (c) threshold not set in config (`None`) → resolves to `crap_threshold` (15.0 default): new function CRAP = 18.0 → `new_violation`; verify full flow from `.gaze.yaml` through `BaselineConfig` → `CompareOptions.new_function_threshold`
- [x] T226 Test `comparison_to_text()`: assert `"--- Baseline Comparison: PASS ---"` when `passed=True`; `"FAIL"` when `passed=False`; regression table present when regressions > 0; "Improvements" section absent when improvements == 0
- [x] T227 Run full test suite: `uv run pytest --cov=gaze_py --cov-fail-under=85`
- [x] T228 Run lint/type gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/`

### Phase 2.6: Docs + CI

- [x] T229 Update `docs/reference/cli/crap.md`: document `--baseline` as implemented; add auto-discovery behavior; add `.gaze.yaml` config keys table (`baseline.file: str|null`, `baseline.epsilon: float`, `baseline.new_function_threshold: float|null`); add baseline edge cases (file-rename false positives, corrupt file behavior)
- [ ] T230 Open PR `opsx/baseline` → CI green → merge

---

## Story 3: Stale content / docs cleanup — branch `opsx/parity-cleanup`

- [ ] T301 Delete stale comment in `main.py`: `# report command (not yet implemented — requires O2)` (search by content, not line number — line may have shifted)
- [ ] T302 Rewrite `docs/reference/cli/report.md`: remove `--ai`/`--ai-timeout` option rows, remove "requires O1+O2" note, add `.gaze.yaml` `ai:` section config reference, add `GAZEPY_AI_*` env var table, correct description to "direct HTTP" (not "subprocess")
- [ ] T303 Consolidate `CHANGELOG.md [Unreleased]` → `## [0.7.0]`: one each of `### Added`, `### Changed`, `### Removed`, `### Breaking Changes` (omitting empty sections); no duplicate headers; no `Spec:` references (including the missing entries listed below); `### Breaking Changes` includes JSON schema migration notice (FR-001, FR-004) with before/after examples; missing entries to add (all without `Spec:` references): docs tree, `_matches_cache_decorator` refactor, python-native detection patterns, AI HTTP adapters
- [ ] T304 Bump `pyproject.toml` `version` → `0.7.0`
- [ ] T305 Bump `src/gaze_py/__init__.py` `__version__` → `0.7.0`
- [ ] T306 Remove `pip` ecosystem entry from `.github/dependabot.yml` (retain `github-actions`); per constitution v1.1.3 SYNC IMPACT REPORT
- [ ] T307 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` — all clean
- [ ] T308 Open PR `opsx/parity-cleanup` → CI green → merge

---

## Story 4: Release v0.7.0

- [ ] T300.5 Verify PyPI history: `curl -sf https://pypi.org/pypi/gaze-py/json | python3 -c "import sys,json; vers=json.load(sys.stdin)['releases']; print(sorted(vers.keys()))"` (use `-f` to fail on HTTP error; if curl fails treat as "no versions published" and document); confirm no version ≥ 0.5.0 published; if found, escalate to 1.0.0 and update all version references
- [ ] T401 Update `release.yml`: (a) add a `test` job that runs `uv run pytest --cov=gaze_py --cov-fail-under=85` using `astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0` with `version: "0.11.21"` — identical pin to existing jobs; (b) make `publish` job `needs: [preflight, test]`; (c) **reorder `publish` job steps**: run PyPI publish BEFORE pushing the git tag (swap current steps 2 and 3) so a failed publish does not leave an orphaned tag that permanently blocks retry via the tag-uniqueness preflight check; (d) verify with `yq '.jobs.publish.needs' .github/workflows/release.yml` that both `preflight` and `test` are listed; (e) add `gh release create` step after smoke test using CHANGELOG section for notes
- [ ] T402 Confirm `main` has S1 + S2 + S3 all merged; confirm `pyproject.toml` = `0.7.0`, `__init__.py` `__version__` = `0.7.0`; **T403 is blocked by T401 — do not trigger the release workflow until T401 is merged to main**
- [ ] T403 Trigger `release.yml` (blocked by T401): GitHub Actions → Release → Run workflow → tag `v0.7.0`
- [ ] T404 Approve `pypi` environment gate when prompted
- [ ] T405 Confirm smoke test passes in workflow: `gazepy --version` outputs `0.7.0`
- [ ] T406 Confirm PyPI listing: `https://pypi.org/project/gaze-py/0.7.0/`
- [ ] T407 Install locally: `uv tool install --force "gaze-py==0.7.0" && gazepy --version`
- [ ] T408 Verify `openspec/changes/archive/002-deferred-capabilities/` is correctly archived (already done). Confirm open items C.3 (O6 full — `.coverage` binary format), G.1 (return-None annotation evaluation), G.2 (37 vs 38 type count verification with Go maintainers) are tracked in a new spec or issue. This task does NOT gate T403 — it is post-release housekeeping.
