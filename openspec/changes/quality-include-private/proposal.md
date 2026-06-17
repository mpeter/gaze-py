## Why

`gazepy quality` and `assess()` silently exclude underscore-prefixed functions
by default, while `gazepy crap` includes them. This inconsistency means the
quality pipeline produces gap hints, contract coverage, and GazeCRAP scores
only for the public API surface — missing the private helpers that are often
the most complex and least directly tested parts of a Python codebase.

The `_` prefix in Python is a convention, not an access boundary. The
`include_unexported=False` default was inherited from Go gaze's semantics,
where unexported (lowercase) functions genuinely cannot be called from outside
the package. In Python there is no equivalent enforcement. The bug was
discovered by running `gazepy quality` against gaze-py itself: 169 functions
detected, only 25 paired (15%), zero gap hints — because 144 private helpers
were silently excluded from the pairing target set.

The inconsistency within gaze-py is clear: `cli/main.py` line 1758 hardcodes
`include_unexported=True` for the `crap` command ("crap analyzes all functions
by default"), while `assess()` in `pipeline.py` calls `detect_and_classify()`
with no `include_unexported` argument, silently defaulting to `False`.

## What Changes

- `assess()` in `src/gaze_py/quality/pipeline.py` — add
  `include_unexported: bool = True`; pass it through to
  `detect_and_classify()`
- `gazepy quality` command in `src/gaze_py/cli/main.py` — change
  `--include-unexported` default from `False` to `True`; update help text;
  pass `include_unexported` through to `assess()`
- `src/gaze_py/analysis/runner.py` — `detect_and_classify()` default stays
  `False` (it is a library function used in multiple contexts); callers that
  want private functions must opt in explicitly — `assess()` becomes that
  explicit caller
- `CHANGELOG.md` — document as a behaviour change
- Tests — update any assertions that assumed private functions were excluded

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `quality-assessment`: `assess()` and `gazepy quality` now include private
  (underscore-prefixed) functions by default. The `--include-unexported` flag
  becomes an opt-out (`--no-include-unexported`) rather than an opt-in.

## Impact

- `src/gaze_py/quality/pipeline.py` — `assess()` signature and body
- `src/gaze_py/cli/main.py` — `quality` command flag default + wiring to
  `assess()`
- `tests/test_quality_*.py` — fixture expectations may increase function count
- `tests/test_cli.py` — `quality` command integration tests
- `CHANGELOG.md` — behaviour change entry

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` (v1.1.3).

### I. Accuracy

**Assessment**: PASS — this change improves accuracy. Private functions with
real side effects and complexity were previously invisible to the quality
pipeline. Including them produces a more complete and accurate picture.

### II. Minimal Assumptions

**Assessment**: PASS — no user annotation required. The change removes an
incorrect assumption (that `_` prefix means "unimportant for quality") that
does not hold for Python.

### III. Actionable Output

**Assessment**: PASS — more functions receiving gap hints and GazeCRAP scores
means more actionable output.

### IV. Testability

**Assessment**: PASS — the change is a default flip. The flag already exists
and is tested; updated tests verify the new default behaviour.

### V. Porting Contract Supremacy

**Assessment**: PASS with documented divergence — Go gaze's
`include_unexported` default reflects Go's package-level access semantics.
Python has no equivalent. This is a deliberate, documented Python-specific
divergence consistent with Principle II. No porting contracts define the
default value for `include_unexported`.

### VI. Composability First

**Assessment**: PASS — no new dependencies. The flag already exists; only the
default changes.

### VII. Supply Chain Integrity

**Assessment**: PASS — no dependency changes.
