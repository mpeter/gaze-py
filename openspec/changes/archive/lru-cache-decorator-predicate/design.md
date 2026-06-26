## Context

`_has_lru_cache_decorator` (added in v0.6.0, `detector.py:1501`) iterates
`fn_node.decorator_list` and checks each decorator node against four AST forms using
four sequential `if … return True` branches. The cyclomatic complexity tool counts each
branch as an independent path, yielding CC=16. The function is correct and fully
tested — the only issue is structural.

The established refactor pattern in this codebase for this exact problem is
`_handle_try_node`, which was extracted from `visit_Try`/`visit_TryStar` for the same
reason. The solution is identical: extract the per-item logic into a predicate, collapse
the outer function to a single expression.

## Goals / Non-Goals

**Goals:**
- Extract `_matches_cache_decorator(dec: ast.expr) -> bool` as a module-level predicate
- Collapse `_has_lru_cache_decorator` to `return any(_matches_cache_decorator(d) for d in fn_node.decorator_list)`
- CC of `_has_lru_cache_decorator`: 16 → 1
- CC of `_matches_cache_decorator`: ~5 (four `if` branches + implicit base)
- No behavioral change; existing tests remain valid without modification

**Non-Goals:**
- Changing detection logic
- Changing which decorator forms are matched
- Adding tests

## Decisions

### D1: Placement of `_matches_cache_decorator`

Place immediately **before** `_has_lru_cache_decorator` at the current line 1501.
Both stay in the module-level helper section between the visitor classes and
`FileDetector`. This preserves the "callee before caller" convention used by all other
module-level helpers (`_is_db_context` before `_handle_with_param`, `_extract_open_mode`
before its callers, etc.).

### D2: Predicate signature

```python
def _matches_cache_decorator(dec: ast.expr) -> bool:
```

`ast.expr` is the correct type annotation — decorator nodes are expressions. This is
consistent with `ast.FunctionDef.decorator_list`, which is typed as `list[ast.expr]`
in the typeshed stubs. `mypy --strict` requires the annotation to be present.

### D3: No change to the four AST branch logic

The four branches move verbatim from `_has_lru_cache_decorator` into
`_matches_cache_decorator`. No logic changes, no reordering, no merging of branches.
This minimises diff noise and makes the refactor trivially auditable.

### D4: `_has_lru_cache_decorator` docstring

Simplify the docstring. The detailed per-form documentation moves to
`_matches_cache_decorator`'s docstring, where it is closer to the relevant code.
The replacement retains a summary line plus `Args:` and `Returns:` sections as
required by CS-004; the implementation-detail commentary is removed.

## Risks / Trade-offs

**[Risk] Mypy sees `ast.expr` as the type for decorator nodes** →
Mitigation: verified — `ast.FunctionDef.decorator_list` is typed as `list[ast.expr]`
in the `ast` typeshed stubs. The annotation is correct.

**[Risk] CC tool may count `any()` as a branch** →
Mitigation: `any()` with a generator expression adds one branch to the CC counter
(the generator's implicit `if`), so `_has_lru_cache_decorator` ends at CC=2, not CC=1.
Still a major improvement from 16; both functions remain well under the project's
noqa threshold.
