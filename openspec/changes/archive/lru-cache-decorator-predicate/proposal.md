## Why

`_has_lru_cache_decorator` was added in v0.6.0 with CC=16 — four explicit `return True`
branches, one per decorator AST form. A `gazepy` self-audit of the gaze-py codebase
surfaced it as the #3 `add_tests` recommendation (CRAP=16), but the right fix is
reducing CC by extracting the per-decorator matching logic into a dedicated predicate,
not adding more tests. This is a pure mechanical refactor with no behavioral change.

## What Changes

- **New**: `_matches_cache_decorator(dec: ast.expr) -> bool` — module-level predicate
  that returns `True` if a single decorator node matches any `@lru_cache`/`@cache` form
- **Modified**: `_has_lru_cache_decorator` — body replaced with
  `return any(_matches_cache_decorator(d) for d in fn_node.decorator_list)`;
  CC drops from 16 → ~2
- No behavioral change, no API change, no test changes

## Capabilities

### New Capabilities

*(none — pure refactor)*

### Modified Capabilities

*(no spec-level requirement changes — implementation detail only)*

## Impact

- `src/gaze_py/analysis/detector.py` — ~35 lines reorganized; one function split into
  two; net line count increases by ~10 (predicate docstring)
- No other files touched
- CC of `_has_lru_cache_decorator`: 16 → 1
- CC of `_matches_cache_decorator`: ~5
- Both functions drop off the `add_tests` recommendation list
- No test changes; existing 6 decorator-form tests exercise both through
  `FileDetector.detect()`
