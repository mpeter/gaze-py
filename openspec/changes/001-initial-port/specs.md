# Delta Specs — Change 001: Initial Port

## ADDED Requirements

### Requirement: EC-001 Tier Membership

The implementation MUST define exactly 38 `SideEffectType` enum values assigned
to exactly 5 tiers (P0–P4) with counts: P0=5, P1=8, P2=10, P3=9, P4=6.
Tier assignments MUST NOT be configurable.

> **Note on porting contract inconsistency**: Both `contracts.md` EC-001 and
> `taxonomy-reference.md` state "37 effect types" in their headers, but the
> actual enumerated lists contain 38 types (5+8+10+9+6=38). The `contracts.md`
> P4 count column says "5" while listing 6 type names. The canonical count is
> determined by enumeration: **38 types, P4=6**. Tests MUST assert 38 total
> members and P4=6. The "37" in the contract headers is a documentation bug
> that will be reported to the Go gaze maintainers.

#### Scenario: All 38 types present
- **GIVEN** the `SideEffectType` enum is imported
- **WHEN** all members are enumerated
- **THEN** exactly 38 members exist with the names specified in taxonomy-reference.md

#### Scenario: Tier counts correct
- **GIVEN** the `TIER_MAP` mapping from `SideEffectType` to `Tier`
- **WHEN** members are grouped by tier
- **THEN** P0 has 5, P1 has 8, P2 has 10, P3 has 9, P4 has 6 members

---

### Requirement: EC-002 P0 Zero Tolerance

The detector MUST detect all 5 P0 effect types with zero false negatives and
zero false positives on the provided testdata fixtures.

#### Scenario: ReturnValue detected — non-None return
- **GIVEN** a Python function with a `return <expr>` statement where expr is
  not the literal `None`
- **WHEN** the detector runs on that function
- **THEN** a `ReturnValue` effect is present in the result

#### Scenario: ReturnValue detected — annotation exception
- **GIVEN** a Python function annotated `-> Item | None` with body `return None`
- **WHEN** the detector runs
- **THEN** a `ReturnValue` effect is present (annotation signals None is meaningful)

#### Scenario: Explicit return None without annotation is NOT a ReturnValue
- **GIVEN** a Python function with `return None` and no return annotation
- **WHEN** the detector runs
- **THEN** the result contains zero `ReturnValue` effects

#### Scenario: Pure function has no effects
- **GIVEN** a Python function with body `pass` and no return annotation
- **WHEN** the detector runs on that function
- **THEN** the result contains zero side effects

#### Scenario: ErrorReturn detected
- **GIVEN** a Python function containing a `raise` statement
- **WHEN** the detector runs
- **THEN** an `ErrorReturn` effect is present

#### Scenario: SentinelError detected — module-level class
- **GIVEN** a module-level class inheriting directly from `Exception`
- **WHEN** the detector runs on that module
- **THEN** a `SentinelError` effect is associated with that class definition

#### Scenario: SentinelError detected — transitive inheritance
- **GIVEN** a module-level class inheriting from `ValueError` (a stdlib Exception subclass)
- **WHEN** the detector runs
- **THEN** a `SentinelError` effect is present

#### Scenario: SentinelError NOT detected for nested class
- **GIVEN** an exception class defined inside a function or method body
- **WHEN** the detector runs
- **THEN** no `SentinelError` effect is produced (nested classes are not sentinels)

#### Scenario: ReceiverMutation detected
- **GIVEN** a method that assigns to `self.<attr>`
- **WHEN** the detector runs
- **THEN** a `ReceiverMutation` effect is present

#### Scenario: PointerArgMutation detected — item assignment
- **GIVEN** a function that item-assigns on a parameter (`param[key] = val`)
- **WHEN** the detector runs
- **THEN** a `PointerArgMutation` effect is present

#### Scenario: SliceMutation detected — list method
- **GIVEN** a function that calls `param.append(...)` on a parameter
- **WHEN** the detector runs
- **THEN** a `SliceMutation` effect is present (NOT PointerArgMutation)

> **Note**: `PointerArgMutation` (P0) and `SliceMutation`/`MapMutation` (P1)
> are distinct. The EC-002 P0 test must assert the correct P0 type is present
> for generic mutations (item assignment). List/dict method calls produce P1
> types. A disjunctive "or" test between P0 and P1 types is not acceptable —
> it would allow a P0 false negative to be masked by a P1 detection.

#### Scenario: Failure mode — syntactically invalid file
- **GIVEN** a file containing a Python syntax error
- **WHEN** the detector runs on that file
- **THEN** a `ParseError` (or equivalent) is raised — NOT a silent empty result

---

### Requirement: EC-003 Effect Identity

Each detected effect MUST have an `id` field that is:
- Deterministic (same source → same id across runs and machines)
- Unique within a function (no two effects share an id)
- Stable (id does not change unless the effect's location or type changes)

The `file_path` component of the hash MUST be the **project-relative path**
(not the absolute path), so IDs are stable across machines and working
directories.

#### Scenario: Deterministic ids
- **GIVEN** a source file analyzed twice
- **WHEN** ids are compared across both runs
- **THEN** all ids are identical

#### Scenario: Stable across machines
- **GIVEN** the same source file at different absolute paths on two machines
- **WHEN** ids are compared
- **THEN** all ids are identical (relative path used in hash, not absolute)

---

### Requirement: EC-004 Effect Structure

Each detected effect MUST carry: `id`, `type`, `tier`, `location`
(`file:line:col` format), `description`, `target`, and `classification`
(object or null).

> Note: `contracts.md` EC-004 specifies `file:line:col` including the column.
> The AST provides `lineno` and `col_offset` on every node — both MUST be used.

#### Scenario: Effect fields present
- **GIVEN** a function with a detected ReturnValue effect
- **WHEN** the effect is serialized to a dict
- **THEN** all required fields are present and non-null (except `classification`
  which is null before classification runs)

#### Scenario: Location format
- **GIVEN** any detected effect
- **THEN** the `location` field matches the pattern `<path>:<line>:<col>` (two colons)

---

### Requirement: EC-005 Language Adaptation

The implementation MUST map each of the 38 effect types to its Python language
equivalent as specified in design.md. Types with clear Python equivalents MUST
be detected. Types with no meaningful Python equivalent (WaitGroupOp, AtomicOp,
RecoverBehavior, UnsafeMutation, SyncPoolOp) MUST remain in the taxonomy but
MAY produce zero detections.

> Note: `source="godoc"` and `source="godoc_keyword_indirect"` are the
> canonical cross-implementation signal source IDs per CC-006. Python
> implementations MUST use these identifiers verbatim — do NOT substitute
> `"docstring"` or `"pydoc"`. This preserves schema compatibility with Go gaze.

#### Scenario: Python-specific effects detected
- **GIVEN** Python source code using `queue.Queue.put()`, `threading.Lock`,
  `os.chmod()`, and `connection.begin()`
- **WHEN** the detector runs
- **THEN** ChannelSend, MutexOp, FileSystemMeta, and DatabaseTransaction
  effects are present in the result

#### Scenario: P1 writer effects detected
- **GIVEN** a function calling `.write()` on a parameter named `writer`
- **WHEN** the detector runs
- **THEN** a `WriterOutput` effect is present

#### Scenario: DeferredReturnMutation detected
- **GIVEN** a function whose `finally:` block assigns to a variable that is
  subsequently returned
- **WHEN** the detector runs
- **THEN** a `DeferredReturnMutation` effect is present

---

### Requirement: CC-001 Confidence Scoring Formula

The classifier MUST compute:
`score = clamp(base + tier_boost + sum(signal_weights) - contradiction_penalty, 0, 100)`
where base=50, P0 boost=+25, P1 boost=+10, P2–P4 boost=0,
contradiction penalty=20 (applied when both positive and negative signals exist).
See CC-002 for clamping specification.

#### Scenario: P0 baseline
- **GIVEN** a P0 effect with no signals
- **WHEN** classified
- **THEN** score is 75 (50 + 25)

#### Scenario: P1 baseline
- **GIVEN** a P1 effect with no signals
- **WHEN** classified
- **THEN** score is 60 (50 + 10)

#### Scenario: Contradiction penalty
- **GIVEN** an effect with one positive signal (+10) and one negative signal (-10)
- **WHEN** classified
- **THEN** contradiction penalty of -20 is applied and recorded as a separate signal

---

### Requirement: CC-002 Score Clamping

The confidence score MUST be clamped to the range [0, 100] after all
components are summed.

#### Scenario: Score clamped at lower bound
- **GIVEN** an effect whose raw computed score is -5
- **WHEN** the score is finalized
- **THEN** the final score is 0

#### Scenario: Score clamped at upper bound
- **GIVEN** an effect whose raw computed score is 120
- **WHEN** the score is finalized
- **THEN** the final score is 100

---

### Requirement: CC-003 Label Thresholds

The classifier MUST assign labels: `contractual` (score >= contractual_threshold,
default 80), `ambiguous` (incidental_threshold <= score < contractual_threshold),
`incidental` (score < incidental_threshold, default 50). Thresholds MUST be
configurable.

#### Scenario: Contractual label
- **GIVEN** a classified effect with score 85
- **WHEN** thresholds are contractual=80, incidental=50
- **THEN** label is "contractual"

#### Scenario: Incidental label
- **GIVEN** a classified effect with score 40
- **THEN** label is "incidental"

#### Scenario: Ambiguous label
- **GIVEN** a classified effect with score 65
- **THEN** label is "ambiguous"

---

### Requirement: CC-004 Contradiction Detection

When both positive-weight and negative-weight signals are present for the same
effect, the classifier MUST apply a contradiction penalty of -20. The
contradiction MUST be recorded as an explicit signal with `source="contradiction"`
and `weight=-20`.

#### Scenario: Contradiction signal recorded
- **GIVEN** an effect that receives one positive signal (e.g., naming +10) and
  one negative signal (e.g., docstring -15)
- **WHEN** classification runs
- **THEN** the signal list contains an entry with `source="contradiction"` and
  `weight=-20`

#### Scenario: No contradiction without both polarities
- **GIVEN** an effect with only positive signals
- **WHEN** classification runs
- **THEN** no contradiction signal is present in the signal list

---

### Requirement: CC-005 Five Signal Categories

The classifier MUST implement all five signal analyzers with the weight rules
specified in contracts.md.

#### Scenario: Interface satisfaction signal
- **GIVEN** a method on a class that inherits from an ABC or Protocol
- **WHEN** the interface signal analyzer runs
- **THEN** a signal with `source="interface"` and `weight=30` is returned

#### Scenario: API visibility signal — fully public
- **GIVEN** a public function on a public class returning a public type
- **WHEN** the visibility signal analyzer runs
- **THEN** a signal with `source="visibility"` and `weight=20` is returned
  (exported function +8, return type +6, receiver type +6, clamped to 20)

#### Scenario: Caller dependency signal weights
- **GIVEN** functions with 0, 1, 2, and 4 distinct caller modules respectively
- **WHEN** the caller signal analyzer runs for each
- **THEN** weights are 0, +5, +10, +15 respectively

#### Scenario: Naming — contractual prefix
- **GIVEN** a function named `GetUser` with a `ReturnValue` effect
- **WHEN** the naming signal analyzer runs
- **THEN** a signal with `source="naming"` and `weight=10` is returned

#### Scenario: Naming — sentinel special case
- **GIVEN** a module-level exception class named `ErrNotFound`
- **WHEN** the naming signal analyzer runs
- **THEN** a signal with `source="naming"` and `weight=30` is returned

#### Scenario: Naming — incidental prefix
- **GIVEN** a function named `logRequest` with a `LogWrite` effect
- **WHEN** the naming signal analyzer runs
- **THEN** a signal with `source="naming"` and `weight=-10` is returned

#### Scenario: Docstring — direct keyword match
- **GIVEN** a function whose docstring contains "returns" and the effect is ReturnValue
- **WHEN** the docstring signal analyzer runs
- **THEN** a signal with `source="godoc"` and `weight=15` is returned

#### Scenario: Docstring — indirect keyword match
- **GIVEN** a function whose docstring contains "writes" and the effect is ReturnValue
- **WHEN** the docstring signal analyzer runs
- **THEN** a signal with `source="godoc_keyword_indirect"` and `weight=5` is returned

#### Scenario: Docstring — incidental keyword
- **GIVEN** a function whose docstring contains "logs"
- **WHEN** the docstring signal analyzer runs
- **THEN** a signal with `source="godoc"` and `weight=-15` is returned

---

### Requirement: CC-006 Signal Recording

Every signal MUST be recorded in the classification result with at minimum a
`source` field (string) and a `weight` field (int). The source identifiers MUST
match the canonical values from contracts.md: `"interface"`, `"visibility"`,
`"caller"`, `"naming"`, `"godoc"`, `"godoc_keyword_indirect"`,
`"contradiction"`.

#### Scenario: Signal fields present
- **GIVEN** a classified effect that received signals from the naming and
  visibility analyzers
- **WHEN** the classification result is inspected
- **THEN** each signal object has a `source` string field and a `weight` int
  field that is non-zero

---

### Requirement: SC-001 CRAP Formula

The scorer MUST compute: `CRAP(m) = complexity² × (1 - coverage/100)³ + complexity`

CRAP MUST be null when `line_coverage` is null (coverage data not provided).

The CRAP reference value tests MUST use `@pytest.mark.parametrize` (TC-005).

#### Scenario: Reference values (all from taxonomy-reference.md)
- **GIVEN** known complexity and coverage inputs
- **WHEN** CRAP is computed
- **THEN** results match the full reference table in taxonomy-reference.md:
  - complexity=1, coverage=100% → 1.0
  - complexity=1, coverage=0% → 2.0
  - complexity=1, coverage=50% → 1.125
  - complexity=5, coverage=100% → 5.0
  - complexity=5, coverage=50% → 8.125
  - complexity=5, coverage=0% → 30.0
  - complexity=10, coverage=100% → 10.0
  - complexity=10, coverage=50% → 22.5
  - complexity=10, coverage=0% → 110.0
  - complexity=15, coverage=100% → 15.0
  - complexity=15, coverage=0% → 240.0
  - complexity=20, coverage=100% → 20.0
  - complexity=20, coverage=50% → 70.0

#### Scenario: CRAP null when coverage absent
- **GIVEN** a function with no coverage data provided (`line_coverage` is null)
- **WHEN** CRAP is computed
- **THEN** `crap` is null

---

### Requirement: SC-002 GazeCRAP Formula

The scorer MUST compute GazeCRAP using the same formula as CRAP but substituting
`contract_coverage` for `line_coverage`:
`GazeCRAP(m) = complexity² × (1 - contract_coverage/100)³ + complexity`

GazeCRAP MUST be null when `contract_coverage` is null (O1 not run).

#### Scenario: GazeCRAP reference values
- **GIVEN** known complexity and contract_coverage inputs
- **WHEN** GazeCRAP is computed
- **THEN** results match the reference table (same formula, different input):
  - complexity=1, contract_coverage=100% → 1.0
  - complexity=5, contract_coverage=50% → 8.125
  - complexity=10, contract_coverage=0% → 110.0

#### Scenario: GazeCRAP null without O1
- **GIVEN** analysis run without quality assessment (O1 not run)
- **WHEN** GazeCRAP is computed
- **THEN** `gaze_crap` is null

---

### Requirement: SC-003 CRAPload and GazeCRAPload

CRAPload MUST be the count of functions where `CRAP >= crap_threshold`
(default 15). GazeCRAPload MUST be the count of functions where
`GazeCRAP >= gaze_crap_threshold` (default 15). Both thresholds MUST be
independently configurable.

#### Scenario: CRAPload counting
- **GIVEN** 5 functions with CRAP scores [5.0, 10.0, 15.0, 20.0, 30.0] and
  threshold 15
- **WHEN** CRAPload is computed
- **THEN** CRAPload is 3 (scores 15.0, 20.0, 30.0 meet or exceed threshold)

#### Scenario: GazeCRAPload null without O1
- **GIVEN** analysis run without quality assessment (O1 not implemented)
- **WHEN** GazeCRAPload is computed
- **THEN** GazeCRAPload is null

---

### Requirement: SC-004 Quadrant Classification

When both CRAP and GazeCRAP are available, the scorer MUST classify each
function into exactly one of: Q1_Safe, Q2_ComplexButTested,
Q3_SimpleButUnderspecified, Q4_Dangerous, per the truth table in contracts.md.

The quadrant truth table MUST be tested with all 4 combinations using
`@pytest.mark.parametrize` (TC-005).

#### Scenario: Q1 Safe
- **GIVEN** a function where CRAP < threshold AND GazeCRAP < threshold
- **THEN** quadrant is "Q1_Safe"

#### Scenario: Q2 Complex But Tested
- **GIVEN** a function where CRAP >= threshold AND GazeCRAP < threshold
- **THEN** quadrant is "Q2_ComplexButTested"

#### Scenario: Q3 Simple But Underspecified
- **GIVEN** a function where CRAP < threshold AND GazeCRAP >= threshold
- **THEN** quadrant is "Q3_SimpleButUnderspecified"

#### Scenario: Q4 Dangerous
- **GIVEN** a function where CRAP >= threshold AND GazeCRAP >= threshold
- **THEN** quadrant is "Q4_Dangerous"

---

### Requirement: SC-005 Fix Strategy Assignment

Functions in the CRAPload MUST receive exactly one fix strategy. The canonical
priority numbers (for SC-006 sort order) are: `add_tests=0`, `add_assertions=1`,
`decompose_and_test=2`, `decompose=3`.

**Evaluation order** (first match wins — checked in this order in code):
1. `complexity >= threshold AND line_coverage == 0` → `decompose_and_test` (priority 2)
2. `complexity >= threshold AND line_coverage > 0` → `decompose` (priority 3)
3. `quadrant == Q3_SimpleButUnderspecified` → `add_assertions` (priority 1)
4. Default → `add_tests` (priority 0)

> **Critical distinction**: The evaluation order (1→4 above, complexity rules
> checked first) is NOT the same as the sort priority (0=add_tests first in
> output). An implementer MUST NOT use the priority number as the evaluation
> order. Check rules 1 and 2 first in code, regardless of priority numbers.

#### Scenario: Rule 1 wins over default
- **GIVEN** a function where complexity >= threshold AND line_coverage == 0
- **THEN** strategy is `decompose_and_test` (not `add_tests`)

#### Scenario: Rule 2 wins over rule 3
- **GIVEN** a function where complexity >= threshold AND line_coverage > 0
  AND quadrant is Q3_SimpleButUnderspecified
- **THEN** strategy is `decompose` (rule 2 evaluated before rule 3)

---

### Requirement: OC-001 Dual Format

The implementation MUST support JSON and text output formats. JSON MUST be
machine-readable and schema-compatible with the Go gaze output. Text MUST be
human-readable terminal output.

#### Scenario: JSON format
- **GIVEN** analysis of a Python source directory
- **WHEN** `--format=json` is specified
- **THEN** output is valid JSON parseable by `json.loads()`

#### Scenario: Text format
- **GIVEN** analysis of a Python source directory
- **WHEN** `--format=text` is specified
- **THEN** output is a non-empty human-readable string (not JSON)

#### Scenario: CLI failure — invalid path
- **GIVEN** `gazepy analyze /nonexistent/path`
- **WHEN** run
- **THEN** exit code is non-zero and stderr contains an error message

---

### Requirement: OC-002 JSON Field Names

JSON output MUST use the canonical snake_case field names from
taxonomy-reference.md. The following fields MUST be present in the output
(even if null):

| Field | Object | In scope for this change |
|---|---|---|
| `side_effects` | AnalysisResult | Yes |
| `line_coverage` | Score | Yes (null when not provided) |
| `crap` | Score | Yes (null when line_coverage is null) |
| `gaze_crap` | Score | Yes (null — O1 deferred) |
| `contract_coverage` | Score | Yes (null — O1 deferred) |
| `contract_coverage_reason` | Score | Yes (null — O1 deferred) |
| `fix_strategy` | Score | Yes (null when CRAP is null) |
| `quadrant` | Score | Yes (null — O1 deferred) |
| `quadrant_counts` | Summary | Yes (null — O1 deferred) |
| `fix_strategy_counts` | Summary | Yes (null — O1 deferred) |
| `gaze_crapload` | Summary | Yes (null — O1 deferred) |
| `avg_contract_coverage` | Summary | Yes (null — O1 deferred) |
| `recommended_actions` | Summary | Yes (null when CRAP is null) |
| `effect_confidence_range` | Score | Deferred to future change |
| `ssa_degraded_packages` | Summary | N/A — no SSA in Python |

#### Scenario: Required fields present
- **GIVEN** a complete analysis result
- **WHEN** serialized to JSON
- **THEN** the following top-level keys are present: `side_effects`,
  `line_coverage`, `crap`, `gaze_crap`, `contract_coverage`, `fix_strategy`,
  `quadrant`, `recommended_actions`

#### Scenario: snake_case enforcement
- **GIVEN** any JSON output field name
- **THEN** no camelCase names appear (e.g., `sideEffects` would be a violation)

---

### Requirement: OC-003 Nullable Fields

Fields that depend on optional capabilities MUST be null when the capability
has not run — not zero or empty list. `line_coverage` MUST be null (not 0.0)
when no coverage data is provided. `crap` MUST be null when `line_coverage`
is null.

#### Scenario: Coverage absent — null not zero
- **GIVEN** analysis run without `--coverage-json`
- **WHEN** JSON output is produced
- **THEN** `line_coverage` is null (NOT 0.0) and `crap` is null

#### Scenario: GazeCRAP null without O1
- **GIVEN** analysis run without quality assessment (O1)
- **WHEN** JSON output is produced
- **THEN** `gaze_crap` is null, `contract_coverage` is null, `quadrant` is null

#### Scenario: contract_coverage_reason when no effects detected
- **GIVEN** a function with no detected side effects
- **WHEN** JSON output is produced
- **THEN** `contract_coverage_reason` is `"no_effects_detected"`

---

### Requirement: Package Infrastructure

The package MUST be buildable as a local wheel via `uv build`, installable
via `uv tool install dist/gaze_py-*.whl`, expose the `gazepy` binary, and be
importable as `import gaze`. PyPI publication is deferred to a future change.

---

### Requirement: SC-006 Recommended Actions Ordering

Recommended actions MUST be sorted by fix strategy priority (add_tests=0,
add_assertions=1, decompose_and_test=2, decompose=3), then by CRAP score
descending within each strategy group. The list MUST be capped at 20 entries.

#### Scenario: Sort order
- **GIVEN** functions with strategies add_tests (CRAP 20), decompose (CRAP 18),
  add_tests (CRAP 25), add_assertions (CRAP 16)
- **WHEN** recommended_actions is built
- **THEN** order is: add_tests/CRAP=25, add_tests/CRAP=20, add_assertions/CRAP=16,
  decompose/CRAP=18

#### Scenario: Cap at 20
- **GIVEN** 25 functions all in the CRAPload
- **WHEN** recommended_actions is built
- **THEN** the list contains exactly 20 entries

---

### Requirement: Coverage Strategy

All new code MUST have a documented coverage strategy per constitution
Principle IV. The `--cov=gaze` flag measures coverage of the `src/gaze/`
package. The 85% floor (`--cov-fail-under=85`) is a floor, not a target.

| Module | Coverage approach |
|---|---|
| `taxonomy/effects.py`, `taxonomy/models.py` | 100% via direct enum/dataclass tests |
| `analysis/detector.py` | testdata fixtures covering all detected effect types |
| `classify/engine.py`, `classify/signals/*.py` | unit tests with synthetic Signal inputs |
| `crap/scorer.py` | parametrized reference value table + quadrant truth table |
| `config/loader.py` | happy path + missing file + invalid YAML + bad threshold values |
| `report/json_formatter.py`, `report/text_formatter.py` | output tests against full AnalysisResult |
| `cli/main.py` | Click test runner smoke tests + failure cases; target ≥70% (Click boilerplate excluded) |

Exclusions from coverage measurement: `tests/testdata/` (enforced by
`norecursedirs`), `__init__.py` files (module docstring only).

P3/P4 effect types with no Python equivalent (WaitGroupOp, AtomicOp,
RecoverBehavior, UnsafeMutation, SyncPoolOp) have no-op detection paths.
These paths MUST be covered by at least one test each asserting an empty
result for the relevant effect type name.
