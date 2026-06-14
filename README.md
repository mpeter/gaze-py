# gaze-py

gaze-py is a Python-native port of [gaze](https://github.com/unbound-force/gaze), the
GazeCRAP analysis engine. It detects observable side effects in Python functions using
AST-only static analysis (no code execution, no imports of analysed modules), classifies
each effect as contractual or incidental using a five-signal confidence engine, and
computes CRAP and GazeCRAP scores to surface functions that are both complex and
under-tested. The output is schema-compatible with the Go gaze implementation.

## Requirements

- Python 3.11+

## Installation (local wheel)

gaze-py is not yet published to PyPI. Install from a locally built wheel:

```bash
uv build
uv tool install --force dist/gaze_py-*.whl
```

This installs the `gazepy` binary into your PATH via `uv tool`.

> **Note**: `uv tool install gaze-py` (from PyPI) will not work — PyPI publication
> is deferred to a future release.

## Basic usage

```bash
# Analyse a source directory (CRAP will be null — no coverage provided)
gazepy analyze src/

# JSON output (default)
gazepy analyze src/ --format=json

# Human-readable text output (one line per function)
gazepy analyze src/ --format=text

# CRAP scoring — auto-runs pytest for coverage
gazepy crap src/

# CRAP scoring with a pre-generated coverage report
gazepy crap src/ --coverprofile coverage.json

# Scaffold OpenCode agent and command files into .opencode/
gazepy init
```

## CRAP scoring with `gazepy crap`

CRAP scoring requires line coverage data. The `crap` command can collect coverage
automatically by running pytest, or accept a pre-generated `coverage.py` JSON report:

```bash
# Auto-run pytest and collect coverage (requires pytest-cov)
gazepy crap src/

# Use a pre-generated coverage report (recommended in CI to avoid a double test run)
pytest --cov=your_package --cov-report=json:coverage.json
gazepy crap src/ --coverprofile coverage.json
```

When coverage is provided, the `line_coverage` and `crap` fields are populated in the
output. When omitted, those fields are `null` (not `0.0`) — null means "not measured",
not "zero coverage". GazeCRAP and quadrant fields remain `null` until O1 ships.

The `analyze` command detects side effects only — it does not compute CRAP scores.
Use `gazepy crap` for CRAP scoring.

## Understanding the output

Each function in the output includes:

| Field | Description |
|---|---|
| `side_effects` | List of detected observable side effects with type, tier, and classification |
| `complexity` | McCabe cyclomatic complexity |
| `line_coverage` | Fraction of lines covered (0.0–1.0), or `null` if not provided |
| `crap` | CRAP score (complexity² × (1 − coverage)³ + complexity), or `null` |
| `gaze_crap` | GazeCRAP score using contract coverage, or `null` (O1 deferred) |
| `quadrant` | Q1–Q4 classification based on CRAP and GazeCRAP, or `null` |
| `fix_strategy` | Recommended action: `add_tests`, `decompose_and_test`, or `decompose` |
| `contract_coverage` | Fraction of contractual effects covered by tests, or `null` |

The summary section includes `recommended_actions` — up to 20 functions sorted by
priority (add_tests → decompose_and_test → decompose) that exceed the CRAP threshold.

## Current limitations

- **GazeCRAP scoring deferred**: The O1 quality/assertion mapping engine (which
  computes `contract_coverage` from test assertions) is not yet implemented. As a
  result, `gaze_crap`, `contract_coverage`, and `quadrant` are always `null` in this
  release. The `fix_strategy` field uses CRAP-only rules (Q3/add_assertions is
  unreachable without O1).
- **PyPI publication deferred**: The package is not yet on PyPI. Install from a local
  wheel as described above.
- **Effect confidence range deferred**: The `effect_confidence_range` field is present
  in the output schema (as `null`) but not yet computed.
