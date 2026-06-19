# Design: python-native-detection

## Context

Five Python-native side-effect patterns have valid EC-005 mappings to existing
types but are not yet detected. All are in the existing `FunctionVisitor`
dispatch pipeline — additions slot cleanly into existing constants and visitor
methods.

Current state:
- `_GOROUTINE_SPAWN_CALLS` has 3 entries: `threading.Thread`,
  `asyncio.create_task`, `multiprocessing.Process`
- `_handle_name_call` handles: `print`, `setattr`, `open` (write modes),
  and callback invocation
- `visit_AsyncWith` handles: `asyncio.TaskGroup` (WaitGroupOp only);
  known gap comment at line 1152 for `async with lock:`
- `visit_FunctionDef` / `visit_AsyncFunctionDef` detect nesting depth only —
  no decorator inspection

## Goals / Non-Goals

**Goals:**
- Detect `subprocess.Popen/run/call/check_output` as `GoroutineSpawn` (P2)
- Detect `async with param:` lock patterns as `MutexOp` (P3)
- Detect `atexit.register()` as `GlobalMutation` (P1)
- Detect `warnings.warn()` as both `LogWrite` (P2) and `GlobalMutation` (P1)
- Detect `@functools.lru_cache` / `@functools.cache` decorated functions as
  `GlobalMutation` (P1) — annotated at definition site

**Non-Goals:**
- New taxonomy types (EC-001 is fixed)
- Detecting lru_cache *call sites* (the effect is the decoration, not each call)
- Signal, sys.settrace, threading.local — these remain deferred/closed
- socket or network write detection (no existing NetworkWrite type)
- Any change to existing detection paths

## Decisions

### D1: subprocess → GoroutineSpawn via `_GOROUTINE_SPAWN_CALLS` extension

Add `("subprocess", "Popen")`, `("subprocess", "run")`, `("subprocess", "call")`,
`("subprocess", "check_output")`, `("subprocess", "check_call")` to
`_GOROUTINE_SPAWN_CALLS`.

Also add `("concurrent.futures", "ThreadPoolExecutor")` and
`("concurrent.futures", "ProcessPoolExecutor")` — these create worker pools
that execute tasks concurrently, fitting GoroutineSpawn semantics.

**Rationale**: EC-005 maps GoroutineSpawn to "spawning a concurrent task."
Subprocess creates an OS process that executes concurrently. Gemini verdict:
MAPS_TO_GOROUTINE_SPAWN — "implementation detail that it's heavier; it still
fits 'spawning a concurrent task.'" Precedent: `multiprocessing.Process`
already maps to GoroutineSpawn.

**Note on `subprocess.run` / `check_output` blocking**: `subprocess.run()` is
synchronous by default (blocks until child exits). However, it *does* spawn a
concurrent process — the concurrency is just not exploited without
`subprocess.Popen` + non-blocking patterns. The GoroutineSpawn type captures
the spawning intent, not the caller's blocking behavior. This is consistent
with how `multiprocessing.Process(target=f).start()` vs `Process(target=f)`
(without .start()) are not distinguished in the taxonomy.

### D2: async with param → MutexOp via `visit_AsyncWith` extension

Extend `visit_AsyncWith` to also check for param-based `async with` patterns,
mirroring the existing `visit_With` logic. The same name heuristics apply:
`connection/conn/session/tx/transaction` → `DatabaseTransaction`; else →
`MutexOp`.

```python
# In visit_AsyncWith, before the TaskGroup check:
for item in node.items:
    ctx = item.context_expr
    if isinstance(ctx, ast.Name) and ctx.id in self._params:
        if ctx.id in {"connection", "conn", "session", "tx", "transaction"}:
            self._add(SideEffectType.DatabaseTransaction, node, ...)
        else:
            self._add(SideEffectType.MutexOp, node, ...)
```

This closes the known gap documented at line 1152.

**Alternative considered**: Detect `async with asyncio.Lock()` or
`async with asyncio.Semaphore()` by type name. Rejected — gaze-py is AST-only
with no type inference; we cannot know the type of the context manager expression
without executing the code. The parameter-name heuristic is consistent with
`visit_With` and is the correct AST-only approach.

### D3: atexit.register() → GlobalMutation via `_handle_lib_attr_call`

Detect `atexit.register(func)` in `_handle_lib_attr_call` (where `obj_name ==
"atexit"` and `method == "register"`). Emit `GlobalMutation`.

```python
# atexit.register() — mutates interpreter shutdown handler list (GlobalMutation)
if obj_name == "atexit" and method == "register":
    self._add(
        SideEffectType.GlobalMutation,
        node,
        "Function registers a shutdown callback via atexit.register()",
    )
    self.generic_visit(node)
    return True
```

**Rationale**: Gemini verdict: GLOBAL_MUTATION — "modifies a list of handler
functions maintained as global state by the Python interpreter." Not
FinalizerRegistration (wrong trigger: shutdown not GC). Not CallbackInvocation
(registers, does not invoke).

**Placement**: Add after the `FinalizerRegistration` (`weakref.finalize`) block
in `_handle_lib_attr_call`, before the `CgoCall` block.

### D4: warnings.warn() → LogWrite + GlobalMutation (two effects)

Detect `warnings.warn(...)` and emit **two effects** from a single call node:

```python
# warnings.warn() — structured warning emission (LogWrite) +
# __warningregistry__ mutation (GlobalMutation)
if obj_name == "warnings" and method == "warn":
    self._add(
        SideEffectType.LogWrite,
        node,
        "Function emits a warning via warnings.warn() (structured dev-facing output)",
    )
    self._add(
        SideEffectType.GlobalMutation,
        node,
        "Function mutates __warningregistry__ in the calling module via warnings.warn()",
    )
    self.generic_visit(node)
    return True
```

**Rationale**: Gemini verdict: LOG_WRITE + GLOBAL_MUTATION — "two distinct,
simultaneous side effects." LogWrite because warnings are a structured,
filterable developer-facing channel (not raw stderr). GlobalMutation because
`__warningregistry__` is always written as deduplication state in the calling
module's globals.

**Emitting two effects from one call**: This is not novel — the existing
`GlobalMutation` detection from `_check_env_var_mutation` can fire alongside
other effects. The `_add()` method appends; it does not short-circuit. The
`return True` short-circuits the *dispatch chain* (preventing other handlers
from also firing), not the `_add` calls within this block.

**Placement**: In `_handle_lib_attr_call`, after the `LogWrite` (`_LOG_NAMES`)
block.

### D5: @lru_cache / @functools.cache → GlobalMutation via decorator detection

Detect `@lru_cache` or `@cache` (from `functools`) on `FunctionDef` and
`AsyncFunctionDef` nodes. Emit `GlobalMutation` on the *function definition*,
not on call sites.

**Why at definition, not call site**: The decoration creates the persistent
cache state. Every subsequent call to the decorated function inherits this
effect. Annotating the function definition is the correct point — it is where
the "write to global-like state" begins. This is analogous to how gaze-py
detects `GlobalMutation` at assignment sites (`x = value`), not at read sites.

**Detection location**: A new private helper `_detect_lru_cache_decorator`
called from `_collect_function_effects` (the per-function orchestration method)
before the main visitor pass, or directly in a post-processing step. Simpler
option: check `fn_node.decorator_list` in `FileDetector.detect()` before
calling `FunctionVisitor`.

**Actual simplest option**: Add detection inside the existing
`FunctionVisitor.__init__` or at the top of `visit_FunctionDef` by inspecting
the parent function node's decorators. Since `FunctionVisitor` is instantiated
*per function* by `FileDetector`, the function node is available.

Specifically, in `FileDetector.detect()` (or the per-function processing loop),
after creating a `FunctionVisitor` for a function, check the function node's
`decorator_list` for `lru_cache` or `cache` names, and if found, call
`self._add(SideEffectType.GlobalMutation, fn_node, "Function has an lru_cache/cache decorator — memoization state is globally shared")` on the visitor before running it.

**AST pattern for decorator detection**:
```python
_LRU_CACHE_DECORATORS: frozenset[str] = frozenset({"lru_cache", "cache"})

def _has_lru_cache_decorator(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn_node.decorator_list:
        # @lru_cache or @cache (bare name)
        if isinstance(dec, ast.Name) and dec.id in _LRU_CACHE_DECORATORS:
            return True
        # @lru_cache(...) or @cache() (call form)
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Name)
            and dec.func.id in _LRU_CACHE_DECORATORS
        ):
            return True
        # @functools.lru_cache or @functools.cache (attribute form)
        if (
            isinstance(dec, ast.Attribute)
            and isinstance(dec.value, ast.Name)
            and dec.value.id == "functools"
            and dec.attr in _LRU_CACHE_DECORATORS
        ):
            return True
        # @functools.lru_cache(...) (attribute call form)
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id == "functools"
            and dec.func.attr in _LRU_CACHE_DECORATORS
        ):
            return True
    return False
```

**Placement**: Add `_LRU_CACHE_DECORATORS` constant to the constants section.
Add `_has_lru_cache_decorator` as a module-level function (not a method —
it does not need `self`). Call it from `FileDetector.detect()` in the
per-function loop, before or after constructing the `FunctionVisitor`.

## Module Structure

```
src/gaze_py/analysis/detector.py       # main: constants + 5 new detection blocks
tests/test_detector.py                 # new test cases appended
tests/testdata/analysis/               # new fixture files:
  python_native.py                     # all 5 patterns in one fixture
```

## AST Pattern Reference

### GoroutineSpawn — subprocess

```python
import subprocess
subprocess.Popen(["ls"])          # ← GoroutineSpawn
subprocess.run(["ls"])            # ← GoroutineSpawn
subprocess.call(["ls"])           # ← GoroutineSpawn
subprocess.check_output(["ls"])   # ← GoroutineSpawn
subprocess.check_call(["ls"])     # ← GoroutineSpawn
```

### MutexOp — async with param

```python
async def f(lock):
    async with lock:       # ← MutexOp (param name heuristic)
        pass

async def g(conn):
    async with conn:       # ← DatabaseTransaction (connection name heuristic)
        pass

async def h():
    async with asyncio.TaskGroup() as tg:  # ← WaitGroupOp (existing)
        pass
```

### GlobalMutation — atexit

```python
import atexit
atexit.register(cleanup)   # ← GlobalMutation
```

### LogWrite + GlobalMutation — warnings

```python
import warnings
warnings.warn("deprecated")        # ← LogWrite + GlobalMutation
warnings.warn("msg", DeprecationWarning)  # ← LogWrite + GlobalMutation
```

### GlobalMutation — lru_cache decorator

```python
from functools import lru_cache, cache

@lru_cache          # ← GlobalMutation on the function definition
def compute(x): ...

@lru_cache(maxsize=128)   # ← GlobalMutation
def fetch(url): ...

@cache              # ← GlobalMutation
def memoized(n): ...

@functools.lru_cache        # ← GlobalMutation
def qualified(x): ...
```

## Risks / Trade-offs

**[Risk] subprocess.run() is blocking — "spawning" is arguable** →
Mitigation: EC-005 maps GoroutineSpawn to spawning intent, not caller behavior.
The process is concurrent regardless of whether the caller blocks. Documented
in D1. Gemini confirms MAPS_TO_GOROUTINE_SPAWN.

**[Risk] warnings.warn() two-effect model may surprise callers** →
Mitigation: the two effects are independently correct and both actionable.
The LogWrite is the primary effect; the GlobalMutation is secondary. The
taxonomy supports multiple effects per call site — no code change needed
to the effect model.

**[Risk] lru_cache decorator detection at definition site may feel indirect** →
Mitigation: this is the correct granularity — the cache is created at
decoration time, not call time. Documented in D5. The description string
makes the semantics explicit.

**[Risk] `_has_lru_cache_decorator` adds a new module-level function** →
Mitigation: consistent with `_collect_return_names_excluding_finally` and
`_extract_open_mode` which are already module-level helpers in `detector.py`.
