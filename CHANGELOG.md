# Changelog

## [Unreleased] — 2026-06-13

### Breaking Changes
- Binary renamed from `gaze-py` to `gazepy`. The PyPI package name (`gaze-py`)
  and Python import path (`gaze_py`) are unchanged. Update any scripts or
  PATH references from `gaze-py` to `gazepy`.



Spec: openspec/changes/quality-call-scanning/proposal.md

### Also Breaking
- `report --format=json` output schema changed from analysis format
  (`version` + `results`) to quality format (`quality_reports` +
  `quality_summary`). Consumers of `gaze-py report --format=json`
  must update their parsers. The previous output was incorrect
  (emitted raw analysis data instead of quality coverage metrics);
  this is the intended schema per the original spec.

### Fixed (opsx/quality-call-scanning)
- `quality.py`: `map_assertions()` now finds all test functions including
  class-based test methods (`class TestFoo: def test_bar`), not just the
  first top-level `def test_*` function. Resolves zero-mapping on standard
  pytest projects that name test files after modules rather than functions.
- `quality.py`: target function resolution now uses call-scanning
  (`_extract_called_names`) instead of filename convention — tests are
  matched to source functions by what they actually call, not by name.
- `cli.py`: `report` command builds an inverted index of test files in
  one pass, eliminating the O(functions × files) cost of the previous loop.
- `cli.py`: `report` command now emits quality JSON
  (`quality_reports` + `quality_summary`) instead of analysis JSON.

### Added
- `analysis.py`: AST-based side-effect detection engine (S1)
- `quality.py`: Assertion mapper and contract coverage computation (S2)
- `report/`: JSON (schema-compatible with Go gaze) and text formatters (S3)
- `analyze`, `quality`, `report` CLI subcommands (S4)
- Domain types: `QualityReport`, `ContractCoverage`, `OverSpecificationScore`, `PackageSummary`, `AssertionMapping` added to `taxonomy.py`

### Deferred
- `--coverprofile` flag validates path but does not yet read `.coverage` SQLite (planned for v0.2)
