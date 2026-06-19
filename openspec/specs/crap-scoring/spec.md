# Spec: crap-scoring

Authoritative requirements for CRAP and GazeCRAP scoring in gaze-py.
Sources: porting contracts SC-001 through SC-006, taxonomy-reference.md
scoring formulas and reference values, and the current `crap/scorer.py`
implementation.

---

### Requirement: SC-001 CRAP Formula

The scorer MUST compute the CRAP score using this exact formula:

```
CRAP(m) = complexity² × (1 - coverage/100)³ + complexity
```

Where:
- `complexity` = cyclomatic complexity of the function (integer >= 1)
- `coverage` = line coverage percentage (float, 0–100)

**Properties**:
- At 100% coverage: `CRAP = complexity` (the cubic term vanishes)
- At 0% coverage: `CRAP = complexity² + complexity`
- Higher complexity amplifies the penalty for missing coverage

**Implementation note**: The `crap/scorer.py` implementation accepts
`line_coverage` as a fraction in [0.0, 1.0] (not a percentage). The formula
is applied as `complexity² × (1 - line_coverage)³ + complexity` where
`line_coverage` is already in [0, 1]. This is mathematically equivalent to
the contract formula when `coverage/100 = line_coverage`.

CRAP MUST be `None` when `line_coverage` is `None` (coverage data not
provided). Per OC-003: null not zero.

#### Scenario: Reference values — full table from taxonomy-reference.md
- **WHEN** CRAP is computed for the following (complexity, coverage%) pairs
- **THEN** results match exactly:

| Complexity | Coverage % | Expected CRAP |
|-----------|------------|---------------|
| 1 | 100% | 1.0 |
| 1 | 0% | 2.0 |
| 1 | 50% | 1.125 |
| 5 | 100% | 5.0 |
| 5 | 50% | 8.125 |
| 5 | 0% | 30.0 |
| 10 | 100% | 10.0 |
| 10 | 50% | 22.5 |
| 10 | 0% | 110.0 |
| 15 | 100% | 15.0 |
| 15 | 0% | 240.0 |
| 20 | 100% | 20.0 |
| 20 | 50% | 70.0 |

These reference values MUST be tested with `@pytest.mark.parametrize`.

#### Scenario: CRAP null when coverage absent
- **WHEN** `line_coverage` is `None`
- **THEN** `crap()` returns `None`

#### Scenario: CRAP at 100% coverage equals complexity
- **WHEN** `line_coverage` is 1.0 (100%)
- **THEN** `crap(complexity, 1.0) == float(complexity)` for any complexity

---

### Requirement: SC-002 GazeCRAP Formula

GazeCRAP uses the same formula as CRAP but substitutes **contract coverage**
for line coverage:

```
GazeCRAP(m) = complexity² × (1 - contract_coverage/100)³ + complexity
```

Where `contract_coverage` is the percentage of contractual side effects that
are asserted on by tests (0–100).

GazeCRAP is only available when the classification and quality assessment
pipelines (O1) have run. When contract coverage data is unavailable, GazeCRAP
MUST be `None` — not zero. Per OC-003: null not zero.

#### Scenario: GazeCRAP reference values
- **WHEN** GazeCRAP is computed for the following (complexity, contract_coverage%) pairs
- **THEN** results match exactly (same formula, different input):

| Complexity | Contract Coverage % | Expected GazeCRAP |
|-----------|---------------------|-------------------|
| 1 | 100% | 1.0 |
| 5 | 50% | 8.125 |
| 10 | 0% | 110.0 |

These reference values MUST be tested with `@pytest.mark.parametrize`.

#### Scenario: GazeCRAP null when O1 not run
- **WHEN** analysis runs without the quality assessment pipeline (O1 not run)
- **THEN** `gaze_crap` is `None` in the output

#### Scenario: GazeCRAP at 100% contract coverage equals complexity
- **WHEN** `contract_coverage` is 1.0 (100%)
- **THEN** `gaze_crap(complexity, 1.0) == float(complexity)` for any complexity

---

### Requirement: SC-003 CRAPload and GazeCRAPload

- **CRAPload** = count of functions where `CRAP >= crap_threshold`
  (default threshold: 15)
- **GazeCRAPload** = count of functions where `GazeCRAP >= gaze_crap_threshold`
  (default threshold: 15)

Both thresholds MUST be independently configurable. Functions with a null
CRAP or GazeCRAP score (coverage not provided) are excluded from the count.

The threshold comparison is inclusive: a function with CRAP exactly equal to
the threshold IS counted in the CRAPload.

#### Scenario: CRAPload counting — inclusive threshold
- **WHEN** 5 functions have CRAP scores [5.0, 10.0, 15.0, 20.0, 30.0] and
  threshold is 15
- **THEN** CRAPload is 3 (scores 15.0, 20.0, 30.0 meet or exceed threshold)

#### Scenario: CRAPload zero — all below threshold
- **WHEN** all functions have CRAP scores below the threshold
- **THEN** CRAPload is 0

#### Scenario: GazeCRAPload null without O1
- **WHEN** analysis runs without the quality assessment pipeline
- **THEN** `gaze_crapload` is `None` in the summary output

#### Scenario: CRAPload excludes null-CRAP functions
- **WHEN** some functions have null CRAP (no coverage data)
- **THEN** those functions are excluded from the CRAPload count

---

### Requirement: SC-004 Quadrant Classification

When both CRAP and GazeCRAP are available, the scorer MUST classify each
function into exactly one of four quadrants based on whether each score meets
or exceeds its respective threshold:

| Quadrant | Condition | Meaning |
|----------|-----------|---------|
| `Q1_Safe` | CRAP < threshold AND GazeCRAP < threshold | Low risk, well tested |
| `Q2_ComplexButTested` | CRAP >= threshold AND GazeCRAP < threshold | Complex but contracts verified |
| `Q3_SimpleButUnderspecified` | CRAP < threshold AND GazeCRAP >= threshold | Simple but contracts not verified |
| `Q4_Dangerous` | CRAP >= threshold AND GazeCRAP >= threshold | Complex AND contracts not verified |

The CRAP threshold and GazeCRAP threshold are independent and separately
configurable. The quadrant is `None` when either score is `None`.

The quadrant truth table MUST be tested with all 4 combinations using
`@pytest.mark.parametrize`.

#### Scenario: Q1 Safe
- **WHEN** a function has CRAP < threshold AND GazeCRAP < threshold
- **THEN** quadrant is `"Q1_Safe"`

#### Scenario: Q2 Complex But Tested
- **WHEN** a function has CRAP >= threshold AND GazeCRAP < threshold
- **THEN** quadrant is `"Q2_ComplexButTested"`

#### Scenario: Q3 Simple But Underspecified
- **WHEN** a function has CRAP < threshold AND GazeCRAP >= threshold
- **THEN** quadrant is `"Q3_SimpleButUnderspecified"`

#### Scenario: Q4 Dangerous
- **WHEN** a function has CRAP >= threshold AND GazeCRAP >= threshold
- **THEN** quadrant is `"Q4_Dangerous"`

#### Scenario: Quadrant null when GazeCRAP unavailable
- **WHEN** `contract_coverage` is `None` (O1 not run)
- **THEN** `quadrant` is `None`

---

### Requirement: SC-005 Fix Strategy Assignment

Functions in the CRAPload (CRAP >= threshold) MUST receive exactly one fix
strategy. Functions below the threshold MUST NOT have a fix strategy (their
`fix_strategy` is `None`).

**Evaluation order** (first matching rule wins — checked in this exact order):

| Rule | Condition | Strategy | Priority |
|------|-----------|----------|----------|
| 1 | complexity >= complexity_threshold AND line_coverage == 0.0 | `decompose_and_test` | 2 |
| 2 | complexity >= complexity_threshold AND line_coverage > 0.0 | `decompose` | 3 |
| 3 | quadrant == `Q3_SimpleButUnderspecified` | `add_assertions` | 1 |
| 4 | (default) | `add_tests` | 0 |

> **Critical distinction**: The evaluation order (rules 1→4 above, complexity
> rules checked first) is NOT the same as the sort priority (0=add_tests first
> in output). An implementer MUST NOT use the priority number as the evaluation
> order. Rules 1 and 2 MUST be checked first in code, regardless of their
> priority numbers.

> **Note on Rule 3**: `add_assertions` requires `quadrant == Q3_SimpleButUnderspecified`,
> which requires GazeCRAP, which requires O1. Rule 3 is unreachable in the live
> pipeline when O1 has not run. Tests for Rule 2 vs Rule 3 MUST inject a
> synthetic Q3 quadrant value directly into `fix_strategy()`.

#### Scenario: Rule 1 — decompose_and_test wins over default
- **WHEN** a function has CRAP >= threshold, complexity >= complexity_threshold,
  and line_coverage == 0.0
- **THEN** strategy is `"decompose_and_test"` (not `"add_tests"`)

#### Scenario: Rule 2 — decompose wins over add_assertions
- **WHEN** a function has CRAP >= threshold, complexity >= complexity_threshold,
  line_coverage > 0.0, AND quadrant is `Q3_SimpleButUnderspecified`
- **THEN** strategy is `"decompose"` (rule 2 evaluated before rule 3)

#### Scenario: Rule 3 — add_assertions for Q3
- **WHEN** a function has CRAP >= threshold, complexity < complexity_threshold,
  and quadrant is `Q3_SimpleButUnderspecified`
- **THEN** strategy is `"add_assertions"`

#### Scenario: Rule 4 — default add_tests
- **WHEN** a function has CRAP >= threshold and none of rules 1–3 apply
- **THEN** strategy is `"add_tests"`

#### Scenario: fix_strategy null for functions below CRAPload threshold
- **WHEN** a function has CRAP < crap_threshold
- **THEN** `fix_strategy` is `None`

#### Scenario: fix_strategy null when CRAP is null
- **WHEN** `line_coverage` is `None` (CRAP cannot be computed)
- **THEN** `fix_strategy` is `None`

---

### Requirement: SC-006 Recommended Actions Ordering

Recommended actions MUST be sorted by fix strategy priority (easiest wins
first), then by CRAP score descending within each strategy group. The list
MUST be capped at 20 entries.

Strategy sort priority (ascending — lower number appears first in output):

| Priority | Strategy |
|----------|----------|
| 0 (first) | `add_tests` |
| 1 | `add_assertions` |
| 2 | `decompose_and_test` |
| 3 (last) | `decompose` |

Each entry in `recommended_actions` MUST contain:
`{"function": str, "file": str, "strategy": str, "crap": float}`

#### Scenario: Sort order — primary by strategy priority, secondary by CRAP descending
- **GIVEN** functions: add_tests/CRAP=25, add_tests/CRAP=20, add_assertions/CRAP=22,
  add_assertions/CRAP=16, decompose/CRAP=18
- **WHEN** `recommended_actions` is built
- **THEN** order is: add_tests/25, add_tests/20, add_assertions/22,
  add_assertions/16, decompose/18

#### Scenario: Cap at 20 entries
- **WHEN** 25 functions are all in the CRAPload
- **THEN** `recommended_actions` contains exactly 20 entries

#### Scenario: Empty list when no CRAPload functions
- **WHEN** CRAP is computed but all functions are below the threshold
- **THEN** `recommended_actions` is `[]` (empty list, NOT null — CRAP was
  computed, result is empty)

---

### Requirement: Null Not Zero in Scoring

Per OC-003, all scoring fields that depend on optional capabilities MUST be
`None` when the capability has not run — not `0.0` or `0`.

| Field | Null when |
|-------|-----------|
| `crap` | `line_coverage` is `None` |
| `gaze_crap` | `contract_coverage` is `None` (O1 not run) |
| `contract_coverage` | O1 not run |
| `quadrant` | Either `line_coverage` or `contract_coverage` is `None` |
| `fix_strategy` | CRAP is `None` or CRAP < threshold |
| `gaze_crapload` | O1 not run |
| `avg_contract_coverage` | O1 not run |
| `quadrant_counts` | O1 not run |
| `fix_strategy_counts` | CRAP not computed |

#### Scenario: GazeCRAP null without O1
- **WHEN** analysis runs without quality assessment
- **THEN** `gaze_crap` is `None`, not `0.0`

#### Scenario: CRAP null without coverage
- **WHEN** `line_coverage` is `None`
- **THEN** `crap` is `None`, not `0.0`

---

### Requirement: Summary Aggregates

The analysis summary MUST include the following aggregate fields:

| Field | Type | Description |
|-------|------|-------------|
| `function_count` | int | Total number of analyzed functions |
| `crapload` | int or None | Count of functions with CRAP >= threshold |
| `gaze_crapload` | int or None | Count of functions with GazeCRAP >= threshold; null when O1 not run |
| `avg_line_coverage` | float or None | Mean line coverage across functions with non-null coverage |
| `avg_contract_coverage` | float or None | Mean contract coverage; null when O1 not run |
| `quadrant_counts` | dict or None | Count of functions per quadrant label; null when O1 not run |
| `fix_strategy_counts` | dict or None | Count of functions per fix strategy; null when CRAP not computed |
| `recommended_actions` | list or None | Prioritized action list; null when CRAP not computed |
| `crap_threshold` | float | Always non-null — from GazeConfig |
| `gaze_crap_threshold` | float | Always non-null — from GazeConfig |

#### Scenario: crap_threshold always present
- **WHEN** any analysis result is produced
- **THEN** `crap_threshold` is a non-null float in the summary

#### Scenario: quadrant_counts null without O1
- **WHEN** O1 has not run
- **THEN** `quadrant_counts` is `None` in the summary
