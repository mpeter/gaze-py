# Change 001: Initial Port — gaze-py

## Why

The unbound-force tool requires a Python-native GazeCRAP analysis engine. The
reference implementation is the Go `gaze` binary. gaze-py must produce
schema-compatible JSON output so that unbound-force can consume Python project
analysis the same way it consumes Go project analysis.

The previous implementation attempt was wiped because it invented its own
effect types, used wrong JSON field names, and never implemented classification
(R2). This change builds the correct implementation from scratch, grounded
entirely in the porting contracts.

## What Changes

All source code is new — the repo is currently a clean scaffold with no
`src/` or `tests/` directories.

### New Capabilities

- **R1 — Side Effect Detection**: AST visitor that detects all 38 effect types
  (P0 with zero false negatives; P1–P2 best-effort; P3–P4 defined but
  unimplemented) in Python source files, per EC-001 through EC-005.
  (Porting contract headers say "37" — this is a documentation bug; the
  canonical count is 38 by enumeration: P0=5+P1=8+P2=10+P3=9+P4=6. See
  specs.md EC-001 note.)
- **R2 — Classification**: Five-signal confidence engine (interface
  satisfaction, API visibility, caller dependency, naming convention,
  docstring) that labels each effect contractual/ambiguous/incidental, per
  CC-001 through CC-006.
- **R3 — CRAP Scoring**: CRAP and GazeCRAP formulas using cyclomatic
  complexity + line/contract coverage, per SC-001 through SC-003.
- **R4 — Quadrants and Fix Strategies**: Q1–Q4 quadrant classification and
  fix strategy assignment (add_tests, add_assertions, decompose_and_test,
  decompose) with recommended actions sorted by priority, per SC-004 through
  SC-006.
- **R5 — Output Formatting**: JSON (OC-002 canonical field names) and
  human-readable text output; nullable fields per OC-003.
- **CLI**: `gazepy analyze <path>` and `gazepy report <src> <tests>` commands
  via Click, installed as the `gazepy` binary.
- **Package infrastructure**: `pyproject.toml` with `name = "gaze-py"`,
  `import gaze`, ruff/mypy/pytest config, CI workflow.

### Modified Capabilities

None — no existing implementation.

### Removed Capabilities

None.

## Impact

- Creates `src/gaze/` package tree (taxonomy, analysis, classify, crap,
  report, cli subpackages)
- Creates `tests/` with conformance test suite and `tests/testdata/` fixtures
- Creates `pyproject.toml`
- Installs `gazepy` binary globally via `uv tool install`

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` (v1.1.1).

### I. Accuracy (Porting Contract Supremacy)

**Assessment**: PASS

All 38 effect types (37 per contract header — documentation bug; see specs.md
EC-001 note), tier assignments, confidence formula, signal weights,
CRAP/GazeCRAP formulas, quadrant rules, fix strategy ordering, and JSON field
names are taken verbatim from `../gaze/docs/porting/contracts.md` and
`taxonomy-reference.md`. No values are invented. Every contract ID (EC-001
through OC-003) maps to at least one test case.

### II. Minimal Assumptions

**Assessment**: PASS

AST-only analysis — no execution of analyzed code, no import of analyzed
modules, no runtime introspection. Coverage data accepted as external input
(line coverage percentage per function). O1 (quality/assertion mapping) is
deferred to a future change; contract_coverage and gaze_crap emit null when
O1 has not run, per OC-003.

### III. Actionable Output

**Assessment**: PASS

JSON output uses canonical snake_case field names (OC-002). Nullable fields
are null/absent when not computed, not zero (OC-003). Text output is
human-readable. The `recommended_actions` list is capped at 20, sorted by
fix strategy priority then CRAP descending (SC-006).

### IV. Testability

**Assessment**: PASS

Every contract ID has a corresponding test. P0 effects are tested with
zero-tolerance fixtures. Scoring formulas are tested against the reference
value table. Testdata fixtures under `tests/testdata/` are static .py files
that are never collected by pytest (norecursedirs enforced).

### V. Porting Contract Supremacy

**Assessment**: PASS

This proposal was written after reading contracts.md, requirements.md, and
taxonomy-reference.md in full. All capability scope, field names, formulas,
and tier assignments match the contracts. No element contradicts a porting
contract.

### VI. Composability First

**Assessment**: PASS

gaze-py is independently installable and usable without any other Unbound
Force hero or external service. The `gazepy` CLI is the sole required entry
point. Optional integrations (`--coverage-json`) degrade gracefully: when
absent, `line_coverage` and `crap` emit null and a warning is written to
stderr. The O1 capability (quality/assertion mapping) is deferred without
breaking the R1–R5 pipeline. No hard runtime dependency on any sibling hero
is introduced.

### VII. Supply Chain Integrity

**Assessment**: PASS (with known pending item)

- `uv.lock` will be committed as part of task 1.6 (immediately after `uv sync`
  creates it). This satisfies the lock-file requirement which activates once
  `pyproject.toml` is first committed.
- CI pipeline actions (`actions/checkout`, `astral-sh/setup-uv`) are already
  SHA-pinned with version tag comments in `.github/workflows/test.yml`.
- Runtime dependencies (`click`, `pyyaml`) are justified: `click` is the
  canonical CLI framework per CS-008; `pyyaml` is required for `.gaze.yaml`
  config loading. No `rich` dependency is added (CS-009 exception documented
  in design.md — gaze-py output is agent-consumed, not interactive terminal UI).
- New dependencies are documented in `pyproject.toml` with version constraints.
