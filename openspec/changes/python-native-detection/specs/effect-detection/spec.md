## MODIFIED Requirements

### Requirement: EC-005 Language Adaptation — Python-Native Detection (now shipped)

> **Replaces**: The "Requirement: Python-Native Detection (Planned)" section in
> `specs/effect-detection/spec.md` (search for "Python-Native Detection (Planned)").
> The "planned" qualifier is removed. These are now normative requirements, not future
> intentions. Tests for these patterns MUST be added to the main test suite
> when this change is merged.
>
> **Also modifies**: the `visit_With` heuristic for `DatabaseTransaction` detection
> is refactored to use `_is_db_context()` (see `specs/python-async-mutex/spec.md`).
> This is a behaviour extension: compound names like `db_conn` now match in the
> sync path where they previously did not.

The following Python-native patterns are now implemented. The canonical mapping
table in EC-005 is extended with these rows:

| Pattern | Effect Type | Tier | Notes |
|---------|-------------|------|-------|
| `subprocess.Popen/run/call/check_output/check_call(...)` | GoroutineSpawn | P2 | Spawns a concurrent OS process |
| `async with param:` (non-connection name) | MutexOp | P3 | Async lock acquisition; parameter only |
| `async with param:` (connection name) | DatabaseTransaction | P2 | Async DB transaction; parameter only |
| `atexit.register(...)` | GlobalMutation | P1 | Mutates interpreter-global atexit handler list |
| `warnings.warn(...)` | LogWrite + GlobalMutation | P2 + P1 | Dual effect: structured output + `__warningregistry__` write |
| `@lru_cache` / `@cache` / `@functools.lru_cache` / `@functools.cache` | GlobalMutation | P1 | Annotated at definition site; persistent shared cache |

The full authoritative detection rules for each pattern are in the
capability-specific delta specs within this change (paths relative to the change
directory; will be updated at archive time):

- `specs/python-subprocess-spawn/spec.md` — subprocess GoroutineSpawn
- `specs/python-async-mutex/spec.md` — async with MutexOp / DatabaseTransaction
- `specs/python-atexit/spec.md` — atexit.register GlobalMutation
- `specs/python-warnings/spec.md` — warnings.warn LogWrite + GlobalMutation
- `specs/python-lru-cache/spec.md` — @lru_cache / @cache GlobalMutation

#### Scenario: subprocess.run produces GoroutineSpawn (now normative)
- **WHEN** a function calls `subprocess.run(cmd)`
- **THEN** a `GoroutineSpawn` effect is present
- **AND** this test MUST be in the main test suite (not gated on a branch)

#### Scenario: async with lock parameter produces MutexOp (now normative)
- **WHEN** a function has parameter `lock` and uses `async with lock:`
- **THEN** a `MutexOp` effect is present
- **AND** this test MUST be in the main test suite

#### Scenario: atexit.register produces GlobalMutation (now normative)
- **WHEN** a function calls `atexit.register(fn)`
- **THEN** a `GlobalMutation` effect is present
- **AND** this test MUST be in the main test suite

#### Scenario: warnings.warn produces LogWrite and GlobalMutation (now normative)
- **WHEN** a function calls `warnings.warn("msg")`
- **THEN** both a `LogWrite` effect and a `GlobalMutation` effect are present
- **AND** this test MUST be in the main test suite

#### Scenario: @lru_cache produces GlobalMutation (now normative)
- **WHEN** a function is decorated with `@lru_cache`
- **THEN** a `GlobalMutation` effect is present, attributed to that function
- **AND** this test MUST be in the main test suite
