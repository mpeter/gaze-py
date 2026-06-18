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

## AI Reports

`gazepy report` can pass the analysis JSON to a local or cloud AI provider to generate
a narrative interpretation. Configure your provider in `.gaze.yaml`:

```yaml
ai:
  provider: ollama       # or: vertex
  model: llama3.2:3b     # any Ollama model, or a Vertex Claude model ID
  endpoint: http://localhost:11434   # Ollama only; ignored for Vertex
  timeout: 120           # seconds per HTTP request (default: 120)
```

For Google Vertex AI (Claude models):
```yaml
ai:
  provider: vertex
  model: claude-sonnet-4-6
  project: my-gcp-project
  region: us-east5
```

**Environment variable overrides** (higher precedence than config file):

| Variable | Description |
|---|---|
| `GAZEPY_AI_PROVIDER` | Provider name (`ollama` or `vertex`) |
| `GAZEPY_AI_MODEL` | Model ID (setting only this implies `ollama`) |
| `GAZEPY_AI_ENDPOINT` | Ollama base URL (default: `http://localhost:11434`) |
| `GAZEPY_AI_PROJECT` | GCP project ID (Vertex only) |
| `GAZEPY_AI_REGION` | GCP region (Vertex only) |
| `GAZEPY_AI_TIMEOUT` | HTTP timeout in seconds |

**Prerequisites**:
- Ollama: install from [ollama.com](https://ollama.com) and pull your model (`ollama pull llama3.2:3b`)
- Vertex: install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) and run `gcloud auth application-default login`

**If no provider is configured**, `gazepy report` emits the raw analysis JSON to stdout and a tip to stderr.

**Migration from `--ai` flag**: the `--ai` and `--ai-timeout` flags have been removed.
Configure your provider in `.gaze.yaml` instead (see above).

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `gcloud auth print-access-token failed (exit 1)` | Not authenticated | Run `gcloud auth application-default login` |
| `vertex provider requires gcloud CLI` | gcloud not on PATH | Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) |
| `unexpected response format from gcloud auth print-access-token` | Outdated gcloud | Run `gcloud components update` |
| `Ollama request timed out after Ns` | Model is slow or timeout too short | Increase `ai.timeout` in `.gaze.yaml` (e.g. `timeout: 300`) |
| `Ollama request failed: Connection refused` | Ollama not running | Start Ollama: `ollama serve` |
| `Ollama returned HTTP 404` | Model not pulled | Pull the model: `ollama pull llama3.2:3b` |
| `Vertex AI rate limited after 5 retries` | API quota exceeded | Wait and retry, or reduce request frequency |
| `Vertex AI returned HTTP 401` after token refresh | Credentials expired | Run `gcloud auth application-default login` again |
| `Warning: ollama provider configured but not available` | Model not pulled or Ollama not running | Pull the model or start Ollama; report falls back to prompt-only mode |
| `Invalid value for GAZEPY_AI_TIMEOUT` | Non-integer or non-positive timeout | Set `GAZEPY_AI_TIMEOUT` to a positive integer (e.g. `120`) |

## Releasing

### Releasing a new version

1. Bump `version` in `pyproject.toml` and `__version__` in
   `src/gaze_py/__init__.py` in a PR. Merge to `main`.
2. Go to GitHub Actions → Release → Run workflow.
3. Enter the tag matching the version (e.g. `v0.3.0`).
4. Approve the `pypi` environment gate if configured.
5. The workflow validates, tags, builds, and publishes automatically.
