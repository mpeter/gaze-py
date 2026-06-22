# Implementation Plan: gaze-py 1:1 Parity with Go gaze

**Branch**: `002-gaze-parity` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

## Summary

Four stories deliver full Go gaze parity and publish v0.7.0 to PyPI. Story 1 (JSON
schema) is the critical path — Story 2 requires Story 1 to land first because the
baseline format is the new schema. Stories 1 and 3 can be developed in parallel.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `dataclasses.asdict()`, `json`, `click` (no new dependencies)
**Serialization**: `src/gaze_py/report/json_formatter.py` — `dataclasses.asdict()` + custom encoder
**Config**: `src/gaze_py/config/loader.py` — `GazeConfig` dataclass
**Reference implementation**: `/home/mpeter/prj/unbound-force/gaze/internal/crap/compare.go`

## Story Branches and Sequencing

```
Story 3 (cleanup) ────────────────────────────────────────────────────────┐
Story 1 (schema) → merge to main → Story 2 (baseline) → merge → Story 4 (release)
```

| Story | Branch | Blocked by |
|---|---|---|
| S1 — JSON schema compat | `opsx/schema-compat` | nothing |
| S2 — baseline | `opsx/baseline` | S1 merged to main |
| S3 — stale cleanup | `opsx/parity-cleanup` | nothing |
| S4 — release v0.7.0 | (workflow trigger, no branch) | S1 + S2 + S3 merged |

## Story 1 — JSON Schema Compatibility

**Why this is the hardest story**: The schema change touches models, the formatter,
the CLI, the schema constant, and ~100+ test assertions. It must land cleanly before
any other story that depends on JSON output shape.

**Files changed:**
- `src/gaze_py/taxonomy/models.py` — add `Metadata` dataclass; update `FunctionTarget`
  to add `package`, `receiver`, `signature`; update `ContractCoverageResult` to add
  `covered_count`, `total_contractual`, `discarded_returns`, `discarded_return_hints`;
  update `QualityReport` to add `test_location`, `over_specification`, `ambiguous_effects`,
  `assertion_count`, `assertion_detection_confidence`; add `OverSpecification` and
  `QualitySummary` dataclasses
- `src/gaze_py/report/json_formatter.py` — update `analysis_to_json()` to emit
  `{"results": [...]}` with `target`/`side_effects`/`metadata` per entry; update
  `quality_to_json()` to emit `{"quality_reports": [...], "quality_summary": {...}}`;
  update `SCHEMA` constant
- `src/gaze_py/analysis/detector.py` — populate `FunctionTarget.package`, `receiver`,
  `signature` during detection
- `src/gaze_py/quality/` — populate new `QualityReport` fields during assessment
- `src/gaze_py/cli/main.py` — inject `Metadata` at serialization call sites; update any
  field accesses that relied on flat structure
- `tests/test_*.py` — update all assertions on old schema keys
- `docs/reference/cli/` — update output format descriptions

**Key design decisions:**
- `FunctionTarget.package` = project-relative file path (e.g., `src/gaze_py/crap/scorer.py`)
- `FunctionTarget.receiver` = class name for methods (`"FileDetector"`), `None` for
  module-level functions — determined by whether the AST function node is inside a
  `ClassDef` parent
- `FunctionTarget.signature` = `"def fn_name(params) -> return_type"` reconstructed from
  the AST `arguments` node; fall back to `"def <name>(...)"` for complex cases
- `Metadata.gaze_version` = `gaze_py.__version__`; injected at serialization time, not
  stored in model (avoids circular imports and keeps models pure)
- `Metadata.duration_ms` = wall-clock ms from run start to serialization call
- `over_specification.incidental_assertions` = `[]` (Go generates these from AI; empty
  is OC-003 compliant)
- `over_specification.suggestions` = `[]` (same rationale)
- `discarded_returns` = `[]`, `discarded_return_hints` = `[]` (Go detects `_ = fn()`
  explicit discards; uncommon in Python; empty is OC-003 compliant)

## Story 2 — `--baseline` implementation

**Files changed:**
- `src/gaze_py/crap/compare.py` (new) — pure comparison module: `FunctionStatus`,
  `CompareOptions`, `FunctionDelta`, `ComparisonSummary`, `ComparisonResult`,
  `load_baseline()`, `compare()`, `classify_delta()`, `build_comparison_summary()`
- `src/gaze_py/config/loader.py` — add `BaselineConfig` dataclass; add `baseline` field
  to `GazeConfig`; add validation
- `src/gaze_py/report/json_formatter.py` — add `comparison_to_json()` and
  `comparison_to_text()` writers
- `src/gaze_py/cli/main.py` — update `--baseline` flag: remove stub error, wire to
  `compare.py` pipeline, add `resolve_baseline_path()` helper
- `tests/test_crap_compare.py` (new) — unit tests for pure comparison functions
- `tests/test_cli.py` — integration tests for `--baseline` CLI behaviour
- `docs/reference/cli/crap.md` — document `--baseline` as implemented

**Key design decisions:**
- Score key for matching = `file_path + ":" + name` — equivalent to Go's `file + ":" + function`
- Baseline input format = new Story 1 schema (`{"results": [...]}`) only; no legacy support
- `epsilon` default = 0.0 (any delta triggers regression/improvement)
- `new_function_threshold` default = `crap_threshold` (15.0) at runtime when `None` in config
- Regression wins on conflict (CRAP regresses + GazeCRAP improves → `regression`)
- Gate (exit 1) fires after output is written — mirrors `--max-crapload` pattern

## Story 3 — Stale content / docs cleanup

**Files changed:**
- `src/gaze_py/cli/main.py` ~line 846 — delete stale comment
- `docs/reference/cli/report.md` — full rewrite
- `CHANGELOG.md` — consolidate `[Unreleased]` → `## [0.7.0]`
- `pyproject.toml`, `src/gaze_py/__init__.py` — bump to `0.7.0`

## Story 4 — Release v0.7.0

No code changes. Trigger `release.yml` workflow after S1 + S2 + S3 are all merged to
`main`.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Story 1 breaks many tests asserting on `"functions"` key | High | Expected — update tests as part of S1 |
| `signature` reconstruction is incomplete for complex args | Medium | Fall back to `"def <name>(...)"` for complex cases |
| Baseline matching fails on renamed/moved files | Low | Go has same limitation; document in CHANGELOG |
| `discarded_returns` left empty silently | None | OC-003 compliant; documented in spec assumptions |
