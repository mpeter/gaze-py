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

- [ ] 1.1 In `src/gaze_py/taxonomy/effects.py`, add inline comments adjacent
      to the two permanently-closed enum members in `SideEffectType`:

      Adjacent to `AtomicOp`:
      ```python
      # PERMANENTLY CLOSED — no Python equivalent.
      # Python has no atomic primitive. threading.local is thread-local
      # storage, not an atomic read-modify-write. ctypes atomics are
      # indistinguishable from general ctypes calls (already CgoCall).
      # Remains in taxonomy for porting contract compatibility (EC-001).
      AtomicOp = "AtomicOp"
      ```

      Adjacent to `SyncPoolOp`:
      ```python
      # PERMANENTLY CLOSED — no Python equivalent.
      # Go's sync.Pool has no Python equivalent. Object reuse pools
      # in Python are application-level; no stdlib type matches the
      # semantics. Remains in taxonomy for porting contract compatibility.
      SyncPoolOp = "SyncPoolOp"
      ```

## 2. New constants in detector.py

- [ ] 2.1 In `src/gaze_py/analysis/detector.py`, add after the existing
      `_GOROUTINE_SPAWN_CALLS` constant block:

      ```python
      # Qualified names for WaitGroupOp detection (asyncio module only).
      # concurrent.futures.wait is detected via name heuristic below
      # (obj_name == "futures") when imported as: import concurrent.futures as futures.
      # threading.Barrier.wait is detected via name heuristic (obj_name in {"barrier",...}).
      _WAIT_GROUP_CALLS: frozenset[tuple[str, str]] = frozenset(
          {
              ("asyncio", "gather"),
              ("asyncio", "wait"),
          }
      )

      # ctypes pointer variable name substrings/prefixes for UnsafeMutation detection.
      # Substring match: "ptr" matches "ptrdiff", "ptr_buf"; "buf" matches "buffer",
      # "bufio"; "mem" matches "membuffer"; "raw" matches "rawdata".
      # "p_" matches ctypes naming convention: p_value, p_buf, p_data.
      # False-positive risk is acceptable for P4 ("may detect") per EC-001.
      _CTYPES_PTR_NAMES: frozenset[str] = frozenset(
          {"ptr", "buf", "mem", "raw", "p_"}
      )
      ```

## 3. RecoverBehavior detection (visit_Try + visit_TryStar)

- [ ] 3.1 In `src/gaze_py/analysis/detector.py`, add a private
      `_handle_try_node` helper to `FunctionVisitor`, then add thin
      `visit_Try` and `visit_TryStar` delegates immediately after
      `visit_With`. This avoids duplicating the detection body across
      both visitors (DRY — `ast.Try` and `ast.TryStar` both expose
      `.handlers: list[ast.ExceptHandler]`):

      ```python
      def _handle_try_node(
          self, node: ast.Try | ast.TryStar
      ) -> None:
          """Shared RecoverBehavior detection for try/except and except* nodes.

          Emits at most one RecoverBehavior per function (checks self._effects).
          Calls generic_visit(node) so visit_Raise fires on re-raise statements
          inside handlers — RecoverBehavior and ErrorReturn are not mutually
          exclusive.

          Only top-level statements in each handler body are inspected for
          transform-and-re-raise exclusion (not nested inside if/for/with).

          Args:
              node: An ast.Try or ast.TryStar node to inspect.
          """
          # self._effects is bounded by distinct effect types per function (≤38);
          # O(n) scan is safe. Do not replace with a flag — see design.md D1.
          if not any(
              e.type == SideEffectType.RecoverBehavior for e in self._effects
          ):
              for handler in node.handlers:
                  if self._is_recovery_handler(handler):
                      self._add(
                          SideEffectType.RecoverBehavior,
                          handler,
                          self._recover_description(handler),
                      )
                      break
          self.generic_visit(node)

      def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
          """Detect RecoverBehavior from try/except blocks."""
          self._handle_try_node(node)

      def visit_TryStar(self, node: ast.TryStar) -> None:  # noqa: N802
          """Detect RecoverBehavior from except* (Python 3.11+) blocks."""
          self._handle_try_node(node)
      ```

      **Sequencing note**: `_handle_try_node` calls `self._recover_description(handler)`
      which is defined in task 3.3 below. Implement tasks 3.1 through 3.3 as a
      unit before running tests — the methods form a single cohesive group.

- [ ] 3.2 Add the helper `_is_recovery_handler` to `FunctionVisitor`:

      ```python
      def _is_recovery_handler(self, handler: ast.ExceptHandler) -> bool:
          """Return True if this except clause performs recovery, not re-raise.

          Rules (checked in order):
          1. Empty body → False (defensive; Python disallows empty except bodies)
          2. Single bare raise (no args) → False (pure re-raise)
          3. Any top-level statement in body is raise with non-None exc → False
             (unconditional transform-and-re-raise).
             NOTE: only inspects handler.body directly (not nested blocks),
             so a guarded `if debug: raise RuntimeError()` does NOT trigger
             this rule — the guarded raise is inside an ast.If, not top-level.
          4. Body contains ast.Return, ast.Assign, ast.AugAssign, or ast.Pass
             → True (recovery action present)
          5. Otherwise → False

          Args:
              handler: The ast.ExceptHandler node to inspect.

          Returns:
              True if the handler body contains a recovery action. False if it
              re-raises unconditionally.
          """
          body = handler.body
          if not body:
              return False  # defensive; unreachable in valid Python
          # Rule 2: single bare raise (re-raise)
          if len(body) == 1 and isinstance(body[0], ast.Raise) and body[0].exc is None:
              return False
          # Rule 3: unconditional transform-and-re-raise (top-level only)
          for stmt in body:
              if isinstance(stmt, ast.Raise) and stmt.exc is not None:
                  return False
          # Rule 4: recovery action
          for stmt in body:
              if isinstance(stmt, (ast.Return, ast.Assign, ast.AugAssign, ast.Pass)):
                  return True
          return False
      ```

- [ ] 3.3 Add `_recover_description` helper to `FunctionVisitor` to emit
      distinct descriptions for suppression vs. recovery:

      ```python
      def _recover_description(self, handler: ast.ExceptHandler) -> str:
          """Return a description string for RecoverBehavior.

          Distinguishes bare-pass suppression from active recovery.

          Args:
              handler: The qualifying ast.ExceptHandler node.

          Returns:
              Human-readable description of the recovery pattern.
          """
          if (
              len(handler.body) == 1
              and isinstance(handler.body[0], ast.Pass)
          ):
              return "Function silently suppresses an exception (bare except: pass)"
          return (
              "Function catches an exception and returns a fallback "
              "or assigns a default value"
          )
      ```

## 4. WaitGroupOp detection

- [ ] 4.1 In `_handle_goroutine_process_time`, add after the existing
      `GoroutineSpawn` detection block. The function signature needs
      `# noqa: PLR0911` because it will have 8 return points (5 existing +
      3 new; consistent with `_handle_lib_attr_call` and
      `_handle_param_attr_call`):

      Update the function signature line from:
      ```python
      def _handle_goroutine_process_time(
      ```
      to:
      ```python
      def _handle_goroutine_process_time(  # noqa: PLR0911
      ```

      Then add after the `concurrent.futures.*.submit` block and before the
      `# ProcessExit` block:
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

      # WaitGroupOp: concurrent.futures.wait (requires alias import:
      #   import concurrent.futures as futures)
      if method == "wait" and obj_name == "futures":
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
          """Detect WaitGroupOp from 'async with asyncio.TaskGroup()' pattern.

          Uses break after first match (only one TaskGroup pattern here).
          Unlike visit_With which has two patterns with no break,
          this method breaks after finding the first TaskGroup context.

          Known gap: 'async with lock:' patterns are not detected as MutexOp.
          Alias limitation: only detects asyncio.TaskGroup(), not aio.TaskGroup().
          """
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
      pointer write patterns. **Target: `FunctionVisitor.visit_Assign` at
      approximately line 503** (docstring: "Detect ReceiverMutation,
      PointerArgMutation, GlobalMutation, EnvVarMutation") — NOT the
      `_ClosureCaptureVisitor.visit_Assign` at approximately line 1290
      (docstring: "Detect ClosureCaptureMutation"). There are two
      `visit_Assign` methods in the file; make sure to edit the correct one.

      Add TWO INDEPENDENT `if` blocks (not `if/else`) at the end of
      `FunctionVisitor.visit_Assign`, AFTER the `GlobalMutation` for-loop
      and BEFORE `self.generic_visit(node)`:

      ```python
      # UnsafeMutation: ctypes pointer subscript assignment (ptr[0] = ...)
      # Two independent checks — subscript and .contents are not mutually exclusive.
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

      # UnsafeMutation: ctypes .contents attribute assignment (ptr.contents = ...)
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
              break
      ```

## 6. Fixture files

All fixture files MUST have `# ruff: noqa` as the first line (CR-002
convention for AST-only fixtures with intentionally undefined names).

- [ ] 6.1 [P] Create `tests/testdata/analysis/recover_behavior.py`:

      ```python
      # ruff: noqa
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


      def return_none_on_error(value: str) -> int | None:
          """Returns None fallback — return only (no assignment)."""
          try:
              return int(value)
          except ValueError:
              return None


      def double_try_recovers_once(value: str) -> int:
          """Two qualifying try/except blocks — RecoverBehavior emitted once."""
          try:
              result = int(value)
          except ValueError:
              result = 0
          try:
              result = result + 1
          except TypeError:
              result = -1
          return result


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
      # ruff: noqa
      """Fixture for WaitGroupOp detection.

      Uses 'import concurrent.futures as futures' to make futures.wait()
      valid Python (required for the obj_name=="futures" heuristic).
      """
      import asyncio
      import concurrent.futures as futures
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
          async def some_coro() -> None:
              pass

          async with asyncio.TaskGroup() as tg:
              tg.create_task(some_coro())


      def futures_wait(fs: set) -> None:
          """concurrent.futures.wait via alias import — WaitGroupOp."""
          futures.wait(fs)


      def barrier_sync(barrier: threading.Barrier) -> None:
          """threading.Barrier.wait — WaitGroupOp."""
          barrier.wait()


      def sync_with_task_group() -> None:
          """sync with asyncio.TaskGroup() — NOT WaitGroupOp (sync with, not async)."""
          pass  # sync 'with asyncio.TaskGroup()' is not valid Python; no fixture needed
      ```

- [ ] 6.3 [P] Create `tests/testdata/analysis/unsafe_mutation.py`:

      ```python
      # ruff: noqa
      """Fixture for UnsafeMutation detection."""
      import ctypes


      def write_ptr_subscript(ptr: ctypes.c_char_p) -> None:
          """Subscript write on ptr — UnsafeMutation."""
          ptr[0] = 0xFF


      def write_buf_subscript(buf: ctypes.c_char_p) -> None:
          """Subscript write on buf — UnsafeMutation."""
          buf[0] = 0x00


      def write_p_name_subscript(p_data: ctypes.c_char_p) -> None:
          """Subscript write on p_ name — UnsafeMutation."""
          p_data[0] = 0x42


      def write_contents(mem: ctypes.Structure) -> None:
          """Attribute .contents write — UnsafeMutation."""
          mem.contents = ctypes.c_int(42)


      def safe_list_write(items: list) -> None:
          """List subscript write — NOT UnsafeMutation."""
          items[0] = 42
      ```

## 7. Tests

All tests use `FileDetector.detect(FIXTURES / "<file>.py", root=ROOT)` unless
noted as inline (using `tmp_path` with `textwrap.dedent` source strings).

- [ ] 7.1 [P] In `tests/test_detector.py`, split the existing
      `test_noop_types_not_detected` parametrized test:
      - Remove `"WaitGroupOp"`, `"RecoverBehavior"`, `"UnsafeMutation"` from
        the parametrize list (these are now actively detected)
      - Keep only `"AtomicOp"` and `"SyncPoolOp"` in the parametrize list
      - Rename the test to `test_permanently_closed_types_never_emitted` with
        docstring `"EC-001/EC-005: AtomicOp and SyncPoolOp have no Python
        equivalent and are permanently closed."`
      - Update the comment block immediately above the test (currently reads:
        `# EC-005: No-op coverage — WaitGroupOp, AtomicOp, RecoverBehavior,`
        `# UnsafeMutation, SyncPoolOp never detected`) to:
        `# EC-001/EC-005: Permanently closed types — AtomicOp and SyncPoolOp`
        `# have no Python equivalent and are never detected.`
      - Use a richer synthetic fixture (inline source via `tmp_path`) instead
        of `pure_function.py` to test against plausible atomic-like patterns:
        ```python
        source = textwrap.dedent("""
            import threading
            def f():
                x = threading.local()
                x.value = 42
        """)
        ```
        Assert no effect of type `SideEffectType.AtomicOp` and (separately)
        `SideEffectType.SyncPoolOp`.

- [ ] 7.2 [P] Append new test functions for `RecoverBehavior`:
      - `test_recover_behavior_assignment_in_handler` — detect on
        `parse_int_with_fallback` from `recover_behavior.py`; assert
        `sum(1 for e in all_effects if e.type == SideEffectType.RecoverBehavior) == 1`
      - `test_recover_behavior_bare_pass` — detect on `suppress_error`;
        assert exactly one `RecoverBehavior`
      - `test_recover_behavior_return_only_in_handler` — detect on
        `return_none_on_error`; assert exactly one `RecoverBehavior`
      - `test_recover_behavior_not_emitted_for_reraise` — detect on
        `reraise_is_not_recovery`; assert no `RecoverBehavior` in effects
      - `test_recover_behavior_not_emitted_for_transform_reraise` — detect on
        `transform_reraise_is_not_recovery`; assert no `RecoverBehavior`
      - `test_recover_behavior_emitted_once_per_function` — detect on
        `double_try_recovers_once`; assert exactly ONE `RecoverBehavior`
        (two qualifying try blocks, only one emission)
      - `test_recover_behavior_flag_resets_between_functions` — detect the
        FULL `recover_behavior.py` file (all functions); group effects by
        `target.name`; assert:
        - `parse_int_with_fallback` has exactly 1 `RecoverBehavior`
        - `suppress_error` has exactly 1 `RecoverBehavior`
        - `reraise_is_not_recovery` has 0 `RecoverBehavior`
        - `transform_reraise_is_not_recovery` has 0 `RecoverBehavior`
      - `test_recover_behavior_except_star` — confirms `visit_TryStar`
        dispatch path fires. Inline source (Python 3.11+ syntax — the
        project minimum is 3.11, so no skip needed):
        ```python
        source = textwrap.dedent("""
            def f(value):
                try:
                    return int(value)
                except* ValueError:
                    return None
        """)
        ```
        Assert exactly one `RecoverBehavior` effect on function `f`.

- [ ] 7.3 [P] Append new test functions for `WaitGroupOp`:
      - `test_wait_group_op_asyncio_gather` — detect on `gather_tasks`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_asyncio_gather_bare_call` — inline source:
        `def f(t1, t2):\n    asyncio.gather(t1, t2)\n`; assert `WaitGroupOp`
        is emitted (detection fires on the ast.Call node regardless of await)
      - `test_wait_group_op_asyncio_wait` — detect on `wait_tasks`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_task_group` — detect on `task_group_sync`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_not_emitted_for_sync_with` — inline source:
        `async def f():\n    pass\n` (sync with TaskGroup is not valid Python;
        confirm `visit_AsyncWith` only fires on `ast.AsyncWith` — use a
        plain `with lock:` block): inline `def f(lock):\n    with lock:\n
            pass\n`; assert no `WaitGroupOp` (only `MutexOp` expected)
      - `test_wait_group_op_futures_wait` — detect on `futures_wait`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_barrier_wait` — detect on `barrier_sync`;
        assert `WaitGroupOp` present
      - `test_wait_group_op_not_emitted_for_async_with_lock` — confirms
        `visit_AsyncWith` does not fire on a non-TaskGroup async context
        manager. Inline source:
        ```python
        source = textwrap.dedent("""
            async def f(lock):
                async with lock:
                    pass
        """)
        ```
        Assert no `WaitGroupOp` in effects. (Verifies the
        `ctx.func.attr == "TaskGroup"` guard in `visit_AsyncWith`.)
      - `test_wait_group_op_multiple_emissions` — inline source with two
        qualifying WaitGroupOp calls in the same function:
        ```python
        source = textwrap.dedent("""
            import asyncio
            import threading

            async def sync_two_ways(tasks, barrier):
                await asyncio.gather(*tasks)
                barrier.wait()
        """)
        ```
        Assert `sum(1 for e in all_effects if e.type == SideEffectType.WaitGroupOp) == 2`.
        (WaitGroupOp has no once-per-function guard — each qualifying call
        emits independently. Contrast with RecoverBehavior which emits at
        most once.)

- [ ] 7.4 [P] Append new test functions for `UnsafeMutation`:
      - `test_unsafe_mutation_ptr_subscript` — detect on `write_ptr_subscript`;
        assert `sum(1 for e in all_effects if e.type == SideEffectType.UnsafeMutation) == 1`
      - `test_unsafe_mutation_buf_subscript` — detect on `write_buf_subscript`;
        assert exactly 1 `UnsafeMutation`
      - `test_unsafe_mutation_p_name_subscript` — detect on
        `write_p_name_subscript`; assert exactly 1 `UnsafeMutation`
        (validates `"p_"` in `_CTYPES_PTR_NAMES`)
      - `test_unsafe_mutation_contents_attr` — detect on `write_contents`;
        assert exactly 1 `UnsafeMutation`
      - `test_unsafe_mutation_not_emitted_for_list_write` — detect on
        `safe_list_write`; assert no `UnsafeMutation` in effects
      - `test_unsafe_mutation_both_patterns_independent` — inline source with
        both patterns in the same function:
        ```python
        import ctypes
        def f(ptr, mem):
            ptr[0] = 0xFF
            mem.contents = ctypes.c_int(0)
        ```
        Assert `sum(...UnsafeMutation...) == 2` (two independent emits,
        one per statement — no once-per-function guard for UnsafeMutation)

## 8. 002-deferred-capabilities update

- [ ] 8.1 In `openspec/changes/002-deferred-capabilities/tasks.md`, append
      `— SHIPPED 0.5.2 (WaitGroupOp + RecoverBehavior implemented; UnsafeMutation implemented; AtomicOp/SyncPoolOp permanently closed — D.3 fully resolved)`
      to the D.3 description line. Per the tracking-doc convention, do NOT
      check the box — append the `— SHIPPED` annotation inline.

## 9. Version bump + CHANGELOG

- [ ] 9.1 Bump version `0.5.1` → `0.5.2` in `pyproject.toml` and
      `src/gaze_py/__init__.py`.

- [ ] 9.2 Add CHANGELOG entry under `## [Unreleased]`. The spec reference goes
      in a `### Specs` bullet — NOT inside the code block — consistent with
      existing CHANGELOG entries:

      ```
      ### Added
      - `RecoverBehavior` (P3) detection: `try/except` blocks that suppress or
        recover from exceptions (return fallback, assign default, bare `pass`).
        Also handles Python 3.11+ `except*` blocks. Re-raise and
        transform-and-re-raise patterns are not flagged.
      - `WaitGroupOp` (P3) detection: `asyncio.gather`, `asyncio.wait`,
        `async with asyncio.TaskGroup()`, `futures.wait(...)` (via alias import),
        and `threading.Barrier.wait` patterns.
      - `UnsafeMutation` (P4) detection: ctypes pointer subscript writes
        (`ptr[0] = ...`, `buf[0] = ...`, `p_data[0] = ...`) and `.contents`
        attribute writes (`mem.contents = ...`).

      ### Fixed
      - `AtomicOp` (P3) and `SyncPoolOp` (P4) formally closed as having no
        Python equivalent. Both remain in the taxonomy (EC-001 compatibility).
        Closure is documented in `taxonomy/effects.py` comments.

      ### Specs
      - `openspec/changes/p3p4-detection-expansion/`
      ```

      Also verify that all prior `[Unreleased]` content is intentionally
      bundled into `0.5.2` — the section currently contains multiple
      significant unreleased features (AI report, gap_hints, quality pipeline
      changes) that will be included in the same tag.

## 10. CI gate

- [ ] 10.1 [P] `uv run ruff check .`
- [ ] 10.2 [P] `uv run ruff format --check .`
- [ ] 10.3 [P] `uv run mypy --strict src/`
- [ ] 10.4     `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`

<!-- spec-review: passed -->
