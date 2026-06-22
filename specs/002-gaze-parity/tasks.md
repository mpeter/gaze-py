# Tasks: gaze-py 1:1 Parity with Go gaze

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Story 1: JSON Schema Compatibility — branch `opsx/schema-compat`

### Phase 1.1: New and updated model types

- [ ] T101 Add `Metadata` frozen dataclass to `models.py`: `gaze_version: str`, `warnings: list[str]`, `duration_ms: int`, `timestamp: str` (ISO 8601 UTC string)
- [ ] T102 Add `package: str`, `receiver: str | None`, `signature: str` fields to `FunctionTarget`
- [ ] T103 Add `OverSpecification` frozen dataclass to `models.py`: `count: int`, `ratio: float`, `incidental_assertions: list`, `suggestions: list[str]`
- [ ] T104 Add `QualitySummary` dataclass to `models.py`: `total_tests: int`, `average_contract_coverage: float | None`, `total_over_specifications: int`, `worst_coverage_tests: list`, `assertion_detection_confidence: int`
- [ ] T105 Add `covered_count: int`, `total_contractual: int` to `ContractCoverageResult`
- [ ] T106 Add `discarded_returns: tuple[SideEffect, ...]`, `discarded_return_hints: tuple[str, ...]` to `ContractCoverageResult` (empty tuples — OC-003 compliant)
- [ ] T107 Add `test_location: str`, `over_specification: OverSpecification`, `ambiguous_effects: tuple[SideEffect, ...]`, `assertion_count: int`, `assertion_detection_confidence: int` to `QualityReport`

### Phase 1.2: Populate new fields in the pipeline

- [ ] T108 Populate `FunctionTarget.package` (= `file_path`) and `receiver` (enclosing class name for methods, `None` otherwise) in `analysis/detector.py` during function node construction
- [ ] T109 Populate `FunctionTarget.signature` from AST `arguments` node in `detector.py`; fall back to `"def <name>(...)"` for complex cases (e.g., `*args`, `**kwargs` with annotations)
- [ ] T110 Populate `QualityReport.test_location` from test function's AST node `lineno` in the quality pipeline
- [ ] T111 Populate `QualityReport.over_specification` in the quality pipeline: `count` from existing `over_specification_count`, `ratio = count / assertion_count` (0.0 when 0), `incidental_assertions = []`, `suggestions = []`
- [ ] T112 Populate `QualityReport.assertion_count` (total detected assertion sites) and `assertion_detection_confidence` (mapped / total * 100, 100 when 0 assertions) in the quality pipeline
- [ ] T113 Populate `ContractCoverageResult.covered_count` and `total_contractual` from existing effect-counting logic in the quality mapper

### Phase 1.3: JSON formatter

- [ ] T114 Update `analysis_to_json()` in `json_formatter.py`: emit `{"results": [...], "summary": {...}}` — each result as `{"target": <FunctionTarget dict>, "side_effects": [...], "metadata": <Metadata dict>, <score fields...>}`
- [ ] T115 Inject `Metadata` at serialization time in `analysis_to_json()`: `gaze_version` from `gaze_py.__version__`, `duration_ms` from caller-supplied timer, `timestamp` as `datetime.now(UTC).isoformat()`, `warnings = []`
- [ ] T116 Update `quality_to_json()`: emit `{"quality_reports": [...], "quality_summary": <QualitySummary dict>}`; `target_function` field is a `FunctionTarget` dict (not a bare string)
- [ ] T117 Update `SCHEMA` constant in `json_formatter.py` to reflect `results`-keyed structure with `target`, `side_effects`, `metadata` per entry
- [ ] T118 Verify `gazepy schema` output matches the updated `SCHEMA` constant

### Phase 1.4: CLI wiring

- [ ] T119 Update `main.py` serialization call sites: pass run-start `time.monotonic()` to `analysis_to_json()` for `duration_ms` computation; remove any remaining references to `result.functions` → `result.results` (or update internal pipeline as needed)

### Phase 1.5: Tests

- [ ] T120 Update all `test_cli.py` assertions that reference `"functions"` top-level key → `"results"`
- [ ] T121 Update `test_report_ai.py`, `test_config.py`, and any other test files with old schema key assertions
- [ ] T122 Add tests: assert `results[0]["target"]["package"]`, `["function"]`, `["receiver"]`, `["signature"]`, `["location"]` are all present and correctly typed
- [ ] T123 Add tests: assert `results[0]["metadata"]["gaze_version"]` equals `gaze_py.__version__`; `duration_ms` is a non-negative int; `timestamp` is an ISO 8601 string
- [ ] T124 Add tests: assert `quality_reports` and `quality_summary` top-level keys on quality JSON output
- [ ] T125 Add tests: assert `over_specification`, `assertion_count`, `assertion_detection_confidence`, `test_location` present in each quality report
- [ ] T126 Add tests: assert `covered_count`, `total_contractual`, `discarded_returns`, `discarded_return_hints` present in `contract_coverage`
- [ ] T127 Run full test suite: `uv run pytest --cov=gaze_py --cov-fail-under=85`
- [ ] T128 Run lint/type gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/`

### Phase 1.6: Docs + CI

- [ ] T129 Update `docs/reference/cli/analyze.md` and `docs/reference/cli/crap.md` output format descriptions to reflect `results`-keyed schema
- [ ] T130 Update `docs/reference/cli/quality.md` output format description to reflect `quality_reports`/`quality_summary` envelope
- [ ] T131 Open PR `opsx/schema-compat` → CI green → merge

---

## Story 2: `--baseline` implementation — branch `opsx/baseline` (requires S1 merged)

### Phase 2.1: Pure comparison module

- [ ] T201 Create `src/gaze_py/crap/compare.py` with `FunctionStatus(enum.StrEnum)`: `REGRESSION = "regression"`, `IMPROVEMENT = "improvement"`, `UNCHANGED = "unchanged"`, `NEW = "new"`, `NEW_VIOLATION = "new_violation"`, `REMOVED = "removed"`
- [ ] T202 Add `CompareOptions` dataclass: `epsilon: float = 0.0`, `new_function_threshold: float = 15.0`
- [ ] T203 Add `FunctionDelta` frozen dataclass: `baseline: dict`, `current: dict`, `crap_delta: float`, `gaze_crap_delta: float | None`, `status: FunctionStatus`
- [ ] T204 Add `ComparisonSummary` dataclass: `regressions: int`, `improvements: int`, `unchanged: int`, `new_functions: int`, `new_violations: int`, `removed_functions: int`, `passed: bool`, `epsilon: float`, `new_function_threshold: float`
- [ ] T205 Add `ComparisonResult` dataclass: `deltas: list[FunctionDelta]`, `new_functions: list[dict]`, `removed_functions: list[dict]`, `summary: ComparisonSummary`
- [ ] T206 Implement `load_baseline(path: Path) -> list[dict]` — open file, `json.load()`, validate `results` key present; raise `ValueError` with clear message on parse failure or empty/missing `results`
- [ ] T207 Implement `score_key(entry: dict) -> str` — returns `entry["target"]["package"] + ":" + entry["target"]["function"]`
- [ ] T208 Implement `classify_delta(crap_delta: float, gaze_crap_delta: float | None, epsilon: float) -> FunctionStatus` — regression wins on conflict; pure function
- [ ] T209 Implement `compare(baseline: list[dict], current: list[dict], opts: CompareOptions) -> ComparisonResult` — pure function; build lookup map, classify each function, collect new/removed
- [ ] T210 Implement `build_comparison_summary(result: ComparisonResult, opts: CompareOptions) -> ComparisonSummary` — count statuses, set `passed = regressions == 0 and new_violations == 0`

### Phase 2.2: Config

- [ ] T211 Add `BaselineConfig` dataclass to `loader.py`: `file: str = ".gaze/baseline.json"`, `epsilon: float = 0.0`, `new_function_threshold: float | None = None`
- [ ] T212 Add `baseline: BaselineConfig = field(default_factory=BaselineConfig)` to `GazeConfig`
- [ ] T213 Add validation in `load_config()`: `baseline.epsilon >= 0`, `baseline.new_function_threshold > 0` when set

### Phase 2.3: Output formatters

- [ ] T214 Add `comparison_to_json(current_output: dict, result: ComparisonResult) -> str` in `json_formatter.py`: emit `{"scores": [...enriched...], "new_functions": [...], "removed_functions": [...], "comparison": <summary dict>, "summary": <crap_summary dict>}`; each score in `scores` gets optional `baseline_crap`, `crap_delta`, `baseline_gaze_crap`, `gaze_crap_delta`, `status` fields
- [ ] T215 Add `comparison_to_text(crap_text: str, result: ComparisonResult) -> str`: crap text + `\n--- Baseline Comparison: PASS/FAIL ---\n` + counts line + regressions table + improvements table + new violations list + removed list; empty sections omitted

### Phase 2.4: CLI wiring

- [ ] T216 Add `resolve_baseline_path(flag_path: str | None, config: GazeConfig, project_root: Path) -> tuple[Path | None, bool]` helper in `main.py`: `--baseline` flag > `config.baseline.file` (non-default) > `.gaze/baseline.json` auto-discovery; returns `(path_or_None, explicit: bool)`
- [ ] T217 Update `crap` command: change `--baseline` help text (remove "stub: not yet implemented"); after running CRAP, call `resolve_baseline_path()`, skip if `None`; load and compare if path found; emit comparison output; apply gate (exit 1 if `not passed`)
- [ ] T218 Wire `CompareOptions` from config: `epsilon = config.baseline.epsilon`, `new_function_threshold = config.baseline.new_function_threshold or config.crap_threshold`

### Phase 2.5: Tests

- [ ] T219 Create `tests/test_crap_compare.py`: unit tests for `compare()`, `classify_delta()`, `build_comparison_summary()`, `load_baseline()` — no CLI, no I/O except `load_baseline` file read
- [ ] T220 Test `classify_delta`: regression case, improvement case, unchanged (within epsilon), conflict (CRAP up + GazeCRAP down → regression)
- [ ] T221 Test `compare()`: new function below threshold → `new`; new function above threshold → `new_violation`; removed function; matched regression; `passed` true/false logic
- [ ] T222 Add CLI integration tests: `--baseline` missing file → exit 2; regression → exit 1 + `passed: false`; no regression → exit 0 + `passed: true`; auto-discovery (`.gaze/baseline.json` present) → comparison runs
- [ ] T223 Test `baseline.epsilon` config: delta within epsilon → `unchanged`
- [ ] T224 Run full test suite: `uv run pytest --cov=gaze_py --cov-fail-under=85`
- [ ] T225 Run lint/type gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/`

### Phase 2.6: Docs + CI

- [ ] T226 Update `docs/reference/cli/crap.md`: document `--baseline` as implemented; add auto-discovery behavior; add `.gaze.yaml` config keys table (`baseline.file`, `baseline.epsilon`, `baseline.new_function_threshold`)
- [ ] T227 Open PR `opsx/baseline` → CI green → merge

---

## Story 3: Stale content / docs cleanup — branch `opsx/parity-cleanup`

- [ ] T301 Delete stale comment at `main.py` ~line 846: `# report command (not yet implemented — requires O2)`
- [ ] T302 Rewrite `docs/reference/cli/report.md`: remove `--ai`/`--ai-timeout` option rows (they do not exist), remove "requires O1+O2 capability layer" note, add `.gaze.yaml` `ai:` section reference, add `GAZEPY_AI_*` env var table, correct description ("direct HTTP" not "subprocess")
- [ ] T303 Consolidate `CHANGELOG.md [Unreleased]` into `## [0.7.0]`: merge two duplicate `### Added` blocks into one, strip all `Spec:` internal references, add missing entries for docs tree / `_matches_cache_decorator` refactor / python-native detection patterns, add `### Breaking Changes` section with JSON schema migration notice (FR from S1)
- [ ] T304 Bump `pyproject.toml` `version` field to `0.7.0`
- [ ] T305 Bump `src/gaze_py/__init__.py` `__version__` to `0.7.0`
- [ ] T306 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` — all clean
- [ ] T307 Open PR `opsx/parity-cleanup` → CI green → merge

---

## Story 4: Release v0.7.0

- [ ] T401 Confirm `main` has S1 + S2 + S3 all merged: `git log --oneline -10`
- [ ] T402 Confirm version consistency: `pyproject.toml` = `0.7.0`, `__init__.py` `__version__` = `0.7.0`
- [ ] T403 Trigger `release.yml`: GitHub Actions → Release → Run workflow → tag `v0.7.0`
- [ ] T404 Approve `pypi` environment gate when prompted
- [ ] T405 Confirm smoke test passes: `uvx --from "gaze-py==0.7.0" gazepy --help` exits 0
- [ ] T406 Confirm PyPI listing: `https://pypi.org/project/gaze-py/0.7.0/`
- [ ] T407 Install locally: `uv tool install --force "gaze-py==0.7.0" && gazepy --help`
- [ ] T408 Close `openspec/changes/002-deferred-capabilities` — all items are now either shipped or tracked in this spec
