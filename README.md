# gaze-py

[![CI](https://github.com/mpeter/gaze-py/actions/workflows/test.yml/badge.svg)](https://github.com/mpeter/gaze-py/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/gaze-py)](https://pypi.org/project/gaze-py/)
[![Python](https://img.shields.io/pypi/pyversions/gaze-py)](https://pypi.org/project/gaze-py/)

gaze-py is a Python-native port of [gaze](https://github.com/unbound-force/gaze), the
GazeCRAP analysis engine. It detects observable side effects in Python functions using
AST-only static analysis (no code execution, no imports of analysed modules), classifies
each effect as contractual or incidental using a five-signal confidence engine, and
computes CRAP and GazeCRAP scores to surface functions that are both complex and
under-tested. The output is schema-compatible with the Go gaze implementation.

## Requirements

- Python 3.11+

## Installation

```bash
# Run without installing (recommended for one-off use)
uvx --from gaze-py gazepy --help

# Permanent install
uv tool install gaze-py

# Or with pip
pip install gaze-py
```

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
gazepy crap src/ --coverprofile cov.json

# Assess test quality and compute GazeCRAP scores
gazepy quality src/

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
pytest --cov=your_package --cov-report=json:cov.json
gazepy crap src/ --coverprofile cov.json

# Fail CI if crapload exceeds a threshold
gazepy crap src/ --max-crapload 30
```

When coverage is provided, the `line_coverage` and `crap` fields are populated in the
output. When omitted, those fields are `null` (not `0.0`) — null means "not measured",
not "zero coverage".

The `analyze` command detects side effects only — it does not compute CRAP scores.
Use `gazepy crap` for CRAP scoring.

## Quality assessment with `gazepy quality`

`gazepy quality` runs the full O1 pipeline: pairs test functions to their production
targets, detects assertion sites, maps assertions to detected side effects, and computes
GazeCRAP using contract coverage (the fraction of contractual effects covered by tests).

```bash
# Assess test quality — auto-discovers tests/ directory
gazepy quality src/

# Explicit tests directory
gazepy quality src/ --tests tests/

# JSON output
gazepy quality src/ --format=json

# Fail CI if average contract coverage drops below a threshold
gazepy quality src/ --min-contract-coverage 80
```

## Understanding the output

Each function in the output includes:

| Field | Description |
|---|---|
| `side_effects` | List of detected observable side effects with type, tier, and classification |
| `complexity` | McCabe cyclomatic complexity |
| `line_coverage` | Fraction of lines covered (0.0–1.0), or `null` if not provided |
| `crap` | CRAP score (complexity² × (1 − coverage)³ + complexity), or `null` |
| `gaze_crap` | GazeCRAP score using contract coverage; populated by `gazepy quality` |
| `quadrant` | Q1–Q4 classification based on CRAP and GazeCRAP; populated by `gazepy quality` |
| `fix_strategy` | Recommended action: `add_tests`, `add_assertions`, `decompose_and_test`, or `decompose` |
| `contract_coverage` | Fraction of contractual effects covered by tests; populated by `gazepy quality` |

The summary section includes `recommended_actions` — up to 20 functions sorted by
priority (add_tests → decompose_and_test → decompose) that exceed the CRAP threshold.

## Releasing

### Releasing a new version

1. Bump `version` in `pyproject.toml` and `__version__` in
   `src/gaze_py/__init__.py` in a PR. Merge to `main`.
2. Go to GitHub Actions → Release → Run workflow.
3. Enter the tag matching the version (e.g. `v0.3.0`).
4. Approve the `pypi` environment gate if configured.
5. The workflow validates, tags, builds, and publishes automatically.
