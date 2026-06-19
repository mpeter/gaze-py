# Spec: effect-detection

Authoritative requirements for AST-based side-effect detection in gaze-py.
Sources: porting contracts EC-001 through EC-005, taxonomy-reference.md,
and the current `analysis/detector.py` implementation.

---

### Requirement: EC-001 Tier Membership

The implementation SHALL define exactly **38** `SideEffectType` enum values
assigned to exactly 5 tiers (P0–P4) with fixed counts: P0=5, P1=8, P2=10,
P3=9, P4=6. Tier assignments MUST NOT be configurable at runtime.

> **Documentation bug in porting contracts**: Both `contracts.md` EC-001 and
> `taxonomy-reference.md` state "37 effect types" in their headers, but the
> actual enumerated lists contain 38 types (5+8+10+9+6=38). The `contracts.md`
> P4 count column says "5" while listing 6 type names. The canonical count is
> determined by enumeration: **38 types, P4=6**. Tests MUST assert 38 total
> members and P4=6. The "37" in the contract headers is a documentation bug.

The 38 types by tier:

| Tier | Types |
|------|-------|
| P0 (5) | ReturnValue, ErrorReturn, SentinelError, ReceiverMutation, PointerArgMutation |
| P1 (8) | SliceMutation, MapMutation, GlobalMutation, WriterOutput, HTTPResponseWrite, ChannelSend, ChannelClose, DeferredReturnMutation |
| P2 (10) | FileSystemWrite, FileSystemDelete, FileSystemMeta, DatabaseWrite, DatabaseTransaction, GoroutineSpawn, Panic, CallbackInvocation, LogWrite, ContextCancellation |
| P3 (9) | StdoutWrite, StderrWrite, EnvVarMutation, MutexOp, WaitGroupOp, AtomicOp, TimeDependency, ProcessExit, RecoverBehavior |
| P4 (6) | ReflectionMutation, UnsafeMutation, CgoCall, FinalizerRegistration, SyncPoolOp, ClosureCaptureMutation |

#### Scenario: All 38 types present
- **WHEN** the `SideEffectType` enum is imported and all members are enumerated
- **THEN** exactly 38 members exist with the names specified in taxonomy-reference.md

#### Scenario: Tier counts correct
- **WHEN** `TIER_MAP` members are grouped by tier
- **THEN** P0 has 5, P1 has 8, P2 has 10, P3 has 9, P4 has 6 members

#### Scenario: Tier assignments are not configurable
- **WHEN** `TIER_MAP` is imported
- **THEN** it is a module-level constant (not a function or class with mutable state)
  and no public API exists to change tier assignments at runtime

---

### Requirement: EC-002 P0 Zero Tolerance

The detector MUST detect all 5 P0 effect types with zero false negatives and
zero false positives on the provided testdata fixtures. P0 effects are the
function's direct observable outputs.

#### Scenario: ReturnValue — non-None return expression
- **WHEN** the detector runs on a function with `return <expr>` where expr is
  not the literal `None`
- **THEN** a `ReturnValue` effect is present in the result

#### Scenario: ReturnValue — annotated return None with non-None annotation
- **WHEN** the detector runs on a function annotated `-> Item | None` with
  body `return None`
- **THEN** a `ReturnValue` effect is present (annotation signals None is meaningful)

#### Scenario: ReturnValue NOT emitted — bare return
- **WHEN** the detector runs on a function with a bare `return` statement
  (no value expression)
- **THEN** zero `ReturnValue` effects are produced

#### Scenario: ReturnValue NOT emitted — return None without annotation
- **WHEN** the detector runs on a function with `return None` and no return
  annotation
- **THEN** zero `ReturnValue` effects are produced

#### Scenario: ErrorReturn — raise statement
- **WHEN** the detector runs on a function containing a `raise SomeException()`
  statement
- **THEN** an `ErrorReturn` effect is present

#### Scenario: ErrorReturn — bare re-raise
- **WHEN** the detector runs on a function containing a bare `raise` (re-raise)
- **THEN** an `ErrorReturn` effect is present

#### Scenario: Panic — raise SystemExit is NOT ErrorReturn
- **WHEN** the detector runs on a function containing `raise SystemExit(1)`
- **THEN** a `Panic` effect is present and no `ErrorReturn` effect is produced
  (a single `raise` node MUST NOT produce both)

#### Scenario: SentinelError — direct Exception subclass
- **WHEN** the detector runs on a module containing a top-level class that
  inherits directly from `Exception`
- **THEN** a `SentinelError` effect is associated with that class definition

#### Scenario: SentinelError — transitive stdlib inheritance
- **WHEN** the detector runs on a module containing a top-level class that
  inherits from `ValueError` (a stdlib Exception subclass)
- **THEN** a `SentinelError` effect is present

#### Scenario: SentinelError NOT emitted — nested class
- **WHEN** an exception class is defined inside a function or method body
- **THEN** no `SentinelError` effect is produced (only top-level ClassDef nodes
  qualify as sentinels)

#### Scenario: ReceiverMutation — self attribute assignment
- **WHEN** the detector runs on a method that assigns to `self.<attr>`
- **THEN** a `ReceiverMutation` effect is present

#### Scenario: ReceiverMutation — augmented assignment
- **WHEN** the detector runs on a method with `self.<attr> += value`
- **THEN** a `ReceiverMutation` effect is present

#### Scenario: PointerArgMutation — item assignment on parameter
- **WHEN** the detector runs on a function that item-assigns on a parameter
  (`param[key] = val`)
- **THEN** a `PointerArgMutation` effect is present

#### Scenario: PointerArgMutation vs SliceMutation distinction
- **WHEN** a function calls `param.append(...)` on a list parameter
- **THEN** a `SliceMutation` (P1) effect is present, NOT `PointerArgMutation` (P0)
  (list method calls produce P1; item-assignment produces P0)

#### Scenario: Parse error raises GazeParseError
- **WHEN** the detector runs on a file containing a Python syntax error
- **THEN** `GazeParseError` is raised — NOT a silent empty result

---

### Requirement: EC-003 Effect Identity

Each detected side effect MUST have a stable, deterministic `id` field.

The ID MUST be computed as:
`sha256(rel_path + ":" + fn_name + ":" + effect_type + ":" + location)`,
truncated to 8 hex characters, prefixed with `se-`.

The `rel_path` component MUST be the **project-relative path** (not the
absolute path), so IDs are stable across machines and working directories.

Properties:
- **Deterministic**: same source input → same ID across runs and machines
- **Unique**: no two distinct effects in the same function share an ID
- **Stable**: the ID does not change unless the effect's location or type changes

#### Scenario: Deterministic IDs across runs
- **WHEN** the same source file is analyzed twice
- **THEN** all effect IDs are identical across both runs

#### Scenario: Stable across machines (relative path)
- **WHEN** the same source file exists at different absolute paths on two machines
  but the same project-relative path
- **THEN** all effect IDs are identical (relative path used in hash, not absolute)

#### Scenario: ID format
- **WHEN** any effect is inspected
- **THEN** the `id` field matches the pattern `se-[0-9a-f]{8}`

---

### Requirement: EC-004 Effect Structure

Each detected side effect MUST carry these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stable identifier (see EC-003); format `se-XXXXXXXX` |
| `type` | SideEffectType | One of the 38 enum values |
| `tier` | Tier | P0–P4, derived from type via TIER_MAP |
| `location` | string | Source position in `file:line:col` format (two colons) |
| `description` | string | Human-readable explanation of the detected effect |
| `target` | string | Affected entity (function name, variable, channel, etc.) |
| `classification` | ClassificationResult or None | Null before classification runs |

The `location` field MUST use both `lineno` and `col_offset` from the AST node.
The format is `<rel_path>:<lineno>:<col_offset>`.

#### Scenario: All required fields present
- **WHEN** a function with a detected ReturnValue effect is analyzed
- **THEN** the effect dict contains all 7 required fields, all non-null
  (except `classification` which is null before classification runs)

#### Scenario: Location format — two colons
- **WHEN** any detected effect is inspected
- **THEN** the `location` field matches the regex `^[^:]+:\d+:\d+$`
  (path, colon, line number, colon, column offset)

#### Scenario: Tier derived from TIER_MAP
- **WHEN** any effect is produced
- **THEN** `effect.tier == TIER_MAP[effect.type]` (tier is never set independently)

---

### Requirement: EC-005 Language Adaptation

The implementation MUST map each of the 38 effect types to its Python language
equivalent. Types with clear Python equivalents MUST be detected. Two types are
**permanently closed** — they remain in the taxonomy for porting contract
compatibility but MUST never be emitted by the detector:

- **AtomicOp** (P3): No Python equivalent. Python has no atomic
  read-modify-write primitive. `threading.local` is thread-local storage, not
  atomic. ctypes atomics are indistinguishable from general ctypes calls.
- **SyncPoolOp** (P4): No Python equivalent. Go's `sync.Pool` has no stdlib
  counterpart in Python.

The canonical Python mappings for implemented types:

| Effect Type | Python Detection Pattern |
|-------------|--------------------------|
| ReturnValue | `return <expr>` (non-None, or annotated non-None return) |
| ErrorReturn | `raise <expr>` (non-SystemExit) or bare `raise` |
| SentinelError | Top-level `class Foo(Exception):` or transitive stdlib subclass |
| ReceiverMutation | `self.<attr> = ...` or `self.<attr> += ...` |
| PointerArgMutation | `param[key] = val` (subscript assignment on a parameter) |
| SliceMutation | `param.append/extend/insert/pop/remove/clear/reverse/sort(...)` |
| MapMutation | `param.update/setdefault/pop/clear(...)` |
| GlobalMutation | Assignment to a `global`-declared name |
| WriterOutput | `param.write(...)` on a non-response parameter |
| HTTPResponseWrite | `response.write(...)` or `resp.write(...)` |
| ChannelSend | `param.put(...)` |
| ChannelClose | `param.close(...)` |
| DeferredReturnMutation | `finally:` block assigns to a variable that is subsequently returned |
| FileSystemWrite | `open(path, "w"/"a"/...)` or `Path.write_text/write_bytes()` |
| FileSystemDelete | `os.remove/unlink()`, `shutil.rmtree()`, `Path.unlink()` |
| FileSystemMeta | `os.chmod/chown/utime/symlink/link()`, `Path.chmod()` |
| DatabaseWrite | `param.execute(...)` or `param.commit(...)` |
| DatabaseTransaction | `with connection/conn/session/tx/transaction:` |
| GoroutineSpawn | `threading.Thread(...)`, `asyncio.create_task(...)`, `multiprocessing.Process(...)`, executor/pool `.submit(...)` |
| Panic | `raise SystemExit(...)` or `raise SystemExit` |
| CallbackInvocation | Direct call of a parameter: `param(...)` |
| LogWrite | `logging.*/logger.*/log.*()` |
| ContextCancellation | `param.cancel()` or `param.set()` |
| StdoutWrite | `print(...)` or `sys.stdout.write(...)` |
| StderrWrite | `sys.stderr.write(...)` |
| EnvVarMutation | `os.environ[key] = val` |
| MutexOp | `with param:` (non-connection parameter names) |
| WaitGroupOp | `asyncio.gather/wait(...)`, `async with asyncio.TaskGroup()`, `barrier.wait()`, `futures.wait()` |
| TimeDependency | `time.time/monotonic/perf_counter()`, `datetime.now/utcnow()` |
| ProcessExit | `sys.exit(...)`, `os._exit(...)`, `os.abort()` |
| RecoverBehavior | `except:` block that returns a fallback or assigns a default (not a re-raise) |
| ReflectionMutation | `setattr(...)` or `obj.__setattr__(...)` |
| UnsafeMutation | `ptr[0] = ...` or `ptr.contents = ...` (ctypes pointer name heuristic) |
| CgoCall | `ctypes.*()` or `cffi.*()` |
| FinalizerRegistration | `weakref.finalize(...)` |
| ClosureCaptureMutation | `nonlocal x` followed by `x = ...` in the inner function |

> **Note on signal source IDs**: The canonical cross-implementation signal
> source identifiers per CC-006 are `"godoc"` and `"godoc_keyword_indirect"`.
> Python implementations MUST use these identifiers verbatim — do NOT substitute
> `"docstring"` or `"pydoc"`. This preserves schema compatibility with Go gaze.

#### Scenario: Python-specific effects detected
- **WHEN** the detector runs on Python source using `queue.Queue.put()`,
  `threading.Lock` as a context manager, `os.chmod()`, and `connection.begin()`
- **THEN** ChannelSend, MutexOp, FileSystemMeta, and DatabaseTransaction
  effects are present

#### Scenario: WriterOutput detected
- **WHEN** a function calls `.write()` on a parameter named `writer`
- **THEN** a `WriterOutput` effect is present

#### Scenario: DeferredReturnMutation detected
- **WHEN** a function's `finally:` block assigns to a variable that is
  subsequently returned
- **THEN** a `DeferredReturnMutation` effect is present

#### Scenario: StderrWrite detected
- **WHEN** a function calls `sys.stderr.write(...)`
- **THEN** a `StderrWrite` effect is present

#### Scenario: EnvVarMutation detected
- **WHEN** a function contains `os.environ[key] = value`
- **THEN** an `EnvVarMutation` effect is present

#### Scenario: TimeDependency detected
- **WHEN** a function calls `time.time()`
- **THEN** a `TimeDependency` effect is present

#### Scenario: ClosureCaptureMutation detected
- **WHEN** an inner function contains `nonlocal x` followed by `x = new_value`
- **THEN** a `ClosureCaptureMutation` effect is present on the **inner** function

#### Scenario: AtomicOp permanently closed — never emitted
- **WHEN** the detector runs on any Python source
- **THEN** no `AtomicOp` effect is ever produced

#### Scenario: SyncPoolOp permanently closed — never emitted
- **WHEN** the detector runs on any Python source
- **THEN** no `SyncPoolOp` effect is ever produced

---

### Requirement: P3 Detection — RecoverBehavior

The detector MUST detect `RecoverBehavior` (P3) when a `try/except` block
performs recovery rather than re-raising. Recovery is defined as an `except`
handler body that contains at least one of: `return`, `ast.Assign`,
`ast.AugAssign`, or `ast.Pass` — and does NOT unconditionally re-raise.

Re-raise exclusion rules (checked in order):
1. A single bare `raise` (no args) → NOT recovery (pure re-raise)
2. Any top-level statement in the handler body is `raise <exc>` (non-None exc)
   → NOT recovery (unconditional transform-and-re-raise)
3. Body contains `return`, assignment, or `pass` → IS recovery

At most one `RecoverBehavior` effect is emitted per function even if multiple
`try/except` blocks qualify.

Python 3.11+ `except*` (ExceptionGroup) blocks MUST be treated identically
to `except` blocks.

#### Scenario: RecoverBehavior — fallback return
- **WHEN** a function has `except SomeError: return default_value`
- **THEN** a `RecoverBehavior` effect is present

#### Scenario: RecoverBehavior — bare pass suppression
- **WHEN** a function has `except SomeError: pass`
- **THEN** a `RecoverBehavior` effect is present

#### Scenario: RecoverBehavior NOT emitted — pure re-raise
- **WHEN** a function has `except SomeError: raise`
- **THEN** no `RecoverBehavior` effect is produced

#### Scenario: RecoverBehavior NOT emitted — transform-and-re-raise
- **WHEN** a function has `except SomeError: raise RuntimeError("wrapped")`
- **THEN** no `RecoverBehavior` effect is produced

#### Scenario: At most one RecoverBehavior per function
- **WHEN** a function has two qualifying `try/except` blocks
- **THEN** exactly one `RecoverBehavior` effect is produced

---

### Requirement: P3 Detection — WaitGroupOp

The detector MUST detect `WaitGroupOp` (P3) for the following patterns:

- `asyncio.gather(...)` — awaiting a group of coroutines
- `asyncio.wait(...)` — waiting on a set of futures
- `async with asyncio.TaskGroup():` — structured concurrency task group
- `barrier.wait()` / `barriers.wait()` — threading.Barrier synchronization
  (name heuristic: object named `barrier` or `barriers`)
- `futures.wait(...)` — concurrent.futures wait (requires alias import:
  `import concurrent.futures as futures`)

#### Scenario: WaitGroupOp — asyncio.gather
- **WHEN** a function calls `asyncio.gather(...)`
- **THEN** a `WaitGroupOp` effect is present

#### Scenario: WaitGroupOp — async with TaskGroup
- **WHEN** a function uses `async with asyncio.TaskGroup() as tg:`
- **THEN** a `WaitGroupOp` effect is present

#### Scenario: WaitGroupOp — threading.Barrier.wait
- **WHEN** a function calls `barrier.wait()`
- **THEN** a `WaitGroupOp` effect is present

---

### Requirement: P4 Detection — UnsafeMutation

The detector MUST detect `UnsafeMutation` (P4) for ctypes pointer write
patterns using a name heuristic. Two patterns are detected:

1. Subscript assignment: `ptr[0] = value` where the variable name contains
   one of the substrings: `ptr`, `buf`, `mem`, `raw`, or starts with `p_`
2. Contents assignment: `ptr.contents = value` (any variable name)

False-positive risk is acceptable for P4 ("may detect") per EC-001.

#### Scenario: UnsafeMutation — subscript write
- **WHEN** a function contains `ptr[0] = value` where `ptr` is a local variable
- **THEN** an `UnsafeMutation` effect is present

#### Scenario: UnsafeMutation — contents assignment
- **WHEN** a function contains `some_ptr.contents = new_value`
- **THEN** an `UnsafeMutation` effect is present

---

### Requirement: Python-Native Detection (Planned)

> **Status**: The following mappings are **planned** in the
> `python-native-detection` branch but are NOT yet implemented in `main`.
> They are documented here as future requirements. Tests for these patterns
> MUST NOT be added to the main test suite until the branch is merged.

The following Python-native patterns are planned for future detection:

| Pattern | Effect Type | Notes |
|---------|-------------|-------|
| `subprocess.Popen/run/call/check_output(...)` | GoroutineSpawn | Spawns a subprocess |
| `async with lock:` | MutexOp | Async lock acquisition |
| `atexit.register(...)` | GlobalMutation | Registers a process-exit callback |
| `warnings.warn(...)` | LogWrite + GlobalMutation | Emits a warning (dual effect) |
| `@functools.lru_cache` / `@functools.cache` | GlobalMutation | Mutates module-level cache |

---

### Requirement: Nested Scope Isolation

The detector MUST NOT attribute effects from nested function definitions to
the outer function. Each function (including nested functions) is analyzed
independently. The outer function's effect list MUST NOT include effects
detected inside inner `def` or `async def` bodies.

#### Scenario: Nested function effects isolated
- **WHEN** an outer function contains an inner function that raises an exception
- **THEN** the outer function's effect list does NOT contain the `ErrorReturn`
  from the inner function's `raise` statement

#### Scenario: Nested function analyzed independently
- **WHEN** a module contains `outer` with nested `inner`
- **THEN** `inner` appears as a separate `FunctionTarget` with its own effects

---

### Requirement: AST-Only Analysis

The detector MUST use Python's `ast` module exclusively. The following are
prohibited:

- Executing the analyzed code
- Importing the analyzed module
- Runtime introspection (`inspect`, `importlib`, `__import__`)
- Any form of dynamic evaluation (`eval`, `exec`)

#### Scenario: Analysis does not import analyzed module
- **WHEN** the detector analyzes a file that has import-time side effects
- **THEN** those side effects are NOT triggered (the file is parsed, not imported)
