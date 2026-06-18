# Proposal: p3p4-detection-expansion

## Why

Five P3/P4 effect types — `WaitGroupOp`, `AtomicOp`, `RecoverBehavior`,
`UnsafeMutation`, `SyncPoolOp` — have no detection logic in the AST detector.
They appear in the taxonomy and tier map but are never emitted. Per porting
contract EC-005, types without a direct Python equivalent SHOULD be omitted
from detection but MUST remain in the taxonomy. This change makes that
decision explicit: implement detection where a Python equivalent exists,
formally close (document as permanently undetected) where none exists.

This closes deferred item D.3 from `openspec/changes/002-deferred-capabilities`.

## What Changes

### New Capabilities

- `p3p4-recover-behavior`: Detect `RecoverBehavior` — `try/except` blocks
  where the `except` clause performs recovery (assigns a fallback, returns
  early, or calls a recovery function) rather than re-raising.
- `p3p4-wait-group-op`: Detect `WaitGroupOp` — calls to `asyncio.gather`,
  `asyncio.wait`, `asyncio.TaskGroup`, `concurrent.futures.wait`,
  `threading.Barrier.wait`, that synchronize on a group of concurrent tasks.
- `p3p4-unsafe-mutation`: Detect `UnsafeMutation` — direct memory writes via
  `ctypes` pointer dereference assignment (`ptr[0] = ...`, `ptr.contents = ...`).
  This is distinct from `CgoCall` (calling a ctypes function); this detects
  the write side-effect of mutating memory directly.

### Modified Capabilities

- `effect-detection`: The existing `_handle_lib_attr_call` and
  `_handle_goroutine_process_time` handlers are extended. A new
  `visit_Try` method is added to `FunctionVisitor`.

### Closed (no Python equivalent — formally documented)

- `AtomicOp` (P3): Python has no atomic primitive. `threading.local` is
  thread-local storage, not an atomic read-modify-write. `ctypes` atomics
  are not idiomatic Python and are indistinguishable from general ctypes
  calls. Permanently closed; remains in taxonomy for compatibility.
- `SyncPoolOp` (P4): Go's `sync.Pool` (an object reuse pool with
  runtime-managed eviction) has no Python equivalent. Permanently closed;
  remains in taxonomy for compatibility.

## Capabilities

### New Capabilities

- `p3p4-recover-behavior`: AST detection of exception-swallowing /
  recovery try/except patterns → emits `RecoverBehavior`
- `p3p4-wait-group-op`: AST detection of task-group synchronization calls
  → emits `WaitGroupOp`
- `p3p4-unsafe-mutation`: AST detection of ctypes pointer write patterns
  → emits `UnsafeMutation`

### Modified Capabilities

- `effect-detection`: Minor extension to existing detection dispatch.
  No behavioral changes to existing detected types.

## Impact

- `src/gaze_py/analysis/detector.py` — primary change file: new constants,
  `visit_Try`, extended `_handle_goroutine_process_time` / `_handle_lib_attr_call`
- `tests/test_detector.py` — new test cases for all three implemented types
  and one test each confirming AtomicOp/SyncPoolOp emit nothing on plausible
  Python patterns
- `tests/testdata/analysis/` — new fixture files for RecoverBehavior,
  WaitGroupOp, UnsafeMutation patterns
- No new runtime dependencies; no API surface changes

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` (v1.1.3).

### I. Accuracy

**Assessment**: PASS

P3/P4 are "may detect" per EC-001. Detection is added only where the Python
pattern is unambiguous. The formal close of AtomicOp/SyncPoolOp eliminates
false negatives that are currently silent (no detection = no output, which is
accurate for types that have no Python equivalent).

### II. Minimal Assumptions

**Assessment**: PASS

`RecoverBehavior` heuristic: bare `except:` or `except Exception:` with a
recovery action (assignment or non-raise return). Does not require
annotations. `WaitGroupOp` matches specific qualified call signatures.
`UnsafeMutation` matches ctypes subscript/attribute assignment — narrow and
explicit.

### III. Actionable Output

**Assessment**: PASS

Each new detected effect emits a human-readable description identifying the
specific pattern (e.g., "Function suppresses an exception and returns a
fallback value"). Formally closed types get a comment in the taxonomy
explaining why they produce no output.

### IV. Testability

**Assessment**: PASS

Each new detector is tested with fixture files under
`tests/testdata/analysis/`. Tests confirm positive detection on known
patterns and negative (no-emission) on unrelated code.

### V. Porting Contract Supremacy

**Assessment**: PASS

EC-001 — tier assignments for all 5 types unchanged.
EC-005 — "types without a direct equivalent SHOULD be omitted from detection
but MUST remain in the taxonomy" is honored: AtomicOp/SyncPoolOp remain in
`SideEffectType` and `TIER_MAP` but emit nothing.
EC-002 — P0 zero-tolerance is unaffected (P0 types unchanged).

### VI. Composability First

**Assessment**: PASS

All changes are additive to the detector. No new required runtime
dependencies. Existing callers of `detect_and_classify` are unaffected.

### VII. Supply Chain Integrity

**Assessment**: PASS

No new dependencies added. Detection uses Python's stdlib `ast` module only.
