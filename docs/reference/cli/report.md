# gazepy report

Generate an analysis report for a file or directory.

## Synopsis

```
gazepy report [OPTIONS] [PATH]
```

## Description

Combines CRAP scoring, quality assessment, and document scanning into a single
report payload. The AI provider is selected via the `ai:` section of `.gaze.yaml`
or `GAZEPY_AI_*` environment variables.

- **No provider configured**: emits the raw JSON analysis payload to stdout
  (prompt-only mode).
- **Provider configured but unavailable**: falls back to prompt-only mode with a
  warning on stderr. Exit code is 0 in both cases.
- **Provider configured and available**: makes a direct HTTP REST call to the
  provider endpoint (`/api/generate` for Ollama, `rawPredict` for Vertex AI) and
  emits the narrative report.

When `--coverprofile` is not provided, gaze-py runs `pytest --cov` automatically.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `text` | Output format |
| `--coverprofile PATH` | auto-run pytest | Path to a pre-generated `coverage.py` JSON report |
| `--max-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when CRAPload exceeds this value |
| `--max-gaze-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when GazeCRAPload exceeds this value |
| `--min-contract-coverage FLOAT` | — | Minimum contract coverage percentage |
| `--tests TEXT` | auto-discovered | Test directory or file |
| `--model TEXT` | — | AI model override (takes precedence over `ai.model` in `.gaze.yaml`) |

## AI Configuration

Configure the AI provider in `.gaze.yaml` under the `ai:` block:

```yaml
ai:
  provider: ollama          # "ollama" or "vertex"
  model: llama3.2:3b        # model identifier
  endpoint: http://localhost:11434  # provider base URL (Ollama default)
  project: my-gcp-project   # GCP project (Vertex AI only)
  region: us-central1       # GCP region (Vertex AI only)
  timeout: 120              # HTTP request timeout in seconds
```

## Environment Variables

| Variable | Description |
|---|---|
| `GAZEPY_AI_PROVIDER` | AI provider: `ollama` or `vertex` |
| `GAZEPY_AI_MODEL` | Model identifier (e.g. `llama3.2:3b`, `claude-3-5-sonnet`) |
| `GAZEPY_AI_ENDPOINT` | Provider base URL |
| `GAZEPY_AI_PROJECT` | GCP project ID (Vertex AI only) |
| `GAZEPY_AI_REGION` | GCP region (Vertex AI only) |
| `GAZEPY_AI_TIMEOUT` | HTTP request timeout in seconds |

Environment variables take precedence over `.gaze.yaml` values. `--model` takes
precedence over both.

## Examples

```bash
# JSON report payload to stdout (no provider configured)
gazepy report src/ --format json

# With pre-generated coverage
gazepy report src/ --coverprofile coverage.json

# CI gate on both CRAP and GazeCRAP load
gazepy report src/ --max-crapload 10 --max-gaze-crapload 5

# Override model for a single invocation
gazepy report src/ --model llama3.2:3b
```
