# gazepy analyze

Detect side effects for a file or directory and optionally classify them.

## Synopsis

```
gazepy analyze [OPTIONS] PATH
```

## Description

Scans `PATH` (a `.py` file or directory) for side effects using AST analysis. Directories are scanned recursively. Outputs an `AnalysisResult` JSON or text report.

CRAP scoring is not included in `analyze` output — use `gazepy crap` for CRAP-derived fields (`line_coverage`, `crap`, `fix_strategy`). Those fields are `null` in `analyze` output.

> **Note:** `--format` defaults to `json` (unlike Go gaze, which defaults to `text`).

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `json` | Output format |
| `-c, --classify` | off | Run the classification engine on detected effects |
| `-v, --verbose` | off | Full signal breakdown (implies `--classify`) |
| `--config PATH` | walk-up search | Path to `.gaze.yaml` configuration file |
| `--contractual-threshold INTEGER` | from config (80) | Override contractual confidence threshold |
| `--incidental-threshold INTEGER` | from config (50) | Override incidental confidence threshold |
| `-f, --function TEXT` | all functions | Analyze a specific function by name |
| `--include-unexported` | off | Include underscore-prefixed functions |

## Output Format

**JSON** (`--format json`): Emits a JSON object matching the `AnalysisResult` schema. Use `gazepy schema` to print the full JSON schema.

**Text** (`--format text`): Human-readable per-function side effect list with classification labels when `--classify` is active.

## Examples

```bash
# Analyze a single file, JSON output
gazepy analyze src/mymodule/parser.py

# Analyze with classification, text output
gazepy analyze src/ --classify --format text

# Analyze a single function
gazepy analyze src/mymodule/parser.py --function parse_expression

# Full signal breakdown
gazepy analyze src/ --verbose
```
