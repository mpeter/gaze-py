# Spec: complexity-algorithm

Authoritative requirements for the McCabe cyclomatic complexity algorithm
in gaze-py. Sources: porting contracts (CX-001, CX-002 from the
effect-confidence-range change), and the current `analysis/complexity.py`
implementation.

---

### Requirement: CX-001 Complexity Node Specification

The `cyclomatic_complexity()` function in `analysis/complexity.py` MUST
implement the McCabe algorithm with exactly these rules:

**Baseline**: every function starts at complexity 1. The minimum possible
complexity for any function is 1.

**Increment nodes** — each occurrence of the following AST node types adds
to the complexity counter:

| AST Node | Increment | Notes |
|----------|-----------|-------|
| `ast.If` | +1 | Each `if` and each `elif` (+1 each; `elif` is a nested `ast.If` in Python's AST — there is no `ast.ElIf` node) |
| `ast.For` | +1 | Each `for` loop body |
| `ast.While` | +1 | Each `while` loop |
| `ast.ExceptHandler` | +1 | Each `except` clause |
| `ast.With` | +len(items) | Each **item** in the `with` statement; `with a, b:` → +2 |
| `ast.Assert` | +1 | Each `assert` statement |
| `ast.BoolOp` | +len(values) - 1 | One per additional operand: `a and b` → +1; `a and b and c` → +2 |
| Comprehension `if`-filters | +1 per filter | Each `if` clause per generator in list/set/dict comprehensions and generator expressions |

**NOT counted** (these nodes do NOT increment complexity):
- `ast.IfExp` — ternary expressions (`x if cond else y`)
- `else` and `finally` clauses
- `lambda` expressions
- `return` statements
- `match`/`case` statements (Python 3.10+)
- `try` itself (only `except` handlers are counted, not the `try` node)

**Nested scope rule**: nested `FunctionDef` and `AsyncFunctionDef` nodes are
excluded from the outer function's count. Each nested function is scored
independently. The outer function's complexity does NOT include decision points
inside inner functions.

#### Scenario: Baseline — empty function
- **WHEN** `cyclomatic_complexity()` is called on `def f(): pass`
- **THEN** the result is 1

#### Scenario: Single if statement
- **WHEN** `cyclomatic_complexity()` is called on a function with one `if` statement
- **THEN** the result is 2 (1 base + 1 for if)

#### Scenario: elif counted separately
- **WHEN** `cyclomatic_complexity()` is called on a function with `if ... elif ... else ...`
- **THEN** the result is 3 (1 base + 1 for if + 1 for elif)

#### Scenario: Assert increments complexity
- **WHEN** `cyclomatic_complexity()` is called on `def f(x): assert x > 0; return x`
- **THEN** the result is 2 (1 base + 1 for assert)

#### Scenario: Multi-item with statement
- **WHEN** `cyclomatic_complexity()` is called on:
  ```python
  def f():
      with a() as x, b() as y:
          pass
  ```
- **THEN** the result is 3 (1 base + 2 for two with-items)

#### Scenario: Multiple except handlers
- **WHEN** `cyclomatic_complexity()` is called on:
  ```python
  def f():
      try:
          pass
      except A:
          pass
      except B:
          pass
  ```
- **THEN** the result is 3 (1 base + 1 for except A + 1 for except B)

#### Scenario: Boolean operator — and
- **WHEN** `cyclomatic_complexity()` is called on `def f(a, b, c): return a and b and c`
- **THEN** the result is 3 (1 base + 2 for BoolOp with 3 values: len(values)-1 = 2)

#### Scenario: Comprehension if-filters
- **WHEN** `cyclomatic_complexity()` is called on:
  `def f(items): return [x for x in items if x > 0 if x < 10]`
- **THEN** the result is 3 (1 base + 2 for two if-filters in the generator)

#### Scenario: Ternary NOT counted
- **WHEN** `cyclomatic_complexity()` is called on `def f(x): return x if x > 0 else 0`
- **THEN** the result is 1 (ternary `ast.IfExp` is not counted)

---

### Requirement: CX-002 Round-Trip Reference Values

The following input patterns MUST have dedicated tests asserting the exact
expected complexity value. Tests MUST use `@pytest.mark.parametrize`.

| Input pattern | Expected complexity |
|---------------|---------------------|
| `def f(x): assert x > 0; return x` | 2 |
| `def f():\n    with a() as x, b() as y:\n        pass` | 3 |
| `def f():\n    try:\n        pass\n    except A:\n        pass\n    except B:\n        pass` | 3 |
| `def f(a, b, c): return a and b and c` | 3 (1 base + BoolOp with 3 values → +2) |
| `def f(items): return [x for x in items if x > 0 if x < 10]` | 3 |
| `inner` function from an outer/inner nested fixture | 3 (scored independently) |
| `high_complexity.py` fixture | exactly 9 (1 base + 8 decision points) |

#### Scenario: Assert reference value
- **WHEN** `cyclomatic_complexity()` is called on `def f(x): assert x > 0; return x`
- **THEN** the result is exactly 2

#### Scenario: Multi-item with reference value
- **WHEN** `cyclomatic_complexity()` is called on `def f():\n    with a() as x, b() as y:\n        pass`
- **THEN** the result is exactly 3

#### Scenario: Two except handlers reference value
- **WHEN** `cyclomatic_complexity()` is called on a function with two `except` clauses
- **THEN** the result is exactly 3

#### Scenario: Boolean and with three operands
- **WHEN** `cyclomatic_complexity()` is called on `def f(a, b, c): return a and b and c`
- **THEN** the result is exactly 3

#### Scenario: Comprehension with two if-filters
- **WHEN** `cyclomatic_complexity()` is called on
  `def f(items): return [x for x in items if x > 0 if x < 10]`
- **THEN** the result is exactly 3

#### Scenario: high_complexity.py fixture
- **WHEN** `cyclomatic_complexity()` is called on the `high_complexity.py` testdata fixture
- **THEN** the result is exactly 9

---

### Requirement: Nested Scope Independence

Nested `FunctionDef` and `AsyncFunctionDef` nodes MUST be excluded from the
outer function's complexity count. Each function is scored independently.

The implementation MUST track nesting depth and skip visiting nested function
bodies when depth > 0.

#### Scenario: Inner function scored independently
- **WHEN** `cyclomatic_complexity()` is called on the `inner` function from
  an outer/inner fixture (where `inner` has its own decision points)
- **THEN** the result reflects only `inner`'s own decision points, not `outer`'s

#### Scenario: Outer function unaffected by inner complexity
- **WHEN** `cyclomatic_complexity()` is called on `outer` from an outer/inner fixture
  where `inner` has 5 decision points
- **THEN** `outer`'s complexity does NOT include `inner`'s 5 decision points

---

### Requirement: Complexity Floor

The complexity of any function MUST be at least 1. The algorithm MUST NOT
return 0 for any valid function definition.

#### Scenario: Minimum complexity
- **WHEN** `cyclomatic_complexity()` is called on any valid function definition
- **THEN** the result is >= 1

#### Scenario: Pure function complexity
- **WHEN** `cyclomatic_complexity()` is called on a function with body `pass`
  and no decision points
- **THEN** the result is exactly 1

---

### Requirement: Complexity Used in Scoring

The complexity value computed by `cyclomatic_complexity()` is the `complexity`
input to both the CRAP formula (SC-001) and the GazeCRAP formula (SC-002).
The complexity value MUST be an integer >= 1.

#### Scenario: Complexity feeds CRAP formula
- **WHEN** a `FunctionTarget` is scored
- **THEN** the `complexity` field in the output equals the value returned by
  `cyclomatic_complexity()` for that function's AST node

#### Scenario: Complexity is always a positive integer
- **WHEN** `cyclomatic_complexity()` is called on any valid function
- **THEN** the return type is `int` and the value is >= 1
