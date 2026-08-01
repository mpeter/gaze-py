## Why

gaze-py applies **file-level** line coverage to every function in a file
instead of resolving coverage **per function**. Every function in `foo.py`
receives `foo.py`'s aggregate `percent_covered`, so CRAP
(`complexity² × (1 - coverage)³ + complexity`) is computed from a number that
does not describe the function being scored.

Verified empirically: across 191 files in a consumer project, **zero** files
had more than one distinct `line_coverage` value among their functions.

This contradicts three independent authorities:

1. **The Go reference** — `internal/crap/coverage.go:41` `ParseCoverProfile`
   "computes per-function coverage percentages"; `funcCoverage()` at `:180`
   intersects coverage blocks with each function's `startLine`/`endLine`/
   `endCol`; `buildCoverMap` keys on `(file, StartLine)`.
2. **The porting contract** — `docs/porting/requirements.md:73`: "Line coverage
   per function (percentage, 0-100)."
3. **gaze-py's own spec** — `openspec/specs/crap-scoring/spec.md:19-20` defines
   coverage as belonging to "the function"; `:306` defines `avg_line_coverage`
   as "Mean line coverage across functions".

Per AGENTS.md — "gaze-py is a port, not an independent tool... Any element that
contradicts a porting contract MUST be revised — the contract wins" — this is a
**bug fix**, not a behavior change. Nothing committed authorizes file-level
attribution.

Measured impact on a consumer project: reported crapload **24** vs true crapload
**84**. 39 wholly-untested functions are concealed by well-covered file-mates
(worst: a command function with true CRAP 132 at 0% coverage, reported as
passing). Conversely one individually 100%-covered function is falsely flagged
with CRAP 18.3.

## What Changes

- `FunctionTarget` gains an `end_line` field so a function's line extent is
  known to the scorer. **Not serialized** — the JSON formatter reads only
  `ft.line` (`json_formatter.py:183`), so Go schema compatibility is preserved.
- The coverage loader carries per-file `executed_lines` / `missing_lines`
  instead of collapsing each file to a single `percent_covered` float.
- Coverage resolution computes each function's own covered-line fraction from
  the lines that function owns, using two edge rules (A and B below) that were
  derived empirically and validated at 1455/1455 functions against coverage.py's
  own `functions` map.
- Files whose coverage entry lacks the line arrays **degrade to file-level**
  coverage — the previous behavior, now an explicit and documented fallback for
  degraded input rather than the universal path. Real coverage.py output always
  carries the line arrays.
- Zero-statement function bodies (e.g. a decorator-only Click group whose body
  is only a docstring) resolve to **1.0**, matching coverage.py's own reporting.

`_compute_avg_line_coverage` needs no logic change: it already averages
per-target `score.line_coverage`, which becomes per-function automatically.
This matches Go `analyze.go:420` (`totalCov / n` over scored functions).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `crap-scoring`: adds an explicit normative requirement that line coverage
  resolves **per function**, specifying the two line-ownership rules, the
  file-level degradation fallback, and the zero-statement case.

### Removed Capabilities

(none)

## Impact

- `src/gaze_py/taxonomy/models.py` — `FunctionTarget.end_line` field + docstring
- `src/gaze_py/analysis/detector.py` — two `FunctionTarget(...)` construction
  sites (`<module>` sentinel at `:2216`, real target at `:2319`)
- `src/gaze_py/cli/main.py` — `_load_coverage_json`, `_resolve_line_coverage`,
  and the `coverage_data` type annotation at its six other mention sites
- `tests/testdata/coverage_sample.json` + new per-function fixtures
- Docs: `docs/getting-started/quickstart.md`,
  `docs/reference/cli/crap.md`, `docs/reference/cli/report.md`
- **Consumer impact**: reported `crapload` and `avg_line_coverage` will change
  for any project whose files mix covered and uncovered functions. Consumers
  pinning gaze-py must regenerate their baselines deliberately.
- **gaze-py's own crapload moves 5 → 9** and `avg_line_coverage` 0.9557 → 0.9390
  (measured on identical coverage input, pre-fix in a clean worktree at `main`).
  All five previously flagged functions remain flagged; four are added. The four
  were concealed behind well-covered file-mates and are genuinely under-tested,
  each confirmed against coverage.py's own per-function figures:

  | Function | True coverage | Containing file |
  |---|---|---|
  | `cli/main.py::_enforce_min_contract_coverage_from_result` | 16.67% | 89.47% |
  | `cli/main.py::_acquire_coverage` | 16.67% | 89.47% |
  | `analysis/detector.py::_check_nonlocal_assignment` | 0.00% | 94.91% |
  | `report/text_formatter.py::comparison_to_text` | 71.79% | 80.30% |

  This repo enforces no crapload gate (only `--cov-fail-under=85`, which passes
  at 95.46%), so nothing protected is breached. Closing these gaps is followup
  work, deliberately not bundled here — this change must not mix a measurement
  correction with the test-writing it exposes.
