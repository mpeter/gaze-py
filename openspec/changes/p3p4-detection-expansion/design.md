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
- No `visit_Try` or `visit_AsyncWith` exists

## Goals / Non-Goals

**Goals:**
- Detect `RecoverBehavior` when a `try/except` block suppresses an exception
  and performs recovery (returns fallback, assigns fallback, or suppresses
  silently) rather than re-raising
- Detect `RecoverBehavior` on Python 3.11+ `except*` blocks (`ast.TryStar`)
  using the same heuristic
- Detect `WaitGroupOp` when code synchronizes on a group of concurrent tasks
  via `asyncio.gather`, `asyncio.wait`, `async with asyncio.TaskGroup()`,
  `import concurrent.futures as futures; futures.wait(...)`, or
  `threading.Barrier.wait`
- Detect `UnsafeMutation` when code performs a direct ctypes memory write via
  pointer subscript assignment (`ptr[0] = ...`) or attribute assignment
  (`ptr.contents = ...`) using name heuristics
- Formally close `AtomicOp` and `SyncPoolOp` with documented rationale

**Non-Goals:**
- Thread-safety or runtime analysis — AST-only per AGENTS.md
- Coverage of every possible ctypes pattern (only the canonical write patterns)
- Detection of async lock primitives as `WaitGroupOp` (those are `MutexOp`)
- Detection of `contextlib.suppress()` as `RecoverBehavior` (context manager,
  not try/except — deferred)
- Detection of `async with lock:` as `MutexOp` (pre-existing gap — deferred)
- Detection of `concurrent.futures.wait(fs)` via chained attribute path
  (`concurrent.futures.wait` — only `futures.wait` via alias import is detected)
- Any change to tier assignments (EC-001 is fixed)
- New CLI flags or output fields (taxonomy and JSON schema are unchanged)

## Decisions

### D1: RecoverBehavior via `visit_Try` and `visit_TryStar`

**Decision**: Add `visit_Try` and `visit_TryStar` to `FunctionVisitor`. Both
use the same `_is_recovery_handler` helper. Emit `RecoverBehavior` when any
handler qualifies AND no `RecoverBehavior` has been emitted for this function
yet. The emit-at-most-once guard uses a `break` inside the handler loop (not a
flag): once `self._add(RecoverBehavior)` is called, `break` exits the handler
loop. Since `visit_Try` (and `visit_TryStar`) can be called multiple times per
function (one per try block), the guard is implemented by checking
`self._effects` for an existing `RecoverBehavior` at the top of the shared
helper `_handle_try_node`:

```python
def _handle_try_node(self, node: ast.Try | ast.TryStar) -> None:
    if not any(e.type == SideEffectType.RecoverBehavior for e in self._effects):
        for handler in node.handlers:
            if self._is_recovery_handler(handler):
                self._add(SideEffectType.RecoverBehavior, handler, "...")
                break
    self.generic_visit(node)

def visit_Try(self, node: ast.Try) -> None:      # noqa: N802
    self._handle_try_node(node)

def visit_TryStar(self, node: ast.TryStar) -> None:  # noqa: N802
    self._handle_try_node(node)
```

Both `ast.Try` and `ast.TryStar` expose `.handlers: list[ast.ExceptHandler]`,
so the shared helper handles both without duplication (DRY).

Note: emitting on the `handler` node (not the `try` node) points the location
to the `except:` clause, which is more actionable.

Note: `generic_visit(node)` is called unconditionally — this descends into
handler bodies and will trigger `visit_Raise` on any `raise` statements. This
is intentional: `RecoverBehavior` and `ErrorReturn` are not mutually exclusive.
A handler that calls `log.error(e); raise` will emit both `LogWrite` (via
`visit_Call`) and `ErrorReturn` (via `visit_Raise`) — this is correct behavior.

The "emit-once" approach here differs from `DeferredReturnMutation` (which uses
a post-pass with an early `return`). This is a new pattern but is simpler for
an online-visit approach — it does not require a separate pass over the AST.

**`_is_recovery_handler` heuristic** (checked in order):

1. Body is empty — return `False` (defensive; Python disallows empty handler bodies)
2. Body is a single bare `raise` (no arguments) — return `False` (re-raise)
3. Any statement in body is a `raise` with a non-None `exc` AND is a
   top-level statement (not inside a nested `if`/`for`/`with`) — return
   `False` (unconditional transform-and-re-raise)
4. Body contains `ast.Return`, `ast.Assign`, `ast.AugAssign`, or `ast.Pass`
   at any level — return `True` (recovery action)
5. Otherwise — return `False`

**Key constraint for rule 3**: Only top-level statements in the handler body
are checked for `raise SomeExc(...)` — NOT statements nested inside `if`
branches. This prevents the false-negative where `if debug: raise RuntimeError()`
is a guarded diagnostic re-raise inside a handler that otherwise recovers.

Implementation of rule 3 in `_is_recovery_handler`:
```python
# Rule 3: unconditional transform-and-raise
for stmt in handler.body:
    if isinstance(stmt, ast.Raise) and stmt.exc is not None:
        return False
```
This checks only top-level statements in `handler.body` (not nested) — the
`for stmt in handler.body` loop does not recurse into nested blocks, so a
`raise` inside an `if` is not seen here.

**Description strings** — two distinct messages for actionable output:
- Bare `pass` in handler: `"Function silently suppresses an exception (bare except: pass)"`
- Return/assignment: `"Function catches an exception and returns a fallback or assigns a default value"`

**`except*` (Python 3.11+, `ast.TryStar`)**: Same logic as `visit_Try`.
`ast.TryStar.handlers` are `ast.ExceptHandler` nodes — identical structure.

**Alternative considered**: Instance flag `_has_recover_behavior`. Rejected —
checking `self._effects` is more robust (no state to reset between functions)
and is the pattern used by `visit_Name` for `GlobalMutation` in the same class.

**Alternative considered**: Detect all `try/except` as `RecoverBehavior`.
Rejected — too many false positives; `except SomeError: raise` is a filter.

### D2: WaitGroupOp via extended `_handle_goroutine_process_time`

**Decision**: Add `WaitGroupOp` detection to `_handle_goroutine_process_time`
alongside the existing `GoroutineSpawn` and `ProcessExit` detection. Add a
new `_WAIT_GROUP_CALLS` frozenset constant.

```python
# Qualified names for WaitGroupOp detection (asyncio module only).
# concurrent.futures.wait is detected via name heuristic (obj_name == "futures")
# when imported as: import concurrent.futures as futures
# threading.Barrier.wait is detected via name heuristic (obj_name in {"barrier", ...})
_WAIT_GROUP_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("asyncio", "gather"),
        ("asyncio", "wait"),
    }
)
```

For `threading.Barrier.wait`: detect `method == "wait"` on `obj_name` in
`{"barrier", "barriers"}` (name heuristic). Consistent with how
`MutexOp` detects lock-like names.

For `concurrent.futures.wait`: detect `method == "wait"` on `obj_name == "futures"`.
This requires the calling code to use `import concurrent.futures as futures`
(not `import concurrent.futures`). The fixture must use the alias form. The
canonical `concurrent.futures.wait(fs)` call (chained attribute, no alias)
produces a nested `ast.Attribute` that `obj_name` extraction cannot handle —
this is a documented false negative.

For `asyncio.TaskGroup`: detected via `visit_AsyncWith` (D5).

**Note on PLR0911**: `_handle_goroutine_process_time` will gain 3 new `return True`
branches (asyncio gather/wait, Barrier.wait, futures.wait), bringing total
return points to 8 (5 existing + 3 new). Add `# noqa: PLR0911` to the function
signature, consistent with `_handle_lib_attr_call` and `_handle_param_attr_call`.

**Note on `asyncio.gather` without `await`**: The detection fires on the
`ast.Call` node regardless of whether it is wrapped in `ast.Await`. A bare
`asyncio.gather(task1, task2)` (without `await`) also emits `WaitGroupOp`.
This is intentional — the synchronization intent is present even if the
coroutine is not awaited in this context.

**Alternative considered**: Detect `asyncio.gather` only. Rejected — the
equivalence set is well-defined and all patterns share the same semantics.

### D3: UnsafeMutation via two independent checks in `visit_Assign`

**Decision**: Extend `visit_Assign` with two **independent** `if` blocks
(not `if/else`) — one for subscript patterns, one for `.contents` patterns.
They must be independent because a single assignment statement can have
both target types (`ptr[0] = ptr.contents = value`), and because the
`.contents` check should not be gated on whether a subscript exists.

```python
# UnsafeMutation: ctypes pointer subscript assignment (ptr[0] = ...)
for target in targets:
    if (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and any(p in target.value.id for p in _CTYPES_PTR_NAMES)
    ):
        self._add(
            SideEffectType.UnsafeMutation,
            node,
            f"Function writes to raw memory via {target.value.id}[...] = ...",
        )
        break

# UnsafeMutation: ctypes .contents attribute assignment (ptr.contents = ...)
for target in targets:
    if (
        isinstance(target, ast.Attribute)
        and target.attr == "contents"
        and isinstance(target.value, ast.Name)
    ):
        self._add(
            SideEffectType.UnsafeMutation,
            node,
            f"Function writes to raw memory via {target.value.id}.contents",
        )
        break
```

These checks come AFTER the existing `if/elif/else` chain for
ReceiverMutation/PointerArgMutation/GlobalMutation in `visit_Assign`. They
are independent `if` blocks (not `elif`) and do not disrupt the existing chain.

Note: there is no "emit at most once per function" guard for `UnsafeMutation`
beyond the `break` inside each loop. Two separate `ast.Assign` nodes (two
separate statements) can each emit `UnsafeMutation`. This is intentional —
each is an independent unsafe write.

**`_CTYPES_PTR_NAMES`** includes `"p_"` as a ctypes naming convention prefix
(e.g., `p_value = ctypes.POINTER(ctypes.c_int)()`). Substring match
(`any(p in name ...)`): `"ptr"`, `"buf"`, `"mem"`, `"raw"` match as substrings.
`"p_"` matches as a prefix (e.g., `p_data`, `p_buf`). The substring check is
broader than an exact-match check — `membuffer`, `rawdata` would also match.
This is acceptable for P4 ("may detect"). The false-positive risk is
documented; false negatives are more costly for a detection tool.

**Alternative considered**: Detect `ctypes.memmove`/`ctypes.memset` calls.
Rejected — already emitted as `CgoCall`.

### D4: Formal close of AtomicOp and SyncPoolOp

**Decision**: Add inline comments to `SideEffectType` enum members in
`taxonomy/effects.py` documenting the closure. No detection logic change.

**Why a comment rather than a sentinel/flag**: Adding a `CLOSED_TYPES` set
would require callers to handle it. The taxonomy MUST remain unchanged per EC-001.

### D5: visit_AsyncWith for TaskGroup

**Decision**: Add `visit_AsyncWith` alongside `visit_With` in `FunctionVisitor`
to handle `async with asyncio.TaskGroup() as tg:`. Calls `generic_visit(node)`
unconditionally. Uses `break` after first match (only one TaskGroup pattern —
unlike `visit_With` which has two patterns with no `break`; the inconsistency
is intentional and documented in the `visit_AsyncWith` docstring).

**Known gap**: `async with lock:` patterns are NOT detected as `MutexOp` by
this change (only synchronous `with` is handled by `visit_With`). This is a
pre-existing gap, not introduced by this change. Deferred.

**Alias limitation**: Detection requires `asyncio` to be the exact module name
(`ctx.func.value.id == "asyncio"`). `import asyncio as aio; async with
aio.TaskGroup()` is not detected. This is consistent with all other detectors
in the codebase.

## Risks / Trade-offs

**[Risk] RecoverBehavior false negatives on guarded re-raises** →
Mitigation: rule 3 in D1 only excludes top-level `raise SomeExc(...)` in the
handler body (not nested inside `if`/`for`/`with`). A guarded
`if debug: raise RuntimeError()` inside a handler that otherwise recovers is
correctly classified as RecoverBehavior.

**[Risk] concurrent.futures.wait false negatives (canonical form)** →
`concurrent.futures.wait(fs)` (chained attribute) is not detected. Only
`futures.wait(fs)` via alias import is detected. Documented as a known gap in
Goals/Non-Goals.

**[Risk] WaitGroupOp name heuristic for Barrier** →
`obj_name in {"barrier", "barriers"}` is narrow. Acceptable for P3 "may detect".

**[Risk] UnsafeMutation name heuristic false positives** →
Substring match means `membuffer`, `rawdata` match. Acceptable for P4.
Documented in `_CTYPES_PTR_NAMES` comment.

**[Risk] CC increase in detector.py** →
`visit_Try`, `visit_TryStar`, `visit_AsyncWith` are new top-level visitor
methods with low CC. `_handle_goroutine_process_time` gains 3 branches;
add `# noqa: PLR0911`.

**[Risk] `except*` (Python 3.11+ `ast.TryStar`)** →
Handled via `visit_TryStar` with same logic as `visit_Try`.

## Module Structure

```
src/gaze_py/analysis/detector.py       # main: new constants, visit_Try,
                                        # visit_TryStar, visit_AsyncWith,
                                        # extended _handle_goroutine_process_time
src/gaze_py/taxonomy/effects.py        # closure comments only (no logic change)
tests/test_detector.py                 # new test cases appended; split
                                        # test_noop_types_not_detected
tests/testdata/analysis/               # new fixture files:
  recover_behavior.py                  # positive and negative RecoverBehavior
  wait_group_op.py                     # WaitGroupOp patterns (needs ruff: noqa)
  unsafe_mutation.py                   # UnsafeMutation patterns (needs ruff: noqa)
```

## AST Pattern Reference

### RecoverBehavior (visit_Try / visit_TryStar)

```python
# POSITIVE — assignment in handler
try:
    result = risky_op()
except ValueError:
    result = 0  # ← assignment → RecoverBehavior

# POSITIVE — return in handler
try:
    return parse(x)
except Exception:
    return None  # ← return → RecoverBehavior

# POSITIVE — bare pass (suppression)
try:
    do_thing()
except Exception:
    pass  # ← RecoverBehavior (suppression)

# NEGATIVE — re-raise (pass-through)
try:
    do_thing()
except Exception:
    raise  # ← NOT RecoverBehavior

# NEGATIVE — unconditional transform-and-re-raise (top-level raise in handler)
try:
    do_thing()
except ValueError as e:
    raise RuntimeError("wrapped") from e  # ← top-level raise → NOT RecoverBehavior

# POSITIVE — guarded diagnostic raise (nested inside if → not top-level)
try:
    do_thing()
except ValueError:
    if debug:
        raise RuntimeError("diagnostic")  # ← nested raise → ignored by rule 3
    result = default  # ← recovery action → RecoverBehavior
```

### WaitGroupOp

```python
# POSITIVE — asyncio.gather (with or without await)
results = await asyncio.gather(task1, task2)

# POSITIVE — asyncio.wait
done, pending = await asyncio.wait(tasks)

# POSITIVE — concurrent.futures.wait (via alias import only)
import concurrent.futures as futures
futures.wait(fs)  # ← obj_name == "futures" → detected
# NOT detected: concurrent.futures.wait(fs) (chained attribute, no alias)

# POSITIVE — threading.Barrier.wait (name heuristic)
barrier.wait()

# POSITIVE — async with asyncio.TaskGroup()
async with asyncio.TaskGroup() as tg:
    tg.create_task(coro())

# NOT detected: sync with asyncio.TaskGroup() (visit_With, not visit_AsyncWith)
```

### UnsafeMutation

```python
# POSITIVE — subscript assignment on ptr/buf/mem/raw/p_ name
ptr[0] = 0xFF
buf[0] = 0x00
p_data[0] = 42

# POSITIVE — .contents assignment (any Name)
mem.contents = ctypes.c_int(42)

# NEGATIVE — list subscript on non-ctypes name
items[0] = value  # ← NOT UnsafeMutation

# NOTE: two separate statements each emit UnsafeMutation independently
```
