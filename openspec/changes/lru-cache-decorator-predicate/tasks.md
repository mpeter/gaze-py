## Convention Pack Compliance

Before implementing, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`

## 1. Refactor `detector.py`

- [x] 1.1 In `src/gaze_py/analysis/detector.py`, immediately before the existing
      `_has_lru_cache_decorator` function (currently line ~1501), insert the new
      predicate:

      ```python
      def _matches_cache_decorator(dec: ast.expr) -> bool:
          """Return True if a single decorator node matches @lru_cache or @cache.

          Handles four decorator forms:
          - @lru_cache or @cache              (bare ast.Name)
          - @lru_cache(...) or @cache(...)    (ast.Call wrapping ast.Name)
          - @functools.lru_cache or @functools.cache   (ast.Attribute)
          - @functools.lru_cache(...) or @functools.cache(...)  (ast.Call wrapping ast.Attribute)

          Note: @functools.cache() with arguments is NOT valid Python at runtime
          (functools.cache is not a decorator factory). The AST pattern is handled
          for completeness but will not appear in valid Python source.

          Args:
              dec: A single decorator expression node from fn_node.decorator_list.

          Returns:
              True if the decorator matches any lru_cache/cache form.
          """
          # Bare name: @lru_cache or @cache
          if isinstance(dec, ast.Name) and dec.id in _LRU_CACHE_DECORATORS:
              return True
          # Call form: @lru_cache(...) or @cache()
          if (
              isinstance(dec, ast.Call)
              and isinstance(dec.func, ast.Name)
              and dec.func.id in _LRU_CACHE_DECORATORS
          ):
              return True
          # Qualified: @functools.lru_cache or @functools.cache
          if (
              isinstance(dec, ast.Attribute)
              and isinstance(dec.value, ast.Name)
              and dec.value.id == "functools"
              and dec.attr in _LRU_CACHE_DECORATORS
          ):
              return True
          # Qualified call: @functools.lru_cache(...) or @functools.cache(...)
          if (
              isinstance(dec, ast.Call)
              and isinstance(dec.func, ast.Attribute)
              and isinstance(dec.func.value, ast.Name)
              and dec.func.value.id == "functools"
              and dec.func.attr in _LRU_CACHE_DECORATORS
          ):
              return True
          return False
      ```

- [x] 1.2 Replace the **entire body** of `_has_lru_cache_decorator` (keep the
      function signature and a simplified docstring; replace the `for` loop and
      all `if … return True` branches) with:

      ```python
      def _has_lru_cache_decorator(
          fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
      ) -> bool:
          """Return True if the function has an @lru_cache or @cache decorator.

          Delegates per-decorator matching to _matches_cache_decorator, which
          handles all four AST forms (bare name, call, qualified attribute,
          qualified attribute call).

          Args:
              fn_node: The function definition AST node to inspect.

          Returns:
              True if any decorator matches the lru_cache/cache pattern.
          """
          return any(_matches_cache_decorator(d) for d in fn_node.decorator_list)
      ```

## 2. CI gate

- [x] 2.1 [P] `uv run ruff check .`
- [x] 2.2 [P] `uv run ruff format --check .`
- [x] 2.3 [P] `uv run mypy --strict src/`
- [x] 2.4     `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`

<!-- spec-review: passed -->

<!-- code-review: passed -->
