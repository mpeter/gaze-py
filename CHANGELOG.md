# Changelog

## [Unreleased]

### Added
- `analysis.py`: AST-based side-effect detection engine (S1)
- `quality.py`: Assertion mapper and contract coverage computation (S2)
- `report/`: JSON (schema-compatible with Go gaze) and text formatters (S3)
- `analyze`, `quality`, `report` CLI subcommands (S4)
- Domain types: `QualityReport`, `ContractCoverage`, `OverSpecificationScore`, `PackageSummary`, `AssertionMapping` added to `taxonomy.py`
