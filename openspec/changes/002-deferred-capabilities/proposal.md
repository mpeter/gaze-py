# Change 002: Deferred Capabilities

## Why

Change 001 (initial port) implements R1+R2+R3+R4+R5 — the full recommended
port — but explicitly defers several capabilities, output fields, and optional
enhancements. This change records all deferred items as a single reference so
nothing is forgotten and each item can be sequenced, scoped, or closed when
the time comes.

This is a **tracking and scaffolding change only**. It contains no
implementation tasks. Implementation of each item requires its own OpenSpec
change (or a Speckit feature if it involves cross-repo work such as the
unbound-force integration or PyPI publication).

## What Changes

### New Capabilities

- **O1 — Quality Assessment**: Test-target pairing, assertion detection, assertion
  mapping, contract coverage computation. Unlocks GazeCRAP, quadrant
  classification, fix strategy `add_assertions`, and all O1-dependent output fields.
- **O2 — AI-Powered Reports**: Pipe combined analysis output to an LLM for
  narrative interpretation. Requires O1 for meaningful contract coverage data.
- **O3 — Document Scanning**: Scan project README/architecture docs for behavioral
  declarations that contribute to classification Signal 5 (Documentation).
- **O4 — Interactive TUI**: Terminal UI for browsing results interactively.
- **O5 — CI Threshold Enforcement**: `--max-crapload`, `--max-gaze-crapload`,
  `--min-contract-coverage` flags with non-zero exit on threshold violation.
- **O6 — Coverage Profile Reuse**: Accept a pre-generated `coverage.py` JSON
  report via `--coverage-json` (already partially spec'd in 001 as external
  input; full O6 means also accepting `.coverage` binary files and running
  `coverage json` internally if needed).
- **effect_confidence_range field**: `[min, max]` confidence range across all
  effects on a function; deferred OC-002 JSON field.
- **PyPI publication**: Release workflow to publish `gaze-py` to PyPI so
  `uv tool install gaze-py` works without a local wheel.
- **Cyclomatic complexity computation**: Currently unspecified — the initial port
  accepts complexity as an external input or computes it via an unspecified
  algorithm. A future change must specify and implement the algorithm explicitly
  (which AST node types increment the counter, how nested scopes are handled).

### Modified Capabilities

- **R1 — Partial P3/P4 detection**: Five effect types currently have no-op
  detection (WaitGroupOp, AtomicOp, RecoverBehavior, UnsafeMutation, SyncPoolOp).
  A future change may implement detection for any that gain a clear Python
  mapping.
- **O7 — Configuration File**: Basic `.gaze.yaml` loading is implemented in
  001 (thresholds only). Full O7 includes `doc_scan.exclude` glob patterns and
  `doc_scan.timeout` settings (only relevant once O3 is implemented).

### Removed Capabilities

None.

## Impact

All items in this change are currently emitting `null` in JSON output or are
simply absent from the implementation. No breaking changes are introduced by
implementing any of these items — they activate fields that are currently null.
The one exception is PyPI publication, which changes the install path.

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` (v1.0.0).

### I. Accuracy

**Assessment**: PASS

O1 is the capability that makes accuracy claims about contract coverage
meaningful. Implementing it improves accuracy by making the null-vs-zero
distinction in `contract_coverage` actually reflect real measurement.

### II. Minimal Assumptions

**Assessment**: PASS

O1 must not require test code to be annotated or restructured. The
test-target pairing must work heuristically from naming conventions and
call graphs only. O2 (AI reports) must use the adapter pattern — no hardcoded
LLM dependency.

### III. Actionable Output

**Assessment**: PASS

Every item here produces more actionable output than the null it currently
emits. O1's contract coverage reason codes (`no_effects_detected`,
`no_test_coverage`, `no_assertions_mapped`, `all_effects_ambiguous`) and the
quadrant/fix-strategy output are the primary mechanisms by which gaze-py
tells users exactly what to fix.

### IV. Testability

**Assessment**: PASS

O1 in particular must be testable in isolation. Test-target pairing,
assertion detection, and assertion mapping must each be testable with
synthetic fixture files. Contract coverage percentages must be verified
against known fixture inputs.

### V. Porting Contract Supremacy

**Assessment**: PASS

All items here are either explicitly OPTIONAL in requirements.md (O1–O7) or
are fields defined in taxonomy-reference.md as nullable (effect_confidence_range).
No item contradicts any porting contract.
