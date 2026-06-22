# Feature Specification: gaze-py 1:1 Parity with Go gaze

**Feature Branch**: `002-gaze-parity`
**Created**: 2026-06-22
**Status**: Draft

## Governance Exception

Story 1 introduces a **breaking change** to the public JSON output schema
(`functions` → `results`, inline fields → `target` object, new `metadata`
per result, `quality` envelope change). The constitution's Releases principle
requires a MAJOR bump for breaking schema changes.

**Exception rationale**: PyPI release history confirms no version ≥ 0.5.0 was
ever published (highest published version: 0.4.1). There are no known public
consumers of the v0.6.0 JSON schema. The breaking change is released as
`v0.7.0` (MINOR) on this basis. The "no prior publication" assumption MUST be
verified in T300.5 before the release tag is created — if any version ≥ 0.5.0
is found on PyPI, this exception is void and the version MUST be bumped to
`1.0.0`.

---

## User Stories

### Story 1 — JSON Schema Compatibility (Priority: P0)

A CI pipeline consuming `gazepy crap --format=json` or `gazepy quality
--format=json` can be written once and work identically against gaze (Go) and
gaze-py (Python). Field names, envelope structure, and nested object shapes
are identical between implementations.

**Why P0**: OC-002 in the porting contracts explicitly requires canonical
field names from the reference implementation to be preserved. The current
gaze-py schema violates this on both `crap`/`analyze` output (uses
`{"functions": [...]}` instead of `{"results": [...]}`, inlines `target.*`
fields, omits `metadata`) and `quality` output (bare array instead of
`{"quality_reports": [...], "quality_summary": {...}}`, missing
`over_specification`, `ambiguous_effects`, `unmapped_assertions`,
`assertion_count`, `assertion_detection_confidence`, `test_location`).

**Independent Test**: `gazepy analyze src/gaze_py/crap/scorer.py --format=json`
and verify top-level key is `results`, first element has `target.package`,
`target.function`, `target.receiver`, `target.signature`, `target.location`,
`metadata.gaze_version`. Run separately from full test suite.

**Acceptance Scenarios**:

1. **Given** `gazepy analyze src/ --format=json`, **When** the output is
   parsed, **Then** the top-level object has key `results` (not `functions`),
   each element has keys `target` (object with `package: str`, `function: str`,
   `receiver: str|null`, `signature: str`, `location: str`), `side_effects`
   (array), and `metadata` (object with `gaze_version: str`, `warnings: [str]`,
   `duration_ms: int`, `timestamp: str` matching `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`).

2. **Given** `gazepy crap src/ --format=json`, **When** the output is parsed,
   **Then** the top-level object has key `results` (not `functions`), same
   structure as scenario 1, plus each function entry has `crap`, `gaze_crap`,
   `line_coverage`, `contract_coverage`, `fix_strategy`, `quadrant` as
   nullable scalars. The `summary` key is preserved.

3. **Given** `gazepy quality src/ --format=json`, **When** the output is
   parsed, **Then** the top-level object has keys `quality_reports` (array)
   and `quality_summary` (object). Each report has: `test_function`,
   `test_location`, `target_function` (FunctionTarget object, not string),
   `contract_coverage` (with `covered_count`, `total_contractual`, `gaps`,
   `gap_hints`, `discarded_returns`, `discarded_return_hints`),
   `over_specification` (with `count`, `ratio`, `incidental_assertions`,
   `suggestions`), `ambiguous_effects`, `unmapped_assertions`,
   `assertion_count`, `assertion_detection_confidence`.

4. **Given** `gazepy schema`, **When** the output is parsed, **Then** it
   reflects the updated `results`-keyed schema, not the old `functions`-keyed
   schema.

5. **Given** existing consumers using `{"functions": [...]}`, **When** they
   upgrade to v0.7.0, **Then** the CHANGELOG `## [0.7.0]` section includes a
   `### Breaking Changes` subsection with a migration notice documenting: (a)
   `functions` → `results` rename, (b) inline fields → `target` object
   nesting, (c) new `metadata` field per result, (d) `quality` envelope change.
   *Verified by PR review, not by automated test.*

**Edge Cases**:
- Function defined inside a class (`receiver` must be populated)
- Module-level function (`receiver` must be `null`)
- Function with `*args`/`**kwargs`/positional-only params (`signature`
  reconstruction must not fall back unless annotation is truly unparseable)
- Method with complex return type annotation (fallback to
  `"def <name>(...)"` only when annotation reconstruction raises)
- Empty `results` array (valid — directory with no Python functions)
- `quality` output with no test-target pairs (empty `quality_reports`)

---

### Story 2 — `--baseline` implementation on `gazepy crap` (Priority: P1)

A developer or CI pipeline can capture a CRAP baseline at one point in time,
then compare subsequent runs to detect regressions. `gazepy crap --baseline
<file>` loads a prior `crap --format=json` output and produces a per-function
diff with regression/improvement/unchanged/new/new_violation/removed status.

**Why P1**: This is a gaze-py-specific extension not enumerated in the
porting contracts. The Go reference implementation includes ~350 lines of
comparison logic in `internal/crap/compare.go`; this story ports that logic.
No porting contract governs its behavior.

**Independent Test**: Write a minimal Python source file and a synthetic
baseline JSON (new schema) to a temp directory. Run `gazepy crap <dir>
--baseline <baseline.json>`. Verify `comparison.passed` and exit code
independently of the main test suite.

**Acceptance Scenarios**:

1. **Given** a baseline file (prior `gazepy crap --format=json` output with
   new Story 1 schema) and a current run, **When** `gazepy crap src/
   --baseline baseline.json` runs, **Then** JSON output includes per-function
   `status` (one of: `regression`, `improvement`, `unchanged`, `new`,
   `new_violation`, `removed`) and a `comparison` object with fields
   `regressions`, `improvements`, `unchanged`, `new_functions`,
   `new_violations`, `removed_functions`, `passed` (bool), `epsilon`,
   `new_function_threshold`.

2. **Given** no functions regressed and no new violations, **When** the
   command completes, **Then** exit code is 0 and `comparison.passed` is
   `true`.

3. **Given** at least one regression or new violation, **When** the command
   completes, **Then** exit code is 1 and `comparison.passed` is `false`.

4. **Given** `--baseline` points to a nonexistent file, **When** the command
   runs, **Then** it exits 2 with a clear error message including the file
   path and the suggestion to re-run `gazepy crap --format=json > baseline.json`.

5. **Given** no `--baseline` flag and no `.gaze/baseline.json` present,
   **When** the command runs, **Then** it runs normally with no comparison
   output (silent skip, exit 0).

6. **Given** no `--baseline` flag but `.gaze/baseline.json` exists, **When**
   the command runs, **Then** comparison runs automatically using the discovered
   file.

7. **Given** `--format=text` with a baseline, **When** comparison runs,
   **Then** output is the normal CRAP text report followed by `--- Baseline
   Comparison: PASS ---` (or `FAIL`) and tables of regressions, improvements,
   new violations, and removed functions. Empty sections are omitted.

8. **Given** `baseline.epsilon: 0.5` in `.gaze.yaml`, **When** a function's
   CRAP delta is ≤ 0.5, **Then** it is classified as `unchanged`, not
   `regression` or `improvement`.

9. **Given** `baseline.new_function_threshold: 20.0` in `.gaze.yaml`, **When**
   a new function has CRAP = 18.0, **Then** its status is `new` (not
   `new_violation`). Verify this by checking that the `comparison.new_violations`
   count is 0 and `comparison.new_functions` count is 1.

10. **Given** a baseline captured before a file rename, **When** comparison
    runs, **Then** functions in the renamed file appear in `new_functions` and
    `removed_functions`, and a warning is emitted to stderr:
    `"Warning: N baseline functions unmatched — file renames cause false positives."`
    when N > 50% of baseline function count.

**Edge Cases**:
- Malformed JSON baseline → `ValueError` with actionable message naming the
  file and suggesting regeneration; NOT a raw `json.JSONDecodeError` trace
- Baseline with `{"functions": [...]}` (old v0.6.0 schema) → `ValueError`
  with message "baseline uses incompatible schema (missing 'results' key);
  re-generate with `gazepy crap --format=json > baseline.json`"
- Baseline with `{"results": null}` → `ValueError` ("results must be a list")
- Baseline with `{"results": []}` → empty comparison result (no error; this
  matches Go behavior where an empty baseline is valid)
- `.gaze/` directory exists but `.gaze/baseline.json` absent → silent skip
  (same as no directory)
- Auto-discovered path disappears between discovery and load → silent skip
  with stderr warning
- Auto-discovered path is a directory (not a file) → exit 2 with error
- CRAP regresses AND GazeCRAP improves simultaneously → `regression` (Go
  behavior: regression wins on conflict)
- CRAP improves AND GazeCRAP regresses simultaneously → `regression` (same
  conservative rule)
- Baseline has no `gaze_crap` values (GazeCRAP was null) → GazeCRAP delta
  skipped; classification based on CRAP delta only

---

### Story 3 — Stale content / docs cleanup (Priority: P1)

The codebase and docs contain stale content from before the `ai-http-adapters`
merge. These are fixed as part of the v0.7.0 release prep.

**Independent Test**: `grep -n "not yet implemented" src/gaze_py/cli/main.py`
returns no results. `grep -n "\-\-ai" docs/reference/cli/report.md` returns no
results for `--ai` or `--ai-timeout` option rows.

**Acceptance Scenarios**:

1. **Given** `src/gaze_py/cli/main.py`, **When** reviewed, **Then** the comment
   `# report command (not yet implemented — requires O2)` is absent.

2. **Given** `docs/reference/cli/report.md`, **When** reviewed, **Then** it
   contains no `--ai` or `--ai-timeout` option rows, does not say AI requires
   O1+O2, and documents the `.gaze.yaml` `ai:` section and `GAZEPY_AI_*` env
   vars as the configuration mechanism.

3. **Given** `CHANGELOG.md`, **When** reviewed, **Then** the `[Unreleased]`
   section is replaced by `## [0.7.0]` containing exactly one each of
   `### Added`, `### Changed`, `### Removed`, and `### Breaking Changes`
   subsections (omitting empty ones). No duplicate section headers. No
   `Spec:` internal references. The `### Breaking Changes` subsection includes
   the JSON schema migration notice per NFR-001.

4. **Given** `pyproject.toml` and `src/gaze_py/__init__.py`, **When** reviewed,
   **Then** both contain version `0.7.0`.

**Edge Cases**:
- `dependabot.yml` `pip` ecosystem entry must be removed (per constitution
  v1.1.3 SYNC IMPACT REPORT which states this entry is inapplicable)

---

### Story 4 — Release v0.7.0 to PyPI (Priority: P1)

`gaze-py 0.7.0` is published to PyPI via the existing `release.yml`
trusted-publishing workflow.

**Independent Test**: After release workflow completes, run
`uvx --from "gaze-py==0.7.0" gazepy --version` on a clean machine and confirm
output contains `0.7.0`.

**Acceptance Scenarios**:

1. **Given** a clean `main` branch at v0.7.0 with S1+S2+S3 merged, **When**
   `release.yml` is triggered with tag `v0.7.0`, **Then** CI passes all
   preflight checks (tag format, tag uniqueness, version match in
   `pyproject.toml` and `__init__.py`) AND the full test suite passes on the
   release commit (`uv run pytest --cov-fail-under=85`).

2. **Given** the workflow completes successfully, **When**
   `uvx --from "gaze-py==0.7.0" gazepy --version` is run, **Then** it exits 0
   and outputs `0.7.0`. *Manual verification after publish.*

**Edge Cases**:
- If T300.5 finds any gaze-py version ≥ 0.5.0 on PyPI, the governance
  exception is void — escalate to `1.0.0` before proceeding.

---

## Requirements

### Functional Requirements

**FR-001** (Story 1): `analyze`/`crap` JSON output MUST use `results` as the
top-level array key (replacing `functions`). Each element MUST be an object
with keys `target` (FunctionTarget object), `side_effects` (array of
SideEffect), and `metadata` (Metadata object), plus all existing scoring
fields (`crap`, `line_coverage`, etc.) at the top level of each result entry.

**FR-002** (Story 1): `FunctionTarget` MUST serialize as
`{"package": str, "function": str, "receiver": str|null, "signature": str, "location": str}`.
`package` is the project-relative file path. `receiver` is the class name for
methods, `null` for module-level functions.

**FR-003** (Story 1): `Metadata` MUST serialize as
`{"gaze_version": str, "warnings": [str], "duration_ms": int, "timestamp": str}`.
`timestamp` MUST use the format `YYYY-MM-DDTHH:MM:SSZ` (seconds precision,
UTC, `Z` suffix — matching Go's `time.RFC3339`). Use
`datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`.

**FR-004** (Story 1): `quality` JSON output MUST use
`{"quality_reports": [...], "quality_summary": {...}}` as the top-level
envelope. `quality_summary` MUST contain: `total_tests: int`,
`average_contract_coverage: float | null`,
`total_over_specifications: int`,
`worst_coverage_tests: list[str]` (test function names, bottom 5 by coverage),
`assertion_detection_confidence: int` (mean of per-report values, rounded).

**FR-005** (Story 1): Each `QualityReport` in JSON MUST include
`test_location: str`, `target_function` (FunctionTarget object, not a bare
string), `over_specification` (`{count: int, ratio: float,
incidental_assertions: [], suggestions: []}`), `ambiguous_effects` (array of
SideEffect), `unmapped_assertions` (array), `assertion_count: int`,
`assertion_detection_confidence: int` (0–100).

**FR-006** (Story 1): `ContractCoverage` in JSON MUST include
`covered_count: int`, `total_contractual: int`,
`discarded_returns: []` (empty array — OC-003 compliant),
`discarded_return_hints: []` (empty array — OC-003 compliant).

**FR-007** (Story 2): `gazepy crap --baseline <path>` MUST load the file,
compare against current results, and emit enriched output. JSON output when
`--baseline` is active MUST use the envelope:
`{"results": [...enriched...], "new_functions": [...], "removed_functions": [...],
"comparison": <ComparisonSummary>, "summary": <CRAPSummary>}`. Each entry in
`results` receives optional fields `baseline_crap`, `crap_delta`,
`baseline_gaze_crap`, `gaze_crap_delta`, `status` when a baseline match exists.
`new_functions` and `removed_functions` each contain entries with all standard
result fields plus `status`.

**FR-008** (Story 2): Baseline path resolution order: (1) `--baseline` flag
(explicit — error on missing file); (2) `config.baseline.file` when not `None`
(explicit — error on missing file); (3) `.gaze/baseline.json` relative to
project root (auto-discovery — silent skip when absent). Auto-discovery edge
cases: directory present but file absent → silent skip; path is a directory
(not a file) → exit 2 with error; file disappears between discovery and load →
silent skip with stderr warning.

**FR-009** (Story 2): `.gaze.yaml` MUST support `baseline.file: str | null`
(null = auto-discovery, default null), `baseline.epsilon: float` (≥ 0,
default 0.0), `baseline.new_function_threshold: float | null` (> 0, default
null = use `crap_threshold` at runtime).

**FR-010** (Story 2): Comparison gate exits 1 when `comparison.passed ==
false` (regressions > 0 or new_violations > 0). Gate fires after output is
written.

**FR-011** (Story 3): Version in `pyproject.toml` and
`src/gaze_py/__init__.py` MUST be `0.7.0`.

**FR-012** (Story 4): `release.yml` MUST include a test job that runs
`uv run pytest --cov=gaze_py --cov-fail-under=85` on the release commit before
the build/publish step. The existing preflight checks (tag format, uniqueness,
version match) are already implemented and MUST be preserved.

### Non-Functional Requirements

**NFR-001**: The Story 1 JSON change is a breaking change. The v0.7.0
CHANGELOG `### Breaking Changes` section MUST document: (a) `functions` →
`results` rename, (b) inline fields → `target` object nesting, (c) new
`metadata` field per result, (d) `quality` envelope change, (e) migration
command.

**NFR-002**: No new runtime dependencies. `dataclasses.asdict()` continues to
be the serialization mechanism.

**NFR-003**: All existing pytest tests pass at ≥ 85% coverage after Story 1
changes. Current baseline is 96%; Story 1 should not cause a significant drop.
New code paths (Metadata injection, FunctionTarget field population,
QualityReport field population, signature reconstruction, receiver detection)
MUST be covered by new tests in T122–T126 before T127 is run.

**NFR-004**: Story 2 comparison logic MUST be a pure function (no I/O, no
global state) tested independently of the CLI.

## Success Criteria

**SC-001**: `gazepy crap --format=json` output validates against the updated
JSON schema with `results` as the top-level key and all five `target`
sub-fields present and correctly typed.

**SC-002**: `gazepy crap --baseline <file>` exits 1 when at least one
regression exists; exits 0 when no regressions and no new violations;
exits 2 when baseline file is missing (explicit flag).

**SC-003**: Full test suite passes at ≥ 85% coverage (T127/T224 gate).

**SC-004**: `release.yml` triggered with `v0.7.0` completes and
`uvx --from "gaze-py==0.7.0" gazepy --version` outputs `0.7.0`.

**SC-005**: PyPI history confirms no version ≥ 0.5.0 was published before
this release (T300.5 verification).

## Porting Contract Compliance

| Contract | Story | Assessment |
|---|---|---|
| OC-002 JSON field names | 1 | This story fixes the current violation |
| OC-003 Nullable fields | 1 | Preserved — all nullable fields remain nullable |
| EC-001 Taxonomy (38 types) | 1 | Preserved — `models.py` changes add fields only; P4 count discrepancy (contracts.md says 5, enumeration yields 6) already documented in constitution v1.1.1 |
| EC-003 Effect identity | 1 | IDs unchanged — envelope changes only |
| SC-001/SC-002 Formulas | All | Unchanged |
| SC-003 CRAPload | 2 | Preserved in comparison output |
| Story 2 | 2 | No porting contract — gaze-py extension ported from Go reference implementation (`internal/crap/compare.go`) |
| Story 3 | 3 | N/A — documentation and version hygiene |
| Story 4 | 4 | N/A — release mechanics |

## Assumptions

- T300.5 verification confirms no gaze-py version ≥ 0.5.0 was ever published
  to PyPI (authorizes the governance exception above).
- `gaze_version` in `Metadata` carries the gaze-py version string —
  semantically equivalent to Go's `gaze_version`.
- `package` in `FunctionTarget` uses project-relative file path as the Python
  equivalent of Go's import path. IDs remain stable within a project (EC-003
  allows algorithm to differ).
- Story 2 baseline format is the new Story 1 schema only — no legacy format
  support. Users with v0.6.0 baselines must regenerate.
- `discarded_returns` and `discarded_return_hints` are empty arrays — Go
  detects `_ = fn()` explicit discard patterns which are uncommon in Python;
  OC-003 compliant.
- `over_specification.incidental_assertions` and `suggestions` are empty
  arrays — Go generates suggestions from AI; gaze-py emits empty arrays;
  OC-003 compliant.
- `FunctionTarget.package`, `receiver`, `signature` are populated at
  construction time in `detector.py` (not incrementally). All existing
  `FunctionTarget(...)` call sites in `detector.py` will be updated to pass
  the new fields. No default values are added (the new fields are always known
  at construction).
- `AnalysisResult.functions` field is renamed to `results` in the Python model
  itself (not just in JSON output), and all internal callers are updated. This
  is consistent with the Go model where the field and JSON key match.
- `QualityReport.target_function` changes from `str | None` to `FunctionTarget
  | None` in the dataclass. All quality pipeline code that currently sets this
  field must be updated (see T107b).
