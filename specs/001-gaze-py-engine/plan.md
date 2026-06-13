# Implementation Plan: gaze-py Analysis Engine

**Branch**: `001-gaze-py-engine` | **Date**: 2026-06-13
**Spec**: [spec.md](spec.md) | **Tasks**: [tasks.md](tasks.md)
**Repos**: `gaze-py` (S1–S4), `unbound-force` (S5)

---

## Summary

Complete the gaze-py engine across five sequential stories:
AST-based side-effect detection → assertion mapper + contract
coverage → GazeCRAP formula + report formatters → full CLI surface
→ `uf init` integration in `unbound-force`.

The existing codebase (`taxonomy.py`, `crap.py`, `cli.py`,
`classify.py`, `config.py`) is preserved. New modules are added
alongside, not replacing, existing code.

---

## Architectural Decision Records

### ADR-001 — AST-only Detection, No SSA/CFG

**Decision**: gaze-py uses `ast.NodeVisitor` for side-effect
detection. SSA and CFG frameworks are not used.

**Rationale**:
- `python-scalpel` (the research doc's recommendation) is pre-
  production beta and not published to PyPI. It is an academic
  Monash University project unsuitable for production dependencies.
- All P0–P2 side effects that materially affect GazeCRAP scores
  are intra-procedural and detectable from AST alone: `ast.Return`,
  `ast.Raise`, `ast.Global`, `ast.Assign` on attributes/subscripts,
  `ast.Call` name matching for stdlib I/O.
- The Go `gaze crap` subcommand (AST + coverage.py, no SSA) is the
  stable reference implementation and does not panic under Go 1.25.
  The Go SSA path panics. The AST path does not. This is the
  empirical proof that AST-only is sufficient.
- Inter-procedural data flow (the primary SSA benefit) is out of
  scope for v1 and MUST be documented as a known limitation.

**Consequences**: Transitive side effects (a function calling a
function that raises) are not detected. This is acceptable: the
taxonomy is applied at the function boundary, matching Go gaze's
v1 scope.

---

### ADR-002 — Schema-Compatible JSON, Not Byte-Identical

**Decision**: gaze-py JSON output is structurally compatible with
Go gaze (same top-level keys, same field names where semantics
match) but is not required to be byte-identical.

**Specific adaptations**:

| Go gaze field | gaze-py field | Change |
|---|---|---|
| `metadata.go_version` | `metadata.python_version` | Renamed |
| `metadata.gaze_version` | `metadata.gaze_version` | Kept (set to schema protocol version, not a Go binary version) |
| — | `metadata.gaze_py_version` | Added |
| `quality_summary.ssa_degraded` | (omitted) | Not applicable |
| `quality_summary.ssa_degraded_packages` | (omitted) | Not applicable |

**`gaze_version` semantics**: In gaze-py output, `gaze_version` is
set to the gaze schema protocol version (e.g., `"0.1.0"`), not a
Go binary version. This allows consumers to verify schema
compatibility without inferring which engine produced the output.

**`metadata` placement**: `metadata` is embedded per-result (inside
each element of `results[]`), not at the top level. This matches
Go gaze's `AnalysisResult` structure where each result carries its
own provenance metadata.

**Rationale**: Downstream consumers (opencode commands, CI gates)
parse the JSON by field name. Field names are stable across both
implementations. Language-specific metadata fields are renamed to
be self-documenting. SSA-specific fields are omitted cleanly since
gaze-py does not use SSA.

**Consequences**: A consumer that checks `metadata.go_version`
specifically will need updating. A consumer that checks
`metadata.gaze_version` works with both. The gaze-py JSON schema
(Draft 2020-12) MUST be committed alongside the code and tested
with `jsonschema>=4.18` in CI.

---

### ADR-003 — Dispatch via uf init, Not Shell Script

**Decision**: Language-aware dispatch is implemented inside
`uf init` (Go, `unbound-force` repo), not via a `gaze-dispatch`
shell script.

**Rationale**: The research doc proposed a shell script without
knowledge of the existing Go infrastructure. Investigation of
`unbound-force/internal/` reveals:

- `internal/scaffold/scaffold.go`: `detectLang()` already checks
  `pyproject.toml`, `setup.py`, `setup.cfg` → returns `"python"`.
- `internal/doctor/checks.go`: `pythonMarkerFiles`,
  `pythonToolChecks` — full Python environment detection.
- `internal/setup/setup.go`: `installGaze()` pattern — the exact
  template for `installGazePy()`.

Replicating language detection in bash would be duplication.
Extending the existing Go setup step is ~20 lines following an
established pattern, is testable with existing `setup_test.go`
infrastructure, and integrates automatically into every `uf init`
run without manual user configuration.

**Version pinning**: `installGazePy()` MUST install a pinned
version (e.g., `gaze-py==0.1.0`), not `latest`. The pinned
version MUST be updated explicitly when a new release is made.
This prevents supply-chain drift from a future broken or malicious
PyPI release.

**Consequences**: S5 requires a Go change to `unbound-force`.
This makes S5 the only cross-repo story. S5 MUST NOT begin until
S3 (schema) and S4 (CLI surface) are stable — the opencode command
template depends on the final subcommand names and flags.

---

## Technical Context

**Language/Version**: Python 3.12+
**Package manager**: uv
**Primary new dependencies**:
  - `jsonschema>=4.18` (dev, test-only) — Draft 2020-12 support
    requires 4.18+; added to `pyproject.toml` dev dependencies
**Testing**: pytest, `uv run pytest`
**Target platform**: macOS, Linux
**Performance goals**: < 2s for a 50-function module (see Coverage
  Strategy for enforcement)
**Constraints**: MUST NOT modify target source; analysis is
  read-only; no annotation of source required
**Encoding assumption**: All source and test files are assumed
  to be UTF-8. Files that cannot be decoded as UTF-8 produce a
  `GazeParseError`. This assumption MUST be noted in CLI help text.

---

## Coverage Strategy

New modules MUST achieve the following line coverage thresholds,
enforced by `--cov-fail-under` in the CI command:

| Module | Target |
|--------|--------|
| `analysis.py` | ≥ 90% |
| `quality.py` | ≥ 85% |
| `report/json.py` | ≥ 90% |
| `report/text.py` | ≥ 80% |
| `cli.py` (new additions) | ≥ 80% |

CI command: `uv run pytest --cov=gaze_py --cov-fail-under=85
--cov-report=term-missing`

(85% is the floor across all modules combined; per-module targets
above are the individual goals.)

Existing modules (`taxonomy.py`, `crap.py`, `classify.py`,
`config.py`) MUST NOT regress below their current coverage
baseline. T020 enforces this with the combined `--cov-fail-under`
flag.

**Types**: Unit tests (primary), integration tests via
`click.testing.CliRunner` (CLI subcommands), schema validation
tests via `jsonschema.validate()` (report formatters).

**Performance regression guard**: A `@pytest.mark.slow` benchmark
test MUST verify `analyze_module()` on a 50-function fixture
completes in under 2 seconds using `time.perf_counter_ns()`.
Add fixture `tests/testdata/analysis/large_module.py` (50
functions) and test `test_performance_50_functions`.

---

## Module Structure

### New files (gaze-py repo)

```text
src/gaze_py/
  analysis.py          S1: AST side-effect detection engine
  quality.py           S2: assertion mapper, contract coverage,
                           over-specification scoring
  report/
    __init__.py        S3: package root + shared build_metadata()
    json.py            S3: JSON formatter (schema-compatible)
    text.py            S3: human-readable text formatter (rich)
    schema.py          S3: JSON Schema constants (Draft 2020-12)

tests/
  test_analysis.py     S1: unit tests for detection engine
  test_quality.py      S2: unit tests for assertion mapper
  test_report_json.py  S3: JSON schema validation tests
  test_report_text.py  S3: text formatter smoke tests
  test_cli.py          S4: CLI integration tests
  testdata/
    analysis/          S1: source fixtures (one file per effect type)
    quality/           S2: paired source+test fixtures
```

**Layout note**: Flat module layout (`analysis.py`, `quality.py`)
is used for consistency with the existing codebase pattern
(`taxonomy.py`, `classify.py`, `crap.py`). The python.md AP-006
subpackage layout is deferred to a future refactoring spec.

**Shared metadata helper**: `report/__init__.py` exports
`build_metadata(version: str, start_ns: int) -> dict` to avoid
duplicating metadata assembly across `json.py` and `text.py`.

### Domain types (new, added to `taxonomy.py`)

The following dataclasses MUST be added to `taxonomy.py` to
maintain the existing domain-type ownership pattern:

```python
@dataclass
class QualityReport:
    test_function: str
    test_location: str
    target_function: FunctionTarget
    contract_coverage: ContractCoverage
    over_specification: OverSpecificationScore
    ambiguous_effects: list[SideEffect]
    unmapped_assertions: list[AssertionMapping]
    assertion_count: int
    assertion_detection_confidence: int  # 0–100
    metadata: Metadata

@dataclass
class ContractCoverage:
    percentage: float          # 0.0–100.0
    covered_count: int
    total_contractual: int
    gaps: list[SideEffect]     # contractual effects not asserted on
    gap_hints: list[str]       # parallel to gaps: suggested assert snippets

@dataclass
class OverSpecificationScore:
    count: int
    ratio: float               # 0.0–1.0
    incidental_assertions: list[AssertionMapping]
    suggestions: list[str]     # one per incidental assertion

@dataclass
class PackageSummary:
    total_tests: int
    average_contract_coverage: float
    total_over_specifications: int
    worst_coverage_tests: list[QualityReport]
    assertion_detection_confidence: int
```

### Modified files (gaze-py repo)

```text
src/gaze_py/
  taxonomy.py          S2: add QualityReport, ContractCoverage,
                           OverSpecificationScore, PackageSummary
                           dataclasses
  cli.py               S4: expand analyze, quality, report subcommands
  crap.py              S3: add compute_gazecrap() alias; preserve
                           gaze_crap_score() unchanged
```

### New files (unbound-force repo)

```text
internal/setup/
  setup.go             S5: add installGazePy() step (modify existing)

internal/scaffold/assets/opencode/commands/
  gaze-report.md       S5: Python-aware /gaze-report opencode command
```

---

## Story Sequencing

```
S1 (analysis.py)
  └─► S2 (quality.py + taxonomy.py domain types)
        └─► S3 (report/, crap.py alias)
              └─► S4 (cli.py expand)
                    └─► S5 (unbound-force: installGazePy + scaffold)
```

S5 MUST NOT begin before S4 is complete.

Within phases: test fixtures (T001, T005) MUST precede test
writing (T002, T006), which MUST precede implementation (T003,
T007). The `[P]` tag on T002 is removed — see tasks.md.

---

## Detection Design (S1)

`FunctionEffectVisitor(ast.NodeVisitor)` in `analysis.py`:

### Visit methods and mapped types

| AST node | Condition | SideEffectType | Tier |
|---|---|---|---|
| `ast.Return` | any | `ReturnValue` | P0 |
| `ast.Raise` | any | `ErrorReturn` | P0 |
| `ast.Global` + store | name in global list | `GlobalMutation` | **P1** |
| `ast.Assign` / `ast.AugAssign` | target is `ast.Attribute` on `self` | `ReceiverMutation` | P0 |
| `ast.Call` on arg name | `.update()`, `.append()`, `.extend()`, `.__setitem__()`, `.pop()`, `.clear()`, `.add()`, `.discard()` | `PointerArgMutation` | P0 |
| `ast.Subscript` store on arg | e.g. `d["k"] = v` | `PointerArgMutation` | P0 |
| `ast.Call` | func is `print` or `sys.stdout.write` | `StdoutWrite` | P3 |
| `ast.Call` | func is `sys.stderr.write` | `StderrWrite` | P3 |
| `ast.Subscript` store on `os.environ` | `os.environ["K"] = v` | `EnvVarMutation` | P3 |
| `ast.Call` | func is `os.environ.__setitem__` or `os.environ.update` | `EnvVarMutation` | P3 |

Tiers are authoritative in `taxonomy.py`'s `TIER_MAP`. The table
above is a reference; `TIER_MAP` governs if there is a conflict.

### Contractual vs. incidental classification

For contract coverage computation, effects are classified as
**contractual** if their tier is P0 or P1:
`ReturnValue`, `ErrorReturn`, `ReceiverMutation`,
`PointerArgMutation`, `GlobalMutation`.

All other effects (P2–P4) are **incidental** for coverage
purposes. This boundary is defined here, not re-derived in
`quality.py` — `quality.py` delegates to this definition via
`taxonomy.is_contractual(effect_type: SideEffectType) -> bool`.

### Scoping

The visitor operates within a single `ast.FunctionDef` or
`ast.AsyncFunctionDef` body. Nested function definitions are
**skipped** — their bodies are not recursed into. This is a
fixed v1 behavior, not a parameter. Known limitation: inner
functions are not analyzed unless passed as separate targets.

The visitor stores `self._arg_names: set[str]` populated from
`node.args` in `visit_FunctionDef`, enabling it to distinguish
`d.update()` (where `d` is an argument) from attribute access
on non-argument names.

### Error handling

`analyze_module()` MUST catch `SyntaxError` from `ast.parse()`
and raise `GazeParseError(path, line, msg)` — a typed wrapper
defined in `analysis.py`. The CLI catches `GazeParseError` and
emits a human-readable error; the file is skipped and a warning
is appended to `metadata.warnings[]`.

`analyze_module()` MUST catch `RecursionError` from the AST
visitor and emit a warning with code `RECURSION_LIMIT` rather
than propagating.

### Path safety

All user-supplied paths MUST be resolved with `Path.resolve()`
and validated to remain within the project root before any file
I/O. Symlinks are followed once; the resolved path is
re-validated. Directory walking uses `Path.rglob("*.py")`,
excluding hidden directories (names starting with `.`) and
`__pycache__/`.

### ID generation

Stable ID: `"se-" + sha256(module + ":" + func + ":" + type + ":" + location)[:8]`

---

## Assertion Mapper Design (S2)

`AssertionVisitor(ast.NodeVisitor)` in `quality.py`:

### Recognised assertion patterns

| Pattern | Maps to |
|---|---|
| `assert result == x` | `ReturnValue` (if `result` bound to call) |
| `assert result is not None` | `ReturnValue` |
| `assert isinstance(result, T)` | `ReturnValue` |
| `assert f() == x` (inline) | `ReturnValue` |
| `with pytest.raises(E): f()` | `ErrorReturn` |
| `pytest.warns(W)` context | `StderrWrite` (not `LogWrite` — see note) |
| `assert obj.attr == x` | `ReceiverMutation` (if `obj` is receiver) |

**Note on `pytest.warns`**: `LogWrite` is not a detected side
effect type in this spec's detection table. `pytest.warns`
assertions are mapped to `StderrWrite` only, since Python
warnings are routed through `sys.stderr` by default. If
`LogWrite` detection is added in a future spec, the mapper
table will be updated accordingly.

### `gap_hints` field

`ContractCoverage.gap_hints` is `list[str]` — each entry is
a suggested `assert` snippet for the corresponding uncovered
contractual effect in `gaps`. Example: for an uncovered
`ReturnValue` effect on function `compute(x)`, the hint is
`"result = compute(x); assert result == <expected>"`.
`len(gap_hints) == len(gaps)` always.

### `suggestions` field

`OverSpecificationScore.suggestions` is `list[str]` — each
entry is actionable advice for the corresponding incidental
assertion. Example: `"assert internal_var is incidental; consider asserting the return value instead."` One suggestion per
incidental assertion: `len(suggestions) == count`.

### Coverage computation

```
contract_coverage = covered_contractual / total_contractual * 100
over_specification_ratio = incidental_asserted / total_assertions
```

Contractual effects: P0–P1 types as defined in Detection Design.
Incidental effects: P2–P4 types and intermediate variables.

Classification is delegated to `taxonomy.is_contractual()`,
not reimplemented in `quality.py`.

### Test isolation requirement

S2 tests in `test_quality.py` MUST construct `SideEffect`
objects directly (not call `analyze_function()`). This keeps
S2 tests isolated from S1 correctness — a bug in `analysis.py`
will not cause misleading failures in `test_quality.py`.

### Target function resolution

The mapper resolves which source function a test function targets
by:
1. Inspecting calls within the test body for the source function
   name.
2. Matching by name convention: `test_foo` → `foo`.
3. If both fail: `assertion_detection_confidence = 0`.

---

## CLI Flag Disposition (S4)

The existing `cli.py` stubs contain richer flag definitions than
what this spec implements. The disposition of each existing flag:

| Existing flag | Story | Disposition |
|---|---|---|
| `--function` | `analyze` | **Preserved** — passes function name filter to `analyze_module()` |
| `--include-unexported` | `analyze` | **Preserved** as `--include-private`; maps to Python's leading-underscore convention |
| `--classify` / `--verbose` | `analyze` | **Preserved** — passed through to `classify.py` |
| `--config` | all | **Preserved** — reads `.gaze.yaml` via existing `config.py` |
| `--contractual-threshold` / `--incidental-threshold` | `analyze` | **Preserved** — thresholds for classification |
| `--format` | all | **Preserved and implemented** in this spec |
| `--target` | `quality` | **Renamed** to positional `src_path` for simplicity; old flag kept as alias |
| `--ai-mapper` / `--ai-mapper-model` | `quality` | **Deferred** — stubs retained, not implemented in this spec |
| `--min-contract-coverage` / `--max-over-specification` | `quality` | **Deferred** — stubs retained, not implemented |
| `--coverprofile` | `quality` | **Implemented** in this spec (see below) |

**`--coverprofile` semantics**: The flag accepts a path to a
`.coverage` SQLite database produced by `coverage.py`. gaze-py
reads it via the `coverage` Python API (`coverage.CoverageData`).
This is NOT a Go-style text profile. The `coverage` package is
added as a runtime dependency. Validation: if the path does not
exist, exit 1 with a clear error before beginning analysis.

---

## Exit Code Contract

| Exit Code | Meaning |
|-----------|---------|
| 0 | Analysis completed successfully (results may be empty) |
| 1 | Input error (invalid path, missing file, bad flag, encoding error) |
| 2 | Internal analysis error (parse failure, unexpected exception) |
| 3 | Configuration error (invalid `.gaze.yaml`) |

A non-empty `metadata.warnings[]` does NOT change the exit code
if at least one result was produced. If zero results were produced
due to errors, exit code is 1 or 2 as appropriate.

---

## `metadata.warnings[]` Schema

Each warning in `metadata.warnings[]` is a string of the form:
`"<CODE>: <human-readable message>"`.

Warning codes:
- `PARSE_ERROR` — `ast.parse()` raised `SyntaxError` on a file
- `ENCODING_ERROR` — file could not be decoded as UTF-8
- `EMPTY_MODULE` — file contained no function definitions
- `RECURSION_LIMIT` — AST visitor hit Python's recursion limit

Example: `"PARSE_ERROR: cannot parse src/foo.py:12: invalid syntax"`

---

## Report Schema (S3)

The gaze-py analysis JSON schema is stored as a constant in
`src/gaze_py/report/schema.py`, following the Go gaze pattern
in `internal/report/schema.go`.

Top-level structure (analysis report):

```json
{
  "version": "0.1.0",
  "results": [
    {
      "target": {
        "package": "gaze_py.crap",
        "function": "compute_score",
        "signature": "compute_score(complexity: int, coverage: float) -> float",
        "location": "src/gaze_py/crap.py:12:0"
      },
      "side_effects": [],
      "metadata": {
        "gaze_version": "0.1.0",
        "gaze_py_version": "0.1.0",
        "python_version": "3.12.3",
        "duration_ms": 42,
        "timestamp": "2026-06-13T10:00:00Z",
        "warnings": []
      }
    }
  ]
}
```

`metadata` is per-result (inside `results[]`), consistent with
Go gaze's `AnalysisResult` structure. `duration_ms` measures
wall-clock time from the start of `analyze_function()` to return,
measured with `time.perf_counter_ns()` converted to milliseconds.

---

## S5 Operational Requirements

**Network failure**: If both `uv tool install` and `pip install`
fail (e.g., network unavailable), `installGazePy()` returns a
non-nil error with message: `"gaze-py install failed: <detail>"`.
`uf init` reports the step as FAILED, prints the error and the
manual install command (`pip install gaze-py==<version>`), and
continues with remaining steps (non-fatal for the overall init).

**`/gaze-report` command robustness**: The scaffold asset MUST
check `gaze-py` is on PATH before invoking it. If not found, emit:
`"gaze-py not found. Run 'uf init' to install it."` and exit
without running analysis. The `src/` and `tests/` paths in the
command body are defaults; the command reads `.gaze.yaml` if
present for project-specific path overrides.

**Known limitation**: Private PyPI mirrors and air-gapped
environments are not supported in v1. Users in restricted
environments must install `gaze-py` manually before `uf init`.

---

## Constitution Alignment

| Principle | Status | Notes |
|---|---|---|
| I. Accuracy | PASS | S1 US1 mandates 100% detection on fixture set with zero false positives (SC-008: pure function → empty list). `GazeParseError` on syntax errors ensures no silent false negatives from invalid source. Accuracy claims backed by regression tests in `test_analysis.py`. |
| II. Minimal Assumptions | PASS | No source annotation or restructuring required. The `test_foo → foo` name-convention assumption in the assertion mapper is explicit (plan.md Target function resolution). Encoding assumption (UTF-8) documented in Technical Context. When assumptions fail, `GazeParseError` surfaces them explicitly. |
| III. Actionable Output | PASS | Every output guides toward improvement: `gap_hints` provides assert snippets for uncovered effects; `suggestions` provides advice per incidental assertion; text formatter produces per-function tables with effect type, tier, location. Exit code contract allows CI scripts to act on failures. |
| IV. Testability | PASS | Every new function tested in isolation. Coverage targets specified with numeric thresholds (see Coverage Strategy). TDD ordering enforced in Phases 1–2. S2 tests isolated from S1 via direct `SideEffect` construction. Performance regression guarded by `@pytest.mark.slow` benchmark. |
