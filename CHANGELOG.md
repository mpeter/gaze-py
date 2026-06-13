# Changelog

All notable changes to gaze-py are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [0.1.0] — 2026-06-13

### Added

- **R1 — Side Effect Detection**: AST-only detection of 38 effect types
  (P0=5, P1=8, P2=10, P3=9, P4=6) across Python source files. P0 effects
  detected with zero false negatives; P1-P2 best-effort; P3-P4 in taxonomy
  with no-op detection.
- **R2 — Classification**: Five-signal confidence engine (interface
  satisfaction, API visibility, caller dependency, naming convention,
  docstring analysis) labels each effect contractual/ambiguous/incidental.
- **R3 — CRAP Scoring**: CRAP formula using cyclomatic complexity and
  external line coverage (via `--coverage-json`). Null-not-zero: `crap` is
  null when coverage is not provided.
- **R4 — Quadrants and Fix Strategies**: Q1-Q4 quadrant classification and
  fix strategy assignment (add_tests, decompose_and_test, decompose).
  Recommended actions sorted by priority, capped at 20.
- **R5 — Output Formatting**: JSON output (schema-compatible with Go gaze)
  and human-readable text output via `gazepy analyze` and `gazepy report`.
- **CLI**: `gazepy analyze <path>` and `gazepy report <src> <tests>`
  commands via Click, installed as the `gazepy` binary.
- **Package infrastructure**: `pyproject.toml` (name=gaze-py, import=gaze_py),
  ruff/mypy/pytest config, local wheel installation via `uv tool install`.

### Deferred (planned for future changes)

- GazeCRAP scoring and quadrant classification (requires O1 — quality/
  assertion mapping)
- PyPI publication (requires release workflow)
- Effect confidence range
