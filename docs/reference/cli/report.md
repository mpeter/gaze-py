# gazepy report

Generate an analysis report for a file or directory.

## Synopsis

```
gazepy report [OPTIONS] [PATH]
```

## Description

Combines CRAP scoring, quality assessment, and document scanning into a single report payload. Without `--ai`, emits the JSON payload to stdout. With `--ai`, calls the specified provider subprocess and returns a narrative report.

When `--coverprofile` is not provided, gaze-py runs `pytest --cov` automatically.

> **Note:** `--ai` and `--model` require the O1+O2 capability layer. These options accept arguments but the AI report generation pipeline is not available in the base `gaze-py` package.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `text` | Output format |
| `--coverprofile PATH` | auto-run pytest | Path to a pre-generated `coverage.py` JSON report |
| `--max-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when CRAPload exceeds this value |
| `--max-gaze-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when GazeCRAPload exceeds this value |
| `--min-contract-coverage FLOAT` | — | Minimum contract coverage percentage (requires O1) |
| `--tests TEXT` | auto-discovered | Test directory or file |
| `--ai TEXT` | — | AI provider for report generation (requires O1+O2) |
| `--model TEXT` | — | AI model to use for report generation |
| `--ai-timeout INTEGER` | — | Timeout in seconds for AI provider calls |

## Examples

```bash
# JSON report payload to stdout
gazepy report src/ --format json

# With pre-generated coverage
gazepy report src/ --coverprofile coverage.json

# CI gate on both CRAP and GazeCRAP load
gazepy report src/ --max-crapload 10 --max-gaze-crapload 5
```
