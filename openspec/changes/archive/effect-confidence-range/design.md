# Design: effect-confidence-range

## A.6 — effect_confidence_range population

### Where confidence scores come from

`ClassificationEngine.classify(effect, target)` returns a `ClassificationResult`
with `.score: int` (0–100). Inside `compute_contract_coverage()` in
`quality/coverage.py`, this is called per-effect but `.score` is discarded —
only `.label` is used to determine contractual/ambiguous/incidental.

The `"all_effects_ambiguous"` branch fires when:
- `target.effects` is non-empty
- No effect has `classification.label == "contractual"`
- All effects have `classification.label == "ambiguous"`
(see the existing `reason` assignment logic in `coverage.py`)

### Data flow

```
coverage.py:compute_contract_coverage()
  → engine.classify(effect, target) per effect
  → save classification.score when all ambiguous
  → ContractCoverageResult(min_confidence=..., max_confidence=...)

pipeline.py:assess()
  → compute_contract_coverage() → QualityReport

cli/main.py:_score_target()
  → if quality_result.reason == "all_effects_ambiguous":
      effect_confidence_range = (quality_result.min_confidence,
                                 quality_result.max_confidence)
  → Score(effect_confidence_range=...)
```

### Model change: ContractCoverageResult

Add two nullable fields to the frozen dataclass:
```python
min_confidence: int | None = None
max_confidence: int | None = None
```

These are set only in the `"all_effects_ambiguous"` path. In all other paths,
they remain `None` (the default).

`ContractCoverageResult` is a `@dataclass(frozen=True)` — adding fields with
defaults is backward-compatible; existing construction call sites that don't
pass these fields continue to work.

### coverage.py change

In the `all_effects_ambiguous` branch, collect scores before returning:

```python
scores = [engine.classify(e, target).score for e in target.effects]
return ContractCoverageResult(
    ...,
    reason="all_effects_ambiguous",
    min_confidence=min(scores),
    max_confidence=max(scores),
)
```

Note: the current implementation calls `engine.classify()` per effect in a loop
and only saves the label. The scores collection replaces (or wraps) that loop.
We call classify once per effect and save both label and score. No double-call.

### cli/main.py change (_score_target, line ~1042)

```python
ecr: tuple[int, int] | None = None
if (
    quality_result is not None
    and quality_result.reason == "all_effects_ambiguous"
    and quality_result.min_confidence is not None
    and quality_result.max_confidence is not None
):
    ecr = (quality_result.min_confidence, quality_result.max_confidence)
...
Score(
    ...,
    effect_confidence_range=ecr,
)
```

### JSON serialization

`report/json_formatter.py:204` already reads
`score_dict.get("effect_confidence_range")`. `Score` is a dataclass so
`dataclasses.asdict()` converts `tuple[int, int]` to `[int, int]` (a list)
automatically. No serialization change needed.

Existing test at `test_output.py:214` (`test_oc003_effect_confidence_range_is_null_key_present`)
asserts the key exists with `None`. This remains valid for the common case.
A new test covers the non-None case.

## B.1–B.2 — Complexity spec tests

No production code changes. The `complexity.py` implementation is correct.
Tests added to `tests/test_complexity.py` using the existing `_parse_first_fn`
helper pattern. Each test is a standalone function asserting an exact value.

The `test_high_complexity_function_greater_than_1` test is updated in-place:
`assert result > 1` → `assert result == 9` with an explanatory comment
documenting the breakdown (6 if/elif + 1 for + 1 while + 1 base = 9).
Verified by running `cyclomatic_complexity()` against the fixture directly.

Nested-function independent scoring test reuses the existing
`outer_with_nested` fixture from `testdata/analysis/` or constructs inline
source — whichever is cleaner. Inline construction preferred to avoid
testdata sprawl.
