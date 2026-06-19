# Side Effects

A **side effect** is any observable change that a function produces beyond its internal computation. When you call a function, its side effects are everything a caller can detect: the values it returns, the variables it mutates, the files it writes, the subprocesses it spawns.

gaze-py detects side effects through static analysis of Python source code using the `ast` module. No code is executed and no modules are imported during analysis. Every detected side effect is assigned a [type](#the-taxonomy-38-effect-types-across-5-tiers), a [tier](#tier-definitions) (P0 through P4), and a stable ID for tracking across runs.

## Why Side Effects Matter

Traditional code coverage answers "was this line executed?" but says nothing about whether the test *verified* anything meaningful. A test that calls a function and ignores its return value achieves 100% line coverage but 0% [contract coverage](../reference/glossary.md#contract-coverage).

Side effects are the bridge between "code was executed" and "behavior was verified." By enumerating every observable change a function can produce, gaze-py can measure whether your tests actually assert on the things that matter.

## Tier Definitions

| Tier | Priority | Description |
|---|---|---|
| P0 | Must Detect | Direct observable outputs — definitionally contractual |
| P1 | High Value | Shared state mutations and I/O writes |
| P2 | Important | External system interactions and concurrency |
| P3 | Nice to Have | Standard I/O, env, synchronization primitives |
| P4 | Exotic | Reflection, unsafe access, finalizers |

## The Taxonomy: 38 Effect Types Across 5 Tiers

Detection status is as of v0.6.0. See `src/gaze_py/taxonomy/effects.py` (`SideEffectType`) for the authoritative enum.

### P0 — Must Detect (5 types)

P0 effects are a function's direct observable outputs. These are definitionally contractual — they are the reason callers invoke the function. gaze-py targets zero false negatives and zero false positives for P0 effects.

| Effect Type | Description | Detection |
|---|---|---|
| `ReturnValue` | A non-error value returned to the caller | Implemented (AST) |
| `ErrorReturn` | An exception-typed value returned or raised | Implemented (AST) |
| `SentinelError` | A module-level sentinel exception (`MyError = ...`) | Implemented (AST) |
| `ReceiverMutation` | Mutation of `self` attributes (e.g., `self.count += 1`) | Implemented (AST) |
| `PointerArgMutation` | Mutation of a mutable argument (e.g., `result.append(x)`) | Implemented (AST) |

### P1 — High Value (8 types)

P1 effects are significant observable changes beyond direct return values. They modify shared state, write to I/O interfaces, or communicate through channels.

| Effect Type | Description | Detection |
|---|---|---|
| `SliceMutation` | Index assignment on a list parameter (e.g., `items[i] = v`) | Implemented (AST) |
| `MapMutation` | Key assignment on a dict parameter (e.g., `mapping[key] = v`) | Implemented (AST) |
| `GlobalMutation` | Assignment to a module-level variable | Implemented (AST) |
| `WriterOutput` | Calls to file-like write interfaces | Implemented (AST) |
| `HTTPResponseWrite` | Writes to an HTTP response object | Implemented (AST) |
| `ChannelSend` | Sending on a queue or channel-like object | Implemented (AST) |
| `ChannelClose` | Closing a queue or channel-like object | Implemented (AST) |
| `DeferredReturnMutation` | Named return variable modified in a `finally` block | Implemented (AST) |

### P2 — Important (10 types)

P2 effects cover interactions with external systems, concurrency, and control flow changes.

| Effect Type | Description | Detection |
|---|---|---|
| `FileSystemWrite` | File creation or write operations (`open()` in write mode, `pathlib.write_*`, `shutil.copy*`) | Implemented (AST) |
| `FileSystemDelete` | File or directory removal (`os.remove`, `shutil.rmtree`, `pathlib.unlink`) | Implemented (AST) |
| `FileSystemMeta` | File metadata changes (`os.chmod`, `os.rename`, `pathlib.rename`) | Implemented (AST) |
| `DatabaseWrite` | Database write operations (`.execute()`, `.commit()` on a connection/cursor parameter) | Implemented (AST) |
| `DatabaseTransaction` | Database transaction initiation (`async with connection:`, `with session:`) | Implemented (AST) |
| `GoroutineSpawn` | Subprocess or thread creation (`subprocess.*`, `threading.Thread`, `multiprocessing.Process`) | Implemented (AST) |
| `Panic` | Raising an exception unconditionally | Implemented (AST) |
| `CallbackInvocation` | Calling a function-typed parameter | Implemented (AST) |
| `LogWrite` | Logging calls (`logging.*`, `warnings.warn()`) | Implemented (AST) |
| `ContextCancellation` | Context setup that can cancel or timeout (`asyncio.timeout`, `asyncio.wait_for`) | Implemented (AST) |

### P3 — Nice to Have (9 types)

P3 effects cover standard I/O, environment manipulation, synchronization primitives, and other observable behaviors.

| Effect Type | Description | Detection |
|---|---|---|
| `StdoutWrite` | Writing to standard output (`print()`, `sys.stdout.write()`) | Implemented (AST) |
| `StderrWrite` | Writing to standard error (`sys.stderr.write()`) | Implemented (AST) |
| `EnvVarMutation` | Modification of environment variables (`os.environ[...] = ...`) | Implemented (AST) |
| `MutexOp` | Lock/unlock on a threading primitive (`threading.Lock`, `asyncio.Lock`) | Implemented (AST) |
| `WaitGroupOp` | WaitGroup-style synchronization (`threading.Barrier`, `asyncio.Barrier`) | Implemented (AST) |
| `AtomicOp` | Atomic load/store operations | Not implemented (no Python equivalent — permanently closed) |
| `TimeDependency` | Dependency on current time (`datetime.now()`, `time.time()`) | Implemented (AST) |
| `ProcessExit` | Process termination (`sys.exit()`, `os._exit()`) | Implemented (AST) |
| `RecoverBehavior` | Exception recovery patterns | Implemented (AST) |

### P4 — Exotic (6 types)

P4 effects are rare patterns that require unusual Python constructs.

| Effect Type | Description | Detection |
|---|---|---|
| `ReflectionMutation` | Dynamic attribute mutation (`setattr()`, `object.__setattr__()`) | Implemented (AST) |
| `UnsafeMutation` | Mutation via `ctypes` or memory manipulation | Implemented (AST) |
| `CgoCall` | Foreign function interface calls (`ctypes.cdll.*`) | Implemented (AST) |
| `FinalizerRegistration` | Registration of finalizers (`weakref.finalize`, `atexit.register`) | Implemented (AST) |
| `SyncPoolOp` | Object pool operations | Not implemented (no Python equivalent — permanently closed) |
| `ClosureCaptureMutation` | Mutation of a captured outer variable via `nonlocal` | Implemented (AST) |
