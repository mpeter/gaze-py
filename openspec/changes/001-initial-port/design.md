# Design — Change 001: Initial Port

## Package Layout

```
src/gaze/
├── __init__.py              # __version__ = "0.1.0" only
├── taxonomy/
│   ├── __init__.py
│   ├── effects.py           # SideEffectType (38-value StrEnum), Tier, TIER_MAP
│   └── models.py            # SideEffect, Signal, ClassificationResult,
│                            # Score, FunctionTarget, AnalysisResult dataclasses
├── analysis/
│   ├── __init__.py
│   └── detector.py          # FileDetector: two-phase AST scan
├── classify/
│   ├── __init__.py
│   ├── engine.py            # ClassificationEngine: runs 5 signals, computes score
│   └── signals/
│       ├── __init__.py
│       ├── interface.py     # Signal 1: ABC/Protocol base class check
│       ├── visibility.py    # Signal 2: public name + return/receiver type
│       ├── caller.py        # Signal 3: cross-file call count scan
│       ├── naming.py        # Signal 4: contractual/incidental prefix table
│       └── docstring.py     # Signal 5: keyword scan of docstrings
├── crap/
│   ├── __init__.py
│   └── scorer.py            # crap(), gaze_crap(), quadrant(), fix_strategy(),
│                            # recommended_actions(), crapload()
├── config/
│   ├── __init__.py
│   └── loader.py            # Load .gaze.yaml; GazeConfig dataclass
├── report/
│   ├── __init__.py
│   ├── json_formatter.py    # to_json(AnalysisResult) -> str
│   └── text_formatter.py    # to_text(AnalysisResult) -> str
└── cli/
    ├── __init__.py
    └── main.py              # @click.group(); analyze + report commands

# Note: src/gaze/quality/ (O1 — assertion mapping) is NOT created in this
# change. It will be added in a future OpenSpec change. AGENTS.md documents
# the target structure including quality/; that structure is aspirational.

tests/
├── test_taxonomy.py         # EC-001: 38 types, tier counts
├── test_detector.py         # EC-002, EC-003, EC-004, EC-005: detection, ids, structure
├── test_classifier.py       # CC-001 through CC-006
├── test_scorer.py           # SC-001 through SC-006: formulas, quadrants, strategies
├── test_output.py           # OC-001 through OC-003: JSON fields, nullable
├── test_cli.py              # CLI smoke + failure tests via Click test runner
└── testdata/
    └── analysis/
        ├── pure_function.py
        ├── return_value.py
        ├── return_value_annotation.py   # -> Item | None with return None
        ├── error_return.py
        ├── sentinel_error.py
        ├── sentinel_error_transitive.py # class MyErr(ValueError)
        ├── receiver_mutation.py
        ├── pointer_arg_mutation.py      # item assignment param[k]=v
        ├── slice_mutation.py            # param.append(...)
        ├── map_mutation.py
        ├── global_mutation.py
        ├── writer_output.py             # .write() on injected param
        ├── http_response_write.py       # response.write(...)
        ├── channel_send.py              # queue.Queue.put()
        ├── channel_close.py             # multiprocessing.Queue.close()
        ├── deferred_return_mutation.py  # finally: block
        ├── filesystem_write.py          # open(..., 'w')
        ├── filesystem_delete.py         # os.remove()
        ├── filesystem_meta.py           # os.chmod()
        ├── db_write.py                  # .execute(), .commit()
        ├── db_transaction.py            # connection.begin()
        ├── thread_spawn.py              # threading.Thread, asyncio.create_task
        ├── context_cancellation.py      # task.cancel()
        ├── log_write.py                 # logging.* calls
        ├── stdout_write.py              # print(), sys.stdout.write()
        ├── callback_invoke.py           # calling a function parameter
        ├── mutex_op.py                  # threading.Lock
        └── syntax_error.py             # invalid Python — failure mode test
```

## Key Design Decisions

### AST-only, two-phase scan

Python's `ast` module is sufficient for all P0 and most P1/P2 detections.
Go's reference implementation uses SSA for mutation tracking — Python's AST
is expressive enough to detect `self.x = ...` (ReceiverMutation),
`param.append(...)` (SliceMutation), and `GLOBAL = ...` (GlobalMutation)
without SSA.

`FileDetector.detect(path)` uses a two-phase approach:

1. **Module-level pass**: Walk top-level `ast.ClassDef` nodes to detect
   `SentinelError` effects. A class is a sentinel if its bases include
   `Exception`, `BaseException`, or any class name that is itself known to
   inherit from `Exception` (checked transitively within the same module using
   a single-pass base-resolution algorithm). Exception classes defined inside
   function or method bodies are NOT sentinels. These effects are associated
   with a synthetic `FunctionTarget(name="<module>", signature=None,
   receiver=None)`.

2. **Per-function pass**: Walk each `ast.FunctionDef` and
   `ast.AsyncFunctionDef` node. A single `FunctionVisitor(ast.NodeVisitor)`
   subclass descends into the function body and collects all other effect
   types.

**Failure mode**: When `ast.parse()` raises `SyntaxError` (invalid Python),
`FileDetector.detect()` MUST raise a `GazeParseError` (a custom exception
subclass) — NOT return an empty list silently. Callers (the CLI pipeline) catch
this and emit a warning, then continue with other files.

### Effect IDs

`sha256(rel_path + ":" + function_name + ":" + effect_type + ":" + location).hexdigest()[:8]`,
prefixed with `se-`. The `rel_path` MUST be the **project-relative path**
(relative to the analyzed project root, not an absolute path), so IDs are
stable across machines and working directories. Matches the reference
implementation's approach (EC-003).

### ReturnValue detection heuristic (EC-005 Python adaptation)

Go's implementation detects ReturnValue by inspecting the declared return type
in the function signature. Python functions have optional annotations, so the
heuristic is:

- Detect `ast.Return` where `node.value` is not `None` **and** not the
  `ast.Constant(value=None)` literal (explicit `return None` → no effect by
  default).
- **Annotation exception**: if the function has a return annotation (`-> X`)
  where `X` is not `None`, `type[None]`, or `None` as a union member alone,
  then even an explicit `return None` IS a `ReturnValue` (the annotation
  signals that `None` is a meaningful return value, e.g., `-> Item | None`).
  Check: if `returns` node is present and not `ast.Constant(value=None)`,
  detect ReturnValue for all `ast.Return` nodes in that function.
- Bare `return` (no value) and functions with no return statement produce no
  `ReturnValue` effect.

This is documented in the effect's `description` field per EC-005.

### PointerArgMutation vs SliceMutation/MapMutation disambiguation

These are distinct effect types with different tiers (P0 vs P1). The rule:

- **PointerArgMutation** (P0): item assignment on a parameter (`param[key] = val`).
  Detected via `ast.Assign` / `ast.AugAssign` where the target is
  `ast.Subscript` on a name matching a parameter.
- **SliceMutation** (P1): list method calls on a parameter (`.append()`,
  `.extend()`, `.insert()`, `.pop()`, `.remove()`, `.clear()`, `.reverse()`,
  `.sort()`).
- **MapMutation** (P1): dict method calls on a parameter (`.update()`,
  `.setdefault()`, `.pop()`, `.clear()`).

A single AST node MUST produce at most one effect. Preference order if the
call is ambiguous: P0 first (item assignment wins over method call on same
parameter). In practice, `param.append()` is unambiguously SliceMutation
and `param[k] = v` is unambiguously PointerArgMutation.

### Panic vs ProcessExit disambiguation

The contracts provide no disambiguation rule. The approach that avoids invented
logic and preserves EC-003 (one effect per AST node):

- **Panic** (P2): `raise SystemExit` only. This is structurally distinct from
  a function call — it is an `ast.Raise` node, not an `ast.Call`.
- **ProcessExit** (P3): `sys.exit()`, `os._exit()`, `os.abort()` — function
  calls only.

No overlap exists. A single AST node cannot be both a `Raise` and a `Call`.
No context (e.g., `except` block) inspection is needed. This is the simplest
rule with no invented disambiguation and full EC-003 compliance.

### Classification engine

Each of the 5 signal analyzers is a standalone function returning a `Signal`
dataclass. `ClassificationEngine.classify(effect, context)` calls all five,
sums weights, applies tier boost and contradiction penalty, clamps to [0, 100],
and returns a `ClassificationResult`. No shared state between calls.

### Caller dependency (Signal 3)

Requires a project-wide scan. The engine accepts a pre-built
`callers: dict[str, int]` mapping function qualified name → caller module count.
The `FileDetector` API accepts an optional caller map; callers without a map
get 0 (no caller signal). This keeps the detector pure and lets the CLI build
the caller map in a separate pre-pass.

### Coverage input

Line coverage is an external input — the CLI accepts `--coverage-json <path>`
pointing to a `coverage.py` JSON report. If not provided:
- `line_coverage` is `None` (NOT 0.0 — per OC-003 null-not-zero)
- `crap` is `None` (CRAP cannot be computed without coverage)
- A warning is emitted to stderr
- The rest of the analysis (detection, classification, effect listing) proceeds normally

This avoids running tests internally (matches O6 intent without implementing the
full capability) and correctly distinguishes "not computed" from "computed as zero."

### GazeCRAP / O1 deferral

Contract coverage requires O1 (quality/assertion mapping). O1 is not
implemented in this change. When O1 has not run:
- `contract_coverage` is `None`
- `gaze_crap` is `None`
- `quadrant` is `None`
- `fix_strategy` is `None` when CRAP is also null; otherwise `fix_strategy`
  uses line_coverage and CRAP (quadrant-based strategies like `add_assertions`
  are unavailable without GazeCRAP)
- `contract_coverage_reason` is `None` (O1 deferred)

### JSON serialization strategy

Domain dataclasses use `dataclasses.asdict()` for JSON serialization.

- `SideEffectType` is a `StrEnum` — serializes automatically as its string value.
- `Tier` is a plain enum — add a `to_dict()` method or use a custom JSON
  encoder that calls `.value` for any enum instance.
- `None` fields serialize as JSON `null` natively.
- The `json_formatter.py` produces output via:
  ```python
  json.dumps(dataclasses.asdict(result), indent=2, default=_json_default)
  ```
  where `_json_default` handles non-`asdict`-able types (e.g., remaining enum
  types not handled by StrEnum).

Value objects (`Signal`, `SideEffect`, `Score`, `ClassificationResult`) MUST
use `@dataclass(frozen=True)`. Container/builder objects (`FunctionTarget`,
`AnalysisResult`) MAY be mutable if the pipeline builds them incrementally.

### pyproject.toml naming

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gaze-py"          # PyPI name (avoids collision with existing "gaze" package)
requires-python = ">=3.11"

[tool.hatch.build.targets.wheel]
packages = ["src/gaze"]   # maps PyPI name "gaze-py" to import name "gaze"

[project.scripts]
gazepy = "gaze.cli.main:cli"
```

Import: `import gaze` (the directory is `src/gaze/`). Hatchling's `packages`
setting explicitly maps the src-layout package, ensuring the installed import
name is `gaze` regardless of the PyPI distribution name. The built wheel will
be named `gaze_py-0.1.0-py3-none-any.whl` (hatchling normalizes `gaze-py`).

### Config loading

`.gaze.yaml` discovery uses a **walk-up algorithm**: resolve the `<path>`
argument to an absolute path, then walk up ancestor directories until
`.gaze.yaml` is found or the filesystem root is reached. This matches the
behavior of ruff, mypy, and pyproject.toml discovery.

If not found, defaults apply: `contractual_threshold=80`,
`incidental_threshold=50`, `crap_threshold=15.0`, `gaze_crap_threshold=15.0`.

Config loader MUST validate all threshold values are in sane ranges:
`contractual_threshold` and `incidental_threshold` in [0, 100];
`crap_threshold` and `gaze_crap_threshold` > 0. Raise `GazeConfigError` on
invalid values.

### Install path

For this change, the install path is local-wheel only:
```
uv build
uv tool install dist/gaze_py-*.whl --force
```

PyPI publication requires a release workflow that is out of scope for this
change. `uv tool install gaze-py` (bare PyPI name) will NOT work until
the package is published.

## Python Language Mappings (EC-005)

| Contract Effect | Tier | Python Detection |
|---|---|---|
| ReturnValue | P0 | `ast.Return` with non-None value; see ReturnValue heuristic above |
| ErrorReturn | P0 | `ast.Raise` in function body |
| SentinelError | P0 | Module-level `ast.ClassDef` inheriting from `Exception` or known subclass — detected in module-level pass |
| ReceiverMutation | P0 | `self.<attr> = ...` (`ast.Assign` / `ast.AugAssign` where target is `ast.Attribute` on `self`) |
| PointerArgMutation | P0 | Item assignment on a parameter (`param[key] = val`) — see disambiguation above |
| SliceMutation | P1 | List method calls on a parameter (`.append()`, `.extend()`, `.insert()`, `.pop()`, `.remove()`, `.clear()`) |
| MapMutation | P1 | Dict method calls on a parameter (`.update()`, `.setdefault()`, `.pop()`, `.clear()`) |
| GlobalMutation | P1 | `ast.Global` statement + subsequent assignment, or direct assignment to a module-level name |
| WriterOutput | P1 | `.write()` called on a function parameter (injected writer pattern) |
| HTTPResponseWrite | P1 | `.write()` or attribute assignment on a parameter named `response`/`resp` |
| ChannelSend | P1 | `queue.Queue.put()`, `asyncio.Queue.put()`, `multiprocessing.Queue.put()` |
| ChannelClose | P1 | `multiprocessing.Queue.close()`, `asyncio.Queue` shutdown patterns |
| DeferredReturnMutation | P1 | Assignment in `finally:` block to a variable subsequently returned by the function |
| FileSystemWrite | P2 | `open(..., 'w'/'a'/'wb')`, `pathlib.Path.write_text/write_bytes`, `shutil.copy*` |
| FileSystemDelete | P2 | `os.remove()`, `os.unlink()`, `pathlib.Path.unlink()`, `shutil.rmtree()` |
| FileSystemMeta | P2 | `os.chmod()`, `os.chown()`, `os.utime()`, `os.symlink()`, `os.link()`, `pathlib.Path.chmod()` |
| DatabaseWrite | P2 | `.execute()`, `.commit()` on a db connection/cursor parameter |
| DatabaseTransaction | P2 | `connection.begin()`, `with connection:` context manager pattern, `session.begin()` |
| GoroutineSpawn | P2 | `threading.Thread(...)`, `asyncio.create_task(...)`, `concurrent.futures.submit(...)`, `multiprocessing.Process(...)` |
| Panic | P2 | `raise SystemExit` only (ast.Raise node — structurally distinct from function calls) |
| CallbackInvocation | P2 | Calling a parameter that is callable (e.g., `func_param(...)`) |
| LogWrite | P2 | `logging.*`, `logger.*`, `log.*` call patterns |
| ContextCancellation | P2 | `.cancel()` on an asyncio Task/Future, `.set()` on a `threading.Event` |
| StdoutWrite | P3 | `print(...)`, `sys.stdout.write(...)` |
| StderrWrite | P3 | `sys.stderr.write(...)` |
| EnvVarMutation | P3 | `os.environ[...] = ...`, `os.putenv(...)` |
| MutexOp | P3 | `threading.Lock.acquire()/release()`, `threading.RLock`, `with lock:` pattern |
| TimeDependency | P3 | `time.time()`, `time.monotonic()`, `datetime.now()`, `datetime.utcnow()` |
| ProcessExit | P3 | `sys.exit()`, `os._exit()`, `os.abort()` (function calls only — no overlap with Panic) |
| ReflectionMutation | P4 | `setattr(...)`, `object.__setattr__(...)` |
| CgoCall | P4 | `ctypes.*`, `cffi.*` |
| FinalizerRegistration | P4 | `weakref.finalize(...)` |
| ClosureCaptureMutation | P4 | Assignment to a `nonlocal` variable (`nonlocal x; x = ...`) |

Types with no meaningful Python equivalent — defined in taxonomy, detection
always returns empty, covered by no-op tests asserting empty result:

| Type | Tier | Reason |
|---|---|---|
| WaitGroupOp | P3 | No direct equivalent; `concurrent.futures.wait()` is semantically different |
| AtomicOp | P3 | Python's GIL makes most operations implicitly atomic; no explicit atomic primitives |
| RecoverBehavior | P3 | Go's `recover()` has no Python equivalent; `try/except` is structural |
| UnsafeMutation | P4 | Direct memory manipulation via ctypes is already covered by CgoCall |
| SyncPoolOp | P4 | No Python equivalent to Go's `sync.Pool` |
