# gazepy quality

Assess contract coverage and GazeCRAP scores for a file or directory.

## Synopsis

```
gazepy quality [OPTIONS] PATH
```

## Description

Pairs production functions with their test functions, maps test assertions to production side effects, and computes contract coverage and GazeCRAP scores. This is the O1 layer — it requires both production source and test source.

When `--tests` is not provided, gaze-py auto-discovers the test directory by searching for `tests/`, `test/`, or `test_*.py` relative to `PATH`'s parent, then relative to the current working directory.

Use `--min-contract-coverage` as a CI gate.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `text` | Output format |
| `--tests TEXT` | auto-discovered | Path to test directory or file |
| `--target TEXT` | all | Restrict to tests exercising a specific production function name |
| `-v, --verbose` | off | Full signal breakdown |
| `--include-unexported` | on | Include underscore-prefixed functions |
| `--config PATH` | walk-up search | Path to `.gaze.yaml` configuration file |
| `--contractual-threshold INTEGER` | from config (80) | Override contractual confidence threshold |
| `--incidental-threshold INTEGER` | from config (50) | Override incidental confidence threshold |
| `--min-contract-coverage FLOAT` | — | CI gate: exit 1 if average contract coverage is below this percentage |
| `--max-over-specification FLOAT` | — | Maximum allowed over-specification percentage |

## Output Format

**Text** (default): Per-function report showing contract coverage %, GazeCRAP score, and gap hints (side effects not covered by assertions).

**JSON**: Full quality assessment including all pairing and mapper data.

## CI Integration

```bash
# Fail if contract coverage drops below 70%
gazepy quality src/ --tests tests/ --min-contract-coverage 70
```

## Examples

```bash
# Run quality assessment
gazepy quality src/

# Specify test directory explicitly
gazepy quality src/mymodule/ --tests tests/unit/

# Full breakdown for a single function
gazepy quality src/mymodule/parser.py --target parse_expression --verbose
```
