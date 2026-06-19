# Scoring

gaze-py computes two scores per function: **CRAP** (based on line coverage) and **GazeCRAP** (based on contract coverage). Both scores identify functions most in need of better tests.

## CRAP

CRAP stands for Change Risk Anti-Patterns. It combines cyclomatic complexity with line coverage to predict how risky a function is to change.

**Formula:**

```
CRAP = complexity² × (1 − line_coverage)³ + complexity
```

Where:
- `complexity` — McCabe cyclomatic complexity (number of independent paths through the function; minimum 1)
- `line_coverage` — fraction of lines executed by tests, in [0.0, 1.0]

A function with complexity 10 and 0% coverage scores `10² × 1³ + 10 = 110`. The same function at 100% coverage scores `10² × 0 + 10 = 10` — CRAP equals complexity at full coverage. The score is `null` when coverage data is unavailable.

The default threshold for flagging a function as high-CRAP is 15.0 (configurable via `crap_threshold` in `.gaze.yaml`).

## GazeCRAP

GazeCRAP extends CRAP by replacing line coverage with **contract coverage** — the fraction of a function's contractual side effects that are actively asserted in tests.

**Formula:**

```
GazeCRAP = complexity² × (1 − contract_coverage)³ + complexity
```

Where `contract_coverage` is in [0.0, 1.0]. A function at 100% line coverage but 0% contract coverage has CRAP = complexity but GazeCRAP = `complexity² + complexity`. This surfaces the gap between "lines were executed" and "behavior was verified."

GazeCRAP is `null` when the quality pipeline (O1 layer) has not run — it requires pairing test assertions with production side effects via `gazepy quality`.

## CRAPload

CRAPload is the count of functions whose CRAP score exceeds the configured threshold. It gives a single number representing the project's overall test debt burden.

GazeCRAPload is the equivalent count based on GazeCRAP scores.

Use `--max-crapload` and `--max-gaze-crapload` as CI gates to enforce project-wide thresholds.

## Fix Strategies

When a function's CRAP or GazeCRAP score exceeds the threshold, gaze-py recommends one of four fix strategies:

| Strategy | Meaning |
|---|---|
| `add_tests` | Low complexity, low coverage — write tests |
| `add_assertions` | Tests exist but don't assert on side effects |
| `decompose_and_test` | High complexity and low coverage — split the function, then test |
| `decompose` | High complexity, high coverage — reduce complexity |

## Quadrants

Functions are placed in one of four quadrants based on complexity and coverage:

| Quadrant | Complexity | Coverage | Interpretation |
|---|---|---|---|
| Q1 | Low | High | Healthy |
| Q2 | Low | Low | Missing tests |
| Q3 | High | High | Covered but fragile — consider decomposing |
| Q4 | High | Low | Highest risk — top priority |

The boundary between "low" and "high" complexity is 15. The boundary between "low" and "high" coverage is 50%.
