## Context

The O1 quality pipeline's `pair_to_targets()` uses three strategies:

1. Name convention (`test_foo → foo`) — matches 20/62 public functions
2. AST `ast.Name` call walk — adds 0 new functions (all relevant calls
   are method calls, which `_extract_call_name()` returns `None` for)
3. Unmatched — 42 functions land here

The 42 unmatched functions are currently scored with `gaze_crap: null`
and `contract_coverage_reason: "no_effects_detected"`. This is incorrect
for any function that has detected side effects. Per the Go gaze
reference (`internal/crap/contract.go`), the correct behaviour when
effects exist but no test targets the function is:
- reason: `"no_test_coverage"`
- percentage: `0.0` (not `null`)
- GazeCRAP: `complexity² + complexity` (at 0% contract coverage)

The realistic pairing ceiling with Astroid transitive inference is
approximately 31/62 (50%). The remaining 31 functions fall into two
structurally unreachable categories:
- 22 `visit_*` visitor methods — dispatched via
  `getattr(self, 'visit_' + node.__class__.__name__)` in
  `ast.NodeVisitor.visit()`. No static analysis tool can resolve this.
- 10 CLI click commands — tested via `CliRunner.invoke()`. Static
  analysis cannot follow through the invoke/dispatch chain.

These 32 functions will correctly receive `"no_test_coverage"` after
this change — a real GazeCRAP score at 0% contract coverage — rather
than the incorrect `"no_effects_detected"` they currently show.

## Goals / Non-Goals

### Goals

- Extend pairing to approximately 31/62 public functions via Astroid
  transitive inference (from current 20/62)
- Correctly emit `"no_test_coverage"` with `percentage=0.0` and
  computable GazeCRAP for all functions with effects but no paired test
- Wire quality pipeline into `gazepy crap` output
- No existing tests modified

### Non-Goals

- Reaching `visit_*` visitor methods (dynamic `getattr` dispatch —
  structural ceiling for all static analysis tools; they correctly
  receive `"no_test_coverage"` after this change)
- Reaching CLI commands tested via `CliRunner.invoke()` (same ceiling)
- Implementing GapHints (separate change)
- AI-assisted assertion mapping (separate change)

## Decisions

### D1: Astroid as Strategy 3 only; Strategies 1 and 2 unchanged

Strategies 1 (name convention) and 2 (ast.Name call walk) are fast and
have zero dependencies. They fire first. Strategy 3 fires only when both
fail. This preserves existing pairing behaviour entirely — Strategy 3
can only add new pairings, not remove or alter existing ones.

### D2: Build Astroid graph once per assess() call, query per test function

`_build_astroid_graph(test_files, src_files)` is called once at the top
of `assess()` and returns a `dict[str, set[str]]` mapping caller fully-
qualified name (FQN) to set of callee FQNs. `_pair_astroid()` then does
a BFS lookup from the test function's FQN — cheap per-function cost.
This avoids rebuilding the inference graph for every test function.

### D3: Match on name segment only, not full FQN

The pairing system works with simple function names (`classify`, not
`gaze_py.classify.engine.ClassificationEngine.classify`). Astroid
returns FQNs; the match extracts the last segment (everything after the
final `.`) and checks it against `source_names`. When multiple
production functions share a short name, the first one reached in BFS
order wins — consistent with Strategy 2's first-match behaviour.

### D4: Depth limit 5; Uninferable silently skipped

BFS traversal is capped at 5 hops to prevent runaway traversal on
highly-connected codebases. Astroid inference on opaque callables (e.g.
`getattr(self, name)()`, function-valued parameters) returns the
`Uninferable` sentinel. These are silently skipped with `continue` — no
error, no warning, no partial result recorded.

### D5: no_test_coverage emits percentage=0.0; text renders with asterisk

When effects exist but no test targets a function, `percentage=0.0`
is the correct value (not `None`). A function with zero assertions
covering its contractual effects has 0% contract coverage — a real,
computable measurement.

`_score_target()` already handles `quality_result.percentage == 0.0`
correctly (it acts on any non-None percentage) — no change needed there.

**Text rendering**: when `contract_coverage_reason == "no_test_coverage"`,
GazeCRAP is displayed with a `*` suffix (e.g. `2652.0*`) and a footnote
is appended below the table:
```
* GazeCRAP computed at 0% contract coverage — no test targets this function
```
This distinguishes "measured at zero because untested" from "measured at
a specific percentage because tested".

**JSON rendering**: raw float with `contract_coverage_reason:
"no_test_coverage"`. No decoration — the reason field carries the
context for programmatic consumers.

### D6: crap command integrates quality pipeline via auto-discovery

`_build_contract_coverage_map(src_path, tests_path, config)` runs
`assess()` and produces a `dict[str, ContractCoverageResult]` keyed by
function name. `_run_crap()` calls this when a tests path is available
(auto-discovered using the same logic as the `quality` command, or via
the new `--tests` option). If no tests path is found, GazeCRAP remains
null — OC-003 compliant (capability did not run).

The best coverage result per function name is selected when multiple
test functions pair to the same production function. Functions with
effects that appear in zero quality reports receive
`percentage=0.0, reason="no_test_coverage"`.

### D7: Astroid import is defensive

`astroid` is imported inside `_build_astroid_graph()`, not at module
level. If the import fails at runtime (e.g. installation error),
`_build_astroid_graph()` logs a warning to stderr and returns `{}`.
With an empty graph, `_pair_astroid()` immediately returns `None` and
the test function falls through to "unmatched" — exactly as before.
The pipeline continues normally.

## Risks / Trade-offs

**Risk: Astroid inference produces incorrect pairings.** Strategy 3
only adds pairings when Strategies 1 and 2 find nothing. A wrong
pairing from Strategy 3 produces an incorrect GazeCRAP for that
function, but cannot displace a correct pairing from an earlier
strategy. Existing pairing tests catch any regression in Strategies 1
and 2.

**Risk: Astroid slows down `gazepy quality` on large codebases.**
Benchmark target: ≤2× wall time vs. current on gaze-py itself (current
baseline ~1.5s; target ≤3s). Graph is built once per `assess()` call.
Recorded in `results.md` (task 6.1).

**Risk: `visit_*` methods receive a very high GazeCRAP (e.g. 2652 for
`visit_Call`, complexity 51).** This is correct and expected. `visit_Call`
has 84% line coverage and no contract coverage — it genuinely is at risk.
GazeCRAPload will increase substantially on first run after this change.
This is accurate signal, not noise.

**Risk: LGPL-2.1 Astroid dependency.** LGPL-2.1 permits library use in
an Apache 2.0 project without relicensing. gaze-py imports Astroid but
does not distribute a modified copy. No conflict. Noted for any future
legal review.
