# Feature Specification: gaze-py Analysis Engine

**Feature Branch**: `001-gaze-py-engine`
**Created**: 2026-06-13
**Status**: S1–S4 Complete | S5 In Progress | Code Review In Progress
**Repos**: `gaze-py` (S1–S4), `unbound-force` (S5)

## Context

gaze-py is the Python-native companion to Go gaze. It detects
observable side effects in Python functions, maps them to test
assertions, and computes GazeCRAP scores — the same quality gate
the Unbound Force swarm applies to Go projects, now available for
Python projects.

The current codebase has taxonomy, CRAP formula, and CLI skeleton.
This spec completes the engine: detection, assertion mapping,
report formatters, full CLI surface, and `uf init` integration.

**Research decisions embedded in this spec**:
- ADR-001: AST-only detection (no SSA/CFG frameworks)
- ADR-002: Schema-compatible JSON output (not byte-identical to Go)
- ADR-003: Dispatch via `uf init`, not shell script

---

## User Story 1 — AST Side-Effect Detection (Priority: P1)

A developer points gaze-py at a Python module and receives a
structured list of every observable side effect each function
produces, detected purely from the AST with no test execution.

**Why P1**: This is the atomic unit of gaze-py's value. Every
higher-level feature (assertion mapping, GazeCRAP) depends on
accurate per-function side-effect detection.

**Independent Test**: Analyze a set of known Python functions with
predetermined side effects. Verify 100% detection with zero false
positives across all P0–P2 effect types.

**Acceptance Scenarios**:

- **SC-001**: **Given** `def f() -> int: return x`, **When**
  analyzed, **Then** result contains one `ReturnValue` side effect.
- **SC-002**: **Given** `def f(): return x, y`, **When** analyzed,
  **Then** result contains one `ReturnValue` side effect (tuple
  return).
- **SC-003**: **Given** `def f(): raise ValueError("bad")`, **When**
  analyzed, **Then** result contains one `ErrorReturn` side effect.
- **SC-004**: **Given** `def f(): global counter; counter += 1`,
  **When** analyzed, **Then** result contains one `GlobalMutation`
  side effect identifying `counter` (tier P1).
- **SC-005**: **Given** `def f(d: dict): d.update({"k": "v"})`,
  **When** analyzed, **Then** result contains one
  `PointerArgMutation` side effect identifying `d`.
- **SC-006**: **Given** a method `def m(self): self.x = 1`, **When**
  analyzed, **Then** result contains one `ReceiverMutation` side
  effect identifying `self.x`.
- **SC-007**: **Given** `def f(): print("hello")`, **When** analyzed,
  **Then** result contains one `StdoutWrite` side effect.
- **SC-008**: **Given** a pure function with no side effects, **When**
  analyzed, **Then** result contains an empty side effects list
  (zero false positives).
- **SC-009**: **Given** `def f(): import sys; sys.stderr.write("e")`,
  **When** analyzed, **Then** result contains one `StderrWrite`.
- **SC-010**: **Given** `def f(): os.environ["K"] = "v"`, **When**
  analyzed, **Then** result contains one `EnvVarMutation`.
- **SC-011**: **Given** `def f(): os.environ.update({"K": "v"})`,
  **When** analyzed, **Then** result contains one `EnvVarMutation`
  (call form, distinct AST pattern from SC-010).
- **SC-012**: **Given** a source file with a `SyntaxError`, **When**
  analyzed, **Then** `analyze_module` raises `GazeParseError`
  (wrapping the original error with file path and line number);
  the CLI exits with code 1 and a human-readable message
  (`error: cannot parse <path>:<line>: <msg>`); no partial JSON
  is emitted.
- **SC-013**: **Given** a function with two `return` statements,
  **When** analyzed, **Then** result contains exactly one
  `ReturnValue` effect (deduplicated by type, not location).

**Edge Cases**:

- A function that calls another function that raises: only direct
  `raise` nodes are detected — transitive effects are out of scope
  for v1 and MUST be documented as a known limitation.
- Nested functions: only the outermost function definition is
  analyzed per invocation. Inner functions are treated as opaque
  unless analyzed separately. This is a fixed v1 behavior.
- `*args` / `**kwargs` mutation: flagged as `PointerArgMutation`
  with target `*args` or `**kwargs`.
- A source file with non-UTF-8 encoding: raises `GazeParseError`
  with code `ENCODING_ERROR`; CLI exits with code 1.
- A path that resolves outside the current working directory
  (e.g., `../../etc`): CLI exits with code 1 and message
  `"error: path escapes project root: <resolved_path>"`; no
  analysis is performed.

---

## User Story 2 — Assertion Mapper / Contract Coverage (Priority: P1)

Given a test function and the source function it tests, gaze-py
maps each `assert` statement in the test to a detected side effect,
computes contract coverage (% of contractual effects asserted on),
and identifies over-specified assertions (incidental effects).

**Why P1**: Contract coverage is the core metric that differentiates
gaze-py from `radon` + `coverage.py`. Without it, there is no
GazeCRAP — only standard CRAP.

**Independent Test**: Analyze paired source+test fixtures with known
assertion-to-effect mappings. Verify coverage % and over-
specification scores match hand-computed expected values.

**Acceptance Scenarios**:

- **SC-014**: **Given** `result = f(); assert result == 42`, **When**
  mapped, **Then** `ReturnValue` is marked covered;
  `ContractCoverage.percentage == 100.0`.
- **SC-015**: **Given** `with pytest.raises(ValueError): f()`,
  **When** mapped, **Then** `ErrorReturn` is marked covered.
- **SC-016**: **Given** a test with no `assert` statements, **When**
  mapped, **Then** `ContractCoverage.percentage == 0.0` and
  `ContractCoverage.gap_hints` is a `list[str]` containing one
  suggested assert snippet per uncovered contractual effect.
- **SC-017**: **Given** `assert internal_var == 3` where
  `internal_var` is not a return value or raised exception, **When**
  mapped, **Then** `OverSpecificationScore.count == 1` and
  `OverSpecificationScore.suggestions[0]` is a non-empty string
  advising on the incidental assertion.
- **SC-018**: **Given** a function with two contractual effects and
  one assert covering only one, **When** mapped, **Then**
  `ContractCoverage.percentage == 50.0` and
  `ContractCoverage.gaps` contains the uncovered effect.
- **SC-019**: **Given** `assert f() == 42` (inline call without
  assignment), **When** mapped, **Then** `ReturnValue` is marked
  covered (inline call pattern recognised).

**Edge Cases**:

- `assert isinstance(result, MyClass)`: treated as a return value
  assertion; coverage increments.
- Helper assertion functions (e.g., `assert_valid(result)`): mapped
  with reduced confidence; `unmapped_reason = "helper_param"` if
  unresolvable.
- `pytest.approx`, `pytest.warns`: recognised as assertion patterns.
- Tests with no identifiable target function call: coverage = 0,
  `assertion_detection_confidence = 0`.
- Malformed test file (`SyntaxError`): `map_assertions` raises
  `GazeParseError`; CLI emits a structured warning and continues
  with remaining test files.
- Empty test file: `ContractCoverage.percentage == 0.0`,
  `gap_hints` lists all contractual effects, no error raised.

---

## User Story 3 — GazeCRAP + Report Formatters (Priority: P1)

gaze-py produces GazeCRAP scores by substituting contract coverage
for line coverage in the CRAP formula, and outputs results in JSON
(schema-compatible with Go gaze) and human-readable text.

**Why P1**: The output formats are the integration surface — CI
gates, opencode commands, and the unbound-force feedback loop all
consume gaze-py output. Schema compatibility with Go gaze is
required for single-consumer downstream tools.

**Acceptance Scenarios**:

- **SC-020**: **Given** complexity=5, contract_coverage=0.0%, **When**
  scored, **Then** GazeCRAP = 5² × 1³ + 5 = 30.
- **SC-021**: **Given** complexity=5, contract_coverage=100.0%,
  **When** scored, **Then** GazeCRAP = 5² × 0³ + 5 = 5.
- **SC-022**: **Given** `--format=json`, **When** output, **Then**
  JSON validates against the gaze-py `ANALYSIS_SCHEMA`
  (Draft 2020-12).
- **SC-023**: **Given** `--format=json`, **When** output, **Then**
  top-level keys are `"version"` and `"results"` — identical to
  Go gaze analysis schema.
- **SC-024**: **Given** `--format=json`, **When** output, **Then**
  each result's `metadata` contains `"gaze_py_version"`,
  `"python_version"`, and `"duration_ms"` fields.
- **SC-025**: **Given** `--format=text`, **When** output, **Then**
  output contains a table per function showing effect type, tier,
  location, and GazeCRAP score.
- **SC-026**: **Given** quality report output, **When** `--format=json`,
  **Then** JSON validates against `QUALITY_SCHEMA` (Draft 2020-12).

**Schema compatibility note** (ADR-002):

- Field names are identical to Go gaze where semantics match.
- `go_version` is replaced by `python_version` in Metadata.
- `ssa_degraded` and `ssa_degraded_packages` are omitted (not
  applicable — gaze-py does not use SSA).
- `gaze_py_version` is added alongside `gaze_version` so consumers
  can identify which engine produced the output.
- `metadata` is per-result (inside `results[]`), not top-level.

**Edge Cases**:

- Functions with zero contractual side effects: GazeCRAP = complexity
  (formula degenerates to CC with no coverage term).
- Empty results list: JSON output is `{"version": "...", "results": []}`.

---

## User Story 4 — CLI Commands (Priority: P2)

`gaze-py` exposes three subcommands — `analyze`, `quality`,
`report` — with flag parity to Go gaze's surface, enabling
drop-in substitution in opencode commands and CI scripts.

**Why P2**: Depends on S1–S3. CLI is a thin delegation layer over
the core engine. Valuable but not blocking.

**Acceptance Scenarios**:

- **SC-027**: **Given** `gaze-py analyze src/`, **When** run, **Then**
  exits 0 and outputs text report of all detected side effects per
  function.
- **SC-028**: **Given** `gaze-py analyze src/ --format=json`, **When**
  run, **Then** exits 0 and outputs valid JSON conforming to
  `ANALYSIS_SCHEMA`.
- **SC-029**: **Given** `gaze-py quality tests/ --coverprofile=.coverage`,
  **When** run, **Then** reads the `.coverage` SQLite database via
  the `coverage.CoverageData` API and outputs a quality report with
  contract coverage per test function.
- **SC-030**: **Given** `gaze-py report src/ tests/`, **When** run,
  **Then** exits 0 and outputs GazeCRAP scores for all functions
  with test coverage.
- **SC-031**: **Given** an invalid (non-existent) path, **When** run,
  **Then** exits 1 with a human-readable error message; no partial
  output is emitted.

**Exit Code Contract**:

| Exit Code | Meaning |
|-----------|---------|
| 0 | Analysis completed successfully (results may be empty) |
| 1 | Input error (invalid path, missing file, bad flag, encoding error) |
| 2 | Internal analysis error (parse failure, unexpected exception) |
| 3 | Configuration error (invalid `.gaze.yaml`) |

A non-empty `metadata.warnings[]` does NOT change the exit code
if at least one result was produced.

**Edge Cases**:

- `--coverprofile` pointing to a missing `.coverage` file: exit 1
  with clear error; no partial output. Input MUST be validated
  before analysis begins.
- Directory with no Python files: empty results, exit 0.
- Path resolving outside project root: exit 1 with
  `"error: path escapes project root: <resolved_path>"`.
- `--coverprofile=.coverage`: flag accepts a SQLite database
  produced by `coverage.py`, not a Go-style text profile.

---

## User Story 5 — uf init Integration (Priority: P2)

`uf init` on a Python project automatically installs `gaze-py` and
deploys a `/gaze-report` opencode command, giving every new Python
project a quality gate without manual configuration.

**Why P2**: Depends on S3–S4 being stable (schema and CLI surface
must be final before the opencode command is written). Cross-repo
change to `unbound-force`.

**Acceptance Scenarios**:

- **SC-032**: **Given** a directory with `pyproject.toml`, **When**
  `uf init` runs, **Then** `gaze-py` is installed at a pinned
  version (via `uv tool install gaze-py==<version>` or
  `pip install --user gaze-py==<version>`) and a success step
  is reported.
- **SC-033**: **Given** a directory with `go.mod` only, **When**
  `uf init` runs, **Then** the `gaze-py` step is skipped with
  reason `"not a Python project"`.
- **SC-034**: **Given** `gaze-py` already installed at the pinned
  version, **When** `uf init` runs, **Then** step reports
  `"already installed"` without reinstalling.
- **SC-035**: **Given** a Python project after `uf init`, **When**
  `/gaze-report` is invoked in opencode, **Then** `gaze-py report`
  runs and output is returned to the agent context.
- **SC-036**: **Given** `--dry-run`, **When** `uf init` runs on a
  Python project, **Then** step reports what would be installed
  without executing.
- **SC-037**: **Given** network is unavailable during install,
  **When** `uf init` runs, **Then** the `gaze-py` step reports
  `FAILED` with message `"gaze-py install failed: <detail>"` and
  the manual install command; other `uf init` steps continue.
- **SC-038**: **Given** `gaze-py` is not on PATH, **When**
  `/gaze-report` is invoked in opencode, **Then** the command
  emits `"gaze-py not found. Run 'uf init' to install it."` and
  exits without running analysis.

**Edge Cases**:

- No `uv` available: fall back to `pip install --user
  gaze-py==<version>`; report which installer was used.
- Mixed Go+Python project (both `go.mod` and `pyproject.toml`):
  both `gaze` and `gaze-py` steps run; `/gaze-report` command
  detects primary language at invocation time.
- Private PyPI mirrors and air-gapped environments: not supported
  in v1. Users must install `gaze-py` manually before `uf init`.
