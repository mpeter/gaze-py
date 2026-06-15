## Why

gaze-py's O1 quality pipeline computes contract coverage and GazeCRAP
correctly for paired functions, but its test-target pairing reaches only
20 of 62 public production functions (32%). The other 42 produce
`gaze_crap: null` with `contract_coverage_reason: "no_effects_detected"`
— which is factually wrong for any function that has detected side
effects but simply has no paired test.

The Go gaze reference implementation (`internal/crap/contract.go`)
distinguishes two different null cases explicitly:

- `"no_effects_detected"` — function truly has no side effects; null is
  correct per OC-003.
- `"no_test_coverage"` — effects were detected but no test targets this
  function; null is also correct (the comment at line 148 is explicit:
  *"no test = no coverage data, not 0% coverage"*), but the reason code
  must be `"no_test_coverage"` — not `"no_effects_detected"`.

This misidentification matters: it makes functions with genuine side
effect risk appear as pure functions in output, suppressing the signal
that they have untested contractual behaviour.

The pairing gap has two root causes:

1. `_extract_call_name()` only handles `ast.Name` calls, missing all
   method calls (`obj.method()`). Tests that call
   `FileDetector.detect()`, `engine.classify()`, etc. never produce a
   pairing.

2. Pairing is shallow — it sees only direct calls in the test body, not
   transitive calls into production code. Signal functions
   (`caller_signal`, `docstring_signal`, etc.) are called as plain names
   inside `ClassificationEngine.classify()`, but tests call
   `engine.classify()` via a helper `_engine() -> ClassificationEngine`
   and never reference signal functions directly.

The fix has two independent parts:

**Part A — Correct reason codes**: Emit `"no_test_coverage"` (not
`"no_effects_detected"`) for functions with effects but no paired test.
GazeCRAP remains null per the Go reference — this is pure diagnostic
accuracy.

**Part B — Astroid Strategy 3**: Add a new call-graph pairing strategy
using Astroid (pylint's analysis backbone) to resolve method calls and
transitive callee chains. This improves pairing from 20/62 to
approximately 31/62, reducing the set of functions with
`"no_test_coverage"` that could have been `"no_effects_detected"`.

## What Changes

### New Capabilities

- `quality-pairing-transitive`: Strategy 3 in `pair_to_targets()` —
  uses Astroid to build a transitive call graph and match reachable
  production function names. Fires only when Strategies 1 and 2 fail.

### Modified Capabilities

- `quality-pairing`: extended with Strategy 3; Strategies 1 and 2
  unchanged; Astroid added as a required dependency; new
  `inference_method="call_graph_transitive"`, `confidence=0.75`.

- `quality-coverage`: new reason code `"no_test_coverage"` correctly
  emitted for functions with effects but no paired test.
  `percentage=None` and `gaze_crap=null` per Go reference (OC-003).

- `crap command`: integrates the quality pipeline to populate
  `contract_coverage_reason` in `gazepy crap` output when a tests path
  is available (auto-discovered or via new `--tests` option). GazeCRAP
  remains null for `"no_test_coverage"` functions per the Go contract.

### Removed Capabilities

None.

## Impact

- `pyproject.toml` — add `astroid>=3.0` to `[project] dependencies`
  (tested against 4.1.2; no upper bound — see D8 in design.md)
- `src/gaze_py/quality/pairing.py` — add `_build_astroid_graph()`,
  `_pair_astroid()`; update `pair_to_targets()` with Strategy 3 kwarg
- `src/gaze_py/quality/pipeline.py` — build Astroid graph once in
  `assess()`; pass to `pair_to_targets()`; populate
  `"no_test_coverage"` reports via new `_untested_reports()` helper
  (separate list, not mixed into main report list)
- `src/gaze_py/quality/coverage.py` — add `no_test_coverage: bool`
  parameter; emit `percentage=None, reason="no_test_coverage"` when set
- `src/gaze_py/taxonomy/models.py` — add `"no_test_coverage"` to
  `ContractCoverageResult.reason` docstring; update `QualityReport`
  docstring to document `test_function=""` sentinel
- `src/gaze_py/cli/main.py` — add `_build_contract_coverage_map()` to
  `quality/` (not CLI); extend `_run_crap()` to call it; add `--tests`
  option to `crap` command; add `_score_target()` guard for
  `"no_test_coverage"` (keep gaze_crap=null)
- `tests/test_quality_pairing.py` — new Strategy 3 tests using
  testdata fixtures
- `tests/test_quality_coverage.py` — new `no_test_coverage` tests
- `tests/test_cli.py` — new crap+quality integration tests
- `openspec/changes/quality-pairing-astroid/results.md` — baseline
  measurements after implementation (created in task 6.1)

## Constitution Alignment

Assessed against `.specify/memory/constitution.md`.

### I. Autonomous Collaboration

**Assessment**: PASS

All changes expressed through existing JSON schema fields and updated
reason code values. The `"no_test_coverage"` reason code is
self-describing. No new communication surfaces.

### II. Minimal Assumptions

**Assessment**: PASS

The `"no_test_coverage"` fix makes no assumptions about what coverage
the untested function has — it explicitly signals "unknown, because
untested." Astroid inference degrades gracefully to unmatched when
inference fails, preserving existing behaviour.

### III. Observable Quality

**Assessment**: PASS

`contract_coverage_reason` becomes accurate for previously-misidentified
functions. The change is immediately verifiable: `gazepy quality` output
shows `"no_test_coverage"` instead of `"no_effects_detected"` for
functions with detected side effects but no paired test.

### IV. Testability

**Assessment**: PASS

All new logic covered by unit tests using dedicated `testdata/quality/`
fixtures. Astroid strategy tested via controlled fixture graphs, not
live project source. All degradation paths (ImportError, InferenceError,
AstroidBuildingError) tested in isolation.

### V. Porting Contract Supremacy

**Assessment**: PASS

The revised design explicitly defers to the Go gaze reference. The
`"no_test_coverage"` reason code matches `contract.go` line 148.
GazeCRAP remains null for `"no_test_coverage"` functions, matching the
`ok=false` return from `BuildContractCoverageFunc`. No divergence from
the porting contracts.

### VI. Composability First

**Assessment**: PASS with note

Astroid becomes a required dependency (tested at 4.1.2, zero transitive
deps on Python 3.11+, LGPL-2.1). LGPL-2.1 permits library use in an
Apache 2.0 project without relicensing. Imported defensively inside
`_build_astroid_graph()`. `_build_contract_coverage_map()` moved to
`quality/pipeline.py` so it is usable without importing CLI code.

### VII. Supply Chain Integrity

**Assessment**: PASS

Astroid (pylint-dev/astroid) is the pylint project's AST backbone —
active, well-maintained, widely deployed. No `<N` upper bound in the
pin (allows compatible upgrades); tested against 4.1.2. LGPL-2.1
license reviewed and compatible with Apache 2.0.
