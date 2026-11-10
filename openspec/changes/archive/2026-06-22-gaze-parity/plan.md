# Implementation Plan: gaze-py 1:1 Parity with Go gaze

**Branch**: `002-gaze-parity` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

## Summary

Four stories deliver full Go gaze parity and publish v0.7.0 to PyPI. Story 1
(JSON schema) is the critical path — Story 2 requires Story 1 to land first
because the baseline format is the new schema. Stories 1 and 3 can be
developed in parallel.

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Accuracy | ✅ | Schema changes are envelope-only; effect detection and scoring unchanged |
| II. Minimal Assumptions | ✅ | AST-only preserved; no new user annotation requirements |
| III. Actionable Output | ✅ | OC-002 violation fixed; null-not-zero preserved per OC-003 |
| IV. Testability | ✅ | Coverage strategy specified per story below; new code paths covered by T122–T126, T219–T223 |
| V. Porting Contract Supremacy | ✅ | OC-002 is the explicit driver; contracts.md, requirements.md, taxonomy-reference.md read before spec authoring; Story 2 has no porting contract (documented) |
| VI. Composability First | ✅ | NFR-002 prohibits new runtime deps; baseline is opt-in via flag |
| VII. Supply Chain Integrity | ✅ | No new runtime dependencies; `release.yml` updated to include test gate (FR-012) |

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `dataclasses.asdict()`, `json`, `click` (no new dependencies)
**Serialization**: `src/gaze_py/report/json_formatter.py` — `dataclasses.asdict()` + custom encoder
**Config**: `src/gaze_py/config/loader.py` — `GazeConfig` dataclass
**Reference implementation**: `/home/mpeter/prj/unbound-force/gaze/internal/crap/compare.go`

## Project Structure

New and modified source files:

```
src/gaze_py/
├── taxonomy/
│   └── models.py              MODIFIED — add Metadata, OverSpecification,
│                              QualitySummary dataclasses; update FunctionTarget
│                              (package, receiver, signature); update
│                              ContractCoverageResult (covered_count,
│                              total_contractual, discarded_returns,
│                              discarded_return_hints); update QualityReport
│                              (test_location, over_specification,
│                              ambiguous_effects, assertion_count,
│                              assertion_detection_confidence); change
│                              target_function: str|None → FunctionTarget|None
├── analysis/
│   └── detector.py            MODIFIED — populate FunctionTarget.package,
│                              receiver, signature at construction time
├── quality/
│   └── (pairing, mapper)      MODIFIED — populate new QualityReport fields;
│                              change target_function to FunctionTarget object
├── crap/
│   ├── compare.py             NEW — pure comparison module
│   └── (existing)             UNCHANGED
├── config/
│   └── loader.py              MODIFIED — add BaselineConfig; add baseline field
│                              to GazeConfig
├── report/
│   └── json_formatter.py      MODIFIED — update analysis_to_json() and
│                              quality_to_json() envelopes; add
│                              comparison_to_json() and comparison_to_text();
│                              update SCHEMA constant
└── cli/
    └── main.py                MODIFIED — inject Metadata; wire --baseline;
                               remove stale comment; version bump

tests/
├── test_crap_compare.py       NEW — unit tests for pure comparison functions
└── (existing tests)           MODIFIED — update schema key assertions

.github/workflows/
└── release.yml                MODIFIED — add test job before publish
```

## Story Branches and Sequencing

```
Story 3 (cleanup) ─────────────────────────────────────────────────────────┐
Story 1 (schema) → merge to main → Story 2 (baseline) → merge → Story 4 (release)
```

| Story | Branch | Blocked by |
|---|---|---|
| S1 — JSON schema compat | `opsx/schema-compat` | nothing |
| S2 — baseline | `opsx/baseline` | S1 merged to main |
| S3 — stale cleanup | `opsx/parity-cleanup` | nothing |
| S4 — release v0.7.0 | (workflow trigger) | S1 + S2 + S3 merged |

## Story 1 — JSON Schema Compatibility

**Coverage strategy**: All new code paths MUST be covered by dedicated tests
in T122–T126 before the gate (T127) is run.
- `Metadata` injection: assert all four fields present and correctly typed
- `FunctionTarget.receiver`: parametrize with method (expect class name) and
  module-level function (expect `null`)
- `FunctionTarget.signature`: assert reconstruction for `*args`, `**kwargs`,
  positional-only params; assert `"def <name>(...)"` fallback fires only when
  annotation reconstruction raises (not for simple variadic params)
- `QualityReport` new fields: assert `over_specification.ratio`,
  `assertion_count`, `assertion_detection_confidence` present in quality JSON
- Schema regression guard: golden-shape test (see T122b) that would fail if
  `results` reverts to `functions` or `target` nesting is flattened

**Key design decisions**:
- `FunctionTarget.package` = project-relative file path (e.g.,
  `src/gaze_py/crap/scorer.py`). No default — populated at construction time.
- `FunctionTarget.receiver` = class name for methods (`"FileDetector"`),
  `None` for module-level functions. Determined by whether the AST function
  node is inside a `ClassDef` parent at parse time. No default — populated at
  construction.
- `FunctionTarget.signature` = `"def fn_name(params) -> return_type"`
  reconstructed from AST `arguments` node. Fall back to `f"def {name}(...)"``
  ONLY when annotation reconstruction raises an exception (e.g., unparseable
  subscript type). `*args`, `**kwargs`, positional-only (`/`), keyword-only
  (`*`) MUST be reconstructed — they are NOT "complex cases."
- `AnalysisResult.functions` renamed to `results` in the Python model itself
  (not just in JSON output). All internal callers updated.
- `QualityReport.target_function` changes from `str | None` to
  `FunctionTarget | None` in the model. All quality pipeline setters updated
  (see T107b).
- `Metadata` injected at serialization time (not stored in model): avoids
  circular imports, keeps models pure. Run timer started at top of `analyze`/
  `crap`/`report` command function; elapsed passed to `analysis_to_json()`.
- `over_specification.ratio` = `count / assertion_count` (0.0 when 0 assertions)
- `assertion_detection_confidence` per report = `mapped / total_assertions * 100`
  (100 when 0 assertions — empty test is "perfectly confident" about nothing)

**Files changed**:
- `src/gaze_py/taxonomy/models.py`
- `src/gaze_py/report/json_formatter.py`
- `src/gaze_py/analysis/detector.py`
- `src/gaze_py/quality/` (pairing, mapper, assess)
- `src/gaze_py/cli/main.py`
- `tests/test_cli.py`, `tests/test_report_ai.py`, `tests/test_config.py`,
  `tests/test_output.py` (update schema key assertions)

## Story 2 — `--baseline` implementation

**Coverage strategy**: `compare.py` is a pure module with no I/O (except
`load_baseline` file read). Target 100% branch coverage on `classify_delta()`
and `compare()` via parametrized unit tests. The 85% floor applies to the full
package; `compare.py` should exceed it significantly. Specific parametrize
cases for `classify_delta()` enumerated in T220.

**Key design decisions**:
- Score key = `file_path + ":" + name` (equivalent to Go's `file + ":" + function`)
- Baseline format = new Story 1 schema (`{"results": [...]}`) only
- `BaselineConfig.file: str | None = None` — `None` means auto-discovery; any
  non-None string is treated as explicit (error on missing)
- `epsilon` default = 0.0 (any delta triggers regression/improvement)
- `new_function_threshold` default = `None` → use `crap_threshold` at runtime
- Regression wins on conflict: if CRAP regresses AND GazeCRAP improves →
  `regression`. If CRAP improves AND GazeCRAP regresses → `regression`.
  (Conservative, matches Go behavior)
- `hasGazeDelta` flag: skip GazeCRAP delta when baseline had no GazeCRAP data
  (null or 0) — matches Go `compare.go:96-101`
- Gate (exit 1) fires after output is written — mirrors `--max-crapload`
- Large-unmatched warning: if > 50% of baseline functions are unmatched, emit
  stderr warning about likely file renames
- `comparison_to_json()` uses `results` (not `scores`) as the top-level key
  for enriched function entries, consistent with FR-001

**Files changed**:
- `src/gaze_py/crap/compare.py` (new)
- `src/gaze_py/config/loader.py`
- `src/gaze_py/report/json_formatter.py`
- `src/gaze_py/cli/main.py`
- `tests/test_crap_compare.py` (new)
- `tests/test_cli.py`
- `docs/reference/cli/crap.md`

## Story 3 — Stale content / docs cleanup

**Files changed**:
- `src/gaze_py/cli/main.py` (~line 846 stale comment)
- `docs/reference/cli/report.md` (full rewrite)
- `CHANGELOG.md` (consolidate → `## [0.7.0]`)
- `pyproject.toml`, `src/gaze_py/__init__.py` (bump to 0.7.0)
- `.github/dependabot.yml` (remove `pip` ecosystem entry)

## Story 4 — Release v0.7.0

No code changes except adding a test job to `release.yml` (FR-012).
After all three story branches merge to `main`, trigger the release workflow.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Story 1 breaks many tests asserting on `"functions"` key | High | Expected — update tests as part of S1; schema regression guard (T122b) prevents revert |
| `signature` reconstruction incomplete for complex annotations | Medium | Explicit fallback rule: raise → fallback; parametric → reconstruct |
| Baseline matching fails on renamed/moved files | Low | Warn when > 50% unmatched (T209b); document in CHANGELOG |
| `FunctionTarget.target_function` type change has wide ripple | Medium | T107b explicitly tasks all setter updates; full suite gate catches misses |
| PyPI history assumption is wrong (v0.6.0 was published) | Low | T300.5 verifies before release; if wrong, escalate to 1.0.0 |
