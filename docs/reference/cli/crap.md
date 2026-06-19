# gazepy crap

Detect side effects and compute CRAP scores for a file or directory.

## Synopsis

```
gazepy crap [OPTIONS] PATH
```

## Description

Scans `PATH` for side effects, collects line coverage by running `pytest --cov` automatically (or from a pre-generated report via `--coverprofile`), and computes CRAP scores. Outputs a report with complexity, coverage, CRAP score, quadrant, and fix strategy per function.

Use `--max-crapload` as a CI gate to fail when too many high-CRAP functions exist.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `text` | Output format |
| `--coverprofile PATH` | auto-run pytest | Path to a pre-generated `coverage.py` JSON report |
| `--crap-threshold FLOAT` | `15.0` | CRAP score threshold for CRAPload computation |
| `--gaze-crap-threshold FLOAT` | `15.0` | GazeCRAP score threshold |
| `--max-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when CRAPload exceeds this value |
| `--max-gaze-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when GazeCRAPload exceeds this value |
| `--baseline PATH` | — | Baseline file for delta reporting (not yet implemented) |
| `--tests TEXT` | auto-discovered | Test directory or file |

## Output Format

**Text** (`--format text`, default): Per-function table with CC, coverage %, CRAP score, quadrant, and fix strategy. Summary shows CRAPload.

**JSON** (`--format json`): Full `AnalysisResult` including all CRAP-derived fields. See `gazepy schema`.

## CI Integration

```bash
# Fail if more than 5 high-CRAP functions
gazepy crap src/ --max-crapload 5

# Use a pre-generated coverage report (faster in CI)
coverage run -m pytest && coverage json
gazepy crap src/ --coverprofile coverage.json --max-crapload 5
```

## Examples

```bash
# Default: text output, auto-run pytest
gazepy crap src/

# JSON output with custom threshold
gazepy crap src/ --format json --crap-threshold 20.0

# Specific test file
gazepy crap src/ --tests tests/test_parser.py
```
