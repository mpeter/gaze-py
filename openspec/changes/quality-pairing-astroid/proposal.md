## Why

gaze-py's O1 quality pipeline computes contract coverage and GazeCRAP
correctly, but its test-target pairing reaches only 20 of 62 public
production functions (32%). The other 42 produce `gaze_crap: null` with
`contract_coverage_reason: "no_effects_detected"` — which is factually
wrong for functions that have detected side effects but simply have no
paired test.

This misidentifies the problem. Per the Go gaze reference implementation
(`internal/crap/contract.go`), when the quality pipeline has run but
finds no test targeting a function, the correct behaviour is:

- `contract_coverage_reason: "no_test_coverage"` (not `"no_effects_detected"`)
- `contract_coverage: 0.0` (not `null`)
- `gaze_crap: complexity² + complexity` — GazeCRAP at 0% contract
  coverage is a real, computable score, not null

OC-003 ("nullable fields") applies when the quality capability has **not
run at all** — not when it ran but failed to pair a function. Unpaired
functions with side effects have a known, correct GazeCRAP: the worst
case (0% contract coverage).

The pairing gap has two root causes:

1. `_extract_call_name()` only handles `ast.Name` calls, missing all
   method calls (`obj.method()`). Tests that call `FileDetector.detect()`,
   `engine.classify()`, etc. never produce a pairing.

2. Pairing is shallow — it sees only direct calls in the test body, not
   transitive calls into production code. Signal functions
   (`caller_signal`, `docstring_signal`, etc.) are called as plain names
   inside `ClassificationEngine.classify()`, but tests call
   `engine.classify()` via a helper `_engine() -> ClassificationEngine`
   and never reference signal functions directly.

The fix is a new **Strategy 3** using **Astroid** (pylint's analysis
backbone) for transitive, type-aware call graph inference. Astroid
resolves method calls through return-type annotations
(`_engine() -> ClassificationEngine`) and then follows transitively into
the callee body to find further production function calls.

## What Changes

### New Capabilities

- `quality-pairing-transitive`: Strategy 3 in `pair_to_targets()` —
  uses Astroid to build a transitive call graph from each test function
  and matches any reachable production function name. Fires only when
  Strategies 1 and 2 both fail.

### Modified Capabilities

- `quality-pairing`: extended with Strategy 3; Strategies 1 (name
  convention) and 2 (ast.Name call walk) unchanged; Astroid added as a
  required dependency; new `inference_method="call_graph_transitive"`,
  `confidence=0.75`.

- `quality-coverage`: new reason code `"no_test_coverage"` for
  production functions with effects that have no paired test;
  `percentage=0.0` (not `null`) in this case so GazeCRAP is computable.

- `quality-rendering`: text output appends `*` to GazeCRAP values
  derived from `"no_test_coverage"` and adds a footnote explaining the
  marker. JSON emits the raw float with `contract_coverage_reason:
  "no_test_coverage"` — no decoration.

- `crap command`: integrates the quality pipeline to populate GazeCRAP
  in `gazepy crap` output when a tests path is available (auto-discovered
  or via new `--tests` option). Mirrors Go gaze's
  `BuildContractCoverageFunc` pattern.

### Removed Capabilities

None.

## Impact

- `pyproject.toml` — add `astroid>=3.0,<4` to `[project] dependencies`
- `src/gaze_py/quality/pairing.py` — add `_build_astroid_graph()`,
  `_pair_astroid()`; update `pair_to_targets()` with Strategy 3 kwarg
- `src/gaze_py/quality/pipeline.py` — build Astroid graph once in
  `assess()`, pass to all `pair_to_targets()` calls; emit
  `QualityReport` for unmatched production functions with effects
- `src/gaze_py/quality/coverage.py` — add `no_test_coverage: bool`
  parameter; emit `percentage=0.0, reason="no_test_coverage"` when set
- `src/gaze_py/taxonomy/models.py` — add `"no_test_coverage"` to
  `ContractCoverageResult.reason` docstring
- `src/gaze_py/report/text_formatter.py` — append `*` to GazeCRAP
  when `contract_coverage_reason == "no_test_coverage"`
- `src/gaze_py/cli/main.py` — add `_build_contract_coverage_map()`;
  extend `_run_crap()` to call quality pipeline; add `--tests` option
  to `crap` command; update `_emit_quality_text()` footnote
- `tests/test_quality_pairing.py` — new tests for Strategy 3
- `tests/test_quality_coverage.py` — new tests for `no_test_coverage`
- `tests/test_output.py` or `tests/test_cli.py` — new rendering tests
- `tests/test_cli.py` — new crap+quality integration tests

## Constitution Alignment

Assessed against `.specify/memory/constitution.md`.

### I. Autonomous Collaboration

**Assessment**: PASS

All changes expressed through updated field values and existing JSON
schema fields. No new communication surfaces. The `"no_test_coverage"`
reason code and `*` text marker are self-describing.

### II. Composability First

**Assessment**: PASS with note

Astroid becomes a required dependency (279 KB wheel, zero transitive
deps on Python 3.11+, LGPL-2.1). LGPL-2.1 permits use as a library
dependency in an Apache 2.0 project without relicensing — gaze-py
imports Astroid but does not distribute a modified copy of it. The
pairing improvement is isolated to `quality/pairing.py`; Astroid is
imported defensively inside `_build_astroid_graph()` and the pipeline
degrades gracefully (Strategy 3 → unmatched) if the import fails.

### III. Observable Quality

**Assessment**: PASS

`gaze_crap` and `contract_coverage_reason` become populated for
previously-null functions. The change is immediately verifiable:
`gazepy crap src/ --tests tests/` produces non-null `gaze_crap` for
functions that were previously `null`. The `*` marker in text output
makes the distinction between "measured" and "untested" visible to
human readers.

### IV. Testability

**Assessment**: PASS

All new logic covered by unit tests using the project's own source as
an integration fixture. Astroid inference tested against real code, not
mocks. Strategy 3 degrades gracefully and the degradation path is
separately tested.
