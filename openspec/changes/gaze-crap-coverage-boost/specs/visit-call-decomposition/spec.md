## ADDED Requirements

### Requirement: visit_Call becomes a thin dispatcher with CC ≤ 3
After decomposition, `visit_Call` MUST delegate to sub-dispatchers and contain no more than 3 cyclomatic complexity points of its own (one `if isinstance(func, ast.Attribute)` branch, one `elif isinstance(func, ast.Name)` branch, base).

#### Scenario: visit_Call delegates attribute calls
- **WHEN** `visit_Call` is called with an `ast.Attribute` function node
- **THEN** it delegates to `_handle_stream_writes`, `_handle_pathlib_attr_call`, `_handle_lib_attr_call`, and `_handle_param_attr_call` in order

#### Scenario: visit_Call delegates name calls
- **WHEN** `visit_Call` is called with an `ast.Name` function node
- **THEN** it delegates to `_handle_name_call`

### Requirement: _handle_stream_writes handles sys.stderr/stdout.write() with CC ≤ 11
`_handle_stream_writes(self, obj, method, node)` MUST detect `sys.stderr.write()` → `StderrWrite` and `sys.stdout.write()` → `StdoutWrite`. Returns `True` when handled, `False` otherwise.

#### Scenario: sys.stderr.write() produces StderrWrite
- **WHEN** `_handle_stream_writes` is called with `method="write"` and obj is `sys.stderr`
- **THEN** `StderrWrite` is added and the method returns `True`

#### Scenario: sys.stdout.write() produces StdoutWrite
- **WHEN** `_handle_stream_writes` is called with `method="write"` and obj is `sys.stdout`
- **THEN** `StdoutWrite` is added and the method returns `True`

### Requirement: _handle_pathlib_attr_call handles Path methods with CC ≤ 4
`_handle_pathlib_attr_call(self, method, node)` MUST detect `Path.unlink()` → `FileSystemDelete`, `Path.chmod()` → `FileSystemMeta`, and `Path.write_text/bytes()` → `FileSystemWrite`. Returns `True` when handled, `False` otherwise.

#### Scenario: Path.unlink() produces FileSystemDelete
- **WHEN** `_handle_pathlib_attr_call` is called with `method="unlink"`
- **THEN** `FileSystemDelete` is added and the method returns `True`

#### Scenario: Path.write_text/bytes() produce FileSystemWrite
- **WHEN** `_handle_pathlib_attr_call` is called with `method` in `{"write_text", "write_bytes"}`
- **THEN** `FileSystemWrite` is added and the method returns `True`

### Requirement: _handle_lib_attr_call handles library-named object calls with CC ≤ 13
`_handle_lib_attr_call(self, obj_name, method, node)` MUST handle: `LogWrite`, `GoroutineSpawn` (named and executor.submit heuristic), `ProcessExit`, `TimeDependency`, `FileSystemDelete` (os.*), `FileSystemMeta` (os.*), `ReflectionMutation` (`__setattr__`), `FinalizerRegistration` (`weakref.finalize`), `CgoCall` (`ctypes/cffi`). Returns `True` when handled, `False` otherwise.

#### Scenario: All 13 lib-attr effect types detected correctly
- **WHEN** `_handle_lib_attr_call` is called with any of the named object/method combinations
- **THEN** the correct effect type is added and the method returns `True`
- **AND** all 13 existing lib-attr effect-detection tests pass unchanged

### Requirement: _handle_param_attr_call handles parameter-based attribute calls with CC ≤ 11
`_handle_param_attr_call(self, obj_name, method, node)` MUST handle all `obj_name in self._params` checks: `HTTPResponseWrite`, `WriterOutput`, `SliceMutation`, `MapMutation`, `ChannelSend`, `ChannelClose`, `DatabaseWrite`, `ContextCancellation` (`.cancel()` and `.set()`). Returns `True` when handled, `False` otherwise.

### Requirement: _handle_name_call handles bare function calls with CC ≤ 6
`_handle_name_call(self, fn, node)` MUST handle `print()` → `StdoutWrite`, `setattr()` → `ReflectionMutation`, `open()` → `FileSystemWrite` (write modes), and parameter callback invocations → `CallbackInvocation`. Returns `True` when handled, `False` otherwise.

### Requirement: All 28 self._add() calls preserved with identical conditions
- **WHEN** `visit_Call` or any sub-dispatcher fires
- **THEN** the `SideEffectType`, `node`, and description string passed to `self._add()` are identical to the pre-decomposition implementation

### Requirement: PLR0911/PLR0912/PLR0915 noqa suppressions removed
After decomposition, `visit_Call` MUST NOT have `# noqa: PLR0911`, `# noqa: PLR0912`, or `# noqa: PLR0915` on its signature line. These suppressions are no longer needed.

### Requirement: All existing effect-detection tests pass unchanged
- **WHEN** any of the 24 existing effect-detection tests in `test_detector.py` are run after decomposition
- **THEN** all 24 pass with no changes to the test code

### Requirement: visit_Call short-circuits after first handled dispatch
- **WHEN** a sub-dispatcher returns `True`
- **THEN** `visit_Call` MUST NOT call any subsequent sub-dispatcher for that node
- **AND** `self._add()` is called exactly once per matched call node (no duplicate effects)

#### Scenario: No duplicate effects from sequential dispatch
- **WHEN** `visit_Call` processes a `sys.stderr.write()` call
- **THEN** exactly one `StderrWrite` effect is added (not two)
- **AND** `_handle_lib_attr_call` is not called for that node

### Requirement: Each helper calls self.generic_visit(node) before returning True
Each sub-dispatcher MUST call `self.generic_visit(node)` before returning `True`, preserving the current execution order (child nodes visited immediately after effect detection, before control returns to the caller).

#### Scenario: generic_visit called for matched attribute calls
- **WHEN** `_handle_stream_writes` matches a `sys.stderr.write()` call
- **THEN** `self.generic_visit(node)` is called before the method returns `True`
- **AND** the `visit_Call` dispatcher returns immediately without calling further helpers

### Requirement: obj_name parameter type is str | None
All sub-dispatchers that receive `obj_name` MUST accept `str | None`. The `is not None` guard required before `obj_name`-based checks MUST remain inside the helper (not in the dispatcher), preserving the current conditional structure.

#### Scenario: mypy --strict passes with str | None signatures
- **WHEN** `mypy --strict src/` is run after decomposition
- **THEN** zero type errors are produced for `visit_Call` or any sub-dispatcher

### Requirement: Dispatch order preserved or documented as safe reordering
The refactored dispatch order for attribute calls MUST either (a) exactly match the current order in `visit_Call` (stream writes → lib-attr → pathlib → param-attr), or (b) document the invariant that makes any reordering safe.

If pathlib checks are called before lib-attr checks, the spec MUST note: pathlib checks match on method name alone (independent of obj_name), while lib-attr checks require obj_name to be non-None and in a specific set — these sets are mutually exclusive, making the order safe.
