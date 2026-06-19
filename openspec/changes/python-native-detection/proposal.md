# Proposal: python-native-detection

## Why

The 38-type effect taxonomy was designed for Go. A systematic gap analysis
identified Python-native side-effect patterns that have valid mappings to
existing types per EC-005 but are not yet detected. These are **detection
gaps within existing types** — not novel types requiring taxonomy amendments
or upstream coordination.

Specifically: five Python stdlib patterns that produce side effects in real
codebases are silently undetected:

1. `subprocess.Popen/run/call/check_output` — spawns an OS child process
   (concurrent with parent → GoroutineSpawn, P2)
2. `async with param:` (lock-named parameter) — async mutex acquire
   (→ MutexOp, P3; known gap documented in `visit_AsyncWith` line 1152)
3. `atexit.register()` — mutates the interpreter's shutdown handler list
   (→ GlobalMutation, P1)
4. `warnings.warn()` — two simultaneous effects: emits a structured
   developer message (→ LogWrite, P2) and mutates `__warningregistry__`
   in the calling module (→ GlobalMutation, P1)
5. `@functools.lru_cache` / `@functools.cache` decorated function calls
   — every call read-modify-writes a persistent cache attached to the
   function object; functionally global state (→ GlobalMutation, P1)

Type mappings validated by Gemini 2.5 Pro independent review (2026-06-18)
from EC-005 semantics and Python ecosystem conventions.

## What Changes

### New Capabilities

- `python-subprocess-spawn`: detect `subprocess.Popen`, `subprocess.run`,
  `subprocess.call`, `subprocess.check_output` as `GoroutineSpawn`
- `python-async-mutex`: detect `async with param:` (lock-named parameter)
  as `MutexOp` in `visit_AsyncWith`
- `python-atexit`: detect `atexit.register()` as `GlobalMutation`
- `python-warnings`: detect `warnings.warn()` as `LogWrite` +
  `GlobalMutation` (two effects from one call)
- `python-lru-cache`: detect `@functools.lru_cache` / `@functools.cache`
  decorated function definitions as `GlobalMutation` (decorator annotation
  on the function, not on the call site)

### Modified Capabilities

- `effect-detection`: `_GOROUTINE_SPAWN_CALLS` extended; `visit_AsyncWith`
  extended for MutexOp; `_handle_name_call` extended for atexit and warnings;
  `visit_FunctionDef` / `visit_AsyncFunctionDef` extended for lru_cache
  decorator detection

## Capabilities

### New Capabilities

- `python-subprocess-spawn`
- `python-async-mutex`
- `python-atexit`
- `python-warnings`
- `python-lru-cache`

### Modified Capabilities

- `effect-detection`: detector additions only, no logic changes to
  existing detection paths

## Impact

- `src/gaze_py/analysis/detector.py` — primary change file: one new constant,
  five new detection blocks across existing visitor methods
- `tests/test_detector.py` — new test cases for each new pattern
- `tests/testdata/analysis/` — new fixture files
- No new runtime dependencies
- No taxonomy changes (EC-001 types and tiers unchanged)
- No JSON schema changes
- No CLI changes

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` (v1.1.3).

### I. Accuracy

**Assessment**: PASS

All five mappings are validated against EC-005 from first principles.
Subprocess → GoroutineSpawn is justified by the existing `multiprocessing.Process`
precedent. atexit → GlobalMutation is unambiguous. warnings → LogWrite +
GlobalMutation correctly represents both effects. lru_cache → GlobalMutation
correctly represents the functionally-global cache state. async with → MutexOp
closes the known detection gap documented in the code.

### II. Minimal Assumptions

**Assessment**: PASS

subprocess detection uses exact qualified names (no heuristics). atexit and
warnings use exact function name matching. lru_cache detection uses decorator
name matching on `FunctionDef.decorator_list` — no runtime introspection.
`async with param:` uses the same name-based heuristic as `with param:`.

### III. Actionable Output

**Assessment**: PASS

Each new detected effect emits a specific human-readable description. The
warnings.warn() two-effect model is the most novel: a single call site
produces both a LogWrite and a GlobalMutation. This accurately reflects what
the function does and is more actionable than either effect alone.

### IV. Testability

**Assessment**: PASS

All five patterns are testable with synthetic fixture files. Positive and
negative tests specified in tasks.md.

### V. Porting Contract Supremacy

**Assessment**: PASS

EC-001 — no type or tier changes.
EC-005 — all five mappings are language adaptations of existing types, not
new type definitions.
The Gemini 2.5 Pro independent review (2026-06-18) confirms all five mappings
are consistent with EC-005 intent and Python ecosystem conventions.

### VI. Composability First

**Assessment**: PASS

All additions are detection-only. No new required dependencies. Existing
callers of `detect_and_classify` are unaffected. Each new pattern is
independently detectable.

### VII. Supply Chain Integrity

**Assessment**: PASS

No new dependencies. All detection uses stdlib `ast` module only.
