# Feature Specification: gaze-py Analysis Engine

**Feature Branch**: `001-gaze-py-engine`
**Created**: 2026-06-13
**Status**: In Progress
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

1. **Given** `def f() -> int: return x`, **When** analyzed,
   **Then** result contains one `ReturnValue` side effect.
2. **Given** `def f(): return x, y`, **When** analyzed, **Then**
   result contains one `ReturnValue` side effect (tuple return).
3. **Given** `def f(): raise ValueError("bad")`, **When** analyzed,
   **Then** result contains one `ErrorReturn` (`Raise`) side effect.
4. **Given** `def f(): global counter; counter += 1`, **When**
   analyzed, **Then** result contains one `GlobalMutation` side
   effect identifying `counter`.
5. **Given** `def f(d: dict): d.update({"k": "v"})`, **When**
   analyzed, **Then** result contains one `PointerArgMutation`
   side effect identifying `d`.
6. **Given** a method `def m(self): self.x = 1`, **When** analyzed,
   **Then** result contains one `ReceiverMutation` side effect
   identifying `self.x`.
7. **Given** `def f(): print("hello")`, **When** analyzed, **Then**
   result contains one `StdoutWrite` side effect.
8. **Given** a pure function with no side effects, **When** analyzed,
   **Then** result contains an empty side effects list (no false
   positives).
9. **Given** `def f(): import sys; sys.stderr.write("err")`,
   **When** analyzed, **Then** result contains one `StderrWrite`.
10. **Given** `def f(): os.environ["K"] = "v"`, **When** analyzed,
    **Then** result contains one `EnvVarMutation`.

**Edge Cases**:

- A function with multiple return statements: each return path
  produces one `ReturnValue` (deduplicated by type, not location).
- A function that calls another function that raises: only direct
  `raise` nodes are detected — transitive effects are out of scope
  for v1 and MUST be documented as a known limitation.
- Nested functions: only the outermost function definition is
  analyzed per invocation. Inner functions are treated as opaque
  unless analyzed separately.
- `*args` / `**kwargs` mutation: flagged as `PointerArgMutation`
  with target `*args` or `**kwargs`.

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

1. **Given** `result = f(); assert result == 42`, **When** mapped,
   **Then** `ReturnValue` is marked covered; coverage = 100%.
2. **Given** `with pytest.raises(ValueError): f()`, **When** mapped,
   **Then** `ErrorReturn` is marked covered.
3. **Given** a test with no `assert` statements, **When** mapped,
   **Then** contract coverage = 0%, gap_hints lists each uncovered
   contractual effect.
4. **Given** `assert internal_var == 3` where `internal_var` is an
   incidental variable (not a return value or raised exception),
   **When** mapped, **Then** over-specification score increments by
   one and a suggestion is generated.
5. **Given** a function with two contractual effects and one assert
   covering only one, **When** mapped, **Then** coverage = 50% and
   gaps lists the uncovered effect.
6. **Given** `assert f() == 42` (inline call without assignment),
   **When** mapped, **Then** `ReturnValue` is marked covered (inline
   call pattern recognised).

**Edge Cases**:

- `assert isinstance(result, MyClass)`: treated as a return value
  assertion; coverage increments.
- Helper assertion functions (e.g., `assert_valid(result)`): mapped
  with reduced confidence; unmapped_reason = `helper_param` if
  unresolvable.
- `pytest.approx`, `pytest.warns`: recognised as assertion patterns.
- Tests with no identifiable target function call: coverage = 0,
  assertion_detection_confidence = 0.

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

1. **Given** complexity=5, contract_coverage=0%, **When** scored,
   **Then** GazeCRAP = 5² × 1³ + 5 = 30.
2. **Given** complexity=5, contract_coverage=100%, **When** scored,
   **Then** GazeCRAP = 5² × 0³ + 5 = 5.
3. **Given** `--format=json`, **When** output, **Then** JSON
   validates against the gaze-py JSON schema (Draft 2020-12).
4. **Given** `--format=json`, **When** output, **Then** top-level
   keys are `version` and `results` — identical to Go gaze schema.
5. **Given** `--format=json`, **When** output, **Then** `metadata`
   contains `gaze_py_version`, `python_version`, and `duration_ms`.
6. **Given** `--format=text`, **When** output, **Then** output is a
   human-readable table per function showing effects, tier, and
   GazeCRAP score.
7. **Given** output piped to `jq`, **When** format is `json`,
   **Then** `jq '.results[0].side_effects'` returns the effect list.

**Schema compatibility note** (ADR-002):

- Field names are identical to Go gaze where semantics match.
- `go_version` is replaced by `python_version` in Metadata.
- `ssa_degraded` and `ssa_degraded_packages` are omitted (not
  applicable — gaze-py does not use SSA).
- `gaze_py_version` is added alongside `gaze_version` so consumers
  can identify which engine produced the output.

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

1. **Given** `gaze-py analyze src/`, **When** run, **Then** outputs
   text report of all detected side effects per function.
2. **Given** `gaze-py analyze src/ --format=json`, **When** run,
   **Then** outputs valid JSON conforming to the analysis schema.
3. **Given** `gaze-py quality tests/ --coverprofile=.coverage`,
   **When** run, **Then** reads coverage data and outputs quality
   report with contract coverage per test function.
4. **Given** `gaze-py report src/ tests/`, **When** run, **Then**
   outputs GazeCRAP scores for all functions with test coverage.
5. **Given** an invalid path, **When** run, **Then** exits non-zero
   with a clear error message.

**Edge Cases**:

- `--coverprofile` pointing to a missing `.coverage` file: clear
  error, non-zero exit, no partial output.
- Directory with no Python files: empty results, zero exit.

---

## User Story 5 — uf init Integration (Priority: P2)

`uf init` on a Python project automatically installs `gaze-py` and
deploys a `/gaze-report` opencode command, giving every new Python
project a quality gate without manual configuration.

**Why P2**: Depends on S3–S4 being stable (schema and CLI surface
must be final before the opencode command is written). Cross-repo
change to `unbound-force`.

**Acceptance Scenarios**:

1. **Given** a directory with `pyproject.toml`, **When** `uf init`
   runs, **Then** `gaze-py` is installed (via `uv tool install`
   or `pip install`) and a success step is reported.
2. **Given** a directory with `go.mod` only, **When** `uf init`
   runs, **Then** the `gaze-py` step is skipped (no Python project
   detected).
3. **Given** `gaze-py` already installed, **When** `uf init` runs,
   **Then** step reports "already installed" without reinstalling.
4. **Given** a Python project after `uf init`, **When**
   `/gaze-report` is invoked in opencode, **Then** `gaze-py report`
   runs and output is returned to the agent context.
5. **Given** `--dry-run`, **When** `uf init` runs on a Python
   project, **Then** step reports what would be installed without
   executing.

**Edge Cases**:

- No `uv` available: fall back to `pip install gaze-py`; report
  which installer was used.
- Mixed Go+Python project (both `go.mod` and `pyproject.toml`):
  both `gaze` and `gaze-py` steps run; `/gaze-report` command
  detects primary language at invocation time.
