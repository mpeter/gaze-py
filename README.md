# gaze-py

Python-native GazeCRAP analysis engine — a port of [gaze](https://github.com/unbound-force/gaze).

Detects observable side effects in Python functions using AST-only analysis,
classifies them as contractual or incidental, and computes CRAP and GazeCRAP scores.

## Requirements

- Python 3.11+

## Installation (local wheel)

```bash
uv build
uv tool install dist/gaze_py-0.1.0-py3-none-any.whl --force
```

> **Note**: gaze-py is not yet published to PyPI. `uv tool install gaze-py` will not work.

## Usage

```bash
# Analyse a source directory (no coverage — CRAP will be null)
gazepy analyze src/

# Analyse with coverage data (enables CRAP scoring)
gazepy analyze src/ --coverage-json coverage.json

# JSON output (default)
gazepy analyze src/ --format=json

# Text output (one line per function)
gazepy analyze src/ --format=text

# Report command (O1 quality assessment deferred — behaves like analyze)
gazepy report src/ tests/
```

### `--coverage-json`

Accepts a `coverage.py` JSON report (`coverage json` or `pytest --cov-report=json`).
When provided, `line_coverage`, `crap`, and related fields are populated.
When omitted, those fields are `null` in the output (not `0.0`).
