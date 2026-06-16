## ADDED Requirements

### Requirement: visit_AsyncFunctionDef depth guard prevents double-counting
Tests MUST verify that a nested `async def` inside another function is scored independently, not counted as part of the outer function's complexity.

#### Scenario: Async outer and async inner are scored independently
- **WHEN** an async function contains a nested async inner function
- **THEN** `cyclomatic_complexity(outer_node)` counts only the outer function's own decision points
- **AND** `cyclomatic_complexity(inner_node)` counts only the inner function's own decision points

### Requirement: Set comprehension if-filters increment complexity
Tests MUST verify that each `if`-filter in a set comprehension adds one to the cyclomatic complexity.

#### Scenario: Set comprehension with one if-filter
- **WHEN** a function contains `{x for x in lst if x > 0}`
- **THEN** `cyclomatic_complexity` returns 2 (1 base + 1 for the if-filter)

### Requirement: Dict comprehension if-filters increment complexity
Tests MUST verify that each `if`-filter in a dict comprehension adds one to the cyclomatic complexity.

#### Scenario: Dict comprehension with one if-filter
- **WHEN** a function contains `{k: v for k, v in d.items() if k}`
- **THEN** `cyclomatic_complexity` returns 2 (1 base + 1 for the if-filter)

### Requirement: Generator expression if-filters increment complexity
Tests MUST verify that each `if`-filter in a generator expression adds one to the cyclomatic complexity.

#### Scenario: Generator expression with one if-filter
- **WHEN** a function contains `sum(x for x in lst if x > 0)`
- **THEN** `cyclomatic_complexity` returns 2 (1 base + 1 for the if-filter)

## Porting Contract Compliance

All four requirements above conform to porting contract **CX-002** (cyclomatic complexity scoring). Each test MUST reference CX-002 in its docstring's first line:
```python
"""CX-002: <description of what this tests>."""
```
