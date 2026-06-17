## Context

The O1 quality pipeline's `pair_to_targets()` uses three strategies:

1. Name convention (`test_foo → foo`) — matches 20/62 public functions
2. AST `ast.Name` call walk — adds 0 new functions (all relevant calls
   are method calls, which `_extract_call_name()` returns `None` for)
3. Unmatched — 42 functions land here

The 42 unmatched functions are currently scored with `gaze_crap: null`
and `contract_coverage_reason: "no_effects_detected"`. This is wrong
for functions with detected side effects — their correct reason is
`"no_test_coverage"`. GazeCRAP correctly remains null in both cases per
the Go gaze reference (`internal/crap/contract.go` line 148).

The realistic pairing ceiling with Astroid transitive inference is
approximately 31/62 (50%). The remaining 31 functions fall into two
structurally unreachable categories for all static analysis tools:

- 22 `visit_*` visitor methods — dispatched via
  `getattr(self, 'visit_' + node.__class__.__name__)` inside
  `ast.NodeVisitor.visit()`. Dynamic getattr dispatch cannot be
  resolved statically.
- 10 CLI click commands — tested via `CliRunner.invoke()`. The
  invoke/dispatch chain is opaque to static analysis.

After this change these 32 functions correctly show
`"no_test_coverage"` (not `"no_effects_detected"`). GazeCRAP remains
null. The correct reason is all that changes.

## Goals / Non-Goals

### Goals

- Emit `"no_test_coverage"` (not `"no_effects_detected"`) for functions
  with effects but no paired test — fixes the diagnostic inaccuracy
- Extend pairing to approximately 31/62 public functions via Astroid
  (from current 20/62) — reduces the set of `"no_test_coverage"`
  functions
- Wire quality pipeline into `gazepy crap` output for
  `contract_coverage_reason` population
- No existing tests modified
- GazeCRAP remains null for `"no_test_coverage"` functions (matches Go
  reference — `ok=false` in `BuildContractCoverageFunc`)

### Non-Goals

- Computing GazeCRAP at 0% for untested functions (contradicts Go
  reference; see D5)
- Reaching `visit_*` visitor methods or CLI `CliRunner`-tested commands
  (structural ceiling — they correctly show `"no_test_coverage"`)
- Implementing GapHints (separate change)
- AI-assisted assertion mapping (separate change)

## Decisions

### D1: Astroid as Strategy 3 only; Strategies 1 and 2 unchanged

Strategies 1 and 2 are fast and have zero dependencies. They fire first.
Strategy 3 fires only when both fail. This preserves all existing
pairing behaviour — Strategy 3 can only add new pairings.

### D2: Build Astroid graph once per assess() call

`_build_astroid_graph(test_files, src_files)` is called once at the top
of `assess()` and returns a `dict[str, set[str]]` (caller FQN → set of
callee FQNs). `_pair_astroid()` does BFS lookup — cheap per-function.
`MANAGER.clear_cache()` is called at the start of each
`_build_astroid_graph()` invocation to prevent stale data when
`assess()` is called multiple times in the same process (e.g. in tests).

**Process-global side effect**: `astroid.MANAGER` is a module-level
singleton. `clear_cache()` evicts all cached AST modules globally —
including any loaded by other tools (pylint, mypy plugins) sharing the
same Python process. This is the correct trade-off for a CLI tool where
gaze-py owns the process. Users who embed gaze-py as a library alongside
other astroid consumers (e.g. pylint) should be aware that each
`assess()` call will evict their tool's AST cache. Documented in
CHANGELOG `### Known Limitations`.

### D3: Match on name segment only; BFS non-determinism documented

Astroid returns fully-qualified names. The match extracts the short name
(last segment after `.`) and checks it against `source_names`. When
multiple production functions share a short name in different modules,
the first one reached in BFS insertion order wins. This is a known
limitation: FQN-based disambiguation is out of scope for this change.

### D4: Depth limit 5; InferenceError and AstroidBuildingError caught

BFS traversal is capped at 5 hops. `call.func.infer()` may raise
`astroid.exceptions.InferenceError` (not only yield `Uninferable`) on
complex or partially-typed call sites — this must be caught in the
iteration loop. `MANAGER.ast_from_file()` may raise
`astroid.exceptions.AstroidBuildingError` (encoding errors, unresolvable
imports, syntax errors) — this must be caught per file. Both failures
produce a partial graph, not a crash. Per-file `AstroidBuildingError`
failures are logged to stderr as warnings so callers can diagnose
incomplete pairing results.

### D5: no_test_coverage → percentage=None, gaze_crap=null (Go contract)

The Go reference is unambiguous (contract.go line 148):

> *"Return ok=false so the CRAP pipeline excludes these from GazeCRAP
> calculations (no test = no coverage data, not 0% coverage). The
> Reason is informational for display."*

`percentage=None` and `gaze_crap=null` are correct for
`"no_test_coverage"`. Computing GazeCRAP at an assumed 0% would
conflate "not measured" with "measured as zero" — the exact violation
OC-003 prohibits. No asterisk rendering or footnote is needed; the
existing `"null"` text display is correct.

### D6: _untested_reports() is a separate helper, separate list

Task 3.3 emits reports for production functions with effects that were
never the `target_function` of any test-keyed report. These are returned
as a separate `tuple[QualityReport, ...]` from a new
`_untested_reports(source_targets, seen_names, config)` helper — not
mixed into the main test-function-keyed report list. `assess()` returns
a frozen dataclass that distinguishes the two:

```python
@dataclass(frozen=True)
class AssessResult:
    reports: tuple[QualityReport, ...]    # one per test function (paired)
    untested: tuple[QualityReport, ...]   # one per unmatched prod func with effects
```

`tuple` fields match the project's convention (all other frozen
dataclasses in the codebase use `tuple[..., ...]` for sequences).

`QualityReport` for untested functions uses `test_function=""` as a
sentinel. This sentinel is explicitly documented in the `QualityReport`
docstring. Callers must handle both fields.

The `quality` CLI command shows only `.reports` (test-keyed output).
Untested functions appear only in `gazepy crap --tests` output via the
coverage map. This keeps the quality command output semantically clean:
every row corresponds to a test function that ran. The `crap` command
uses both fields to build the complete coverage map.

### D7: Astroid stderr via sys.stderr; ImportError handler is documentation

`astroid` is a required production dependency — `ImportError` cannot
fire in a correctly installed environment. The import is placed at
module level in `pairing.py` (standard practice for required deps).
The `ImportError` path in `_build_astroid_graph()` is retained as
future-proofing commentary only (in a code comment, not live code) for
the hypothetical case where astroid becomes optional in a future
change.

Stderr messages in `_build_astroid_graph()` use `sys.stderr.write()`
directly (not `click.echo()`) because `quality/pairing.py` is a library
module and must not import Click. This keeps the library/CLI boundary
clean per D9.

### D8: Project root for FQN computation

"Project root" for FQN derivation in `_pair_astroid()` is defined as
the **common ancestor directory of `test_func.filename` and the first
source file passed to `_build_astroid_graph()`**. Concretely: the
directory that contains both `tests/` and `src/` — found by walking up
from `test_func.filename` until a directory contains `pyproject.toml`
or `setup.py`. If no such marker is found, fall back to the parent of
the test file. This is the same root the Astroid MANAGER uses when
loading modules from the editable install.

FQN computation: `root.relative_to(project_root)` with path separators
replaced by `.`, then append `.test_func.name`. If the path starts with
`tests/` or `src/`, strip the leading component to match Astroid's
module naming.

### D9: build_contract_coverage_map() belongs in quality/pipeline.py

`build_contract_coverage_map()` (public, no underscore) is domain
logic, not CLI logic. Placing it in `quality/pipeline.py` makes it
importable by library users without pulling in Click. The `crap` CLI
function imports it from there.

### D10: Double detect_and_classify() and include_unexported gap

`_run_crap()` calls `detect_and_classify()` with `include_unexported=True`
(all functions). `build_contract_coverage_map()` calls `assess()` which
calls `detect_and_classify()` with `include_unexported=False` (public
functions only, the default). Two consequences:

1. **Double analysis cost**: With `--tests`, source is analysed twice.
   On gaze-py this adds approximately 0.5s. Deduplication is deferred.

2. **Known Limitation: private functions never receive contract coverage
   enrichment in `gazepy crap --tests`.** Every private (underscore-
   prefixed) function will show `contract_coverage_reason: null` in
   crap JSON output even if it has tests. This is documented in the
   CHANGELOG as a known limitation. The fix (passing `include_unexported`
   through `build_contract_coverage_map()`) is a follow-up change.

Both consequences are documented in `results.md` after measurement.

### D11: astroid>=3.0, no upper bound; CI verified at 4.1.2

Production floor is `>=3.0`. CI always runs against the latest
available (currently 4.1.2 — uv resolves to the newest compatible
version). The floor is asserted stable but CI-verified only at 4.x.

Key APIs used (`BoundMethod.qname()`, `FunctionDef.qname()`,
`MANAGER.ast_from_file()`, `MANAGER.clear_cache()`, `InferenceError`,
`AstroidBuildingError`, `Uninferable`) are confirmed present in both
3.3.x and 4.1.2. `BoundMethod.qname()` is used directly (cleaner than
`._proxied`; works in both versions). No `<4` cap — users with pylint
at 4.x (which requires astroid 4.x) receive a compatible install.

### D12: Version bump

This change adds a required dependency, a new inference method value
(`"call_graph_transitive"`), a new reason code (`"no_test_coverage"`),
changes the `assess()` return type from `list[QualityReport]` to
`AssessResult`, and adds a `--tests` option to `crap`. Per the
Conventional Commits / semantic versioning policy this is a MINOR
version bump (new capability, no removed fields, existing consumers
continue to work if they only read `reports` from `AssessResult` which
has the same shape as the old list).

## Risks / Trade-offs

**Risk: Astroid inference produces incorrect pairings.** Strategy 3 can
only add pairings when Strategies 1 and 2 find nothing. A wrong pairing
produces an incorrect `contract_coverage_reason`, but existing pairing
tests catch regressions in Strategies 1 and 2.

**Risk: Astroid slows down `gazepy quality`.** Benchmark target ≤3s on
gaze-py itself (current baseline ~1.5s). `MANAGER.clear_cache()` trades
correctness for a modest repeated-load cost. Recorded in `results.md`.
If wall time exceeds 6s on gaze-py after implementation, Strategy 3
must become opt-in via a `--transitive-inference` flag (added as a
follow-up change, not blocked on this one).

**Risk: BFS is non-deterministic for same-short-name collisions.** D3
documents this. Determinism within a single run is guaranteed by dict
insertion order (Python 3.7+). Across astroid versions, traversal order
may differ, changing which production function wins for collisions.
Acceptable for a Strategy 3 (last-resort) match.

**Risk: Double detect_and_classify() cost.** D10 documents this.
Acceptable for this change; deduplication is deferred.

**Risk: LGPL-2.1 Astroid dependency.** LGPL-2.1 permits library use in
an Apache 2.0 project without relicensing. Noted for legal review.
