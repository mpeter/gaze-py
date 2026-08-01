# Design: Per-Function Line Coverage Attribution

## Problem

CRAP is a per-function metric. gaze-py feeds it a per-file number. The scorer,
the summary, and the baseline comparator are all correct; the input is wrong.

## Which lines does a function own?

Given the AST node for a function, the naive answer is
`[node.lineno, node.end_lineno]`. Both endpoints need correcting, and both
corrections were derived empirically rather than assumed.

### Rule A — start at `node.body[0].lineno`, not `node.lineno`

Exclude the function's own `def` line and its decorator lines from the range it
owns.

The `def` statement (and each decorator) **executes at import time**, not when
the function is called. coverage.py therefore records those lines as executed
for any module that gets imported at all. Including them in the function's own
range makes 0% arithmetically unreachable: a first prototype reported a
never-called function as **3.7%** instead of **0%**, because the `def` line it
wrongly owned was marked executed.

This is also what the Go reference does implicitly — Go's `funcCoverage`
intersects against coverage *blocks*, which begin after the function signature.

### Rule B — when subtracting a nested function, subtract from `nested.body[0].lineno`

Nested functions (closures, decorated inner helpers) are scored as independent
targets — gaze's complexity metric does not recurse into nested `def`s. So a
parent's owned range must have each nested function's extent removed, or the
parent would be credited (or penalized) for its children's coverage.

The subtraction must start at the nested function's **body**, not its `def`
line: the `def` statement itself executes in the *parent's* scope, so the parent
legitimately owns it. This is exactly what coverage.py does.

**This rule is not cosmetic.** Out-of-band validation against coverage.py's own
`functions` map across the `fieldkit-cmd` consumer project (not reproducible
from this repo — that project is not vendorable here):

| | Functions matching coverage.py |
|---|---|
| With rules A + B | **1455 / 1455** |
| With rule A only | 1400 / 1455 |

The 55 mismatches without rule B were systematic off-by-N errors
(e.g. `declare_write` counted 4 statements instead of 5; `make_lazy_group`
2 instead of 4) — every one a function containing nested definitions.

The **in-repo** acceptance test is `tests/test_coverage_ownership.py`, which
runs the same comparison against a committed coverage.py report over
`tests/testdata/analysis/coverage_ownership.py`. That fixture is small (8
function entries) but deliberately covers every case the rules distinguish:
a never-called function, a partially covered one, a parent with a covered
nested function, a parent with an *uncovered* nested function, and a
docstring-only body. Both rules are mutation-verified — reverting rule A fails
6 tests, reverting rule B fails 2, including the statement-set comparison.

The same comparison was also run over gaze-py's own source at 256/256 exact
set match, with the end-to-end resolver reproducing coverage.py's per-function
percentages 256/256 (198/256 without rule A, and 0 of the 4 truly-0% functions
reported as 0%).

## Zero-statement functions

A body consisting only of a docstring has no statements to attribute:

```python
@click.group()
def cli() -> None:
    """Manage things."""
```

Three candidate answers were considered:

- **0.0** — mirrors Go's `funcCoverage` (`total == 0 => 0.0`). Rejected: it
  reports a false deficit, dragging `avg_line_coverage` down with functions
  that are trivially and completely covered.
- **None** — the strictest reading of OC-003 "null not zero". Rejected: it
  claims the value is *unknown*, but it is known and knowable. Coverage ran.
- **1.0** — what coverage.py itself reports. **Chosen.** Vacuous truth: nothing
  to cover, nothing missed. Users cross-checking `gazepy` against
  `coverage report` see consistent numbers.

The divergence from Go is deliberate and narrow. The porting contract specifies
*per-function coverage*; it does not specify this edge case, and Go's answer is
wrong for Python's execution model.

**This choice cannot affect any gate.** A zero-statement body has cyclomatic
complexity 1 by construction, so CRAP is between 1.0 (at 1.0 coverage) and 2.0
(at 0.0 coverage) — it can never reach the 15.0 threshold under any choice.
Only the reported `avg_line_coverage` moves.

## Two ways to intersect with nothing

An empty intersection between a function's owned lines and the report's line
arrays has two causes that must not be conflated:

1. **The function owns no lines.** A docstring-only body. Genuinely, vacuously
   covered — `1.0` is correct.
2. **The function owns lines the report says nothing about.** The report
   predates the source, or was generated against different code. The function
   is *unmeasured*, and `1.0` would be a fabrication.

The first draft of this change returned `1.0` for both, on the reasoning that
only case 1 could produce an empty set. That was wrong, and dangerously so: for
a stale report, a brand-new untested function with complexity 20 scored
CRAP 20.0 instead of 420.0 — a perfect score, silently passing `--max-crapload`.
Note this is *worse* than the file-level behavior it replaced, which would at
least have returned a number derived from real measurements (20.4).

The two are separated at the source. `_fn_owned_lines` returns the empty set for
a docstring-only body, so ownership itself carries the distinction:
`not owned` means case 1, while an empty intersection over non-empty ownership
means case 2 and degrades to the file aggregate.

A naive guard — treating any empty intersection as degraded — would regress
case 1, because a docstring line *is* owned under a line-range view but is not a
statement. Hence the detector-side signal rather than a resolver-side heuristic.

## Degraded input: missing line arrays

Real coverage.py JSON always emits `executed_lines` and `missing_lines`
per file. Only hand-built fixtures omit them.

When a file entry lacks both arrays, that file falls back to `percent_covered`
applied file-wide — the pre-fix behavior. This is chosen over a hard error
because a hard error would break consumers hand-feeding minimal JSON in a patch
release, and over silence-with-no-policy because the fallback is now a written,
tested contract rather than the accidental universal path.

The tradeoff accepted: a minimal hand-built JSON still yields file-level
numbers. Mitigated by documenting the requirement and by the fact that the
supported input format is coverage.py's own report.

## Path resolution is unchanged

`_resolve_line_coverage`'s three-key lookup (root-relative → cwd-relative →
filename-only) is preserved **verbatim**. Only the value type behind those keys
and the derivation of the final fraction change. The lookup order has its own
tests and its own subtle cwd-skip branch; this change must not disturb them.

## Where ownership is computed

Rules A and B both need the AST: rule A needs each function's `body[0].lineno`,
and rule B needs its nested definitions' extents. A `FunctionTarget` carrying
only `line`/`end_line` cannot express either — the resolver would have to infer
nesting from line containment across the file's target set, and special-case the
`<module>` sentinel, which spans everything.

So ownership is computed in `detector.py`, where the AST is already in hand, and
the resulting line set is stored on the target as `owned_lines`. The resolver
then only intersects. This keeps the rules next to the syntax they describe,
needs one field rather than two, and removes the containment inference entirely.

`owned_lines` is `frozenset[int] | None`, defaulted to `None`, and is not
serialized — `json_formatter.py` builds `FunctionTarget` output manually and
emits only `line` via `location`, so Go schema compatibility is unaffected.
(`dataclasses.asdict()` is used on `Summary` and `SideEffect`, not on
`FunctionTarget`.) It joins `docstring`, `class_bases`, and `return_type_hint`
as documented analysis-only context.

A defaulted field rather than a required one is deliberate: `FunctionTarget(` is
constructed at 26 sites across the test suite, none of which care about
coverage. Requiring the field would force 26 unrelated edits, and dataclass
ordering forbids a required field after the existing defaults block anyway. The
`None` case is not an extra code path — it collapses into the same file-level
fallback the degraded-input policy already requires. `test_detector_populates_
owned_lines_for_every_function` guards that fallback from quietly becoming the
normal path.

## Call-site shape

`main.py`'s scoring loop is *already* per-target, so threading the function
through is a one-line change:

```python
for target in targets:
    abs_file = root / target.file_path
    line_coverage_frac = _resolve_line_coverage(abs_file, root, coverage_data, target)
    _score_target(target, line_coverage_frac=line_coverage_frac, config=config)
```

## Known adjacent seam — not fixed here

`crapload` counts `crap >= 15.0` (inclusive, `crap/scorer.py:66`) but the
baseline comparator's `new_violations` check uses `crap > 15.0` (strictly
greater, `crap/compare.py:415`). A function at exactly 15.0 counts toward
crapload but is not a new violation. This asymmetry is real and predates this
change; correcting per-function attribution will make it observable more often
(complexity-15 functions at 100% coverage land exactly on 15.0). Deliberately
left alone — it is a separate concern and mixing it in would confound the
measurement this change is meant to correct. Flagged for a follow-up change.

Likewise `compare.py:61`'s regression epsilon of `0.0` means any positive delta
is a regression. Unchanged, but worth consumers knowing: post-fix, a change that
lowers one function's coverage no longer regresses its file-mates — which is an
improvement in signal quality.
