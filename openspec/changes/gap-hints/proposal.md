## Why

The `quality` command computes contract coverage and identifies which
contractual effects have no mapped assertion, but discards the gap
information after computing the percentage. The result is a number —
say 40% — with no indication of which effects are uncovered or how to
cover them.

The `/gaze-fix` command, the `gaze-test-generator` agent, and the
`report` command (Change 4) all need this gap data. Without `gaps` and
`gap_hints` in the output, remediation is blind: the agent knows *that*
coverage is low but not *what* to write. This is a port of Go's
`hints.go` and the `Gaps`/`GapHints` fields in `ContractCoverage`.

## What Changes

### New Capabilities

- `quality-gap-hints`: `gaps` and `gap_hints` fields on
  `ContractCoverageResult` — the set of uncovered contractual effects
  and a parallel tuple of Python code snippets suggesting how to
  assert each one.

### Modified Capabilities

- `quality-coverage`: `compute_contract_coverage()` now populates
  `gaps` and `gap_hints` on the returned result. No behaviour change
  for existing callers — both fields default to `()`.
- `quality-output`: `quality_to_json()` serialises `gaps` (full
  `SideEffect` objects) and `gap_hints` (string array). `crap` JSON
  output is unchanged.

### Removed Capabilities

None.

## Impact

- `src/gaze_py/quality/hints.py` — new pure-function module
- `src/gaze_py/taxonomy/models.py` — two new fields on
  `ContractCoverageResult`
- `src/gaze_py/quality/coverage.py` — wire in `hint_for_effect()`
- `src/gaze_py/report/json_formatter.py` — schema update
- `tests/test_quality_hints.py` — new
- `tests/test_quality_coverage.py` — appended tests
- `tests/test_quality_integration.py` — appended test

## Acceptance Criteria

- AC-1: `len(result.gaps) == len(result.gap_hints)` for all contract coverage
  computations — the two sequences are always co-indexed.
- AC-2: All 38 `SideEffectType` values produce a non-empty hint string from
  `hint_for_effect()` — no silent fall-through to an empty string.
- AC-3: `quality_to_json()` output includes `gaps` (array of effect objects)
  and `gap_hints` (array of strings) when coverage is partial or zero.

## Constitution Alignment

Assessed against `.specify/memory/constitution.md`.

### I. Accuracy

**Assessment**: PASS

`hint_for_effect()` maps every effect type to a concrete assertion
snippet. All 38 `SideEffectType` values are covered; the match is
exhaustive with no fallback placeholder. Hints accurately reflect
the effect's semantic meaning.

### II. Minimal Assumptions

**Assessment**: PASS

`hints.py` is a pure function with no config, no engine, no network.
Hints are generated from the effect type and description only — no
assumptions about the test framework or project structure. All 38
effect types are covered; unknown types cannot occur (enum is closed).

### III. Actionable Output

**Assessment**: PASS

The gap is surfaced in existing JSON output without a new command or
flag. Consumers that already parse `quality` JSON gain actionable data
immediately after upgrading. Each hint is a concrete pytest code
snippet — not a generic description.

### IV. Testability

**Assessment**: PASS

`hint_for_effect()` is a pure function. Every branch is tested
independently. The postcondition `len(gaps) == len(gap_hints)` is
verified by unit tests. Integration test confirms real pipeline
produces non-empty hints for a fixture with coverage gaps.

### V. Porting Contract Supremacy

**Assessment**: PASS

Direct port of Go's `hints.go` and `ContractCoverage.{Gaps,GapHints}`
fields. Python hints are adapted to Python idioms (`pytest.raises`,
`capsys`, `io.BytesIO`) but carry the same semantic intent as the Go
snippets. No porting contract is modified or extended.

### VI. Composability First

**Assessment**: PASS

No new runtime dependencies. `hints.py` imports only from
`gaze_py.taxonomy`. Fully usable as a library — `hint_for_effect()`
is importable without the CLI.

### VII. Supply Chain Integrity

**Assessment**: PASS

No new dependencies. `hints.py` uses only stdlib and internal imports.
`uv.lock` unchanged.
