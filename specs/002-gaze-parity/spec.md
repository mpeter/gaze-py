# Feature Specification: gaze-py 1:1 Parity with Go gaze

**Feature Branch**: `002-gaze-parity`
**Created**: 2026-06-22
**Status**: Draft

## User Stories

### Story 1 — JSON Schema Compatibility (Priority: P0)

A CI pipeline consuming `gazepy crap --format=json` or `gazepy quality --format=json`
can be written once and work identically against gaze (Go) and gaze-py (Python). Field
names, envelope structure, and nested object shapes are identical between implementations.

**Why P0**: OC-002 in the porting contracts explicitly requires canonical field names
from the reference implementation to be preserved. The current gaze-py schema violates
this on both `crap`/`analyze` output (uses `{"functions": [...]}` instead of
`{"results": [...]}`, inlines `target.*` fields, omits `metadata`) and `quality` output
(bare array instead of `{"quality_reports": [...], "quality_summary": {...}}`, missing
`over_specification`, `ambiguous_effects`, `unmapped_assertions`, `assertion_count`,
`assertion_detection_confidence`, `test_location`).

**Acceptance Scenarios**:

1. **Given** `gazepy analyze src/ --format=json`, **When** the output is parsed, **Then**
   the top-level object has key `results` (not `functions`), each element has keys
   `target` (object with `package`, `function`, `receiver`, `signature`, `location`),
   `side_effects` (array), and `metadata` (object with `gaze_version`, `warnings`,
   `duration_ms`, `timestamp`).

2. **Given** `gazepy crap src/ --format=json`, **When** the output is parsed, **Then**
   the top-level object has key `results` (not `functions`), same structure as Story 1
   scenario 1, plus each function entry has `crap`, `gaze_crap`, `line_coverage`,
   `contract_coverage`, `fix_strategy`, `quadrant` as nullable scalars. The `summary`
   key is preserved.

3. **Given** `gazepy quality src/ --format=json`, **When** the output is parsed, **Then**
   the top-level object has keys `quality_reports` (array) and `quality_summary` (object).
   Each report has: `test_function`, `test_location`, `target_function` (FunctionTarget
   object, not string), `contract_coverage` (with `covered_count`, `total_contractual`,
   `gaps`, `gap_hints`, `discarded_returns`, `discarded_return_hints`),
   `over_specification` (with `count`, `ratio`, `incidental_assertions`, `suggestions`),
   `ambiguous_effects`, `unmapped_assertions`, `assertion_count`,
   `assertion_detection_confidence`.

4. **Given** `gazepy schema`, **When** the output is parsed, **Then** it reflects the
   updated `results`-keyed schema, not the old `functions`-keyed schema.

5. **Given** existing consumers using `{"functions": [...]}`, **When** they upgrade to
   v0.7.0, **Then** the CHANGELOG entry for v0.7.0 includes a migration notice
   documenting the rename and structural change.

---

### Story 2 — `--baseline` implementation on `gazepy crap` (Priority: P1)

A developer or CI pipeline can capture a CRAP baseline at one point in time, then
compare subsequent runs to detect regressions. `gazepy crap --baseline <file>` loads
a prior `crap --format=json` output and produces a per-function diff with
regression/improvement/unchanged/new/new_violation/removed status.

**Why P1**: This is O6 in the porting contracts (optional), explicitly requested, and
the current stub (exits 1 on use) is worse than not having the flag. The Go
implementation is ~350 lines of pure comparison logic — straightforward to port.

**Acceptance Scenarios**:

1. **Given** a baseline file (prior `gazepy crap --format=json` output) and a current
   run, **When** `gazepy crap src/ --baseline baseline.json` runs, **Then** output
   includes per-function `status` (one of: `regression`, `improvement`, `unchanged`,
   `new`, `new_violation`, `removed`) and a `comparison` summary with counts and
   `passed: true/false`.

2. **Given** no functions regressed and no new violations, **When** the command
   completes, **Then** exit code is 0 and `comparison.passed` is `true`.

3. **Given** at least one regression or new violation, **When** the command completes,
   **Then** exit code is 1 and `comparison.passed` is `false`.

4. **Given** `--baseline` points to a nonexistent file, **When** the command runs,
   **Then** it exits 2 with a clear error message (not silent).

5. **Given** no `--baseline` flag and no `.gaze/baseline.json` present, **When** the
   command runs, **Then** it runs normally with no comparison output (silent skip).

6. **Given** no `--baseline` flag but `.gaze/baseline.json` exists, **When** the command
   runs, **Then** comparison runs automatically using the discovered file.

7. **Given** `--format=text` with a baseline, **When** comparison runs, **Then** output
   is the normal CRAP text report followed by `--- Baseline Comparison: PASS ---` (or
   `FAIL`) and tables of regressions, improvements, new violations, and removed functions.
   Empty sections are omitted.

8. **Given** `baseline.epsilon: 0.5` in `.gaze.yaml`, **When** a function's CRAP delta
   is ≤ 0.5, **Then** it is classified as `unchanged`, not `regression` or `improvement`.

9. **Given** `baseline.new_function_threshold: 20.0` in `.gaze.yaml`, **When** a new
   function has CRAP = 18.0, **Then** its status is `new` (not `new_violation`).

---

### Story 3 — Stale content / docs cleanup (Priority: P1)

The codebase and docs contain stale content from before the `ai-http-adapters` merge:
a leftover "not yet implemented" comment in `main.py`, a report docs page that lists
flags that do not exist and denies features that are fully implemented, and a fragmented
`[Unreleased]` CHANGELOG section. These are fixed as part of the v0.7.0 release prep.

**Acceptance Scenarios**:

1. **Given** `main.py` ~line 846, **When** reviewed, **Then** the comment
   `# report command (not yet implemented — requires O2)` is absent.

2. **Given** `docs/reference/cli/report.md`, **When** reviewed, **Then** it contains no
   reference to `--ai` or `--ai-timeout` flags (which were removed), does not say AI
   requires O1+O2, and documents the `.gaze.yaml` `ai:` section and `GAZEPY_AI_*` env
   vars as the configuration mechanism.

3. **Given** `CHANGELOG.md`, **When** reviewed, **Then** the `[Unreleased]` section is
   replaced by a single well-structured `## [0.7.0]` section with no duplicate `### Added`
   headers and no internal `Spec:` references.

4. **Given** `pyproject.toml` and `src/gaze_py/__init__.py`, **When** reviewed, **Then**
   both contain version `0.7.0`.

---

### Story 4 — Release v0.7.0 to PyPI (Priority: P1)

`gaze-py 0.7.0` is published to PyPI via the existing `release.yml` trusted-publishing
workflow. `uvx --from "gaze-py==0.7.0" gazepy --help` works from any machine.

**Acceptance Scenarios**:

1. **Given** a clean `main` branch at v0.7.0, **When** `release.yml` is triggered with
   tag `v0.7.0`, **Then** CI passes all preflight checks (tag format, tag uniqueness,
   version match in `pyproject.toml` and `__init__.py`).

2. **Given** the workflow completes successfully, **When**
   `uvx --from "gaze-py==0.7.0" gazepy --help` is run, **Then** it exits 0.

---

## Requirements

### Functional Requirements

**FR-001** (Story 1): `analyze`/`crap` JSON output MUST use `results` as the top-level
array key (replacing `functions`). Each element MUST be an object with keys `target`
(FunctionTarget object), `side_effects` (array of SideEffect), and `metadata` (Metadata
object).

**FR-002** (Story 1): `FunctionTarget` MUST serialize as
`{"package": str, "function": str, "receiver": str|null, "signature": str, "location": str}`.
`package` is the project-relative file path (Python equivalent of Go's import path).
`receiver` is the class name for methods, `null` for module-level functions.

**FR-003** (Story 1): `Metadata` MUST serialize as
`{"gaze_version": str, "warnings": [str], "duration_ms": int, "timestamp": str (ISO 8601 UTC)}`.

**FR-004** (Story 1): `quality` JSON output MUST use
`{"quality_reports": [...], "quality_summary": {...}}` as the top-level envelope.

**FR-005** (Story 1): Each `QualityReport` in JSON MUST include `test_location` (str),
`target_function` (FunctionTarget object, not a bare string),
`over_specification` (`{count, ratio, incidental_assertions, suggestions}`),
`ambiguous_effects` (array of SideEffect), `unmapped_assertions` (array),
`assertion_count` (int), `assertion_detection_confidence` (int 0–100).

**FR-006** (Story 1): `ContractCoverage` in JSON MUST include `covered_count` (int),
`total_contractual` (int), `discarded_returns` (array, empty for now),
`discarded_return_hints` (array, empty for now).

**FR-007** (Story 2): `gazepy crap --baseline <path>` MUST load the file, compare
against current results, and emit enriched output with per-function `status` and a
`comparison` summary.

**FR-008** (Story 2): Auto-discovery MUST check `.gaze/baseline.json` relative to the
project root (nearest `pyproject.toml`). Auto-discovered missing file → silent skip.
Explicit `--baseline` pointing to missing file → exit 2 with error.

**FR-009** (Story 2): `.gaze.yaml` MUST support `baseline.file` (str),
`baseline.epsilon` (float ≥ 0, default 0.0), and `baseline.new_function_threshold`
(float > 0, default = `crap_threshold` at runtime).

**FR-010** (Story 2): Comparison gate exits 1 when `comparison.passed == false`
(regressions > 0 or new_violations > 0). Gate fires after output is written.

**FR-011** (Story 3): Version in `pyproject.toml` and `src/gaze_py/__init__.py` MUST
be `0.7.0`.

**FR-012** (Story 4): `release.yml` triggered with tag `v0.7.0` MUST complete without
error and publish to PyPI.

### Non-Functional Requirements

**NFR-001**: The Story 1 JSON change is a breaking change. The v0.7.0 CHANGELOG MUST
include a migration notice documenting: (a) `functions` → `results` rename,
(b) inline fields → `target` object nesting, (c) new `metadata` field per result,
(d) `quality` envelope change.

**NFR-002**: No new runtime dependencies. `dataclasses.asdict()` continues to be the
serialization mechanism.

**NFR-003**: All existing pytest tests pass at ≥ 85% coverage after Story 1 changes.
Tests asserting on `"functions"` key or flat field structure MUST be updated.

**NFR-004**: Story 2 comparison logic MUST be a pure function (no I/O, no global state)
tested independently of the CLI.

## Porting Contract Compliance

| Contract | Story | Assessment |
|---|---|---|
| OC-002 JSON field names | 1 | This story exists to fix the current violation |
| OC-003 Nullable fields | 1 | Preserved — all nullable fields remain nullable |
| EC-003 Effect identity | 1 | IDs unchanged — envelope changes only |
| SC-001/SC-002 Formulas | All | Unchanged |
| SC-003 CRAPload | 2 | Preserved in comparison output |

## Assumptions

- No existing public consumers of the current JSON schema (v0.6.0 was never published to PyPI).
- `gaze_version` in `Metadata` carries the gaze-py version string — semantically equivalent to Go's `gaze_version`.
- `package` in `FunctionTarget` uses project-relative file path as the Python equivalent of Go's import path. IDs remain stable within a project (EC-003 allows algorithm to differ).
- Story 2 baseline format is the new Story 1 schema only — no legacy format support.
- `discarded_returns` and `discarded_return_hints` are empty arrays for now — Go detects `_ = fn()` explicit discard patterns which are uncommon in Python; OC-003 compliant.
- `over_specification.incidental_assertions` and `suggestions` are empty arrays — Go generates suggestions from AI; gaze-py emits empty arrays; OC-003 compliant.
