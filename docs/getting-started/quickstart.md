# Quickstart

This guide runs `gazepy crap` on a Python file and shows how to read the output.

## Prerequisites

- gaze-py installed (`gazepy --version` works)
- A Python project with tests using `pytest`

## Run CRAP Analysis

From your project root:

```bash
gazepy crap src/
```

gaze-py discovers all `.py` files under `src/`, runs `pytest --cov` automatically, and prints a report.

**Example output (text format):**

```
CRAP Report
===========

src/mymodule/parser.py

  parse_expression        CC=12  cov=34%  CRAP=108.4  Q4  decompose_and_test
  tokenize                CC=4   cov=91%  CRAP=4.0    Q1  -
  handle_error            CC=2   cov=0%   CRAP=10.0   Q2  add_tests

Summary
-------
Functions analyzed:  3
CRAPload (>15.0):    1  [parse_expression]
```

**Reading the output:**

| Column | Meaning |
|---|---|
| `CC` | Cyclomatic complexity — number of independent code paths |
| `cov` | Line coverage percentage from pytest |
| `CRAP` | CRAP score — higher is worse |
| `Q1`–`Q4` | Quadrant (Q4 = high complexity + low coverage = highest risk) |
| Last column | Recommended fix strategy |

## Act on the Results

A `decompose_and_test` recommendation means the function is both complex and undertested — start there. An `add_tests` recommendation means the function is simple but has no test coverage.

To get contract coverage (which side effects your tests actually assert on):

```bash
gazepy quality src/ --tests tests/
```

## Use a Pre-generated Coverage Report

If you already have a `coverage.py` JSON report:

```bash
coverage run -m pytest && coverage json
gazepy crap src/ --coverprofile coverage.json
```

## Next Steps

- [Side Effects](../concepts/side-effects.md) — what gaze-py detects
- [Scoring](../concepts/scoring.md) — how CRAP and GazeCRAP are computed
- [CLI: crap](../reference/cli/crap.md) — full option reference
- [CLI: quality](../reference/cli/quality.md) — contract coverage analysis
