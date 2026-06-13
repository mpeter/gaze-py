# Changelog

## [Unreleased] — 2026-06-13

Spec: specs/001-gaze-py-engine/spec.md

### Added
- `analysis.py`: AST-based side-effect detection engine (S1)
- `quality.py`: Assertion mapper and contract coverage computation (S2)
- `report/`: JSON (schema-compatible with Go gaze) and text formatters (S3)
- `analyze`, `quality`, `report` CLI subcommands (S4)
- Domain types: `QualityReport`, `ContractCoverage`, `OverSpecificationScore`, `PackageSummary`, `AssertionMapping` added to `taxonomy.py`

### Deferred
- `--coverprofile` flag validates path but does not yet read `.coverage` SQLite (planned for v0.2)
