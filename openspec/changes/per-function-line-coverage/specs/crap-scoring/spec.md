## ADDED Requirements

### Requirement: Line coverage resolves per function

Line coverage supplied to the CRAP formula MUST describe the individual
function being scored, not the file that contains it. Two functions in the same
file with different coverage MUST receive different `line_coverage` values.

This restates the porting contract (`requirements.md:73`, "Line coverage per
function") and matches the Go reference `funcCoverage()`
(`internal/crap/coverage.go:180`), which intersects coverage blocks with each
function's own line extent.

#### Scenario: Two functions in one file receive distinct coverage
- **GIVEN** a file containing `covered()` (fully exercised by tests) and
  `uncovered()` (never called)
- **AND** a coverage.py JSON report carrying `executed_lines` and
  `missing_lines` for that file
- **WHEN** `gazepy crap` scores the file
- **THEN** `covered()` has `line_coverage` 1.0 and `uncovered()` has
  `line_coverage` 0.0
- **AND** their CRAP scores differ accordingly

#### Scenario: A fully covered function is not penalized by an uncovered file-mate
- **GIVEN** a file whose aggregate coverage is 50%
- **AND** one function within it that is individually 100% covered
- **WHEN** CRAP is computed for that function
- **THEN** its CRAP equals its complexity (the cubic term vanishes)

#### Scenario: An uncovered function is not concealed by a covered file-mate
- **GIVEN** a file whose aggregate coverage is 90%
- **AND** one function within it that is never executed
- **WHEN** CRAP is computed for that function
- **THEN** its `line_coverage` is 0.0 and its CRAP is `complexity² + complexity`

### Requirement: Function line ownership excludes the def and decorator lines

The set of lines a function owns MUST begin at the first line of its body
(`node.body[0].lineno`), excluding its `def` line and any decorator lines.

Those statements execute at import time rather than on call, so coverage.py
records them as executed for any imported module. Including them makes 0%
coverage arithmetically unreachable for a never-called function.

#### Scenario: A never-called function reports exactly 0%
- **GIVEN** a module that is imported but contains a function never invoked
- **WHEN** that function's line coverage is resolved
- **THEN** the result is exactly 0.0, not a small positive fraction

### Requirement: Nested function extents are subtracted from the parent, keeping the nested def line

When a function contains nested function definitions (`def` or `async def`),
each nested definition's line extent MUST be removed from the parent's owned
lines. The removal MUST begin at the nested definition's **body**
(`nested.body[0].lineno`), so the nested `def` line itself remains owned by the
parent — that statement executes in the parent's scope.

Nested functions are scored as independent targets, so without this subtraction
a parent would be credited or penalized for its children's coverage.

Nested **class** bodies MUST NOT be subtracted. A class body executes in the
enclosing scope at definition time, so its statements belong to the enclosing
function. The class's methods are still subtracted, because each is itself a
nested function definition and an independently scored target.

#### Scenario: Statement counts match coverage.py exactly
- **GIVEN** a project analyzed with a coverage.py JSON report that includes the
  per-file `functions` map
- **WHEN** each function's owned-line count is computed under these rules
- **THEN** every function's count equals coverage.py's own count for that
  function, with no mismatches

#### Scenario: The nested def line belongs to the parent
- **GIVEN** a parent function whose body contains a nested `def`
- **WHEN** the parent's owned lines are computed
- **THEN** the nested `def` line is included in the parent's range
- **AND** every line of the nested function's body is excluded from it

### Requirement: Zero-statement function bodies resolve to full coverage

A function whose body contains no executable statements — for example a body
consisting only of a docstring — MUST resolve to a line coverage of `1.0`.

This matches coverage.py, which reports such a function as fully covered.
It diverges deliberately from Go's `funcCoverage()`, which returns `0.0` when
the statement total is zero; that answer misreports a trivially complete
function as a total deficit under Python's execution model.

Such a function has cyclomatic complexity 1 by construction, so its CRAP is
bounded by 2.0 and cannot reach the flagging threshold under any choice. Only
`avg_line_coverage` is affected.

#### Scenario: A docstring-only body is fully covered
- **GIVEN** a decorated group function whose body is only a docstring
- **WHEN** its line coverage is resolved
- **THEN** the result is 1.0
- **AND** it does not appear in the crapload

### Requirement: A report that describes none of a function's lines MUST NOT infer full coverage

When a function owns at least one line, but the coverage report accounts for
none of those lines in either `executed_lines` or `missing_lines`, the function
is **unmeasured** — not covered. It MUST fall back to the file's aggregate
`percent_covered`, never to `1.0`.

This case arises whenever a report predates its source: a file grew, or the
artifact was generated against different code. Inferring full coverage from
that silence would award a brand-new, wholly untested function a CRAP equal to
its complexity on the path that feeds `--max-crapload`. A complexity-20
function would score 20.0 instead of 420.0 and pass every gate silently.

This is distinct from a function that owns **no** lines, which is genuinely
vacuously covered. The two MUST be distinguishable: a body with no executable
statements owns the empty set, so an empty intersection alone cannot be read as
full coverage.

#### Scenario: A function beyond the report's recorded lines is not scored as covered
- **GIVEN** a coverage report whose recorded lines stop at line 20
- **AND** an untested function occupying lines 101-120 of that file
- **WHEN** its coverage is resolved
- **THEN** the result is the file's aggregate coverage, not 1.0

#### Scenario: A docstring-only body still resolves to full coverage
- **GIVEN** a function whose body is only a docstring
- **WHEN** its coverage is resolved
- **THEN** the result is 1.0, distinguished from the unmeasured case by its
  owning no lines at all

### Requirement: Malformed line arrays degrade rather than read as empty

A line array that is present and non-empty but yields no usable line numbers —
strings, nulls, or objects instead of integers — MUST be treated as a degraded
entry, exactly as an absent array is.

Reading it as an empty set would assert that the file contains no statements,
scoring every function in it as fully covered.

Booleans MUST NOT be accepted as line numbers. Python evaluates
`isinstance(True, int)` as true and `frozenset({True}) == {1}`, so an
unfiltered boolean would silently masquerade as line 1.

#### Scenario: An array of non-integers is degraded
- **GIVEN** a file entry whose `executed_lines` is `["1", "2"]`
- **WHEN** functions in that file are scored
- **THEN** the entry is treated as degraded and file-level coverage is used

#### Scenario: Booleans are rejected as line numbers
- **GIVEN** a line array containing `true` or `false`
- **WHEN** it is parsed
- **THEN** those values contribute no line numbers

### Requirement: Coverage entries lacking line arrays degrade to file-level

When a file's entry in the coverage report provides neither `executed_lines`
nor `missing_lines`, every function in that file MUST fall back to the file's
`percent_covered`.

Coverage.py's own JSON output always emits both arrays; this fallback exists
for hand-constructed or degraded input. It is the documented exception, not the
normal path.

#### Scenario: Summary-only entry falls back to file-level coverage
- **GIVEN** a coverage JSON whose file entry contains only
  `{"summary": {"percent_covered": 80.0}}`
- **WHEN** functions in that file are scored
- **THEN** each receives a `line_coverage` of 0.8

#### Scenario: Line arrays take precedence when present
- **GIVEN** a coverage JSON file entry containing both a `summary` and
  `executed_lines`/`missing_lines`
- **WHEN** functions in that file are scored
- **THEN** coverage is computed from the line arrays and the summary
  `percent_covered` is not used

### Requirement: Path resolution order is unchanged

Resolving a source file to its coverage entry MUST continue to try three keys
in order: root-relative, then cwd-relative, then filename-only; and MUST return
`None` when no key matches. Per-function attribution changes only the value
behind a matched key, never which key matches.

#### Scenario: Unmatched file yields null coverage
- **GIVEN** a coverage report containing no key matching a source file under
  any of the three forms
- **WHEN** coverage is resolved for a function in that file
- **THEN** the result is `None` and its CRAP is `None` per OC-003

## MODIFIED Requirements

### Requirement: Summary Aggregates

The analysis summary MUST include the following aggregate fields:

| Field | Type | Description |
|-------|------|-------------|
| `function_count` | int | Total number of analyzed functions |
| `crapload` | int or None | Count of functions with CRAP >= threshold |
| `gaze_crapload` | int or None | Count of functions with GazeCRAP >= threshold; null when O1 not run |
| `avg_line_coverage` | float or None | Mean **per-function** line coverage across functions with non-null coverage |
| `avg_contract_coverage` | float or None | Mean contract coverage; null when O1 not run |
| `quadrant_counts` | dict or None | Count of functions per quadrant label; null when O1 not run |
| `fix_strategy_counts` | dict or None | Count of functions per fix strategy; null when CRAP not computed |
| `recommended_actions` | list or None | Prioritized action list; null when CRAP not computed |
| `crap_threshold` | float | Always non-null — from GazeConfig |
| `gaze_crap_threshold` | float | Always non-null — from GazeConfig |

`avg_line_coverage` is the unweighted mean over scored functions, matching Go
`analyze.go:420` (`totalCov / n`). It is **not** the mean of file coverages and
**not** a line-weighted project total, so it may differ from the headline figure
reported by `coverage report`.

#### Scenario: crap_threshold always present
- **WHEN** any analysis result is produced
- **THEN** `crap_threshold` is a non-null float in the summary

#### Scenario: quadrant_counts null without O1
- **WHEN** O1 has not run
- **THEN** `quadrant_counts` is `None` in the summary

#### Scenario: avg_line_coverage averages functions, not files
- **GIVEN** a file with one fully covered function and three uncovered ones
- **WHEN** the summary is built
- **THEN** `avg_line_coverage` is 0.25, regardless of the file's own
  `percent_covered`
