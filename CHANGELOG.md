# Changelog

All notable changes to gaze-py are documented here.

## [0.4.1] — 2026-06-15

### Bug Fixes

- **`gazepy init` scaffold asset names corrected** — `init` now deploys
  `gaze-reporter.md` and `gaze.md` instead of `gazepy-reporter.md` and
  `gazepy.md`, coordinated with the `replicator init` sentinel change.

### Improvements

- **`docscan` repo-root detection** — Uses the shared `SENTINELS` frozenset
  from `gaze_py.config.loader` instead of hard-coded filename checks, keeping
  repo-root detection consistent across the codebase.

## [0.4.0] — 2026-06-14

### New Features

- **O3 Document Scanning** — `gazepy docscan` is now a real command. Walks
  the repository for `.md` files, applies glob filtering, assigns proximity
  priority (1=same-dir, 2=repo-root, 3=other), and emits a JSON array of
  `{path, content, priority}` objects or a text summary.
- **Signal 5 augmentation** — `gazepy analyze` and `gazepy crap` now
  automatically scan project docs before analysis. The documentation signal
  (CC-005, Signal 5) incorporates project-level behavioral declarations from
  `.md` files alongside per-function docstrings. Scan failures degrade
  gracefully (warning to stderr, analysis continues).
- **`.gaze.yaml` `doc_scan` config** — new `classification.doc_scan` block
  supports `exclude`, `include`, and `timeout` settings.

### Usage

```bash
# Scan project docs and list discovered files
gazepy docscan

# JSON output (default)
gazepy docscan . --format=json

# Override exclude patterns
gazepy docscan . --exclude "docs/internal/**" --exclude "vendor/**"

# Analyze with doc augmentation (happens automatically)
gazepy analyze src/mypackage/
```

## [0.3.1] — 2026-06-14

### Bug Fixes / Improvements

- **`effect_confidence_range` now populated** — `Score.effect_confidence_range`
  is no longer always `null`. When all detected effects on a function are
  classified as ambiguous (`reason == "all_effects_ambiguous"`), the field
  is set to `[min_confidence, max_confidence]` (two ints in [0,100]).
  Matches Go gaze reference semantics. In all other cases it remains `null`.
- **Complexity algorithm formally specified** — `analysis/complexity.py`
  algorithm is now locked by 7 new round-trip tests with exact expected
  values. The previous `test_high_complexity_function_greater_than_1`
  (asserted `> 1`) is replaced by `test_high_complexity_function_exact_value`
  (asserts `== 9`).

## [0.3.0] — 2026-06-14

### New Features

- **O1 quality assessment pipeline** — `gazepy quality` is now a real command.
  Pairs test functions to their production targets, detects assertion sites,
  maps assertions to detected side effects, and computes contract coverage.
- **GazeCRAP scores** — `Score.gaze_crap` is now populated when running
  `gazepy quality`. Uses contract coverage (not line coverage) as input to
  the GazeCRAP formula (SC-002).
- **Quadrant classification** — `Score.quadrant` (Q1–Q4) now populated.
- **Contract coverage** — `Score.contract_coverage` (0–100%) now populated.
- **Summary fields** — `gaze_crapload`, `avg_contract_coverage`,
  `quadrant_counts`, `fix_strategy_counts` all now populated.
- **Shared analysis utilities** — `analysis/files.py` and `analysis/runner.py`
  extracted as reusable pipeline primitives.

### Usage

```bash
# Assess test quality and compute GazeCRAP
gazepy quality src/mypackage/ --tests tests/ --format=json

# Auto-discover tests directory
gazepy quality src/mypackage/

# CI gate: fail if average contract coverage below threshold
gazepy quality src/mypackage/ --min-contract-coverage 80
```

## [0.2.0] — 2026-06-14

### Breaking Changes

- **`analyze` JSON schema change**: `analyze` no longer emits CRAP scoring
  fields. All CRAP-derived fields in `FunctionTarget` (`line_coverage`, `crap`,
  `gaze_crap`, `fix_strategy`, `quadrant`, `contract_coverage`) are now `null`
  in `analyze` output. `Summary.crapload` is also `null`. Callers that relied
  on non-null CRAP fields from `gazepy analyze` must migrate to `gazepy crap`.

- **`report` CLI signature change**: The `report` command signature changes from
  `gazepy report <src> <tests>` (two positional arguments) to `gazepy report
  [path]` (one optional positional argument). The old two-argument invocation
  produces a Click `UsageError` (exit 2). Use `gazepy crap [path]` for CRAP
  scoring previously available via `gazepy report`.

- **`--coverage-json` flag removed from `analyze`**: The `--coverage-json` flag
  has been removed from `gazepy analyze`. It has moved to `gazepy crap` as
  `--coverprofile`. Update any scripts or agent configs that pass `--coverage-json`
  to `analyze`.

### New Features

- **`gazepy crap` command**: Full CRAP scoring pipeline. Accepts `PATH`
  (directory or file), auto-runs pytest for coverage when no `--coverprofile`
  is provided, enforces `--max-crapload` CI gate (exit 1 on violation).
  Flag surface matches Go gaze `newCrapCmd` exactly.

- **New flags on `gazepy analyze`**: `--classify` / `-c`, `--verbose` / `-v`,
  `--config`, `--contractual-threshold`, `--incidental-threshold`,
  `--function` / `-f`, `--include-unexported`. Achieves flag-level parity
  with Go gaze `newAnalyzeCmd`.

### New Commands

- **`quality` (stub)**: Accepts full Go gaze flag surface. Exits 1 with
  guidance to use Go gaze until O1 (change 002/A) is implemented.
- **`docscan` (stub)**: Accepts `[PATH]` and `--config`. Exits 1 with
  guidance to use Go gaze until O3 is implemented.
- **`schema`**: Emits the JSON schema for the `AnalysisResult` envelope used
  by `analyze` and `crap` output.
- **`self-check`**: Runs CRAP analysis on gaze-py's own source tree
  (`src/gaze_py/`). Walks up from cwd to find the project root via
  `pyproject.toml`. Supports `--format`, `--max-crapload`, and
  `--max-gaze-crapload`.
- **`init`**: Scaffolds `.opencode/agents/gazepy-reporter.md` and
  `.opencode/commands/gazepy.md` into the current project. Idempotent;
  use `--force` to overwrite existing user-owned files.

### Migration Guide

| Old invocation | New invocation |
|---|---|
| `gazepy analyze <path> --coverage-json=cov.json` | `gazepy crap <path> --coverprofile=cov.json` |
| `gazepy report <src> <tests>` | `gazepy crap <src>` |

## [0.1.0] — 2026-06-13

Initial release — Python-native port of the Go gaze GazeCRAP analysis engine.

### Features

- **Side-effect detection engine** — AST-only static analysis of Python source
  files. Detects 38 observable side-effect types across five tiers (P0–P4),
  matching the Go gaze taxonomy exactly (EC-001).
- **CRAP and GazeCRAP scoring** — Implements the CRAP formula
  (complexity² × (1 − coverage)³ + complexity) and the GazeCRAP variant using
  contract coverage instead of line coverage (SC-001, SC-002).
- **Five-signal confidence classification** — Classifies each detected effect
  as contractual or incidental using configurable confidence thresholds.
- **JSON output** — Schema-compatible with the Go gaze implementation.
  Null fields serialize as `null`, not `0.0` or `""` (OC-003).
- **CLI commands**: `analyze` (detect + classify), `report` (two-argument
  positional form: `gazepy report <src> <tests>`).
- **`.gaze.yaml` configuration** — `contractual_threshold` and
  `incidental_threshold` configurable per-project.
- **Python 3.11+** — Tested on CPython 3.11, 3.12, 3.13.
