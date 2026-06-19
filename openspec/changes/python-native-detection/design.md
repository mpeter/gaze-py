## Context

`src/gaze_py/analysis/detector.py` is a 1678-line AST visitor implementing a
two-phase detection pipeline. Phase 1 is a module-level pass for `SentinelError`.
Phase 2 iterates all `ast.FunctionDef` / `ast.AsyncFunctionDef` nodes and runs
`_FunctionVisitor` on each, collecting `SideEffect` objects.

The visitor dispatches through a chain of focused helpers:
- `visit_Call` → `_handle_stream_writes` → `_handle_pathlib_attr_call` → `_handle_lib_attr_call` → `_handle_param_attr_call` → `_handle_name_call`
- `visit_With` — sync context manager detection
- `visit_AsyncWith` — currently only detects `asyncio.TaskGroup()`
- `FileDetector.detect()` — Phase 2 loop; constructs `FunctionTarget` per function

The existing `_GOROUTINE_SPAWN_CALLS` frozenset drives GoroutineSpawn detection
in `_handle_goroutine_process_time`. The sync `visit_With` uses an inline exact-set
`{"connection", "conn", "session", "tx", "transaction"}` for DatabaseTransaction;
the async-mutex spec requires substring/word-part matching and adds `db` to the set.

All linting rules (`ruff check`, `mypy --strict`) must continue to pass.
Helper methods exceeding ruff's CC limit carry `# noqa: PLR0911`.

## Goals / Non-Goals

**Goals:**
- Detect all six Python-native patterns specified in `openspec/changes/python-native-detection/specs/`
- Align sync `visit_With` and new `visit_AsyncWith` param detection to a shared `_is_db_context()` helper
- Add one fixture file and targeted tests per new capability; keep test count proportional to spec scenarios
- Archive `return-none-annotation` change (decision already implemented)
- Pass `ruff check`, `ruff format --check`, `mypy --strict`, `pytest --cov-fail-under=85`

**Non-Goals:**
- Alias-aware detection (e.g., `import subprocess as sp; sp.run()`) — name-based heuristics only
- Detecting `@lru_cache` at call sites of the decorated function (definition site only, per spec)
- Changes to CLI, JSON schema, or report output
- Modifying existing tests for patterns already covered

## Decisions

### D1: subprocess detection via `_GOROUTINE_SPAWN_CALLS` extension

Extend the existing `_GOROUTINE_SPAWN_CALLS` frozenset with five `("subprocess", method)` tuples.
`_handle_goroutine_process_time` already performs set-membership routing for this frozenset —
no new conditional logic is needed.

**Alternative**: Add a dedicated `_handle_subprocess_call` helper. Rejected — unnecessary
indirection; the frozenset extension is the established pattern for new GoroutineSpawn sources
(see `("threading", "Thread")`, `("asyncio", "create_task")`, `("multiprocessing", "Process")`).

### D2: `_is_db_context(name)` shared helper (module-level function)

Extract a `_is_db_context(name: str) -> bool` module-level function that uses:
1. Word-part split on `_`: check if any part is in `{"conn", "connection", "session", "tx", "transaction", "db"}`
2. Substring check on the full name for the longer keywords `{"conn", "connection", "session", "transaction"}` — handles camelCase compound words like `dbConnection`

This replaces the inline exact-match set in `visit_With` and drives the new `visit_AsyncWith` param detection.

**Why word-part split + substring, not pure substring?**
Pure substring on `"tx"` would match `"ctx"` (Click context param, extremely common in Python).
Word-part split on `_` safely handles `db_conn` (`["db", "conn"]` → `"db"` matches) while
excluding `ctx` (`["ctx"]` → no match). The substring check for longer keywords (`conn`, etc.)
covers unsplit camelCase without the false-positive risk.

**Why not word-boundary regex?** Adds a `re` import and runtime cost for something that can be
expressed as a two-step pure-string check. The heuristic is intentionally simple.

**Updating `visit_With`**: Replace the inline `if ctx.id in {"connection", "conn", "session", "tx", "transaction"}:` guard with `if _is_db_context(ctx.id):`. All existing fixture param names (`connection`, `conn`, `lock`) classify identically under the new heuristic — no existing tests break.

### D3: `atexit.register` and `warnings.warn` in `_handle_lib_attr_call`

Add two guarded branches after the existing `weakref.finalize` check:

```python
if obj_name == "atexit" and method == "register":
    self._add(SideEffectType.GlobalMutation, node, "...")
    self.generic_visit(node)
    return True

if obj_name == "warnings" and method == "warn":
    self._add(SideEffectType.LogWrite, node, "...")
    self._add(SideEffectType.GlobalMutation, node, "...")
    self.generic_visit(node)
    return True
```

`warnings.warn` is the only detection site that emits two effects from a single node.
Both `_add()` calls fire before `return True`. Each effect gets a distinct ID because
`_effect_id` incorporates `effect_type` in its hash payload (EC-003).

`_handle_lib_attr_call` already carries `# noqa: PLR0911` — no CC concern.

### D4: `@lru_cache`/`@cache` decorator detection in `FileDetector.detect()`

The spec requires attribution at definition site, not call sites. The per-function loop
in `FileDetector.detect()` has direct access to `fn_node.decorator_list`. Inspect it
after the visitor runs and before constructing `FunctionTarget`:

```python
for dec in fn_node.decorator_list:
    if _is_cache_decorator(dec):
        effects.append(_make_effect(
            rel_path=rel_path,
            fn_name=fn_name,
            effect_type=SideEffectType.GlobalMutation,
            node=fn_node,
            description="Function definition is memoized via @lru_cache/@cache ...",
        ))
        break  # one GlobalMutation per function, regardless of stacked decorators
```

`_is_cache_decorator(node)` is a module-level helper that matches all six decorator forms:
- `ast.Name` with `id in {"lru_cache", "cache"}`
- `ast.Call` whose `func` is an `ast.Name` with `id in {"lru_cache", "cache"}`
- `ast.Attribute` with `attr in {"lru_cache", "cache"}` and `value.id == "functools"`
- `ast.Call` whose `func` is the above `ast.Attribute`

`break` after the first match: stacking `@lru_cache` twice is a misuse, not a reason to emit two effects.

**Why not in `_FunctionVisitor`?** The visitor runs inside the function body. Decorator nodes are
on the `FunctionDef` node itself, not in the body. The Phase 2 loop already has `fn_node` — the
right place to inspect decorators is there, not inside the body visitor.

### D5: `visit_AsyncWith` extended with param-based detection

`visit_AsyncWith` currently has a single loop checking for `asyncio.TaskGroup()`. Add a
second loop that mirrors `visit_With` for param-based context managers:

```python
for item in node.items:
    ctx = item.context_expr
    if isinstance(ctx, ast.Name) and ctx.id in self._params:
        if _is_db_context(ctx.id):
            self._add(SideEffectType.DatabaseTransaction, node, f"...")
        else:
            self._add(SideEffectType.MutexOp, node, f"...")
```

This runs independently of the TaskGroup loop — the guards are mutually exclusive
(`ast.Call` for TaskGroup vs `ast.Name in self._params` for params).

## Risks / Trade-offs

**`_is_db_context` false positives on `db_lock`**: A parameter named `db_lock` would classify
as `DatabaseTransaction` (contains word-part `db`) rather than `MutexOp`. This is a
heuristic limitation — the spec accepts it as "may detect" behaviour for compound names.
Mitigation: document the heuristic and its scope in the function docstring.

**`warnings.warn` dual-effect ID collision**: Both effects share the same AST node.
`_effect_id` includes `effect_type` in its hash, so IDs are distinct by construction
(EC-003). No mitigation needed — verified by the dual-effect test.

**`_handle_lib_attr_call` CC growth**: Adding two branches increases CC. The method
already carries `# noqa: PLR0911`. If CC becomes a concern in future, the two new
branches can be extracted into `_handle_stdlib_mutation_call`. Deferred — current CC
remains within the project's review convention.

**`break` in lru_cache decorator loop**: Prevents double-emission for stacked decorators.
Edge case: if a function has `@lru_cache` from `functools` and `@cache` from another
source, only the first match fires. Acceptable — this scenario is a usage error.

## Migration Plan

No schema or API changes. All changes are internal to the detector.

1. Create branch `opsx/python-native-detection` from `main`
2. Implement all detector changes in a single commit (constants → helpers → visit methods → FileDetector loop)
3. Add fixture files and tests in a second commit
4. Archive `return-none-annotation` as a third commit
5. Run full CI gate (`ruff`, `mypy`, `pytest --cov-fail-under=85`) before PR
6. PR targets `main`; no migration or rollback needed (additive detection only)

## Open Questions

None — all design decisions resolved during planning. The heuristic alignment
(Option B) was confirmed by the user before proposal creation.
