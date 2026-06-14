# Design — Change 001: Initial Port

## Package Layout

```
src/gaze_py/
├── __init__.py              # __version__ = "0.1.0" only
├── taxonomy/
│   ├── __init__.py
│   ├── effects.py           # SideEffectType (38-value StrEnum), Tier, TIER_MAP
│   ├── models.py            # SideEffect, Signal, ClassificationResult,
│   │                        # Score, FunctionTarget, AnalysisResult dataclasses
│   └── exceptions.py        # GazeParseError, GazeConfigError (AP-008: shared
│                            # exceptions belong here, not in subpackages)
├── analysis/
│   ├── __init__.py
│   ├── complexity.py        # cyclomatic_complexity(node) -> int (McCabe algorithm)
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
│   └── loader.py            # Load .gaze.yaml; GazeConfig dataclass; raises
│                            # GazeConfigError (imported from taxonomy/exceptions.py)
├── report/
│   ├── __init__.py
│   ├── json_formatter.py    # to_json(AnalysisResult) -> str
│   └── text_formatter.py    # to_text(AnalysisResult) -> str
└── cli/
    ├── __init__.py
    └── main.py              # @click.group(); analyze + report commands

# Note: src/gaze_py/quality/ (O1 — assertion mapping) is NOT created in this
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
        ├── stderr_write.py              # sys.stderr.write(x) — StderrWrite P3
        ├── env_var_mutation.py          # os.environ['KEY'] = 'val' — EnvVarMutation P3
        ├── time_dependency.py           # time.time() — TimeDependency P3
        ├── closure_capture_mutation.py  # nonlocal x; x = new_val — ClosureCaptureMutation P4
        ├── high_complexity.py           # multiple if/for/while branches — for scorer tests
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

**Failure mode**: When `ast.parse()` raises `SyntaxError` **or `ValueError`**
(invalid Python — `ValueError` is raised on null bytes in source, e.g. binary
files accidentally named `.py`), `FileDetector.detect()` MUST raise a
`GazeParseError` (imported from `taxonomy/exceptions.py`) — NOT return an
empty list silently. Catch both: `except (SyntaxError, ValueError): raise
GazeParseError(...) from e`. The exception MUST carry the file path in its
message or `filename` attribute so the error is actionable. Callers (the CLI
pipeline) catch this, emit a warning via `click.echo(err=True)`, and continue
with other files.

### Cyclomatic Complexity (EC-005 Python adaptation)

Cyclomatic complexity is computed internally using the AST — this matches the
Go implementation which uses `github.com/fzipp/gocyclo` for the same purpose,
and satisfies the porting contract (`requirements.md:72`: "A port must either
compute this or accept it from an external tool."). No external tool dependency
is added.

**Algorithm** (`analysis/complexity.py`):

```python
def cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    ...
```

- Start at 1 (base complexity for any function).
- Increment for each:
  - `ast.If` node (includes `elif` — each `elif` is its own `ast.If` in the AST)
  - `ast.For` node
  - `ast.While` node
  - `ast.ExceptHandler` node (each `except` clause)
  - `ast.With` item (each `with` clause, counting all `items`)
  - `ast.Assert` node
  - `ast.BoolOp` with `ast.And` or `ast.Or` (each boolean operator)
  - Comprehension `if` filter (each `if` in a `listcomp`/`dictcomp`/`setcomp`/`genexpr`)
- Does **NOT** recurse into nested `ast.FunctionDef` or `ast.AsyncFunctionDef` nodes
  (each function is scored independently; nested function complexity does not
  roll up into the outer function).

**FunctionTarget model**: The `FunctionTarget` dataclass MUST include a
`complexity: int` field (populated by the detector using `cyclomatic_complexity()`).
The CRAP scorer reads this field — it does not accept complexity as a separate
argument.

**Note**: Effect type names are retained verbatim from the Go taxonomy (e.g.,
`GoroutineSpawn` rather than `ThreadSpawn`) to preserve JSON schema compatibility
per OC-002 and EC-001. The Python detection uses `threading.Thread`,
`asyncio.create_task`, etc., but the effect type string remains `GoroutineSpawn`.

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

- **Panic** (P2): Any `ast.Raise` node where the exception expression is
  `ast.Name(id='SystemExit')` OR `ast.Call(func=ast.Name(id='SystemExit'), ...)`.
  Both `raise SystemExit` and `raise SystemExit(1)` match. This is structurally
  distinct from a function call — it is an `ast.Raise` node.
- **ProcessExit** (P3): `sys.exit()`, `os._exit()`, `os.abort()` — function
  calls only (detected via `ast.Call` on qualified name).

No overlap exists. A single AST node cannot be both a `Raise` and a `Call`.
No context (e.g., `except` block) inspection is needed. This is the simplest
rule with no invented disambiguation and full EC-003 compliance.

### Detection heuristic boundaries

Several effect types use heuristic detection that accepts false positives in
exchange for implementation simplicity. These are documented here to bound the
implementation and prevent over-engineering.

**GlobalMutation**: Detected when a function body contains an explicit
`ast.Global` statement for name `N` followed by an assignment to `N` within
the same function body (no implicit module-level name detection — keeps
detector stateless per function). Direct assignment to module-level names
inside a function body WITHOUT a `global` declaration does NOT count as
`GlobalMutation`. The `global_mutation.py` fixture MUST use the explicit
`global X; X = val` pattern.

**DeferredReturnMutation**: Detected when a `finally:` block contains
`ast.Assign` where the target is `ast.Name(id=N)`, AND the function body
contains `ast.Return` whose value is `ast.Name(id=N)`. Name-matching only —
no cross-block data-flow analysis. This bounds the implementation to a simple
two-pass within the function node.

> **Important**: The `return` statement MUST be in the main function body,
> NOT inside the `finally` block. Only name-matching between the `finally`
> assignment target and the `return` value is performed.

**HTTPResponseWrite**: Detected by parameter name pattern — `.write()` or
attribute assignment on any function parameter named `response` or `resp`.
False positives from non-HTTP response objects with these names are accepted
(P1 detection policy). False negatives from differently-named response objects
are accepted. This heuristic limitation is intentional.

**ChannelSend / ChannelClose**: Detected by method name on a function parameter
— `.put()` on any parameter → ChannelSend; `.close()` on any parameter →
ChannelClose. No import tracking or type inference. The `channel_send.py`
fixture uses `def send(q): q.put(x)` where `q` is a function parameter (no
`import queue` needed in the fixture).

**ClosureCaptureMutation**: The effect is attributed to the **inner** (nested)
function containing the `nonlocal` statement, not the outer function.

**CallerDependency data flow**: The `callers: dict[str, int]` map (function
qualified name → caller module count) is built by the CLI in a pre-pass and
passed as a parameter through the pipeline: CLI → `FileDetector.detect()` →
`FunctionTarget.caller_count` → `ClassificationEngine.classify()` →
`signals/caller.py`. No subpackage imports from any other subpackage for this
data — it flows via parameters only (AP-006 compliant).

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
- A warning is emitted to stderr via `click.echo(err=True)`
- The rest of the analysis (detection, classification, effect listing) proceeds normally

This avoids running tests internally (matches O6 intent without implementing the
full capability) and correctly distinguishes "not computed" from "computed as zero."

**Coverage JSON format** (`coverage.py` v6+ schema):
```json
{
  "files": {
    "<relative_path>": {
      "summary": {
        "percent_covered": 75.0
      }
    }
  }
}
```
The CLI reads `files[path].summary.percent_covered` as a float [0, 100] for
each analyzed file. This is the output of `coverage json` or
`pytest --cov-report=json`.

**Failure modes for `--coverage-json`**:
- Path resolved with `Path.resolve()` before any existence or read operation;
  resolved path is used for all subsequent operations
- File does not exist → `GazeConfigError` with actionable message, exit non-zero
- File exists but is not valid JSON → `GazeConfigError` with file path and parse error, exit non-zero
- File is valid JSON but lacks the `files` key → `GazeConfigError` with field
  name and expected schema, exit non-zero
- A specific path in the coverage JSON does not match any analyzed file →
  warning emitted, that file analyzed with `line_coverage=None`

When wrapping a `json.JSONDecodeError` when parsing coverage JSON, use
`raise GazeConfigError(...) from e` to preserve the original parse traceback
and include the original message in GazeConfigError's message string.

A minimal valid test fixture is provided at `tests/testdata/coverage_sample.json`.

### GazeCRAP / O1 deferral

Contract coverage requires O1 (quality/assertion mapping). O1 is not
implemented in this change. When O1 has not run:
- `contract_coverage` is `None`
- `gaze_crap` is `None`
- `quadrant` is `None`
- `fix_strategy` is `None` when CRAP is null OR when CRAP < crap_threshold.
  Only functions in the CRAPload (CRAP >= crap_threshold) receive a strategy.
  When CRAP is non-null and >= threshold, `fix_strategy` uses line_coverage
  and CRAP. Rule 3 (`add_assertions`, which requires `quadrant == Q3`) is
  unreachable in this change — Q3 requires GazeCRAP which requires O1.
  In practice, only Rules 1, 2, and 4 (default) can fire in this change.
- `contract_coverage_reason` is `None` when O1 is deferred **except** for one
  special case: when a function has **zero detected effects**, the reason MUST be
  `"no_effects_detected"`. This value is determinable from the detector alone
  (no O1 required). All other reason codes (`no_test_coverage`,
  `no_assertions_mapped`, `all_effects_ambiguous`) are deferred to O1.

**SC-005 evaluation order** (critical — read before implementing `fix_strategy()`):
Evaluation order (first match wins in code) is NOT the same as sort priority
(used for output ordering):

| Evaluation order | Condition | Strategy | Sort priority |
|---|---|---|---|
| 1 (check first) | complexity >= threshold AND coverage == 0 | decompose_and_test | 2 |
| 2 | complexity >= threshold AND coverage > 0 | decompose | 3 |
| 3 (unreachable without O1) | quadrant == Q3 | add_assertions | 1 |
| 4 (default) | none of the above | add_tests | 0 |

Output sorts by priority number ascending (add_tests=0 appears first). Do NOT
use priority number as evaluation order — they are inversely related.

### JSON serialization strategy

Domain dataclasses use `dataclasses.asdict()` for JSON serialization.

> **AP-003 deviation**: The universal Python pack (AP-003) requires `to_dict()`
> methods on domain types. This project uses `dataclasses.asdict()` + a custom
> `_json_default` encoder instead. Rationale: `asdict()` handles the full
> nested dataclass tree recursively (SideEffect → Signal → ClassificationResult →
> Score → FunctionTarget → AnalysisResult) without boilerplate. Individual
> `to_dict()` methods on 7+ dataclasses would duplicate this recursive walk and
> create drift risk. This deviation is approved and documented in
> `.opencode/uf/packs/python-custom.md` as CR-005.

- `SideEffectType` is a `StrEnum` — serializes automatically as its string value.
- `Tier` is a plain enum — the custom `_json_default` encoder calls `.value`
  for any non-StrEnum enum instance.
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

### Domain model sketches

**GazeConfig** fields (for `config/loader.py`):
```python
@dataclass
class GazeConfig:
    contractual_threshold: int = 80     # [0, 100]
    incidental_threshold: int = 50      # [0, 100]
    crap_threshold: float = 15.0        # > 0
    gaze_crap_threshold: float = 15.0   # > 0
```
YAML key hierarchy: `classification.thresholds.contractual/incidental`,
`scoring.crap_threshold/gaze_crap_threshold`. Unknown keys silently ignored.

**AnalysisResult** structure (for `taxonomy/models.py`):
```python
@dataclass
class AnalysisResult:
    functions: list[FunctionTarget]     # one per analyzed function
    summary: Summary                    # aggregate counts/stats
```

`FunctionTarget` carries: `name: str`, `file_path: str`, `line: int`,
`complexity: int`, `caller_count: int = 0`, `effects: list[SideEffect]`,
`score: Score | None`.

`Score` carries: `line_coverage: float | None`, `crap: float | None`,
`gaze_crap: float | None`, `contract_coverage: float | None`,
`contract_coverage_reason: str | None`, `fix_strategy: str | None`,
`quadrant: str | None`, `effect_confidence_range: tuple[int, int] | None`.

`Summary` carries: `function_count: int`, `crapload: int`,
`gaze_crapload: int | None`, `avg_line_coverage: float | None`,
`avg_contract_coverage: float | None`, `quadrant_counts: dict | None`,
`fix_strategy_counts: dict | None`,
`recommended_actions: list[RecommendedAction] | None`,
`crap_threshold: float`, `gaze_crap_threshold: float`.

Each `RecommendedAction` is a dict with keys: `function` (str — qualified
function name), `file` (str — relative path), `strategy` (str — fix strategy
value), `crap` (float — CRAP score).

### pyproject.toml naming

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gaze-py"          # PyPI name (avoids collision with existing "gaze" package)
requires-python = ">=3.11"

[tool.hatch.build.targets.wheel]
packages = ["src/gaze_py"]   # maps PyPI name "gaze-py" to import name "gaze_py"

[project.scripts]
gazepy = "gaze_py.cli.main:cli"
```

Import: `import gaze_py` (the directory is `src/gaze_py/`). Hatchling's `packages`
setting explicitly maps the src-layout package, ensuring the installed import
name is `gaze_py` regardless of the PyPI distribution name. The built wheel will
be named `gaze_py-0.1.0-py3-none-any.whl` (hatchling normalizes `gaze-py`).

### Config loading

`.gaze.yaml` discovery uses a **walk-up algorithm**: resolve the `<path>`
argument to an absolute path, then walk up ancestor directories until
`.gaze.yaml` is found or the filesystem root is reached. This matches the
behavior of ruff, mypy, and pyproject.toml discovery.

The path argument MUST be resolved with `Path.resolve()` before the walk begins.
The walk MUST stop at the first ancestor containing `pyproject.toml` or `.git`
(project root sentinel) — do not walk above the project root. If neither
sentinel is found, stop at the filesystem root. This matches ruff/mypy behavior
and prevents reading malicious `.gaze.yaml` files placed above the project root.

If not found, defaults apply: `contractual_threshold=80`,
`incidental_threshold=50`, `crap_threshold=15.0`, `gaze_crap_threshold=15.0`.

Config loader MUST validate all threshold values are in sane ranges:
`contractual_threshold` and `incidental_threshold` in [0, 100];
`crap_threshold` and `gaze_crap_threshold` > 0. Raise `GazeConfigError` on
invalid values.

When wrapping a `yaml.YAMLError`, use `raise GazeConfigError(...) from e` to
preserve the original parse traceback and include the original message in
GazeConfigError's message string. Same pattern for `json.JSONDecodeError` when
parsing coverage JSON.

**GazeConfig threshold data flow** (AP-006): GazeConfig is loaded by the CLI
and threshold values are passed as parameters to `crap()`, `fix_strategy()`,
`crapload()`, and `ClassificationEngine.classify()` — NOT imported from
`config/` by those modules. This preserves AP-006 (imports flow toward the
domain core, not sideways).

### Report command behavior

The `gazepy report <src> <tests>` command is defined to eventually pair source
and test files for O1 assertion mapping. In this change, O1 is deferred.

**Behavior in this change**: `report` accepts `<src>` and `<tests>` as positional
arguments, runs the same detector → classifier → scorer → formatter pipeline as
`analyze <src>`, and ignores `<tests>` with a warning:
```
Warning: report --tests: quality assessment (O1) deferred — ignoring tests directory
```

The command exits 0. The output JSON is structurally identical to `analyze` output.

**Rationale**: Providing the command surface now (even as a stub) lets the CLI
API stabilize. Users can script against `gazepy report` and the command will
gain O1 behavior when that change ships, without breaking the call site.

### Text formatter output format

The text formatter (`report/text_formatter.py`) produces plain text output
using Python's `str.format()` — no `rich` dependency.

> **CS-009 exception**: The universal Python pack (CS-009) requires `rich` for
> terminal output formatting. gaze-py's text output is consumed primarily by
> automated agents (the `gaze-reporter` agent), not interactive terminal users.
> Adding `rich` as a dependency provides no value for agent-consumed output and
> would increase the package footprint. This exception is documented in
> `.opencode/uf/packs/python-custom.md` as CR-006. Output is still routed
> through `click.echo()` in the CLI layer per CS-008 (never `print()`).

Output format (one line per function):
```
<relative_path>:<function_name>  complexity=N  CRAP=<value|null>  effects=<count>  strategy=<value|null>
```

Followed by a summary line:
```
Total: N functions, M in CRAPload (threshold=15.0)
```

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
| GlobalMutation | P1 | `ast.Global` statement for name N followed by assignment to N within the same function body (no implicit module-level name detection — keeps detector stateless per function) |
| WriterOutput | P1 | `.write()` called on a function parameter (injected writer pattern) |
| HTTPResponseWrite | P1 | `.write()` or attribute assignment on a parameter named `response`/`resp` |
| ChannelSend | P1 | `queue.Queue.put()`, `asyncio.Queue.put()`, `multiprocessing.Queue.put()` |
| ChannelClose | P1 | `multiprocessing.Queue.close()`, `asyncio.Queue` shutdown patterns |
| DeferredReturnMutation | P1 | Assignment in `finally:` block to a variable subsequently returned by the function (return MUST be outside the finally block) |
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
| ClosureCaptureMutation | P4 | Assignment to a `nonlocal` variable (`nonlocal x; x = ...`) (effect attributed to the **inner** nested function where `nonlocal` is declared) |

Types with no meaningful Python equivalent — defined in taxonomy, detection
always returns empty, covered by no-op tests asserting empty result:

| Type | Tier | Reason |
|---|---|---|
| WaitGroupOp | P3 | No direct equivalent; `concurrent.futures.wait()` is semantically different |
| AtomicOp | P3 | Python's GIL makes most operations implicitly atomic; no explicit atomic primitives |
| RecoverBehavior | P3 | Go's `recover()` has no Python equivalent; `try/except` is structural |
| UnsafeMutation | P4 | Direct memory manipulation via ctypes is already covered by CgoCall |
| SyncPoolOp | P4 | No Python equivalent to Go's `sync.Pool` |
