# Tasks: gaze-py Analysis Engine

**Input**: `specs/001-gaze-py-engine/spec.md` and `plan.md`
**Prerequisites**: plan.md (required), spec.md (required)
**Repos**: `gaze-py` (T001–T021), `unbound-force` (T022–T026)

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

- [ ] T001 [S1] Create `tests/testdata/analysis/` with one fixture
  file per effect type:
  `returns.py`, `raises.py`, `globals.py`, `arg_mutation.py`,
  `receiver_mutation.py`, `stdout.py`, `stderr.py`,
  `env_mutation.py`, `pure.py`
  Each fixture contains 2–3 functions with known, predetermined
  side effects.

- [ ] T002 [P] [S1] Write `tests/test_analysis.py` — one test per
  acceptance scenario in spec.md US1 (SC-001 through SC-010),
  plus edge cases. Tests MUST fail before T003.
  Use `@pytest.mark.parametrize` for fixture-driven cases.

- [ ] T003 [S1] Implement `src/gaze_py/analysis.py`:
  - `FunctionEffectVisitor(ast.NodeVisitor)` with visit methods
    per the detection table in plan.md
  - `analyze_function(node: ast.FunctionDef, module: str) -> list[SideEffect]`
  - `analyze_module(source: str, module_path: str) -> list[AnalysisResult]`
  - ID generation: `"se-" + sha256(module:func:type:location)[:8]`
  - Nested function scoping: skip inner `FunctionDef` bodies by
    default

- [ ] T004 [P] [S1] Verify all T002 tests pass. Fix until green.
  Run: `uv run pytest tests/test_analysis.py -v`

**Checkpoint**: `uv run pytest tests/test_analysis.py` — all green,
zero false positives on `pure.py` fixture.

---

## Phase 2 — S2: Assertion Mapper / Contract Coverage

**Goal**: `quality.py` maps test assertions to detected side
effects, computes contract coverage %, and scores over-
specification.

**Write tests FIRST — ensure they FAIL before implementing.**

- [ ] T005 [S2] Create `tests/testdata/quality/` with paired
  fixtures:
  `src_basic.py` + `test_basic.py` (return value, covered),
  `src_raises.py` + `test_raises.py` (pytest.raises, covered),
  `src_multi.py` + `test_partial.py` (50% coverage),
  `src_incidental.py` + `test_incidental.py` (over-specification),
  `src_inline.py` + `test_inline.py` (inline call pattern)

- [ ] T006 [P] [S2] Write `tests/test_quality.py` — one test per
  acceptance scenario in spec.md US2 (SC-001 through SC-006),
  plus edge cases. Tests MUST fail before T007.

- [ ] T007 [S2] Implement `src/gaze_py/quality.py`:
  - `AssertionVisitor(ast.NodeVisitor)` with recognised patterns
    per plan.md assertion mapper design
  - `map_assertions(test_source: str, target_effects: list[SideEffect], target_func: str) -> QualityReport`
  - `compute_contract_coverage(report: QualityReport) -> ContractCoverage`
  - `compute_over_specification(report: QualityReport) -> OverSpecificationScore`
  - Target function resolution: name convention + call inspection

- [ ] T008 [P] [S2] Verify all T006 tests pass. Fix until green.
  Run: `uv run pytest tests/test_quality.py -v`

**Checkpoint**: `uv run pytest tests/test_quality.py` — all green.
Contract coverage formula verified against hand-computed values.

---

## Phase 3 — S3: Report Formatters + GazeCRAP Update

**Goal**: JSON and text formatters. Schema-compatible output.
GazeCRAP formula updated to use contract coverage.

- [ ] T009 [S3] Create `src/gaze_py/report/__init__.py` (empty
  package root).

- [ ] T010 [P] [S3] Implement `src/gaze_py/report/schema.py`:
  - `ANALYSIS_SCHEMA` constant: Draft 2020-12 JSON Schema for
    analysis report (mirrors Go `internal/report/schema.go` with
    ADR-002 adaptations: `python_version`, `gaze_py_version`,
    no `ssa_degraded`)
  - `QUALITY_SCHEMA` constant: Draft 2020-12 JSON Schema for
    quality report

- [ ] T011 [P] [S3] Implement `src/gaze_py/report/json.py`:
  - `write_analysis_json(results: list[AnalysisResult], version: str, out: IO) -> None`
  - `write_quality_json(reports: list[QualityReport], summary: PackageSummary, version: str, out: IO) -> None`
  - Top-level keys: `version`, `results` (analysis) /
    `quality_reports`, `quality_summary` (quality)
  - Metadata: `gaze_version`, `gaze_py_version`, `python_version`,
    `duration_ms`, `timestamp`, `warnings`

- [ ] T012 [P] [S3] Implement `src/gaze_py/report/text.py`:
  - `write_analysis_text(results: list[AnalysisResult], out: IO) -> None`
  - `write_quality_text(reports: list[QualityReport], out: IO) -> None`
  - Per-function table: effect type, tier, location, description
  - Summary line: GazeCRAP score, contract coverage %

- [ ] T013 [P] [S3] Update `src/gaze_py/crap.py`:
  - Add `compute_gazecrap(complexity: int, contract_coverage: float) -> float`
    using contract coverage in place of line coverage
  - Preserve existing `compute_crap` (line-coverage CRAP) for
    backwards compatibility — do not remove

- [ ] T014 [P] [S3] Write `tests/test_report_json.py`:
  - Validate JSON output against `ANALYSIS_SCHEMA` using
    `jsonschema.validate()`
  - Add `jsonschema` to `pyproject.toml` dev dependencies
  - Verify `jq '.results[0].side_effects'` parses correctly
  - Verify ADR-002 fields: `python_version` present,
    `go_version` absent, `gaze_py_version` present

- [ ] T015 [P] [S3] Write `tests/test_report_text.py`:
  - Smoke tests: text output is non-empty, contains function name,
    contains tier labels (`P0`–`P4`)

- [ ] T016 [S3] Verify GazeCRAP formula: `uv run pytest tests/test_crap.py -v`
  (existing tests + new contract-coverage cases)

**Checkpoint**: `uv run pytest tests/test_report_json.py tests/test_report_text.py tests/test_crap.py` — all green. JSON validates against schema.

---

## Phase 4 — S4: CLI Commands

**Goal**: `gaze-py analyze`, `gaze-py quality`, `gaze-py report`
with `--format` and `--coverprofile` flags.

- [ ] T017 [S4] Expand `src/gaze_py/cli.py`:
  - Add `analyze` subcommand: accepts `src_path`, `--format=text|json`
    delegates to `analysis.analyze_module()` + report formatters
  - Add `quality` subcommand: accepts `tests_path`,
    `--coverprofile=.coverage`, `--format=text|json`
    delegates to `quality.map_assertions()` + report formatters
  - Add `report` subcommand: accepts `src_path tests_path`,
    `--format=text|json`
    runs full pipeline: analyze → quality → GazeCRAP → output
  - Error handling: non-zero exit + clear message for bad paths,
    missing coverprofile

- [ ] T018 [P] [S4] Write `tests/test_cli.py`:
  - Integration tests using `click.testing.CliRunner`
  - Test each subcommand with `--format=json` and `--format=text`
  - Test error paths: missing path, missing coverprofile

- [ ] T019 [P] [S4] Verify all existing tests still pass:
  `uv run pytest -x --tb=short`

- [ ] T020 [S4] Run full CI parity check:
  `uv run ruff check .`
  `uv run ruff format --check .`
  `uv run mypy src/`
  `uv run pytest --cov=gaze_py --cov-report=term-missing`
  Fix all issues before marking complete.

**Checkpoint**: All tests green. Ruff clean. Mypy clean. Coverage
report shows new modules at meaningful coverage.

---

## Phase 5 — S5: uf init Integration (unbound-force repo)

**Prerequisites**: T020 complete. S4 CLI surface is stable.
Work in `unbound-force` repo on branch `001-gaze-py-engine`.

- [ ] T021 [S5] Add `installGazePy()` to
  `unbound-force/internal/setup/setup.go`:
  - Check `gaze-py --version` (already installed → skip)
  - Method dispatch: `uv tool install gaze-py` (preferred),
    fall back to `pip install gaze-py`
  - Dry-run support: report what would be installed
  - Follow `installGaze()` pattern exactly

- [ ] T022 [P] [S5] Add `gaze-py` to the setup step list in
  `setup.go`, gated on `detectLang(opts.TargetDir) == "python"`:
  ```go
  {name: "gaze-py", tool: "gaze-py", install: installGazePy,
   gate: func() bool { return lang == "python" },
   gateDetail: "not a Python project"},
  ```

- [ ] T023 [P] [S5] Create scaffold asset
  `unbound-force/internal/scaffold/assets/opencode/commands/gaze-report.md`:
  - Description: "Run gaze-py quality analysis on this Python project"
  - Body: invokes `gaze-py report src/ tests/ --format=json`
  - Deployed by scaffold for Python projects (language-gated)

- [ ] T024 [S5] Write tests for new setup step in
  `unbound-force/internal/setup/setup_test.go`:
  - Python project: gaze-py step runs
  - Go-only project: gaze-py step skipped
  - Already installed: step returns "already installed"
  - Dry-run: step reports without executing

- [ ] T025 [P] [S5] Run `unbound-force` CI parity:
  `go test ./...`
  `go vet ./...`
  Fix all issues before marking complete.

- [ ] T026 [P] [S5] Update documentation:
  - `unbound-force/AGENTS.md`: note gaze-py install step
  - `unbound-force/CHANGELOG.md`: entry for S5
  - `gaze-py/AGENTS.md`: update architecture tree (analysis.py,
    quality.py, report/ modules now exist)
  - `gaze-py/CHANGELOG.md`: entry for 001-gaze-py-engine

**Checkpoint**: `go test ./internal/setup/...` green.
`uf init --dry-run` on a pyproject.toml project reports gaze-py
step. `/gaze-report` command file deployed by scaffold.

---

## Completion Gate

All of the following MUST be true before this spec is marked Done:

- [ ] `uv run pytest` — all green (gaze-py repo)
- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format --check .` — clean
- [ ] `uv run mypy src/` — clean
- [ ] JSON output validates against `ANALYSIS_SCHEMA` and `QUALITY_SCHEMA`
- [ ] `go test ./...` — all green (unbound-force repo)
- [ ] `uf init --dry-run` on Python project shows gaze-py step
- [ ] AGENTS.md updated in both repos
- [ ] CHANGELOG.md entries in both repos
- [ ] `/review-council` run and all REQUEST CHANGES resolved
