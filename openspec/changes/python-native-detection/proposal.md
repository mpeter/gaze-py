## Why

gaze-py's detector handles Go-centric concurrency and I/O patterns well, but
six Python-native idioms — `subprocess.*`, `async with <param>:`, `atexit.register`,
`warnings.warn`, `@lru_cache`/`@cache`, and the `return None` annotation decision —
are either undetected or undocumented. These patterns appear in real Python codebases
and produce false negatives or silent inconsistencies. All six are now specified in
`openspec/changes/python-native-detection/specs/`; this change implements them.

Additionally, the synchronous `with <param>:` heuristic for `DatabaseTransaction` uses
exact name matching while the async spec requires substring matching — the two code
paths need to be aligned to a single shared `_is_db_context()` helper.

## What Changes

- **New detection**: `subprocess.{Popen,run,call,check_output,check_call}` → `GoroutineSpawn` (P2)
- **New detection**: `async with <param>:` → `MutexOp` (P3) or `DatabaseTransaction` (P2), param-only, mirroring the existing sync `with` detection
- **New detection**: `atexit.register(...)` → `GlobalMutation` (P1); `atexit.unregister` explicitly excluded
- **New detection**: `warnings.warn(...)` → dual effect: `LogWrite` (P2) + `GlobalMutation` (P1)
- **New detection**: `@lru_cache`, `@cache`, `@functools.lru_cache`, `@functools.cache` (all call/no-call forms) → `GlobalMutation` (P1) at definition site
- **Heuristic alignment**: sync `visit_With` and new `visit_AsyncWith` share a `_is_db_context(name)` helper using word-part split + substring, replacing the inline exact-match set in `visit_With`
- **Documentation**: `return None` without annotation is treated as void (EC-005/G.1 decision) — already implemented; the `return-none-annotation` change is archived as part of this work

## Capabilities

### New Capabilities

- `python-subprocess-spawn`: `subprocess.*` call detection → `GoroutineSpawn`
- `python-async-mutex`: `async with <param>:` detection → `MutexOp` / `DatabaseTransaction`
- `python-atexit`: `atexit.register` detection → `GlobalMutation`
- `python-warnings`: `warnings.warn` detection → dual `LogWrite` + `GlobalMutation`
- `python-lru-cache`: `@lru_cache`/`@cache` decorator detection → `GlobalMutation`

### Modified Capabilities

- `effect-detection`: The `_is_db_context` heuristic refactor changes how `DatabaseTransaction` is classified from `with <param>:` — substring/word-part matching replaces exact-set matching. Existing fixture names all pass identically; the only behavioural change is that compound names like `db_conn` now correctly classify as `DatabaseTransaction`. EC-005 requirement extended with five new pattern rows.

## Impact

- `src/gaze_py/analysis/detector.py` — ~50 lines added/modified across constants, `_handle_lib_attr_call`, `visit_With`, `visit_AsyncWith`, `FileDetector.detect()`
- `tests/testdata/analysis/` — 5 new fixture files
- `tests/test_detector.py` — ~26 new tests
- `openspec/specs/effect-detection/spec.md` — EC-005 table extended; G.1 decision added
- `openspec/changes/return-none-annotation/` — archived (decision already implemented)
- No API or CLI changes; no new dependencies
