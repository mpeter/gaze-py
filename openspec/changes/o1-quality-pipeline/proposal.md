## Why

gaze-py currently computes CRAP using line coverage, but all GazeCRAP,
quadrant, contract coverage, and `add_assertions` fix strategy fields
remain null. The O1 quality assessment pipeline is the missing piece:
it pairs test functions to their targets, detects assertion sites, maps
assertions to detected side effects, and computes contract coverage —
unlocking GazeCRAP, quadrant classification, and the full Gaze value
proposition.

## What Changes

- **NEW `src/gaze_py/quality/`** — new package with five modules:
  `models.py`, `pairing.py`, `assertions.py`, `mapper.py`, `coverage.py`
- **`gazepy quality` command** — stops being a stub; runs the full
  O1 pipeline against a source path and a test path
- **`taxonomy/models.py`** — add `QualityReport` dataclass; add
  `AssertionSite`, `ContractCoverageResult`, `TestTargetPair` to support
  the quality pipeline output
- **All currently-null output fields populated**: `Score.gaze_crap`,
  `Score.contract_coverage`, `Score.quadrant`, `Summary.gaze_crapload`,
  `Summary.avg_contract_coverage`, `Summary.quadrant_counts`,
  `Summary.fix_strategy_counts`
- **Test fixtures** in `tests/testdata/quality/` — source + test pairs
  covering the full assertion/coverage spectrum

## Capabilities

### New Capabilities

- `quality-pairing`: discovers test functions and pairs them to
  production function targets using name convention and AST call analysis
- `quality-assertions`: detects assertion sites in test functions —
  stdlib assert, pytest.raises, unittest.TestCase methods — with helper
  function recursion up to depth 3
- `quality-mapper`: maps each assertion to the side effect it verifies
  using three passes: binding match (return value), exception match
  (raises), and name/semantic match (mutations)
- `quality-coverage`: computes contract coverage ratio (contractual
  effects with at least one mapped assertion / total contractual effects)
  and over-specification score
- `quality-output`: wires all quality data into GazeCRAP scoring,
  quadrant classification, fix strategy selection, and output formatting

### Modified Capabilities

- `analyze`: unchanged (detect + classify only, no quality data)
- `crap`: unchanged (line-coverage CRAP only)
- `quality`: promoted from stub to real implementation

## Impact

- `src/gaze_py/quality/` — new package (5 modules)
- `src/gaze_py/taxonomy/models.py` — new dataclasses
- `src/gaze_py/crap/scorer.py` — `gaze_crap()`, `quadrant()` functions
  now callable with contract coverage data
- `src/gaze_py/cli/main.py` — `quality` command implementation
- `src/gaze_py/report/json_formatter.py` — schema update for quality fields
- `tests/test_quality_*.py` — new test files
- `tests/testdata/quality/` — new fixture directory
- No breaking changes to existing `analyze` or `crap` output
