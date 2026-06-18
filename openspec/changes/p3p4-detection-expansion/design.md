# Design: p3p4-detection-expansion

## Context

Five P3/P4 `SideEffectType` values have lived in the taxonomy since the
initial port but produce no output: `WaitGroupOp`, `AtomicOp`,
`RecoverBehavior`, `UnsafeMutation`, `SyncPoolOp`. This creates two problems:
(1) silent false negatives for types that do have Python equivalents, and (2)
no documentation of why the others are empty. This design specifies the
detection approach for the three implementable types and the rationale for
formally closing the other two.

Current state of `FunctionVisitor` (1 478 lines, `detector.py`):
- Detection dispatches through `visit_Call` → `_handle_lib_attr_call` /
  `_handle_goroutine_process_time` / `_handle_name_call` / `_handle_param_attr_call`
- `visit_With` handles `MutexOp` and `DatabaseTransaction`
- `collect_deferred_return_mutation` handles `DeferredReturnMutation` via a
  post-pass on the full function body
- No `visit_Try` exists

## Goals / Non-Goals

**Goals:**
- Detect `RecoverBehavior` when a `try/except` block suppresses an exception
  and performs recovery (returns fallback, assigns fallback, calls a recovery
  function) rather than re-raising
- Detect `WaitGroupOp` when code synchronizes on a group of concurrent tasks
  via `asyncio.gather`, `asyncio.wait`, `asyncio.TaskGroup.__aexit__` (via
  `async with asyncio.TaskGroup()`), `concurrent.futures.wait`, or
  `threading.Barrier.wait`
- Detect `UnsafeMutation` when code performs a direct ctypes memory write via
  pointer subscript assignment (`ptr[0] = ...`) or attribute assignment
  (`ptr.contents = ...`) where the target is a Name containing `ptr`/`buf`/
  `mem`/`raw` or an `ast.Subscript` of a Name
- Formally close `AtomicOp` and `SyncPoolOp` with documented rationale

**Non-Goals:**
- Thread-safety or runtime analysis — AST-only per AGENTS.md
- Coverage of every possible ctypes pattern (only the canonical write patterns)
- Detection of async lock primitives as `WaitGroupOp` (those are `MutexOp`)
- Any change to tier assignments (EC-001 is fixed)
- New CLI flags or output fields (taxonomy and JSON schema are unchanged)

## Decisions

### D1: RecoverBehavior via `visit_Try`

**Decision**: Add `visit_Try` to `FunctionVisitor`. Emit `RecoverBehavior`
when a `try` node has at least one non-bare `except` handler (or bare
`except:`) that does NOT simply re-raise and DOES contain a recovery action
(assignment, return, or call to a non-raise function).

**Recovery pattern heuristic** (in priority order):
1. Handler body contains a `return` statement — function returns a fallback
2. Handler body contains an assignment (`ast.Assign` or `ast.AugAssign`) —
   assigns a fallback value
3. Handler body is a single `ast.Pass` — swallows the exception silently; this
   IS a RecoverBehavior (suppression)
4. Handler body contains only a `raise` with no arguments (re-raise) — NOT
   RecoverBehavior
5. Handler body contains `raise SomeException(...)` — NOT RecoverBehavior
   (transforms and re-raises)

Emit at most one `RecoverBehavior` per function even if multiple
try/except blocks qualify (same pattern as `DeferredReturnMutation`).

**Alternative considered**: Detect only bare `except: pass` blocks. Rejected
— too narrow; Python codebases routinely assign fallback values in handlers.

**Alternative considered**: Detect all `try/except` as `RecoverBehavior`.
Rejected — too many false positives; `except SomeError: raise` is a filter,
not a recovery.

### D2: WaitGroupOp via extended `_handle_goroutine_process_time`

**Decision**: Add `WaitGroupOp` detection to `_handle_goroutine_process_time`
alongside the existing `GoroutineSpawn` and `ProcessExit` detection. Add a
new `_WAIT_GROUP_CALLS` frozenset constant.

```python
_WAIT_GROUP_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("asyncio", "gather"),
        ("asyncio", "wait"),
        ("concurrent.futures", "wait"),  # handled via obj_name=="futures"
        # threading.Barrier.wait — detected via method == "wait" on Barrier-named obj
    }
)
```

For `threading.Barrier.wait`: detect `method == "wait"` on `obj_name` in
`{"barrier", "barriers"}` (name heuristic). This is consistent with how
`MutexOp` detects lock-like names.

For `asyncio.TaskGroup`: detected via `visit_AsyncWith` — `async with
asyncio.TaskGroup() as tg:` creates an `ast.AsyncWith` node. Check if the
context expression is `ast.Call` with `ast.Attribute(value=Name("asyncio"),
attr="TaskGroup")`.

**Alternative considered**: Detect `asyncio.gather` only. Rejected — the
equivalence set is well-defined and all four patterns share the same semantics
(wait for a group of tasks).

### D3: UnsafeMutation via AST subscript/attribute assignment detection

**Decision**: Extend `visit_Assign` (or add a helper called from it) to
detect ctypes pointer write patterns. The specific patterns are:

1. `ptr[0] = value` — `ast.Assign` where the target is `ast.Subscript` of a
   Name that is known to be a ctypes pointer (heuristic: name contains `ptr`,
   `buf`, `mem`, `raw`, or `p_`)
2. `ptr.contents = value` — `ast.Assign` where the target is `ast.Attribute`
   with `attr == "contents"` and the value is a Name

**Why name heuristics**: ctypes variables are untyped from the AST perspective.
`memmove`/`memset` are function calls (already captured by `CgoCall` via
`ctypes.*`). The write side-effect requires inspecting the assignment target.

Emit at most one `UnsafeMutation` per function.

**Alternative considered**: Detect `ctypes.memmove`/`ctypes.memset` calls.
Rejected — those are already emitted as `CgoCall` (the call to native code).
`UnsafeMutation` is specifically about writing to raw memory, which in Python
is the pointer dereference assignment pattern.

**Alternative considered**: Detect all `ptr[...] = ...` patterns regardless of
name. Rejected — too many false positives (list assignments, dict assignments).
Name heuristic is narrow enough to be practically useful.

### D4: Formal close of AtomicOp and SyncPoolOp

**Decision**: Add comments to `TIER_MAP` in `taxonomy/effects.py` adjacent to
the `AtomicOp` and `SyncPoolOp` entries documenting the closure. No code
change to detection logic (there is none to change — they simply have no
`visit_*` handler, which is correct). Add a docstring note to `SideEffectType`
listing the permanently-closed types.

**Why a comment rather than a sentinel/flag**: Adding a `CLOSED_TYPES` set
would require callers to handle it. A comment in the taxonomy is sufficient
documentation and requires no API changes. The taxonomy MUST remain unchanged
per EC-001.

### D5: visit_AsyncWith for TaskGroup

**Decision**: Add `visit_AsyncWith` alongside `visit_With` in `FunctionVisitor`
to handle `async with asyncio.TaskGroup() as tg:`.

## Risks / Trade-offs

**[Risk] RecoverBehavior false positives on re-raise-transforms** →
Mitigation: rule 5 in D1 (handlers with `raise SomeExc(...)` are excluded).
Residual risk: contextlib.suppress() is not detected (it's a context manager,
not try/except). Acceptable — contextlib.suppress is itself a separate pattern
that could be added later.

**[Risk] WaitGroupOp name heuristic for Barrier** → Mitigation: the heuristic
(`obj_name in {"barrier", "barriers"}`) is narrow. A variable named `barrier`
that is not a `threading.Barrier` would be a false positive, but this is
extremely unlikely in practice.

**[Risk] UnsafeMutation name heuristic misses uncommon ctypes names** →
Mitigation: documented as narrow detection. False negatives are acceptable for
P4 per EC-001 ("may detect").

**[Risk] CC increase in detector.py** → Mitigation: `visit_Try` and
`visit_AsyncWith` are new top-level visitor methods (no nesting into existing
high-CC functions). `_handle_goroutine_process_time` gains 2 branches but
starts below CC 10.

## Module Structure

```
src/gaze_py/analysis/detector.py       # main change: new constants, visit_Try,
                                        # visit_AsyncWith, extended dispatch
src/gaze_py/taxonomy/effects.py        # closure comments only (no logic change)
tests/test_detector.py                 # new test cases appended
tests/testdata/analysis/               # new fixture files:
  recover_behavior.py
  wait_group_op.py
  unsafe_mutation.py
  no_recover_reraise.py               # negative: re-raise is not RecoverBehavior
```

## AST Pattern Reference

### RecoverBehavior (visit_Try)

```python
# POSITIVE — assignment in handler
try:
    result = risky_op()
except ValueError:
    result = default  # ← assignment → RecoverBehavior

# POSITIVE — return in handler
try:
    return parse(x)
except Exception:
    return None  # ← return → RecoverBehavior

# POSITIVE — bare pass (suppression)
try:
    do_thing()
except Exception:
    pass  # ← RecoverBehavior

# NEGATIVE — re-raise (pass-through)
try:
    do_thing()
except Exception:
    raise  # ← NOT RecoverBehavior

# NEGATIVE — transform and re-raise
try:
    do_thing()
except ValueError as e:
    raise RuntimeError("wrapped") from e  # ← NOT RecoverBehavior
```

### WaitGroupOp

```python
# POSITIVE — asyncio.gather
results = await asyncio.gather(task1, task2)

# POSITIVE — asyncio.wait
done, pending = await asyncio.wait(tasks)

# POSITIVE — concurrent.futures.wait (obj_name heuristic)
concurrent.futures.wait(fs)

# POSITIVE — threading.Barrier.wait (name heuristic)
barrier.wait()

# POSITIVE — async with asyncio.TaskGroup()
async with asyncio.TaskGroup() as tg:
    tg.create_task(coro())
```

### UnsafeMutation

```python
# POSITIVE — subscript assignment on ptr/buf/mem/raw/p_ name
ptr[0] = 0xFF

# POSITIVE — .contents assignment
buf.contents = new_value

# NEGATIVE — list subscript on non-ctypes name
items[0] = value  # ← NOT UnsafeMutation
```
