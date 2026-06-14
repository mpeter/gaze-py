## Context

Go gaze implements O1 using SSA call graphs. Python has no SSA equivalent;
gaze-py uses AST-only analysis throughout. The porting contracts (requirements.md
O1) permit any mapping strategy that produces accurate contract coverage
percentages. GazeCRAP (SC-002) and quadrant (SC-004) formulas are porting
contracts and must be computed exactly.

**Unit convention throughout this change**: all coverage values passed to
`gaze_crap()`, `quadrant()`, and `crap()` are **fractions in [0.0, 1.0]**.
`ContractCoverageResult.percentage` stores [0.0, 100.0] for JSON output
compatibility. Callers MUST divide by 100.0 before passing to scorer functions.

## Module Structure

```
src/gaze_py/quality/
├── __init__.py          # module docstring only (CR-001)
├── pipeline.py          # assess() entry point
├── models.py            # TestFunc only (internal, wraps AST node, never serialized)
├── pairing.py           # A.1: find_test_functions(), pair_to_targets()
├── assertions.py        # A.2: detect_assertions()
├── mapper.py            # A.3: map_assertions_to_effects(), build_call_bindings()
└── coverage.py          # A.4: compute_contract_coverage()

# Output types belong in taxonomy (AP-006 — report/ and cli/ import only from taxonomy):
src/gaze_py/taxonomy/models.py  ← add QualityReport, AssertionSite, AssertionKind,
                                     TestTargetPair, ContractCoverageResult
```

Note: `TestFunc` stays in `quality/models.py` because it wraps `ast.FunctionDef`
(never serialized to JSON). All other new types are output/domain types consumed
by the CLI and formatter, so they belong in `taxonomy/`.

## Data Types

### quality/models.py (internal only)

```python
@dataclass
class TestFunc:
    """Internal representation of a test function.

    Not frozen — contains ast.FunctionDef which is mutable.
    Never serialized; used only within the quality pipeline.
    The AST node is read-only in practice; MUST NOT be mutated.
    """
    name: str           # "test_process"
    filename: str       # absolute path
    lineno: int
    node: ast.FunctionDef  # read-only; mutable type, so @dataclass (not frozen)
```

### taxonomy/models.py additions

```python
class AssertionKind(StrEnum):   # Python 3.11+ StrEnum (matching SideEffectType pattern)
    STDLIB_EQUALITY   = "stdlib_equality"    # assert x == y
    STDLIB_NONE_CHECK = "stdlib_none_check"  # assert x is None / is not None
    STDLIB_ERROR_CHECK = "stdlib_error_check" # assert err is None (name contains "err")
    STDLIB_TRUTH      = "stdlib_truth"       # assert x
    STDLIB_RAISES     = "stdlib_raises"      # pytest.raises / with raises(...)
    UNITTEST_EQUAL    = "unittest_equal"     # self.assertEqual
    UNITTEST_NONE     = "unittest_none"      # self.assertIsNone
    UNITTEST_RAISES   = "unittest_raises"    # self.assertRaises
    UNKNOWN           = "unknown"

@dataclass(frozen=True)
class AssertionSite:
    """Detected assertion location in a test function.

    Args:
        location: Source position as "file:line:col" (three-part, matching
            SideEffect.location format). When column is unavailable from
            the AST node, use col=0: "file:line:0".
        kind: Assertion pattern type.
        depth: 0=direct in test body, 1–3=inside helper function.
        referenced_names: Variable names referenced in the assertion expression.
            For calls (e.g., assert f() == g()), collect the function name strings.
            For subscripts (assert result[0] == 1), collect "result".
            For attribute access (assert obj.value == 42), collect "obj".
    """
    location: str
    kind: AssertionKind
    depth: int
    referenced_names: frozenset[str] = field(default_factory=frozenset)

@dataclass(frozen=True)
class TestTargetPair:
    """Pairing between a test function and its inferred target.

    Args:
        test_name: Name of the test function.
        target_name: Name of the production function (None if unmatched).
        inference_method: "name_convention" | "call_graph" | "unmatched".
        confidence: 0.0–1.0.
    """
    test_name: str
    target_name: str | None
    inference_method: str
    confidence: float

@dataclass(frozen=True)
class ContractCoverageResult:
    """Contract coverage for one test-target pair.

    Args:
        percentage: Contract coverage as percentage [0.0, 100.0], or None
            when there are no contractual effects (null-not-zero per OC-003).
            Callers passing this to gaze_crap() or quadrant() MUST divide by 100.
        covered_effects: Count of contractual effects with ≥1 mapped assertion.
        total_contractual: Total contractual effects on the target function.
        over_specification_count: Assertions that map to incidental effects.
        unmapped_assertions: Assertions that did not map to any effect.
        reason: "no_contractual_effects" | "no_effects_detected" | None.
            Set when percentage is None.
    """
    percentage: float | None      # [0.0, 100.0] or None
    covered_effects: int
    total_contractual: int
    over_specification_count: int
    unmapped_assertions: int
    reason: str | None = None     # set when percentage is None

@dataclass(frozen=True)
class QualityReport:
    """Quality assessment result for one test-target pair.

    Args:
        test_function: Name of the test function.
        target_function: Name of the target function (None if unmatched).
        assertions: Detected assertion sites in the test function.
        contract_coverage: Coverage result (None if no target found).
        warnings: Non-fatal warnings from pairing or mapping.
    """
    test_function: str
    target_function: str | None
    assertions: tuple[AssertionSite, ...]
    contract_coverage: ContractCoverageResult | None
    warnings: tuple[str, ...]
```

## A.1 — Test-Target Pairing (pairing.py)

### find_test_functions(filepath: Path) -> list[TestFunc]

Parse with `ast.parse()`. Collect top-level `FunctionDef` nodes starting with
`test_`. Also collect methods of classes named `Test*` (unittest.TestCase).

### pair_to_targets(test_func: TestFunc, source_functions: list[FunctionTarget]) -> TestTargetPair

Returns a `TestTargetPair`. If `source_functions` is empty, returns immediately
with `method="unmatched"`, `target_name=None`, `confidence=0.0`.

**Strategy 1 — Name convention** (confidence 0.9 exact, 0.7 case-insensitive):
```python
candidate = test_func.name.removeprefix("test_")
for fn in source_functions:
    if fn.name == candidate:
        return TestTargetPair(test_func.name, fn.name, "name_convention", 0.9)
for fn in source_functions:
    if fn.name.lower() == candidate.lower():
        return TestTargetPair(test_func.name, fn.name, "name_convention", 0.7)
```

**Strategy 2 — Call graph** (confidence 0.8): walk `ast.walk(test_func.node)`.
This is a **deep walk** — it finds all calls anywhere in the test function body,
including inside nested functions, comprehensions, and closures. This is
intentional: Python tests frequently call the target from within `with` blocks,
lambda expressions, or setup helpers defined inline. The deep walk is a known
approximation; when multiple source functions are found, the first one in
`ast.walk` order (pre-order, depth-first) is selected. This may produce
non-deterministic results if the source_functions set changes. Documented as
a known limitation; future improvement: restrict walk to top-level body only.

```python
source_names = {fn.name for fn in source_functions}
for node in ast.walk(test_func.node):
    if isinstance(node, ast.Call):
        called = _extract_call_name(node)
        if called and called in source_names:
            return TestTargetPair(test_func.name, called, "call_graph", 0.8)
```

**No match** (confidence 0.0):
```python
return TestTargetPair(test_func.name, None, "unmatched", 0.0)
```

`_extract_call_name(node: ast.Call) -> str | None`: returns `node.func.id` if
`node.func` is `ast.Name`, else `None` (ignores method calls and qualified names).

## A.2 — Assertion Detection (assertions.py)

### detect_assertions(test_func: TestFunc, *, pkg_ast: dict[str, ast.Module] | None = None, max_depth: int = 3) -> list[AssertionSite]

Walk `test_func.node.body`. Detect:

**ast.Assert nodes**:
```python
# assert x == y → STDLIB_EQUALITY, referenced_names from both sides
# assert x is None → STDLIB_NONE_CHECK
# assert err is None → STDLIB_ERROR_CHECK (ident name contains "err")
# assert x → STDLIB_TRUTH
```

**ast.With nodes** (context managers):
```python
# with pytest.raises(SomeError): → STDLIB_RAISES
# Look for: With(items[0].context_expr = Call(func=Attribute(attr='raises')))
```

**ast.ExprStmt → ast.Call** (method assertions):
```python
# self.assertEqual(a, b) → UNITTEST_EQUAL
# self.assertIsNone(x) → UNITTEST_NONE
# self.assertRaises(Err, fn) → UNITTEST_RAISES
```

**Helper recursion** (up to max_depth): if a call's name starts with `assert_`
or `check_`, and the function is defined in `pkg_ast` (same file or explicitly
provided module AST map), recurse at `depth+1`. Stop at `depth == max_depth`.

**First-match-wins for double classification**: each `ast.Assert` node produces
exactly one `AssertionSite`. The kind is determined by inspecting the condition
in priority order: error-check (contains "err") → none-check (is None) →
equality (BinOp or Compare) → truth (fallback).

### _extract_referenced_names(expr: ast.expr) -> frozenset[str]

Walk the expression tree collecting names:
- `ast.Name` → add `node.id`
- `ast.Attribute` → add `node.attr` AND the base name of `node.value`
- `ast.Subscript` → add the base name of `node.value` (e.g., `result` from `result[0]`)
- `ast.Call` → add the function name string (e.g., `"f"` from `f()`)

### location format

Use `"file:line:col"` (three-part, matching `SideEffect.location`). When the
AST node has no column info, use col=0: `f"{filepath}:{node.lineno}:0"`.

## A.3 — Assertion Mapping (mapper.py)

### build_call_bindings(test_func: TestFunc, target_name: str) -> dict[str, str]

Scan the test body for assignments where the right-hand side calls `target_name`:
```python
# result = target_name(...) → {"result": "return_value"}
# x, err = target_name(...) → {"x": "return_value", "err": "error_return"}
# a, b, c = target_name(...)→ {"a": "return_value", "b": "error_return"}
#                              (index 0 → return_value, index 1 → error_return,
#                               indices 2+ ignored — only first two bindings named)
# target_name(...)          → {} (void call, no binding)
```

### map_assertions_to_effects(assertions: list[AssertionSite], target: FunctionTarget, call_bindings: dict[str, str]) -> list[tuple[AssertionSite, SideEffectType | None]]

Returns a list with exactly one entry per input assertion. **First-match-wins**
across passes — once an assertion is matched, it is not re-evaluated in later
passes. This prevents double-counting when Pass 1 and Pass 2 could both match.

```python
result: list[tuple[AssertionSite, SideEffectType | None]] = []
matched: set[int] = set()  # indices of already-matched assertions

# Pass 1 — Binding match
for i, assertion in enumerate(assertions):
    for name in assertion.referenced_names:
        if name in call_bindings and i not in matched:
            role = call_bindings[name]
            if role == "return_value":
                result.append((assertion, SideEffectType.ReturnValue))
            elif role == "error_return":
                result.append((assertion, SideEffectType.ErrorReturn))
            matched.add(i)
            break

# Pass 2 — Exception match
for i, assertion in enumerate(assertions):
    if i in matched:
        continue
    if assertion.kind in (AssertionKind.STDLIB_RAISES, AssertionKind.UNITTEST_RAISES):
        result.append((assertion, SideEffectType.RaiseException))
        matched.add(i)

# Pass 3 — Name/semantic match
for i, assertion in enumerate(assertions):
    if i in matched:
        continue
    matched_effect: SideEffectType | None = None
    for effect in target.effects:
        if effect.target and any(name in effect.target
                                 for name in assertion.referenced_names):
            matched_effect = effect.type   # SideEffect.type (not effect_type)
            break
    result.append((assertion, matched_effect))  # None if no match
    matched.add(i)

return result
```

## A.4 — Contract Coverage (coverage.py)

**Per-effect classification**: `SideEffect` has no `.classification` field —
classification lives on `FunctionTarget` (last-effect-wins). For O1, each effect
must be classified individually. `compute_contract_coverage()` runs
`ClassificationEngine.classify(effect, target)` per effect to determine
contractual vs incidental status.

**Correct field name**: `SideEffect.type` (not `effect_type`).

### compute_contract_coverage(target: FunctionTarget, mapped: list[tuple[AssertionSite, SideEffectType | None]], *, config: GazeConfig) -> ContractCoverageResult

```python
from gaze_py.classify.engine import ClassificationEngine
engine = ClassificationEngine(config.contractual_threshold,
                               config.incidental_threshold)

contractual: list[SideEffect] = []
incidental_types: set[SideEffectType] = set()
for effect in target.effects:
    result = engine.classify(effect, target)
    if result.label == "contractual":
        contractual.append(effect)
    elif result.label == "incidental":
        incidental_types.add(effect.type)    # .type, not .effect_type

if not contractual:
    reason = ("no_effects_detected" if not target.effects
              else "no_contractual_effects")
    return ContractCoverageResult(
        percentage=None, covered_effects=0, total_contractual=0,
        over_specification_count=0, unmapped_assertions=0, reason=reason
    )

contractual_types = {e.type for e in contractual}  # .type, not .effect_type
covered_types = {et for _, et in mapped if et is not None}
covered_count = len(contractual_types & covered_types)
over_spec = sum(1 for _, et in mapped if et in incidental_types)
unmapped = sum(1 for _, et in mapped if et is None)

return ContractCoverageResult(
    percentage=covered_count / len(contractual_types) * 100.0,
    covered_effects=covered_count,
    total_contractual=len(contractual_types),
    over_specification_count=over_spec,
    unmapped_assertions=unmapped,
    reason=None,
)
```

Note: uses `contractual_types` (set of distinct effect types) not raw `contractual` list.
One `ReturnValue` effect counts as covered if ANY assertion maps to `ReturnValue`.

## assess() entry point (pipeline.py)

```python
def assess(
    src_path: Path,
    tests_path: Path,
    *,
    config: GazeConfig,
    target_func: str | None = None,
) -> list[QualityReport]:
    """Run the full O1 quality assessment pipeline.

    Args:
        src_path: Source directory or file to analyze.
        tests_path: Test directory or file containing test functions.
        config: GazeConfig with classification thresholds.
        target_func: If provided, restrict output to test functions that
            pair to this production function name.

    Returns:
        List of QualityReport, one per discovered test function. Returns an
        empty list if no test functions are discovered in `tests_path` —
        this is not an error.
    """
```

## A.5 — Output Wiring

### Updated `_score_target()` signature

```python
def _score_target(
    target: FunctionTarget,
    *,
    line_coverage_frac: float | None,
    config: GazeConfig,
    quality_result: ContractCoverageResult | None = None,
) -> None:
```

Existing callers (`_run_crap()`) pass no `quality_result` — the default `None`
preserves backward compatibility.

### GazeCRAP and quadrant computation (CRITICAL: unit conversion required)

```python
if quality_result is not None and quality_result.percentage is not None:
    # MUST divide by 100: ContractCoverageResult.percentage is [0,100],
    # but gaze_crap() and quadrant() take fractions [0.0, 1.0]
    contract_frac = quality_result.percentage / 100.0
    gaze_crap_score = gaze_crap(target.complexity, contract_frac)
    quad = quadrant(line_coverage_frac, contract_frac)  # quadrant() takes fractions
    strategy = fix_strategy(
        crap_score=crap_score,
        complexity=target.complexity,
        line_coverage=line_coverage_frac,
        quadrant_label=quad,
        threshold=config.crap_threshold,
        complexity_threshold=int(config.crap_threshold),
    )
    contract_coverage_pct = quality_result.percentage
    contract_coverage_reason = quality_result.reason
else:
    gaze_crap_score = None
    quad = None
    contract_coverage_pct = None
    contract_coverage_reason = (quality_result.reason
                                 if quality_result else None)

# Preserve existing pure-function fallback: if no quality result and
# the function has zero effects, keep the "no_effects_detected" reason
# that was already set by the detector pipeline.
if contract_coverage_reason is None and not target.effects:
    contract_coverage_reason = "no_effects_detected"
```

### How quality data reaches `_score_target()`

The `quality` command handler (not `_run_crap()`) calls `assess()` and builds
a lookup map, then calls a separate scoring path that injects quality results:

```python
# In the quality command handler:
quality_map: dict[str, ContractCoverageResult] = {}
reports = assess(src_path, tests_path, config=config, target_func=target_func)
for report in reports:
    if report.target_function and report.contract_coverage:
        quality_map[report.target_function] = report.contract_coverage

# Then score each production function:
for target in production_targets:
    quality_result = quality_map.get(target.name)
    _score_target(target, line_coverage_frac=None, config=config,
                  quality_result=quality_result)
```

`_run_crap()` is NOT modified — the `crap` command remains line-coverage only.
GazeCRAP is only available via the `quality` command. This separation keeps
`crap` fast (no test discovery or O1 pipeline) and `quality` comprehensive.

### `quality` CLI command text output format

The `quality` command does not run line coverage collection, so `line_coverage_frac`
is `None` for all targets. Since `quadrant()` requires both line and contract
coverage fractions, quadrant labels are ALWAYS `None` from the quality command.
The text output shows contract coverage and GazeCRAP only; there is no quadrant
column.

```
Quality Report: src/gaze_py/
────────────────────────────────────────────────────────
Function                      Contract Coverage  GazeCRAP
────────────────────────────────────────────────────────
process (← test_process)     100.0%             1.0  ← complexity=1; formula: 1²×0³+1=1
validate (← test_validate)    50.0%             3.1  ← complexity=2; formula: 4×0.125+2=2.5≈3
undertested (← test_...)       0.0%            12.0  ← complexity=3; formula: 9×1+3=12
────────────────────────────────────────────────────────
Avg contract coverage: 50.0%  GazeCRAPload: 1
```

Note: GazeCRAP formula (SC-002): complexity² × (1 − contract_frac)³ + complexity.
At 100% coverage (frac=1.0): cubic term = 0, GazeCRAP = complexity (NOT 0.0).
At 0% coverage (frac=0.0): GazeCRAP = complexity² + complexity.

CI threshold violation message (when `--min-contract-coverage` exceeded):
```
contract coverage: 50.0% avg, min 80% (FAIL)
Error: contract coverage below minimum: test_validate: 50.0% < 80%
```

### JSON output

`quality` command emits a JSON array of `QualityReport` objects (NOT wrapped
in `AnalysisResult`). Each entry uses `dataclasses.asdict()` via the existing
JSON encoder. The `SCHEMA` constant in `json_formatter.py` is updated to
reflect quality output fields when `--format=json` is used with `quality`.

### Summary population

```python
# fix_strategy_counts: aggregated from Score.fix_strategy across all targets
# (does not require O1 — populated whenever CRAP scores are available)
fix_counts: dict[str, int] = {}
for target in all_targets:
    if target.score and target.score.fix_strategy:
        fix_counts[target.score.fix_strategy] = fix_counts.get(
            target.score.fix_strategy, 0) + 1

gaze_crapload_fns = [t for t in all_targets
                     if t.score and t.score.gaze_crap is not None
                     and t.score.gaze_crap >= config.gaze_crap_threshold]

coverages = [t.score.contract_coverage for t in all_targets
             if t.score and t.score.contract_coverage is not None]
```

## Coverage Strategy

| Module | Approach | Key edge cases |
|---|---|---|
| `pairing.py` | Unit: parametrized fixture strings | empty source list, underscore names, class methods, multi-word stripping |
| `assertions.py` | Unit: inline AST parse | complex expressions (f()==g()), subscripts, attributes, helper depth limit |
| `mapper.py` | Unit: controlled effect + assertion lists | first-match-wins, double-match prevention, all-unmapped, Pass 3 contractual |
| `coverage.py` | Unit: known effect lists | zero contractual (None not 0.0), all incidental, partial |
| `pipeline.py` | Integration: testdata fixtures | simple=100%, raises=covered, undertested=0% |
| CLI `quality` | CLI runner with testdata | --tests, auto-discovery, --target, threshold, text+json format |
