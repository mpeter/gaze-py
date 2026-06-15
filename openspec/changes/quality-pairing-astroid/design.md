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
as a separate `list[QualityReport]` from a new
`_untested_reports(source_targets, seen_names, config)` helper — not
mixed into the main test-function-keyed report list. `assess()` returns
a named tuple or structured result that distinguishes the two:

```python
@dataclass(frozen=True)
class AssessResult:
    reports: list[QualityReport]       # one per test function
    untested: list[QualityReport]      # one per unmatched prod func
```

`QualityReport` for untested functions uses `test_function=""` as a
sentinel. This sentinel is explicitly documented in the `QualityReport`
docstring. Callers must handle both lists.

The `quality` CLI command merges both for display. The `crap` command
uses both to build the coverage map.

### D7: Astroid import is defensive; warnings via stderr

`astroid` is imported inside `_build_astroid_graph()`, not at module
level. On `ImportError`, emit a message to stderr via
`click.echo("warning: astroid not available — Strategy 3 disabled",
err=True)` (not `warnings.warn` — suppressible by user code) and return
`{}`. With an empty graph, Strategy 3 never fires; the pipeline
continues normally as before.

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

### D9: _build_contract_coverage_map() belongs in quality/pipeline.py

This function is domain logic, not CLI logic. Placing it in
`quality/pipeline.py` makes it importable by library users without
pulling in Click. The `crap` CLI function imports it from there.

### D10: Double detect_and_classify() acknowledged as tech debt

`_run_crap()` calls `detect_and_classify()` independently, and
`_build_contract_coverage_map()` calls `assess()` which calls it again.
With `--tests`, the source is analysed twice. On gaze-py itself this
adds approximately 0.5s. Deduplication (sharing the `source_targets`
list) is deferred — the two call sites have different options
(`include_unexported` differs) and merging them requires careful
parameter threading. Documented in `results.md` after measurement.

### D11: astroid>=3.0, no upper bound

Tested against 4.1.2. Key APIs used (`BoundMethod.qname()`,
`FunctionDef.qname()`, `MANAGER.ast_from_file()`, `MANAGER.clear_cache()`,
`InferenceError`, `AstroidBuildingError`, `Uninferable`) are stable
across 3.x and 4.x. BoundMethod._proxied exists as an instance
attribute in both versions but `BoundMethod.qname()` is the cleaner API
and is used directly. No `<4` cap — users with pylint at 4.x (which
requires astroid 4.x) receive a compatible install.

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
