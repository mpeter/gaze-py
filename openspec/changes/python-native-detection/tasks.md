<!--
  [P] marks tasks eligible for parallel execution.
  Tasks without [P] run sequentially first, then [P] tasks run in parallel.
  Do NOT add [P] when tasks modify the same file.
-->

## Convention Pack Compliance

Before implementing any task, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`

## 1. New constants and helpers in detector.py

- [ ] 1.1 In `src/gaze_py/analysis/detector.py`, add to the constants section
      after `_GOROUTINE_SPAWN_CALLS`:

      ```python
      # Qualified names for GoroutineSpawn — subprocess module (separate from
      # _GOROUTINE_SPAWN_CALLS to keep OS-process spawning semantically distinct
      # from thread/coroutine spawning). concurrent.futures executor constructors
      # are deferred — they require chained-attribute obj_name handling.
      _SUBPROCESS_SPAWN_CALLS: frozenset[tuple[str, str]] = frozenset(
          {
              ("subprocess", "Popen"),
              ("subprocess", "run"),
              ("subprocess", "call"),
              ("subprocess", "check_output"),
              ("subprocess", "check_call"),
          }
      )

      # Decorator names (bare and qualified) that indicate lru_cache/cache decoration
      _LRU_CACHE_DECORATORS: frozenset[str] = frozenset({"lru_cache", "cache"})
      ```

- [ ] 1.2 Add `_is_db_context` as a module-level function alongside the other
      module-level helpers (`_extract_open_mode`, `_collect_return_names_excluding_finally`),
      after the visitor classes and before `FileDetector`:

      ```python
      def _is_db_context(name: str) -> bool:
          """Return True if the parameter name suggests a database connection context.

          Uses word-part split on underscores plus substring check for compound words.
          Avoids the ctx→tx false positive (ctx → parts ["ctx"] → no match).

          `session` is excluded from the word-part set: `session_id` is a common
          HTTP/user session identifier (a string), not a DB connection — including it
          would produce DatabaseTransaction false positives in web framework code.
          `db` is word-part only (not substring) to avoid matching `debug`.
          `dbConn` (camelCase, no underscore) → False — accepted limitation.

          Examples:
              _is_db_context("conn")        → True
              _is_db_context("db_conn")     → True   (word parts: "db" and "conn" match)
              _is_db_context("my_db")       → True   (word part "db" matches)
              _is_db_context("session_id")  → False  ("session" not in word-part set)
              _is_db_context("ctx")         → False  ("ctx" not in set)
              _is_db_context("lock")        → False
              _is_db_context("dbConn")      → False  (camelCase — accepted gap)
          """
          parts = set(name.lower().split("_"))
          if parts & {"conn", "connection", "tx", "transaction", "db"}:
              return True
          # Substring check for camelCase or unsplit compound words (e.g. dbConnection)
          for kw in ("conn", "connection", "transaction"):
              if kw in name.lower():
                  return True
          return False
      ```

## 2. subprocess → GoroutineSpawn

- [ ] 2.1 In `_handle_goroutine_process_time`, add after the existing
      `GoroutineSpawn` (`_GOROUTINE_SPAWN_CALLS`) detection block and
      before the `concurrent.futures.*.submit` block:

      ```python
      # GoroutineSpawn: subprocess.Popen/run/call/check_output/check_call
      if obj_name is not None and (obj_name, method) in _SUBPROCESS_SPAWN_CALLS:
          self._add(
              SideEffectType.GoroutineSpawn,
              node,
              f"Function spawns a child process via {obj_name}.{method}()",
          )
          self.generic_visit(node)
          return True
      ```

      `_handle_goroutine_process_time` already carries `# noqa: PLR0911` at
      its definition. The existing suppression covers this additional return
      point — no new noqa comment is needed.

## 3. async with param → MutexOp / DatabaseTransaction; align visit_With

- [ ] 3.1 In `visit_AsyncWith`, add param-based lock detection immediately
      **before** the existing TaskGroup detection loop. Use `_is_db_context`
      (added in task 1.2) instead of an inline name set. The full method becomes:

      ```python
      def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802
          """Detect WaitGroupOp and MutexOp/DatabaseTransaction from async with patterns.

          Param-based patterns (async with lock:, async with conn:):
              Uses _is_db_context() heuristic — conn/connection/tx/db names
              → DatabaseTransaction; all others → MutexOp. Param-only: local
              variables do not trigger these effects.

          TaskGroup pattern:
              async with asyncio.TaskGroup() as tg: → WaitGroupOp.

          The two branches use `elif` because a single context manager expression
          cannot be both an ast.Name (param-based) and an ast.Call (TaskGroup) —
          they are mutually exclusive by AST node type. `break` exits the item
          loop after the first TaskGroup match (only one TaskGroup is expected per
          async with). Known limitation: items after a TaskGroup in the same
          async with statement are not inspected (see design.md Risks).

          Alias limitation: only detects asyncio.TaskGroup(), not aio.TaskGroup().
          """
          for item in node.items:
              ctx = item.context_expr
              # Param-based async context managers — same heuristic as visit_With
              if isinstance(ctx, ast.Name) and ctx.id in self._params:
                  if _is_db_context(ctx.id):
                      self._add(
                          SideEffectType.DatabaseTransaction,
                          node,
                          f"Function uses a database connection as an async context manager via {ctx.id}",
                      )
                  else:
                      self._add(
                          SideEffectType.MutexOp,
                          node,
                          f"Function acquires a lock/mutex via 'async with {ctx.id}:'",
                      )
              # TaskGroup pattern — WaitGroupOp
              elif (
                  isinstance(ctx, ast.Call)
                  and isinstance(ctx.func, ast.Attribute)
                  and isinstance(ctx.func.value, ast.Name)
                  and ctx.func.value.id == "asyncio"
                  and ctx.func.attr == "TaskGroup"
              ):
                  self._add(
                      SideEffectType.WaitGroupOp,
                      node,
                      "Function synchronizes tasks via async with asyncio.TaskGroup()",
                  )
                  break
          self.generic_visit(node)
      ```

      **Note**: the TaskGroup check now uses `elif` (not a separate loop with
      `break`) to avoid double-processing items. The `break` on TaskGroup match
      still exits the item loop after finding the first TaskGroup.

- [ ] 3.2 In `visit_With`, replace the inline connection-name set with
      `_is_db_context` to align the sync heuristic with the async one:

      ```python
      # Before (exact-set):
      if ctx.id in {"connection", "conn", "session", "tx", "transaction"}:

      # After (shared helper):
      if _is_db_context(ctx.id):
      ```

      All existing fixture param names (`connection`, `conn`, `lock`) classify
      identically — no existing tests break. This is a pure refactor within the
      sync path; the docstring for `visit_With` should be updated to mention
      `_is_db_context` in place of the inline set description.

## 4. atexit.register() → GlobalMutation

- [ ] 4.1 In `_handle_lib_attr_call`, add after the `FinalizerRegistration`
      (`weakref.finalize`) block and before the `CgoCall` block:

      ```python
      # GlobalMutation: atexit.register() — mutates interpreter shutdown handler list
      if obj_name == "atexit" and method == "register":
          self._add(
              SideEffectType.GlobalMutation,
              node,
              "Function registers a shutdown callback via atexit.register()"
              " (mutates interpreter-global atexit handler list)",
          )
          self.generic_visit(node)
          return True
      ```

      **CC note**: After adding atexit and warnings blocks (tasks 4.1 and 5.1),
      verify the cyclomatic complexity of `_handle_lib_attr_call`. It currently
      has ~7 branches and already carries `# noqa: PLR0911`. If CC exceeds 10
      after both additions, extract a `_handle_stdlib_mutation_call` helper and
      add a task for it before proceeding.

## 5. warnings.warn() → LogWrite + GlobalMutation

- [ ] 5.1 In `_handle_lib_attr_call`, add after the `LogWrite` (`_LOG_NAMES`)
      block:

      ```python
      # warnings.warn() — two effects:
      # (1) LogWrite: structured, filterable developer-facing warning emission
      # (2) GlobalMutation: typically writes to __warningregistry__ in the calling
      #     module's globals for deduplication (filter-configuration dependent)
      if obj_name == "warnings" and method == "warn":
          self._add(
              SideEffectType.LogWrite,
              node,
              "Function emits a warning via warnings.warn()"
              " (structured developer-facing output; may go to stderr, logging, or be suppressed)",
          )
          self._add(
              SideEffectType.GlobalMutation,
              node,
              "Function typically mutates __warningregistry__ in the calling module"
              " via warnings.warn() (deduplication state; filter-configuration dependent)",
          )
          self.generic_visit(node)
          return True
      ```

      **Note on two `_add` calls before `return True`**: `_add` appends to
      `self._effects` without short-circuiting. Both effects are correctly
      emitted. The `return True` short-circuits the dispatch chain (prevents
      other handlers from also firing on this node), NOT the `_add` calls.

## 6. @lru_cache / @cache → GlobalMutation

- [ ] 6.1 Add a module-level helper function `_has_lru_cache_decorator` to
      `src/gaze_py/analysis/detector.py`, alongside the other module-level
      helpers (`_extract_open_mode`, `_collect_return_names_excluding_finally`),
      after the visitor classes and before `FileDetector`:

      ```python
      def _has_lru_cache_decorator(
          fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
      ) -> bool:
          """Return True if the function has an @lru_cache or @cache decorator.

          Handles four decorator forms:
          - @lru_cache        (bare name)
          - @lru_cache(...)   (call form)
          - @functools.lru_cache      (qualified attribute)
          - @functools.lru_cache(...) (qualified attribute call)
          Same for @cache / @functools.cache.

          Args:
              fn_node: The function definition AST node to inspect.

          Returns:
              True if any decorator matches the lru_cache/cache pattern.
          """
          for dec in fn_node.decorator_list:
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

- [ ] 6.2 In `FileDetector.detect()`, in the per-function loop (`for fn_node
      in ast.walk(module):`), add lru_cache detection immediately after
      `effects.extend(visitor.effects)` and before `complexity =
      cyclomatic_complexity(fn_node)`:

      ```python
      # GlobalMutation: @lru_cache / @functools.cache decorator
      # The cache dict is attached to the function object at decoration time
      # and persists across all callers (functionally global mutable state).
      if _has_lru_cache_decorator(fn_node):
          effects.append(
              _make_effect(
                  rel_path=rel_path,
                  fn_name=fn_name,
                  effect_type=SideEffectType.GlobalMutation,
                  node=fn_node,
                  description=(
                      "Function is decorated with @lru_cache/@cache —"
                      " memoization cache is persistent global mutable state"
                      " shared across all callers"
                  ),
              )
          )
      ```

## 7. Fixture file

- [ ] 7.1 Create `tests/testdata/analysis/python_native.py`:

      ```python
      # ruff: noqa
      """Fixture for Python-native detection patterns.

      Covers: subprocess GoroutineSpawn, async-with MutexOp,
      atexit GlobalMutation, warnings LogWrite+GlobalMutation,
      lru_cache GlobalMutation.
      """
      import asyncio
      import atexit
      import subprocess
      import warnings
      from functools import lru_cache, cache


      # --- GoroutineSpawn: subprocess ---

      def spawn_popen() -> None:
          """subprocess.Popen — GoroutineSpawn."""
          subprocess.Popen(["ls", "-la"])


      def spawn_run() -> None:
          """subprocess.run — GoroutineSpawn."""
          subprocess.run(["echo", "hello"])


      def spawn_call() -> None:
          """subprocess.call — GoroutineSpawn."""
          subprocess.call(["true"])


      def spawn_check_output() -> str:
          """subprocess.check_output — GoroutineSpawn."""
          return subprocess.check_output(["date"]).decode()


      def spawn_check_call() -> None:
          """subprocess.check_call — GoroutineSpawn."""
          subprocess.check_call(["true"])


      # --- MutexOp: async with param ---

      async def async_lock(lock) -> None:
          """async with lock: — MutexOp."""
          async with lock:
              pass


      async def async_mutex(mutex) -> None:
          """async with mutex: — MutexOp."""
          async with mutex:
              pass


      async def async_sem(sem) -> None:
          """async with sem: — MutexOp (not a connection name → MutexOp by default)."""
          async with sem:
              pass


      async def async_conn(conn) -> None:
          """async with conn: — DatabaseTransaction."""
          async with conn:
              pass


      async def async_session(session) -> None:
          """async with session: — DatabaseTransaction."""
          async with session:
              pass


      async def async_db_conn(db_conn) -> None:
          """async with db_conn: — DatabaseTransaction (word-part 'db' match)."""
          async with db_conn:
              pass


      def sync_db_conn(db_conn) -> None:
          """with db_conn: — DatabaseTransaction via _is_db_context (regression)."""
          with db_conn:
              pass


      def sync_ctx_not_db(ctx) -> None:
          """with ctx: — MutexOp, NOT DatabaseTransaction (ctx excluded from heuristic)."""
          with ctx:
              pass


      # --- GlobalMutation: atexit ---

      def register_shutdown(cleanup) -> None:
          """atexit.register — GlobalMutation."""
          atexit.register(cleanup)


      def register_lambda_shutdown() -> None:
          """atexit.register with lambda — GlobalMutation."""
          atexit.register(lambda: None)


      # --- LogWrite + GlobalMutation: warnings ---

      def emit_warning() -> None:
          """warnings.warn — LogWrite + GlobalMutation."""
          warnings.warn("this is deprecated", DeprecationWarning)


      # --- GlobalMutation: lru_cache decorator ---

      @lru_cache
      def cached_compute(n: int) -> int:
          """@lru_cache bare — GlobalMutation."""
          return n * n


      @lru_cache(maxsize=128)
      def cached_fetch(url: str) -> str:
          """@lru_cache call form — GlobalMutation."""
          return url


      @cache
      def cached_memoized(x: int) -> int:
          """@cache bare — GlobalMutation."""
          return x + 1


      def not_cached(n: int) -> int:
          """No decorator — NOT GlobalMutation from lru_cache."""
          return n * n
      ```

## 8. Tests

- [ ] 8.1 [P] In `tests/test_detector.py`, append new test section for
      subprocess GoroutineSpawn:

      ```python
      # ---------------------------------------------------------------------------
      # Python-native detection — subprocess GoroutineSpawn
      # ---------------------------------------------------------------------------

      def test_subprocess_popen_is_goroutine_spawn() -> None:
          """subprocess.Popen → GoroutineSpawn."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "spawn_popen")
          assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


      def test_subprocess_run_is_goroutine_spawn() -> None:
          """subprocess.run → GoroutineSpawn."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "spawn_run")
          assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


      def test_subprocess_call_is_goroutine_spawn() -> None:
          """subprocess.call → GoroutineSpawn."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "spawn_call")
          assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


      def test_subprocess_check_output_is_goroutine_spawn() -> None:
          """subprocess.check_output → GoroutineSpawn."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "spawn_check_output")
          assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


      def test_subprocess_check_call_is_goroutine_spawn() -> None:
          """subprocess.check_call → GoroutineSpawn."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "spawn_check_call")
          assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)
      ```

- [ ] 8.2 [P] Append tests for async with MutexOp / DatabaseTransaction:

      ```python
      # ---------------------------------------------------------------------------
      # Python-native detection — async with MutexOp / DatabaseTransaction
      # ---------------------------------------------------------------------------

      def test_async_with_lock_is_mutex_op() -> None:
          """async with lock (param) → MutexOp."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "async_lock")
          assert any(e.type == SideEffectType.MutexOp for e in fn.effects)


      def test_async_with_mutex_is_mutex_op() -> None:
          """async with mutex (param) → MutexOp."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "async_mutex")
          assert any(e.type == SideEffectType.MutexOp for e in fn.effects)


      def test_async_with_sem_is_mutex_op() -> None:
          """async with sem (param) → MutexOp (not a connection name → MutexOp by default)."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "async_sem")
          assert any(e.type == SideEffectType.MutexOp for e in fn.effects)


      def test_async_with_conn_is_database_transaction() -> None:
          """async with conn (param) → DatabaseTransaction."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "async_conn")
          assert any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


      def test_async_with_session_is_database_transaction() -> None:
          """async with session (param) → DatabaseTransaction."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "async_session")
          assert any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


      def test_async_with_db_conn_is_database_transaction() -> None:
          """async with db_conn (param, word-part 'db' match) → DatabaseTransaction."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "async_db_conn")
          assert any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


      def test_async_with_db_conn_not_mutex_op() -> None:
          """async with db_conn → DatabaseTransaction, NOT MutexOp."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "async_db_conn")
          assert not any(e.type == SideEffectType.MutexOp for e in fn.effects)


      def test_sync_with_db_conn_is_database_transaction() -> None:
          """with db_conn (sync) → DatabaseTransaction via _is_db_context (regression)."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "sync_db_conn")
          assert any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


      def test_sync_with_ctx_is_not_database_transaction() -> None:
          """with ctx (sync) → NOT DatabaseTransaction (ctx excluded from _is_db_context)."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "sync_ctx_not_db")
          assert not any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


      def test_async_with_non_param_does_not_emit_mutex(tmp_path: Path) -> None:
          """async with non-param local var → no MutexOp (not a parameter)."""
          source = textwrap.dedent("""
              import asyncio
              async def f():
                  lock = asyncio.Lock()
                  async with lock:
                      pass
          """)
          path = tmp_path / "async_local.py"
          path.write_text(source)
          targets = FileDetector.detect(path, root=tmp_path)
          fn = next(t for t in targets if t.name == "f")
          assert not any(e.type == SideEffectType.MutexOp for e in fn.effects)
      ```

- [ ] 8.3 [P] Append tests for atexit GlobalMutation:

      ```python
      # ---------------------------------------------------------------------------
      # Python-native detection — atexit GlobalMutation
      # ---------------------------------------------------------------------------

      def test_atexit_register_is_global_mutation() -> None:
          """atexit.register → GlobalMutation."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "register_shutdown")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_atexit_register_lambda_is_global_mutation() -> None:
          """atexit.register(lambda) → GlobalMutation."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "register_lambda_shutdown")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_atexit_register_not_finalizer_registration() -> None:
          """atexit.register → NOT FinalizerRegistration."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "register_shutdown")
          assert not any(e.type == SideEffectType.FinalizerRegistration for e in fn.effects)


      def test_atexit_register_not_callback_invocation() -> None:
          """atexit.register → NOT CallbackInvocation (registers, does not invoke)."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "register_shutdown")
          assert not any(e.type == SideEffectType.CallbackInvocation for e in fn.effects)


      def test_atexit_unregister_not_global_mutation(tmp_path: Path) -> None:
          """atexit.unregister → NOT GlobalMutation (only .register is detected)."""
          source = textwrap.dedent("""
              import atexit
              def cancel_shutdown(cleanup):
                  atexit.unregister(cleanup)
          """)
          path = tmp_path / "atexit_unreg.py"
          path.write_text(source)
          targets = FileDetector.detect(path, root=tmp_path)
          fn = next(t for t in targets if t.name == "cancel_shutdown")
          assert not any(e.type == SideEffectType.GlobalMutation for e in fn.effects)
      ```

- [ ] 8.4 [P] Append tests for warnings.warn() LogWrite + GlobalMutation:

      ```python
      # ---------------------------------------------------------------------------
      # Python-native detection — warnings.warn LogWrite + GlobalMutation
      # ---------------------------------------------------------------------------

      def test_warnings_warn_emits_log_write() -> None:
          """warnings.warn → LogWrite."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "emit_warning")
          assert any(e.type == SideEffectType.LogWrite for e in fn.effects)


      def test_warnings_warn_emits_global_mutation() -> None:
          """warnings.warn → GlobalMutation (__warningregistry__)."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "emit_warning")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_warnings_warn_emits_exactly_one_each_with_distinct_ids() -> None:
          """warnings.warn → exactly one LogWrite AND one GlobalMutation, distinct IDs (EC-003)."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "emit_warning")
          log_effects = [e for e in fn.effects if e.type == SideEffectType.LogWrite]
          mut_effects = [e for e in fn.effects if e.type == SideEffectType.GlobalMutation]
          assert len(log_effects) == 1, f"Expected 1 LogWrite, got {len(log_effects)}"
          assert len(mut_effects) == 1, f"Expected 1 GlobalMutation, got {len(mut_effects)}"
          assert log_effects[0].id != mut_effects[0].id, "Effects from same node must have distinct IDs (EC-003)"


      def test_warnings_warn_with_stacklevel_emits_both_effects(tmp_path: Path) -> None:
          """warnings.warn(..., stacklevel=2) → both LogWrite and GlobalMutation."""
          source = textwrap.dedent("""
              import warnings
              def warn_stacklevel():
                  warnings.warn("deprecated", stacklevel=2)
          """)
          path = tmp_path / "warn_stacklevel.py"
          path.write_text(source)
          targets = FileDetector.detect(path, root=tmp_path)
          fn = next(t for t in targets if t.name == "warn_stacklevel")
          assert any(e.type == SideEffectType.LogWrite for e in fn.effects)
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_warnings_warn_not_finalizer_or_callback(tmp_path: Path) -> None:
          """warnings.warn → NOT FinalizerRegistration or CallbackInvocation."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "emit_warning")
          assert not any(e.type == SideEffectType.FinalizerRegistration for e in fn.effects)
          assert not any(e.type == SideEffectType.CallbackInvocation for e in fn.effects)
      ```

- [ ] 8.5 [P] Append tests for @lru_cache GlobalMutation:

      ```python
      # ---------------------------------------------------------------------------
      # Python-native detection — @lru_cache GlobalMutation
      # ---------------------------------------------------------------------------

      def test_lru_cache_bare_is_global_mutation() -> None:
          """@lru_cache (bare) → GlobalMutation."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "cached_compute")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_lru_cache_call_form_is_global_mutation() -> None:
          """@lru_cache(maxsize=128) → GlobalMutation."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "cached_fetch")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_cache_decorator_is_global_mutation() -> None:
          """@cache → GlobalMutation."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "cached_memoized")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_uncached_function_not_global_mutation_from_decorator() -> None:
          """Plain function with no cache decorator → no lru_cache GlobalMutation."""
          targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
          fn = next(t for t in targets if t.name == "not_cached")
          # May have other GlobalMutation effects but NOT from lru_cache
          lru_effects = [
              e for e in fn.effects
              if e.type == SideEffectType.GlobalMutation
              and "lru_cache" in e.description
          ]
          assert len(lru_effects) == 0


      def test_functools_lru_cache_qualified_form(tmp_path: Path) -> None:
          """@functools.lru_cache → GlobalMutation."""
          source = textwrap.dedent("""
              import functools
              @functools.lru_cache
              def f(x: int) -> int:
                  return x * x
          """)
          path = tmp_path / "qualified_cache.py"
          path.write_text(source)
          targets = FileDetector.detect(path, root=tmp_path)
          fn = next(t for t in targets if t.name == "f")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_functools_lru_cache_call_form_is_global_mutation(tmp_path: Path) -> None:
          """@functools.lru_cache(maxsize=None) → GlobalMutation."""
          source = textwrap.dedent("""
              import functools
              @functools.lru_cache(maxsize=None)
              def f(x: int) -> int:
                  return x * x
          """)
          path = tmp_path / "qualified_cache_call.py"
          path.write_text(source)
          targets = FileDetector.detect(path, root=tmp_path)
          fn = next(t for t in targets if t.name == "f")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_functools_cache_qualified_form_is_global_mutation(tmp_path: Path) -> None:
          """@functools.cache → GlobalMutation."""
          source = textwrap.dedent("""
              import functools
              @functools.cache
              def f(x: int) -> int:
                  return x * x
          """)
          path = tmp_path / "qualified_cache_bare.py"
          path.write_text(source)
          targets = FileDetector.detect(path, root=tmp_path)
          fn = next(t for t in targets if t.name == "f")
          assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


      def test_lru_cache_effect_on_definition_not_call_site(tmp_path: Path) -> None:
          """@lru_cache effect attributed to decorated fn, NOT to its callers."""
          source = textwrap.dedent("""
              from functools import lru_cache
              @lru_cache
              def compute(x: int) -> int:
                  return x * x
              def caller_a() -> int:
                  return compute(1)
              def caller_b() -> int:
                  return compute(2)
              def caller_c() -> int:
                  return compute(3)
          """)
          path = tmp_path / "cache_call_site.py"
          path.write_text(source)
          targets = FileDetector.detect(path, root=tmp_path)
          compute_fn = next(t for t in targets if t.name == "compute")
          assert any(e.type == SideEffectType.GlobalMutation for e in compute_fn.effects)
          for caller in ("caller_a", "caller_b", "caller_c"):
              caller_fn = next(t for t in targets if t.name == caller)
              lru_effects = [
                  e for e in caller_fn.effects
                  if e.type == SideEffectType.GlobalMutation and "lru_cache" in e.description
              ]
              assert len(lru_effects) == 0, f"{caller} should not have lru_cache GlobalMutation"
      ```

## 9. CHANGELOG + version bump

- [ ] 9.1 Bump version `0.5.2` → `0.5.3` in `pyproject.toml` and
      `src/gaze_py/__init__.py`. Verify the current version in `pyproject.toml`
      before bumping — this spec was written against `0.5.2`.

- [ ] 9.2 Append the following at the end of the current `## [Unreleased]` block
      in `CHANGELOG.md` (after any existing `### Specs` reference):

      ```
      ### Added
      - `subprocess.Popen`, `subprocess.run`, `subprocess.call`,
        `subprocess.check_output`, `subprocess.check_call` detected as
        `GoroutineSpawn` (P2). OS child processes are concurrent tasks per EC-005.
      - `async with param:` patterns detected as `MutexOp` (P3) or
        `DatabaseTransaction` (P2), using the `_is_db_context` name heuristic.
        Closes the known gap documented in `visit_AsyncWith`.
      - `atexit.register()` detected as `GlobalMutation` (P1). Registering a
        shutdown callback mutates the interpreter-global atexit handler list.
      - `warnings.warn()` detected as `LogWrite` (P2) + `GlobalMutation` (P1).
        Warnings are a structured filterable developer output channel; they also
        typically write to `__warningregistry__` in the calling module's globals.
      - `@lru_cache` / `@functools.lru_cache` / `@cache` / `@functools.cache`
        decorated functions detected as `GlobalMutation` (P1). The memoization
        cache is persistent global-like state shared across all callers.

      ### Changed
      - `with param:` (synchronous) connection detection now uses the shared
        `_is_db_context` helper, aligning sync and async heuristics. Compound
        names like `db_conn` now correctly classify as `DatabaseTransaction`.
        Existing fixture param names (`connection`, `conn`, `lock`) are unaffected.

      ### Specs
      - `openspec/changes/python-native-detection/specs/`
      ```

## 10. CI gate

- [ ] 10.1 [P] `uv run ruff check .`
- [ ] 10.2 [P] `uv run ruff format --check .`
- [ ] 10.3 [P] `uv run mypy --strict src/`
- [ ] 10.4     `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`

## 11. Archive return-none-annotation

The `return-none-annotation` change documents design decision EC-005/G.1
(`return None` without annotation → no `ReturnValue`). This is already
implemented in `detector.py:visit_Return` and has a passing test
(`test_detector.py:98–104`).

- [ ] 11.0 Add EC-005/G.1 traceability comment to `visit_Return` docstring in
      `src/gaze_py/analysis/detector.py`. The spec requires: "the decision is
      documented in `detector.py` `visit_Return` with reference to EC-005/G.1
      and the spec archive." Add a comment such as:

      ```python
      # EC-005/G.1: unannotated `return None` is idiomatically equivalent to
      # bare `return` in Python — it does not signal that None is a meaningful
      # return value. Treating it as ReturnValue would produce false positives
      # on a large class of void functions. Documented in:
      # openspec/changes/archive/return-none-annotation/
      ```

- [ ] 11.1 Move `openspec/changes/return-none-annotation/` to
      `openspec/changes/archive/return-none-annotation/`:
      ```bash
      mv openspec/changes/return-none-annotation \
         openspec/changes/archive/return-none-annotation
      ```

- [ ] 11.2 Commit the archive:
      ```
      chore: archive return-none-annotation (EC-005/G.1 already implemented)
      ```
