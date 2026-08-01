## Why

The baseline comparator keys functions on `package:function` (`compare.py`
`score_key`), with no receiver. Four `to_dict` methods in one module is
ordinary Python, and they all collapse to one key. `baseline_map` is built with
a dict comprehension, so only the **last** entry per key survives, and every
occurrence is then scored against that survivor's baseline.

This was latent until 0.9.0. While coverage was attributed per file, every
function in a file shared one coverage value, so same-named functions of equal
complexity produced equal CRAP and the mismatch cancelled out. Per-function
coverage makes them differ, and the aliasing becomes an active gate failure.

Measured in a consumer project (`fieldkit-cmd`, 1524 functions) on 0.9.0:

- `cli_registry.py` has four `to_dict` methods. `WriteDeclaration.to_dict` is
  0%-covered (CRAP 2.0); `CommandEntry.to_dict` is fully covered (CRAP 1.0) and
  is the entry the map keeps. The uncovered method is scored against the
  covered one and reports **+1.00, a regression no code change caused**.
- `shadowbot/client.py` has two `query` functions, reporting a phantom −3.00.

The default regression epsilon is `0.0`, so any positive delta fails the gate.
The consequence is that **a baseline regenerated from a coverage report fails
against the very data that produced it** — the comparator is not
self-consistent, which makes the gate unusable rather than merely noisy.

This is the same defect class 0.8.2 fixed for test-target pairing (bare
function names matching across files and classes), surfacing in a second
place.

## What Changes

- `score_key` qualifies methods by receiver: `package:receiver.function` for
  methods, `package:function` (unchanged) for module-level functions. Go's key
  needs no qualifier because Go methods already carry the receiver in the
  function name; qualifying here reproduces that uniqueness rather than
  departing from it.
- Baseline entries are **grouped** by key instead of collapsed to one entry
  each, and matched one-to-one in encounter order within a group. Receiver
  alone is not sufficient — two module-level functions of the same name in one
  file (nested helpers named `decorator`) remain ambiguous, and last-wins would
  still misscore them.
- A `legacy_score_key` fallback matches baselines written before this change,
  which key methods bare. Without it, every method in every committed baseline
  would report as simultaneously removed and new on upgrade.
- Removed-function detection keys on identity rather than name, so deleting one
  of two namesakes is reported instead of being hidden by the survivor.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `crap-scoring`: adds a normative requirement that baseline matching
  identifies a function uniquely and never scores one function against
  another's baseline.

### Removed Capabilities

(none)

## Impact

- `src/gaze_py/crap/compare.py` — `score_key`, new `legacy_score_key`, and the
  matching loop in `compare()`
- `tests/test_crap_compare.py` — 7 new tests
- **No baseline regeneration required.** The legacy fallback keeps existing
  baselines matching. Consumers already regenerating for 0.9.0 need do nothing
  extra.
- Verified against `fieldkit-cmd`'s real 1524-function baseline: comparing it
  against the data that produced it now yields `regressions=0 improvements=0
  unchanged=1524 new=0 removed=0`, versus 1 regression + 1 improvement before.
