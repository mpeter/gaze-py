# Tasks: gaze-py Analysis Engine

**Input**: `specs/001-gaze-py-engine/spec.md` and `plan.md`
**Prerequisites**: plan.md (required), spec.md (required)
**Repos**: `gaze-py` (T001–T021), `unbound-force` (T022–T027)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- **[Story]**: Which user story (S1–S5)
- Exact file paths included in all descriptions
- Mark `[x]` immediately on completion

---

## Phase 1 — S1: AST Side-Effect Detection

**Goal**: `analysis.py` detects all P0–P2 Python side effects from
AST alone. Zero false positives on pure functions. 100% detection
on the fixture set.

**Write tests FIRST — ensure they FAIL before implementing.**

- [x] T001 [S1] Create `tests/testdata/analysis/` with one fixture
  file per effect type:
  `returns.py`, `raises.py`, `globals.py`, `arg_mutation.py`,
  `receiver_mutation.py`, `stdout.py`, `stderr.py`,
  `env_mutation.py` (include BOTH subscript and `.update()` forms),
  `pure.py`, `multi_return.py` (two return statements, for SC-013),
  `syntax_error.py` (deliberately invalid Python, for SC-012),
  `large_module.py` (50 functions, for performance benchmark)
  Each fixture contains 2–3 functions with known, predetermined
  side effects.

- [x] T002 [S1] Write `tests/test_analysis.py` — one test per
  acceptance scenario SC-001 through SC-013, plus edge cases.
  Tests MUST fail before T003. Use `@pytest.mark.parametrize`
  for fixture-driven cases. Include:
  - `test_sc012_syntax_error_raises_parse_error`
  - `test_sc013_multi_return_deduplicated`
  - `test_sc011_env_mutation_call_form`
  - `test_performance_50_functions` (`@pytest.mark.slow`)
  - `test_analyze_path_traversal_raises_error` (unit: `analyze_path()` raises on escape)
  - `test_analyze_path_excludes_hidden_and_pycache` (unit: walk excludes hidden dirs)
  NOTE: T002 depends on T001 (fixtures must exist before
  parametrize paths are referenced). Do NOT mark as [P].

- [x] T003 [S1] Add domain types to `src/gaze_py/taxonomy.py`:
  - `QualityReport` dataclass (fields per plan.md Domain Types)
  - `ContractCoverage` dataclass
  - `OverSpecificationScore` dataclass
  - `PackageSummary` dataclass
  - `taxonomy.is_contractual(effect_type: SideEffectType) -> bool`
    (returns True for P0–P1 types: `ReturnValue`, `ErrorReturn`,
    `ReceiverMutation`, `PointerArgMutation`, `GlobalMutation`)
  - All dataclasses include `to_dict()` methods

- [x] T004 [S1] Implement `src/gaze_py/analysis.py`:
  - `GazeParseError(Exception)` — typed wrapper for parse failures
  - `FunctionEffectVisitor(ast.NodeVisitor)` with visit methods
    per the detection table in plan.md (including Tier column)
  - `self._arg_names: set[str]` populated from `node.args` in
    `visit_FunctionDef` (distinguishes arg mutations from other)
  - `analyze_function(node: ast.FunctionDef, module: str) -> list[SideEffect]`
  - `analyze_module(source: str, module_path: str) -> list[AnalysisResult]`
    — catches `SyntaxError` → raises `GazeParseError`
    — catches `RecursionError` → appends `RECURSION_LIMIT` warning
  - `analyze_path(path: Path) -> list[AnalysisResult]`
    — resolves with `Path.resolve()`, validates within project root
    — walks with `Path.rglob("*.py")`, excludes hidden dirs and `__pycache__/`
    — catches encoding errors → raises `GazeParseError`
  - ID generation: `"se-" + sha256(module:func:type:location)[:8]`

- [x] T005 [P] [S1] Verify all T002 tests pass. Fix until green.
  Run: `uv run pytest tests/test_analysis.py -v`
  (Skip `@pytest.mark.slow` unless running explicitly.)

**Checkpoint**: `uv run pytest tests/test_analysis.py -m "not slow"`
— all green, zero false positives on `pure.py` fixture.

---

## Phase 2 — S2: Assertion Mapper / Contract Coverage

**Goal**: `quality.py` maps test assertions to detected side
effects, computes contract coverage %, and scores over-
specification.

**Write tests FIRST — ensure they FAIL before implementing.**

- [x] T006 [S2] Create `tests/testdata/quality/` with paired
  fixtures:
  `src_basic.py` + `test_basic.py` (SC-014: return value, covered),
  `src_raises.py` + `test_raises.py` (SC-015: pytest.raises),
  `src_multi.py` + `test_partial.py` (SC-018: 50% coverage),
  `src_incidental.py` + `test_incidental.py` (SC-017: over-spec),
  `src_inline.py` + `test_inline.py` (SC-019: inline call),
  `src_no_assert.py` + `test_no_assert.py` (SC-016: gap_hints)

- [x] T007 [S2] Write `tests/test_quality.py` — one test per
  acceptance scenario SC-014 through SC-019, plus edge cases.
  Tests MUST fail before T008.
  IMPORTANT: Construct `SideEffect` objects directly (do NOT call
  `analyze_function()`) to keep S2 tests isolated from S1.
  Include assertions on specific field values:
  - SC-016: assert `coverage.gap_hints` is `list[str]`, non-empty
  - SC-017: assert `over_spec.count == 1` and
    `over_spec.suggestions[0]` is a non-empty string
  NOTE: T007 depends on T006 (fixtures must exist). Do NOT mark [P].

- [x] T008 [S2] Implement `src/gaze_py/quality.py`:
  - `AssertionVisitor(ast.NodeVisitor)` with recognised patterns
    per plan.md assertion mapper design
  - `map_assertions(test_source: str, target_effects: list[SideEffect], target_func: str) -> QualityReport`
  - `compute_contract_coverage(report: QualityReport) -> ContractCoverage`
    — delegates to `taxonomy.is_contractual()` for classification
    — `gap_hints` is `list[str]`, parallel to `gaps`
  - `compute_over_specification(report: QualityReport) -> OverSpecificationScore`
    — `suggestions` is `list[str]`, one per incidental assertion
  - Target function resolution: name convention + call inspection
  - `pytest.warns` maps to `StderrWrite` only (not `LogWrite`)
  - Malformed test file: raises `GazeParseError`
  - Empty test file: returns `ContractCoverage(percentage=0.0, ...)`

- [x] T009 [P] [S2] Verify all T007 tests pass. Fix until green.
  Run: `uv run pytest tests/test_quality.py -v`

**Checkpoint**: `uv run pytest tests/test_quality.py` — all green.
Coverage formula verified against hand-computed values for SC-018.

---

## Phase 3 — S3: Report Formatters + GazeCRAP Update

**Goal**: JSON and text formatters. Schema-compatible output.
GazeCRAP formula aliased for contract coverage.

**Write tests FIRST — ensure they FAIL before implementing.**

- [x] T010 [S3] Write `tests/test_report_json.py` (BEFORE
  implementing formatters):
  - Tests MUST fail initially (no implementation yet)
  - Validate analysis JSON against `ANALYSIS_SCHEMA` via
    `jsonschema.validate()` (SC-022)
  - Validate quality JSON against `QUALITY_SCHEMA` via
    `jsonschema.validate()` (SC-026)
  - Verify top-level keys are `"version"` and `"results"` (SC-023)
  - Verify `metadata` fields: `"gaze_py_version"` present,
    `"python_version"` present, `"go_version"` absent,
    `"duration_ms"` present (SC-024)
  - Verify `jq`-compatible structure (assert via Python dict
    key access: `output["results"][0]["side_effects"]`)

- [x] T011 [P] [S3] Write `tests/test_report_text.py` (BEFORE
  implementing text formatter):
  - Smoke tests: text output is non-empty, contains function name,
    contains tier labels (`P0`–`P4`), contains GazeCRAP score

- [x] T012 [S3] Create `src/gaze_py/report/__init__.py`:
  - Export `build_metadata(version: str, start_ns: int) -> dict`
    — assembles `gaze_version`, `gaze_py_version`, `python_version`,
    `duration_ms` (from `start_ns` to now), `timestamp`, `warnings`
    — single source of truth for metadata assembly across formatters

- [x] T013 [P] [S3] Implement `src/gaze_py/report/schema.py`:
  NOTE: Depends on T010 and T011 (tests must exist and fail
  before implementation begins). [P] means parallel with T014
  and T015, not with T010/T011.
  - `ANALYSIS_SCHEMA` constant: Draft 2020-12 JSON Schema for
    analysis report (ADR-002 adaptations: `python_version`,
    `gaze_py_version`, no `ssa_degraded`)
  - `QUALITY_SCHEMA` constant: Draft 2020-12 JSON Schema for
    quality report
  - Add `jsonschema>=4.18` to `pyproject.toml` dev dependencies

- [x] T014 [P] [S3] Implement `src/gaze_py/report/json.py`:
  NOTE: Depends on T010 and T011 (tests must exist and fail
  before implementation begins). [P] means parallel with T013
  and T015, not with T010/T011.
  - `write_analysis_json(results: list[AnalysisResult], version: str, out: IO) -> None`
  - `write_quality_json(reports: list[QualityReport], summary: PackageSummary, version: str, out: IO) -> None`
  - Uses `report.build_metadata()` for metadata — no duplication
  - Top-level keys: `version`, `results` (analysis) /
    `quality_reports`, `quality_summary` (quality)

- [x] T015 [P] [S3] Implement `src/gaze_py/report/text.py`:
  NOTE: Depends on T010 and T011 (tests must exist and fail
  before implementation begins). [P] means parallel with T013
  and T014, not with T010/T011.
  - `write_analysis_text(results: list[AnalysisResult], out: IO) -> None`
  - `write_quality_text(reports: list[QualityReport], out: IO) -> None`
  - Use `rich.Table` / `rich.Console` for output (python.md CS-009)
  - Per-function table: effect type, tier, location, description
  - Summary line: GazeCRAP score, contract coverage %

- [x] T016 [P] [S3] Update `src/gaze_py/crap.py`:
  - Verify `gaze_crap_score(complexity, contract_coverage_pct)`
    already exists and matches S3 SC-020/SC-021 formula
  - Add `compute_gazecrap` as an alias:
    `compute_gazecrap = gaze_crap_score`
  - Preserve `crap_score()` (line-coverage CRAP) unchanged
  - Do NOT rename or remove any existing functions

- [x] T017 [S3] Verify all schema and crap tests pass:
  `uv run pytest tests/test_report_json.py tests/test_report_text.py tests/test_crap.py -v`
  Add new parametrized test cases to `test_crap.py` for SC-020
  and SC-021 (complexity=5 / coverage=0% → 30; coverage=100% → 5).

**Checkpoint**: All Phase 3 tests green. Both `ANALYSIS_SCHEMA`
and `QUALITY_SCHEMA` validated. Ruff and mypy clean on new files.

---

## Phase 4 — S4: CLI Commands

**Goal**: `gaze-py analyze`, `gaze-py quality`, `gaze-py report`
with `--format`, `--coverprofile`, and exit code contract.

- [x] T018 [S4] Write `tests/test_cli.py` BEFORE expanding cli.py:
  - Tests MUST fail initially
  - Integration tests using `click.testing.CliRunner`
  - Test SC-027 through SC-031 for each subcommand
  - Test exit codes: 0 on success, 1 on missing path, 1 on
    missing coverprofile
  - `test_cli_path_traversal_exits_1` (CLI-layer: exit code + message)
  - `test_cli_directory_walk_excludes_hidden` (CLI-layer: dir walk)

- [x] T019 [S4] Expand `src/gaze_py/cli.py`:
  - Implement `analyze` subcommand per existing stub:
    preserve all existing flags; add `--format=text|json`;
    validate path with `analyze_path()` before analysis begins
  - Implement `quality` subcommand per existing stub:
    preserve all existing flags; implement `--coverprofile`
    (reads `.coverage` via `coverage.CoverageData`); add
    `--format=text|json`; validate coverprofile path before
    analysis begins (exit 1 if missing, no partial output)
  - Implement `report` subcommand: `src_path tests_path`,
    `--format=text|json`; full pipeline: analyze → quality →
    GazeCRAP → output
  - Exit code contract: 0=success, 1=input error, 2=internal
    error, 3=config error; see spec.md S4 Exit Code Contract
  - `--ai-mapper` / `--min-contract-coverage` stubs retained
    but not implemented (deferred per plan.md flag disposition)
  - Add `coverage` to runtime dependencies in `pyproject.toml`

- [x] T020 [P] [S4] Verify all existing tests still pass:
  `uv run pytest -x --tb=short`

- [x] T021 [S4] Run full CI parity check:
  `uv run ruff check .`
  `uv run ruff format --check .`
  `uv run mypy src/`
  `uv run pytest --cov=gaze_py --cov-fail-under=85 --cov-report=term-missing`
  Fix all issues before marking complete.

**Checkpoint**: All tests green. Ruff clean. Mypy clean.
Coverage ≥ 85% overall; new modules at per-module targets
(analysis.py ≥ 90%, quality.py ≥ 85%, report/*.py ≥ 80%).

---

## Phase 5 — S5: uf init Integration (unbound-force repo)

**Prerequisites**: T021 complete. S4 CLI surface is stable.
Work in `unbound-force` repo on branch `001-gaze-py-engine`.

**Write tests FIRST (T022) — ensure they FAIL before implementing
T023/T024.**

- [ ] T022 [S5] Write tests for new setup step in
  `unbound-force/internal/setup/setup_test.go` BEFORE implementing:
  - Tests MUST fail initially (no implementation yet)
  - SC-032: Python project → gaze-py step runs at pinned version
  - SC-033: Go-only project → gaze-py step skipped
  - SC-034: Already installed → step returns "already installed"
  - SC-036: Dry-run → step reports without executing
  - SC-037: Network failure → step returns error with message

- [ ] T023 [S5] Add `installGazePy()` to
  `unbound-force/internal/setup/setup.go`:
  - Check `gaze-py --version` (already installed → skip)
  - Method dispatch: `uv tool install gaze-py==<version>` (preferred),
    fall back to `pip install --user gaze-py==<version>`
  - Define `const GazePyVersion = "0.1.0"` as a named constant;
    document update procedure in release checklist
  - Version MUST be pinned (not `latest`)
  - Network failure: return non-nil error with actionable message
    and manual install command; non-fatal for overall `uf init`
  - Dry-run support: report what would be installed
  - Follow `installGaze()` pattern exactly

- [ ] T024 [S5] Add `gaze-py` to the setup step list in
  `setup.go`, gated on `detectLang(opts.TargetDir) == "python"`.
  NOTE: T024 depends on T023 (`installGazePy` must be defined
  before it can be referenced). Do NOT mark as [P].
  ```go
  {name: "gaze-py", tool: "gaze-py", install: installGazePy,
   gate: func() bool { return lang == "python" },
   gateDetail: "not a Python project"},
  ```

- [ ] T025 [P] [S5] Create scaffold asset
  `unbound-force/internal/scaffold/assets/opencode/commands/gaze-report.md`:
  - Description: "Run gaze-py quality analysis on this Python project"
  - Body: checks `gaze-py` on PATH; emits clear error if not found
    (SC-038); falls back to `.gaze.yaml` for path config;
    defaults to `gaze-py report src/ tests/ --format=json`
  - Deployed by scaffold for Python projects (language-gated)

- [ ] T026 [P] [S5] Run `unbound-force` CI parity:
  `go test ./...`
  `go vet ./...`
  Fix all issues before marking complete.

- [ ] T027 [S5] Update documentation (after T026 green):
  - `unbound-force/AGENTS.md`: note gaze-py install step
  - `unbound-force/CHANGELOG.md`: entry for S5
  - `gaze-py/AGENTS.md`: update architecture tree (analysis.py,
    quality.py, report/ modules now exist; update flat layout note)
  - `gaze-py/CHANGELOG.md`: entry for 001-gaze-py-engine

**Checkpoint**: `go test ./internal/setup/...` green.
`uf init --dry-run` on a pyproject.toml project reports gaze-py
step with pinned version. `/gaze-report` command deployed by
scaffold.

---

## Completion Gate

All of the following MUST be true before this spec is marked Done:

- [x] `uv run pytest -m "not slow"` — all green (gaze-py repo)
- [x] `uv run pytest --cov=gaze_py --cov-fail-under=85` — passes
- [x] `uv run ruff check .` — clean
- [x] `uv run ruff format --check .` — clean
- [x] `uv run mypy src/` — clean
- [x] Analysis JSON validates against `ANALYSIS_SCHEMA`
- [x] Quality JSON validates against `QUALITY_SCHEMA`
- [ ] `go test ./...` — all green (unbound-force repo)
- [ ] `uf init --dry-run` on Python project shows gaze-py step with pinned version
- [x] AGENTS.md updated in both repos
- [x] CHANGELOG.md entries in both repos
- [ ] `unbound-force/website` issue filed for new CLI commands (`analyze`, `quality`, `report`) and `uf init` gaze-py step
- [ ] `/review-council` run and all REQUEST CHANGES resolved

<!-- spec-review: passed -->
