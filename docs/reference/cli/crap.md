# gazepy crap

Detect side effects and compute CRAP scores for a file or directory.

## Synopsis

```
gazepy crap [OPTIONS] PATH
```

## Description

Scans `PATH` for side effects, collects line coverage by running `pytest --cov` automatically (or from a pre-generated report via `--coverprofile`), and computes CRAP scores. Outputs a report with complexity, coverage, CRAP score, quadrant, and fix strategy per function.

Use `--max-crapload` as a CI gate to fail when too many high-CRAP functions exist.

Use `--baseline` to compare current scores against a previously saved baseline and fail on regressions.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `text` | Output format |
| `--coverprofile PATH` | auto-run pytest | Path to a pre-generated `coverage.py` JSON report |
| `--crap-threshold FLOAT` | `15.0` | CRAP score threshold for CRAPload computation |
| `--gaze-crap-threshold FLOAT` | `15.0` | GazeCRAP score threshold |
| `--max-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when CRAPload exceeds this value |
| `--max-gaze-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when GazeCRAPload exceeds this value |
| `--baseline PATH` | auto-discovered | Path to a baseline JSON file for delta reporting |
| `--tests TEXT` | auto-discovered | Test directory or file |

## Baseline Comparison

When `--baseline` is provided (or a baseline is auto-discovered), `gazepy crap` compares the current CRAP scores against the saved baseline and emits a comparison report. The command exits 1 when any regression or new violation is found.

### Auto-Discovery

When `--baseline` is not specified and `baseline.file` is not set in `.gaze.yaml`, `gazepy crap` automatically checks for `.gaze/baseline.json` relative to the analysis root. If the file exists, it is loaded silently. If it is missing or corrupt, a warning is emitted to stderr and the comparison is skipped (no exit 2).

### Generating a Baseline

```bash
gazepy crap src/ --format=json > .gaze/baseline.json
```

### Baseline Output Format (JSON)

When a baseline comparison runs, the JSON output envelope changes:

```json
{
  "results": [...],         // current entries enriched with baseline_crap, crap_delta, status
  "new_functions": [...],   // functions not in baseline (status: "new" or "new_violation")
  "removed_functions": [...], // functions in baseline but not current (status: "removed")
  "comparison": {
    "regressions": 0,
    "improvements": 1,
    "unchanged": 3,
    "new_functions": 0,
    "new_violations": 0,
    "removed_functions": 0,
    "passed": true,
    "epsilon": 0.0,
    "new_function_threshold": 15.0
  },
  "summary": {...}          // same as normal crap --format=json summary
}
```

Each entry in `results` gains these optional fields:
- `baseline_crap` — CRAP score from the baseline (null when not in baseline)
- `crap_delta` — current minus baseline CRAP (positive = worse)
- `baseline_gaze_crap` — GazeCRAP from baseline (null when unavailable)
- `gaze_crap_delta` — GazeCRAP delta (null when baseline had no GazeCRAP data)
- `status` — one of `"regression"`, `"improvement"`, `"unchanged"`

### `.gaze.yaml` Configuration

| Key | Type | Default | Description |
|---|---|---|---|
| `baseline.file` | `str \| null` | `null` | Explicit path to baseline JSON. When set, treated as explicit (exit 2 on error). |
| `baseline.epsilon` | `float` | `0.0` | Minimum delta magnitude to trigger regression/improvement. Deltas within `[-epsilon, +epsilon]` are `unchanged`. Must be ≥ 0. |
| `baseline.new_function_threshold` | `float \| null` | `null` | CRAP score above which a new function is a `new_violation`. When `null`, uses `scoring.crap_threshold` (default 15.0). Must be > 0 when set. |

Example `.gaze.yaml`:

```yaml
baseline:
  file: null                    # auto-discover .gaze/baseline.json
  epsilon: 0.5                  # ignore deltas ≤ 0.5
  new_function_threshold: 20.0  # new functions with CRAP > 20 are violations
```

### Edge Cases

- **File-rename false positives**: When source files are renamed, all functions in the old file appear as "removed" and all functions in the new file appear as "new". If more than 50% of baseline functions are unmatched, a warning is emitted to stderr suggesting file renames as the cause.
- **Corrupt auto-discovered file**: When `.gaze/baseline.json` is corrupt or unreadable, a warning is emitted to stderr and the comparison is skipped. The command exits 0 with normal CRAP output. This prevents CI failures caused by a stale or partially-written baseline file.
- **Explicit path errors**: When `--baseline` is provided explicitly (or via `baseline.file` in config) and the file is missing, empty, or corrupt, the command exits 2 with an actionable error message.

## Output Format

**Text** (`--format text`, default): Per-function table with CC, coverage %, CRAP score, quadrant, and fix strategy. Summary shows CRAPload. When a baseline is loaded, a comparison section is appended showing PASS/FAIL verdict, counts, and regression/improvement tables.

**JSON** (`--format json`): Top-level envelope is `{"results": [...], "summary": {...}}`. Each entry in `results` wraps function identity in a `target` object (`package`, `function`, `receiver`, `signature`, `location`) and includes `metadata` (`gaze_version`, `duration_ms`, `timestamp`). CRAP-derived fields (`line_coverage`, `crap`, `gaze_crap`, `fix_strategy`, `quadrant`) appear at the top level of each result entry. See `gazepy schema`. When a baseline is loaded, the envelope gains `new_functions`, `removed_functions`, and `comparison` keys (see above).

## CI Integration

```bash
# Fail if more than 5 high-CRAP functions
gazepy crap src/ --max-crapload 5

# Use a pre-generated coverage report (faster in CI)
coverage run -m pytest && coverage json
gazepy crap src/ --coverprofile coverage.json --max-crapload 5

# Save a baseline and compare on next run
gazepy crap src/ --format=json > .gaze/baseline.json
gazepy crap src/  # auto-discovers .gaze/baseline.json; exits 1 on regression

# Explicit baseline with epsilon tolerance
gazepy crap src/ --baseline=.gaze/baseline.json
```

## Examples

```bash
# Default: text output, auto-run pytest
gazepy crap src/

# JSON output with custom threshold
gazepy crap src/ --format json --crap-threshold 20.0

# Specific test file
gazepy crap src/ --tests tests/test_parser.py

# Compare against a saved baseline
gazepy crap src/ --baseline=.gaze/baseline.json --format=json

# Generate a new baseline
gazepy crap src/ --format=json > .gaze/baseline.json
```
