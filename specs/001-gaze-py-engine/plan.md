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
| `metadata.gaze_version` | `metadata.gaze_version` | Kept |
| — | `metadata.gaze_py_version` | Added |
| `quality_summary.ssa_degraded` | (omitted) | Not applicable |
| `quality_summary.ssa_degraded_packages` | (omitted) | Not applicable |

**Rationale**: Downstream consumers (opencode commands, CI gates)
parse the JSON by field name. Field names are stable across both
implementations. Language-specific metadata fields are renamed to
be self-documenting. SSA-specific fields are omitted cleanly since
gaze-py does not use SSA.

**Consequences**: A consumer that checks `metadata.go_version`
specifically will need updating. A consumer that checks
`metadata.gaze_version` works with both. The gaze-py JSON schema
(Draft 2020-12) MUST be committed alongside the code and tested
with `jsonschema` in CI.

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

**Consequences**: S5 requires a Go change to `unbound-force`.
This makes S5 the only cross-repo story. S5 MUST NOT begin until
S3 (schema) and S4 (CLI surface) are stable — the opencode command
template depends on the final subcommand names and flags.

---

## Technical Context

**Language/Version**: Python 3.12+
**Package manager**: uv
**Primary new dependencies**: none (stdlib `ast` only for S1–S2;
`radon` already available for complexity; `jsonschema` added for
schema validation tests)
**Testing**: pytest, `uv run pytest`
**Target platform**: macOS, Linux
**Performance goals**: < 2s for a 50-function module
**Constraints**: MUST NOT modify target source; analysis is
read-only; no annotation of source required

---

## Module Structure

### New files (gaze-py repo)

```text
src/gaze_py/
  analysis.py          S1: AST side-effect detection engine
  quality.py           S2: assertion mapper, contract coverage,
                           over-specification scoring
  report/
    __init__.py        S3: package root
    json.py            S3: JSON formatter (schema-compatible)
    text.py            S3: human-readable text formatter
    schema.py          S3: JSON Schema constant (Draft 2020-12)

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

### Modified files (gaze-py repo)

```text
src/gaze_py/
  cli.py               S4: add analyze, quality, report subcommands
  crap.py              S3: update formula to accept contract_coverage
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
  └─► S2 (quality.py)
        └─► S3 (report/, crap.py update)
              └─► S4 (cli.py expand)
                    └─► S5 (unbound-force: installGazePy + scaffold)
```

S1 and S2 tasks within each story are parallelisable (test
fixtures can be written while the visitor skeleton is built).
S5 MUST NOT begin before S4 is complete.

---

## Detection Design (S1)

`FunctionEffectVisitor(ast.NodeVisitor)` in `analysis.py`:

### Visit methods and mapped types

| AST node | Condition | SideEffectType |
|---|---|---|
| `ast.Return` | any | `ReturnValue` |
| `ast.Raise` | any | `ErrorReturn` |
| `ast.Global` + store | name in global list | `GlobalMutation` |
| `ast.Assign` / `ast.AugAssign` | target is `ast.Attribute` on `self` | `ReceiverMutation` |
| `ast.Call` on arg name | `.update()`, `.append()`, `.extend()`, `.__setitem__()`, `.pop()`, `.clear()`, `.add()`, `.discard()` | `PointerArgMutation` |
| `ast.Subscript` store on arg | e.g. `d["k"] = v` | `PointerArgMutation` |
| `ast.Call` | func is `print` or `sys.stdout.write` | `StdoutWrite` |
| `ast.Call` | func is `sys.stderr.write` | `StderrWrite` |
| `ast.Subscript` store on `os.environ` | `os.environ["K"] = v` | `EnvVarMutation` |
| `ast.Call` | func is `os.environ.__setitem__` or `os.environ.update` | `EnvVarMutation` |

### Scoping

The visitor operates within a single `ast.FunctionDef` or
`ast.AsyncFunctionDef` body. Nested function definitions are
visited as opaque callables — their bodies are not recursed into
unless `analyze_nested=True` is passed (default: False).

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
| `pytest.warns(W)` context | `LogWrite` / `StderrWrite` |
| `assert obj.attr == x` | `ReceiverMutation` (if `obj` is receiver) |

### Coverage computation

```
contract_coverage = covered_contractual / total_contractual * 100
over_specification_ratio = incidental_asserted / total_assertions
```

Contractual effects: `ReturnValue`, `ErrorReturn`, `ReceiverMutation`,
`PointerArgMutation`, `GlobalMutation`.

Incidental effects: everything else (P3–P4, intermediate variables).

### Target function resolution

The mapper resolves which source function a test function targets
by:
1. Inspecting calls within the test body for the source function
   name.
2. Matching by name convention: `test_foo` → `foo`.
3. If both fail: `assertion_detection_confidence = 0`.

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
      "side_effects": [...],
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

---

## Constitution Alignment

| Principle | Status | Notes |
|---|---|---|
| I. Autonomous Collaboration | PASS | gaze-py is independently installable and produces self-contained JSON artifacts. No runtime coupling to other heroes. |
| II. Composability First | PASS | Each story (S1–S4) is independently testable. S5 adds integration without making it mandatory. |
| III. Observable Quality | PASS | JSON output (Draft 2020-12 schema) with provenance metadata. Text output for humans. Both formats tested in CI. |
| IV. Testability | PASS | Every new function is tested in isolation. Test fixtures are static Python files — no external services required. |
