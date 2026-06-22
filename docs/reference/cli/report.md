# gazepy report

Generate an analysis report for a file or directory.

## Synopsis

```
gazepy report [OPTIONS] [PATH]
```

## Description

Combines CRAP scoring, quality assessment, and document scanning into a single report payload. When no AI provider is configured, emits the JSON payload to stdout. When an AI provider is configured (via `.gaze.yaml` or environment variables), calls the provider over HTTP and returns a narrative report.

When `--coverprofile` is not provided, gaze-py runs `pytest --cov` automatically.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `text` | Output format |
| `--coverprofile PATH` | auto-run pytest | Path to a pre-generated `coverage.py` JSON report |
| `--max-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when CRAPload exceeds this value |
| `--max-gaze-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when GazeCRAPload exceeds this value |
| `--min-contract-coverage FLOAT` | — | Minimum contract coverage percentage (requires quality assessment) |
| `--tests TEXT` | auto-discovered | Test directory or file |

## AI Provider Configuration

Configure an AI provider in `.gaze.yaml` under the `ai:` key:

```yaml
ai:
  provider: ollama          # or: vertex
  model: llama3.2:3b
  timeout: 120
  base_url: http://localhost:11434   # Ollama default
```

Or via environment variables:

| Variable | Description |
|---|---|
| `GAZEPY_AI_PROVIDER` | Provider name (`ollama`, `vertex`) |
| `GAZEPY_AI_MODEL` | Model identifier |
| `GAZEPY_AI_TIMEOUT` | Request timeout in seconds |
| `GAZEPY_AI_BASE_URL` | Provider base URL (Ollama) |

Without a configured provider, `gazepy report` emits the raw analysis JSON to stdout.

## Examples

```bash
# JSON report payload to stdout (no AI provider configured)
gazepy report src/ --format json

# With pre-generated coverage
gazepy report src/ --coverprofile coverage.json

# CI gate on both CRAP and GazeCRAP load
gazepy report src/ --max-crapload 10 --max-gaze-crapload 5
```
