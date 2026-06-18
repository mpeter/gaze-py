<!--
  [P] marks tasks eligible for parallel execution.
  Add [P] when a task: (a) touches different files from
  other [P] tasks in the group, (b) has no dependency
  on prior tasks in the group, (c) can safely execute
  without ordering constraints.
  Do NOT add [P] when tasks modify the same file —
  parallel workers will cause merge conflicts.
  Tasks without [P] run sequentially first, then [P]
  tasks run in parallel.
-->

## Convention Pack Compliance

Before implementing any task, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`

## 1. Taxonomy formal-close comments

- [ ] 1.1 In `src/gaze_py/taxonomy/effects.py`, add a module-level docstring
      section (or inline comment block) documenting the two permanently-closed
      types. Add adjacent to `AtomicOp` in `SideEffectType`:
      ```python
      # AtomicOp — PERMANENTLY CLOSED (no Python equivalent)
      # Python has no atomic primitive. threading.local is thread-local
      # storage, not an atomic read-modify-write. ctypes atomics are
      # indistinguishable from general ctypes calls (already CgoCall).
      # Remains in taxonomy for porting contract compatibility (EC-001).
      AtomicOp = "AtomicOp"
      ```
      Add adjacent to `SyncPoolOp`:
      ```python
      # SyncPoolOp — PERMANENTLY CLOSED (no Python equivalent)
      # Go's sync.Pool has no Python equivalent. Object reuse pools
      # in Python are application-level; no stdlib type matches the
      # semantics. Remains in taxonomy for porting contract compatibility.
      SyncPoolOp = "SyncPoolOp"
      ```

## 2. New constants in detector.py

- [ ] 2.1 In `src/gaze_py/analysis/detector.py`, add after the existing
      `_GOROUTINE_SPAWN_CALLS` constant block, a new frozenset:
      ```python
      # Qualified names for WaitGroupOp detection (asyncio / concurrent.futures)
      _WAIT_GROUP_CALLS: frozenset[tuple[str, str]] = frozenset(
          {
              ("asyncio", "gather"),
              ("asyncio", "wait"),
          }
      )

      # ctypes pointer variable name prefixes/substrings for UnsafeMutation
      _CTYPES_PTR_NAMES: frozenset[str] = frozenset(
          {"ptr", "buf", "mem", "raw"}
      )
      ```

## 3. RecoverBehavior detection (visit_Try)

- [ ] 3.1 In `src/gaze_py/analysis/detector.py`, add a new visitor method
      `visit_Try` to `FunctionVisitor` after `visit_With`. The method:
      - Iterates over `node.handlers` (each is `ast.ExceptHandler`)
      - For each handler, calls a helper `_is_recovery_handler(handler)`
      - If any handler qualifies AND no `RecoverBehavior` has been emitted
        for this function yet (use a `_has_recover_behavior: bool` instance
        flag initialized to `False`), emits `RecoverBehavior` and sets the
        flag to `True`
      - Calls `self.generic_visit(node)`

      ```python
      def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
          """Detect RecoverBehavior from exception-swallowing try/except."""
          if not self._has_recover_behavior:
              for handler in node.handlers:
                  if self._is_recovery_handler(handler):
                      self._has_recover_behavior = True
                      self._add(
                          SideEffectType.RecoverBehavior,
                          node,
                          "Function catches an exception and performs recovery "
                          "(returns fallback, assigns default, or suppresses)",
                      )
                      break
          self.generic_visit(node)
      ```

- [ ] 3.2 Add the helper `_is_recovery_handler` to `FunctionVisitor`:
      ```python
      def _is_recovery_handler(self, handler: ast.ExceptHandler) -> bool:
          """Return True if this except clause performs recovery, not re-raise.

          Recovery = body contains a return, an assignment, or a bare pass.
          Re-raise = body is a single 'raise' (no arguments) or
                     'raise SomeExc(...)' (transform-and-raise).
          """
          body = handler.body
          if not body:
              return False
          # Pure re-raise: single 'raise' with no value
          if len(body) == 1 and isinstance(body[0], ast.Raise):
              return body[0].exc is None
          # Transform-and-raise: any stmt is raise with a value
          for stmt in body:
              if isinstance(stmt, ast.Raise) and stmt.exc is not None:
                  return False
          # Check for recovery actions
          for stmt in body:
              if isinstance(stmt, (ast.Return, ast.Assign, ast.AugAssign, ast.Pass)):
                  return True
          return False
      ```

- [ ] 3.3 Add `_has_recover_behavior: bool = False` to `FunctionVisitor.__init__`
      alongside the other per-function state flags.

## 4. WaitGroupOp detection

- [ ] 4.1 In `_handle_goroutine_process_time`, add after the existing
      `GoroutineSpawn` detection block:
      ```python
      # WaitGroupOp: asyncio.gather, asyncio.wait
      if obj_name is not None and (obj_name, method) in _WAIT_GROUP_CALLS:
          self._add(
              SideEffectType.WaitGroupOp,
              node,
              f"Function synchronizes on a group of tasks via {obj_name}.{method}()",
          )
          self.generic_visit(node)
          return True

      # WaitGroupOp: threading.Barrier.wait (name heuristic)
      if method == "wait" and obj_name in {"barrier", "barriers"}:
          self._add(
              SideEffectType.WaitGroupOp,
              node,
              f"Function waits on a threading.Barrier via {obj_name}.wait()",
          )
          self.generic_visit(node)
          return True

      # WaitGroupOp: concurrent.futures.wait (module-level call)
      if method == "wait" and obj_name in {"futures"}:
          self._add(
              SideEffectType.WaitGroupOp,
              node,
              "Function waits on a concurrent.futures result set via futures.wait()",
          )
          self.generic_visit(node)
          return True
      ```

- [ ] 4.2 Add `visit_AsyncWith` to `FunctionVisitor` after `visit_With` to
      detect `async with asyncio.TaskGroup() as tg:`:
      ```python
      def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802
          """Detect WaitGroupOp from 'async with asyncio.TaskGroup()' pattern."""
          for item in node.items:
              ctx = item.context_expr
              if (
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

## 5. UnsafeMutation detection

- [ ] 5.1 Extend `visit_Assign` in `FunctionVisitor` to check for ctypes
      pointer write patterns AFTER the existing checks. Add at the end of
      `visit_Assign` (before `self.generic_visit(node)`):
      ```python
      # UnsafeMutation: ctypes pointer subscript or .contents assignment
      if not any(isinstance(t, ast.Subscript) for t in targets):
          # No subscript target — check for .contents assignment
          for target in targets:
              if (
                  isinstance(target, ast.Attribute)
                  and target.attr == "contents"
                  and isinstance(target.value, ast.Name)
              ):
                  self._add(
                      SideEffectType.UnsafeMutation,
                      node,
                      f"Function writes to raw memory via {target.value.id}.contents",
                  )
      else:
          for target in targets:
              if (
                  isinstance(target, ast.Subscript)
                  and isinstance(target.value, ast.Name)
                  and any(p in target.value.id for p in _CTYPES_PTR_NAMES)
              ):
                  self._add(
                      SideEffectType.UnsafeMutation,
                      node,
                      f"Function writes to raw memory via {target.value.id}[...] = ...",
                  )
                  break
      ```

      Note: The UnsafeMutation check must come AFTER the existing checks in
      `visit_Assign` (ReceiverMutation, PointerArgMutation, GlobalMutation)
      since those use `elif` chains and check `self._params` / `self._global_names`.
      The ctypes check is an independent `if` (not `elif`) added at the end.

## 6. Fixture files

- [ ] 6.1 [P] Create `tests/testdata/analysis/recover_behavior.py`:
      ```python
      """Fixture for RecoverBehavior detection."""


      def parse_int_with_fallback(value: str) -> int:
          """Returns 0 on parse failure — assignment in except."""
          try:
              return int(value)
          except ValueError:
              result = 0
              return result


      def suppress_error() -> None:
          """Suppresses error silently — bare pass in except."""
          try:
              risky_op()
          except Exception:
              pass


      def reraise_is_not_recovery(value: str) -> int:
          """Re-raise is NOT RecoverBehavior."""
          try:
              return int(value)
          except ValueError:
              raise


      def transform_reraise_is_not_recovery(value: str) -> int:
          """Transform-and-reraise is NOT RecoverBehavior."""
          try:
              return int(value)
          except ValueError as e:
              raise RuntimeError("bad value") from e
      ```

- [ ] 6.2 [P] Create `tests/testdata/analysis/wait_group_op.py`:
      ```python
      """Fixture for WaitGroupOp detection."""
      import asyncio
      import concurrent.futures
      import threading


      async def gather_tasks(coros: list) -> list:
          """asyncio.gather — WaitGroupOp."""
          return await asyncio.gather(*coros)


      async def wait_tasks(tasks: set) -> tuple:
          """asyncio.wait — WaitGroupOp."""
          done, pending = await asyncio.wait(tasks)
          return done, pending


      async def task_group_sync() -> None:
          """asyncio.TaskGroup — WaitGroupOp."""
          async with asyncio.TaskGroup() as tg:
              tg.create_task(some_coro())


      def futures_wait(fs: set) -> None:
          """concurrent.futures.wait — WaitGroupOp."""
          futures.wait(fs)


      def barrier_sync(barrier: threading.Barrier) -> None:
          """threading.Barrier.wait — WaitGroupOp."""
          barrier.wait()
      ```

- [ ] 6.3 [P] Create `tests/testdata/analysis/unsafe_mutation.py`:
      ```python
      """Fixture for UnsafeMutation detection."""
      import ctypes


      def write_ptr_subscript(ptr: ctypes.c_char_p) -> None:
          """Subscript write on ptr — UnsafeMutation."""
          ptr[0] = 0xFF


      def write_buf_subscript(buf: ctypes.c_char_p) -> None:
          """Subscript write on buf — UnsafeMutation."""
          buf[0] = 0x00


      def write_contents(mem: ctypes.Structure) -> None:
          """Attribute .contents write — UnsafeMutation."""
          mem.contents = ctypes.c_int(42)


      def safe_list_write(items: list) -> None:
          """List subscript write — NOT UnsafeMutation."""
          items[0] = 42
      ```

## 7. Tests

- [ ] 7.1 [P] In `tests/test_detector.py`, append new test functions for
      `RecoverBehavior`:
      - `test_recover_behavior_assignment_in_handler` — detect on
        `parse_int_with_fallback` from `recover_behavior.py`; assert
        one effect of type `RecoverBehavior` is present
      - `test_recover_behavior_bare_pass` — detect on `suppress_error`;
        assert `RecoverBehavior` present
      - `test_recover_behavior_not_emitted_for_reraise` — detect on
        `reraise_is_not_recovery`; assert no `RecoverBehavior` in effects
      - `test_recover_behavior_not_emitted_for_transform_reraise` — detect on
        `transform_reraise_is_not_recovery`; assert no `RecoverBehavior`
      - `test_recover_behavior_emitted_once_per_function` — construct a
        fixture with two qualifying try/except blocks in one function;
        assert exactly one `RecoverBehavior` effect

- [ ] 7.2 [P] Append new test functions for `WaitGroupOp`:
      - `test_wait_group_op_asyncio_gather` — detect on `gather_tasks`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_asyncio_wait` — detect on `wait_tasks`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_task_group` — detect on `task_group_sync`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_futures_wait` — detect on `futures_wait`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_barrier_wait` — detect on `barrier_sync`;
        assert `WaitGroupOp` present

- [ ] 7.3 [P] Append new test functions for `UnsafeMutation`:
      - `test_unsafe_mutation_ptr_subscript` — detect on `write_ptr_subscript`;
        assert `UnsafeMutation` present
      - `test_unsafe_mutation_buf_subscript` — detect on `write_buf_subscript`;
        assert `UnsafeMutation` present
      - `test_unsafe_mutation_contents_attr` — detect on `write_contents`;
        assert `UnsafeMutation` present
      - `test_unsafe_mutation_not_emitted_for_list_write` — detect on
        `safe_list_write`; assert no `UnsafeMutation` in effects

- [ ] 7.4 [P] Append two tests confirming permanently-closed types emit nothing:
      - `test_atomic_op_never_emitted` — run the full detector on a synthetic
        module string with `import threading; x = threading.local()` and any
        plausible atomic-like pattern; assert no effect with
        `type == SideEffectType.AtomicOp`
      - `test_sync_pool_op_never_emitted` — run the detector on a synthetic
        module with pool-like patterns; assert no effect with
        `type == SideEffectType.SyncPoolOp`

## 8. 002-deferred-capabilities update

- [ ] 8.1 In `openspec/changes/002-deferred-capabilities/tasks.md`, append
      `— SHIPPED 0.5.2` to D.3 description line:
      ```
      - [ ] D.3 Revisit P3/P4 no-equivalent types — close SyncPoolOp/UnsafeMutation/
            AtomicOp permanently; evaluate WaitGroupOp and RecoverBehavior — SHIPPED 0.5.2
      ```
      Note: per the tracking-doc convention, do NOT check the box — append
      the `— SHIPPED` annotation inline.

## 9. Version bump + CHANGELOG

- [ ] 9.1 Bump version `0.5.1` → `0.5.2` in `pyproject.toml` and
      `src/gaze_py/__init__.py`.

- [ ] 9.2 Add CHANGELOG entry under `## [Unreleased]`:
      ```
      ### Added
      - `RecoverBehavior` (P3) detection: `try/except` blocks that suppress or
        recover from exceptions (return fallback, assign default, bare `pass`).
        Re-raise and transform-and-re-raise patterns are not flagged.
      - `WaitGroupOp` (P3) detection: `asyncio.gather`, `asyncio.wait`,
        `async with asyncio.TaskGroup()`, `concurrent.futures.wait`, and
        `threading.Barrier.wait` patterns.
      - `UnsafeMutation` (P4) detection: ctypes pointer subscript writes
        (`ptr[0] = ...`) and `.contents` attribute writes (`mem.contents = ...`).

      ### Fixed
      - `AtomicOp` (P3) and `SyncPoolOp` (P4) formally closed as having no
        Python equivalent. Both remain in the taxonomy (EC-001 compatibility).
        Closure is documented in `taxonomy/effects.py` comments.

      - Spec: `openspec/changes/p3p4-detection-expansion/`
      ```

## 10. CI gate

- [ ] 10.1 [P] `uv run ruff check .`
- [ ] 10.2 [P] `uv run ruff format --check .`
- [ ] 10.3 [P] `uv run mypy --strict src/`
- [ ] 10.4     `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
