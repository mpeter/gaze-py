# Specs: effect-confidence-range

## ECR-001 — effect_confidence_range populated when all effects ambiguous

**Given** a function with one or more detected effects where all are classified
as ambiguous (no contractual effects exist, `reason == "all_effects_ambiguous"`)
**When** `gazepy quality` runs the O1 pipeline on that function
**Then** `Score.effect_confidence_range` is a `tuple[int, int]` of
`(min_confidence, max_confidence)` where both values are the min and max of
the `ClassificationResult.score` integers across all effects on that function.

## ECR-002 — effect_confidence_range is None in all other cases

**Given** a function where `contract_coverage.reason` is not
`"all_effects_ambiguous"` (including `None`, `"no_effects_detected"`,
or any normal coverage computation)
**When** `gazepy quality` runs the O1 pipeline on that function
**Then** `Score.effect_confidence_range` is `None`.

## ECR-003 — ContractCoverageResult carries min/max confidence

**Given** `compute_contract_coverage()` classifies all effects as ambiguous
**When** the function returns a `ContractCoverageResult`
**Then** the result has `min_confidence: int | None` and
`max_confidence: int | None` fields set to the observed min and max
`ClassificationResult.score` values respectively.
When the reason is not `"all_effects_ambiguous"`, both fields are `None`.

**Implementation note**: The current `coverage.py` `if not contractual:` branch
produces only `"no_effects_detected"` or `"no_contractual_effects"`. To support
`"all_effects_ambiguous"`, this branch must be split:
- `target.effects` is empty → `"no_effects_detected"`
- All effects are incidental (none ambiguous) → `"no_contractual_effects"`
- All effects are ambiguous (none contractual, none incidental) →
  `"all_effects_ambiguous"` with `min_confidence`/`max_confidence` populated

**Go divergence (documented)**: The Go reference uses non-nullable `int` (zero-value
sentinel) for `MinConfidence`/`MaxConfidence`. Python uses `int | None`; the guard
`min_confidence is not None` is the Python equivalent of Go's `effectCount > 0`.
This is a deliberate language adaptation, not a behavioral divergence.

**`ContractCoverageResult.reason` valid values** (updated):
- `None` — normal coverage computed
- `"no_effects_detected"` — function has no side effects at all
- `"no_contractual_effects"` — effects exist but all are incidental
- `"all_effects_ambiguous"` — effects exist but all are ambiguous (new)

## ECR-004 — JSON serialization: tuple serializes as array

**Given** `Score.effect_confidence_range == (60, 85)`
**When** the score is serialized to JSON
**Then** the JSON output contains `"effect_confidence_range": [60, 85]`
(two-element integer array, not null).

## CX-001 — Complexity algorithm: formal node specification

The `cyclomatic_complexity()` function in `analysis/complexity.py` MUST
implement the McCabe algorithm with exactly these rules:

- **Baseline**: every function starts at complexity 1.
- **Increment nodes** (each occurrence adds to complexity):
  - `ast.If` — each `if` and `elif` (+1 each; `elif` is a nested `ast.If`)
  - `ast.For` — each `for` loop body (+1)
  - `ast.While` — each `while` loop (+1)
  - `ast.ExceptHandler` — each `except` clause (+1)
  - `ast.With` — each **item** in the `with` statement (`with a, b:` → +2)
  - `ast.Assert` — each `assert` statement (+1)
  - `ast.BoolOp` — `+len(values) - 1` (one per additional operand)
  - Comprehension `if`-filters — each `if` clause per generator (+1 each)
- **Not counted**: `ast.IfExp` (ternary), `else`/`finally`, `lambda`,
  `return`, `match`/`case`, `try` itself.
- **Nested scope**: nested `FunctionDef`/`AsyncFunctionDef` are excluded
  from the outer function's count. Each nested function is scored
  independently.

## CX-002 — Round-trip tests: exact known values

Each of the following inputs MUST have a dedicated test asserting the exact
expected complexity value:

| Input pattern | Expected |
|---|---|
| `def f(x): assert x > 0; return x` | 2 |
| `def f():\n    with a() as x, b() as y:\n        pass` | 3 |
| `def f():\n    try:\n        pass\n    except A:\n        pass\n    except B:\n        pass` | 3 |
| `def f(a, b, c): return a and b and c` | 3 (1 + 1 BoolOp×2) |
| `def f(items): return [x for x in items if x > 0 if x < 10]` | 3 |
| Score `inner` from `outer`/`inner` fixture independently | 3 |
| `high_complexity.py` fixture | exactly 9 (verified: 1 base + 8 decision points) |
