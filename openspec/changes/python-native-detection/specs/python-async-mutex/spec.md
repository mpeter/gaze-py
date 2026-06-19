## ADDED Requirements

### Requirement: EC-005 Language Adaptation — async with MutexOp and DatabaseTransaction

The detector MUST detect effects from `async with` statements using the same
name heuristics as the existing synchronous `with` statement detection.

**Scope constraint**: Both `MutexOp` and `DatabaseTransaction` detection via
`async with` fire ONLY when the context manager expression is a function
parameter (i.e., the variable name is in `self._params` for the current
function). Local variables created inside the function body do NOT trigger
these effects. This mirrors the existing `with param:` constraint.

#### MutexOp via async with

`async with param:` where `param` is a function parameter and the variable
name does NOT match the connection name heuristic → `MutexOp` (P3).

The connection name heuristic (which routes to DatabaseTransaction instead)
matches names containing any of: `conn`, `connection`, `session`, `tx`,
`transaction`, `db`.

Any parameter name that does not match the connection heuristic is treated as
a lock/mutex and produces `MutexOp`.

##### Scenario: async with lock parameter produces MutexOp
- **WHEN** a function has parameter `lock` and uses `async with lock:`
- **THEN** a `MutexOp` effect is present

##### Scenario: async with mutex parameter produces MutexOp
- **WHEN** a function has parameter `mutex` and uses `async with mutex:`
- **THEN** a `MutexOp` effect is present

##### Scenario: async with sem parameter produces MutexOp
- **WHEN** a function has parameter `sem` and uses `async with sem:`
- **THEN** a `MutexOp` effect is present (semaphore name heuristic)

##### Scenario: async with local variable does NOT produce MutexOp
- **WHEN** a function creates `lock = asyncio.Lock()` locally and uses
  `async with lock:`
- **THEN** no `MutexOp` effect is produced (local variable, not a parameter)

#### DatabaseTransaction via async with

`async with param:` where `param` is a function parameter and the variable
name matches the connection name heuristic → `DatabaseTransaction` (P2).

The connection name heuristic matches names containing any of: `conn`,
`connection`, `session`, `tx`, `transaction`, `db`.

##### Scenario: async with conn parameter produces DatabaseTransaction
- **WHEN** a function has parameter `conn` and uses `async with conn:`
- **THEN** a `DatabaseTransaction` effect is present

##### Scenario: async with session parameter produces DatabaseTransaction
- **WHEN** a function has parameter `session` and uses `async with session:`
- **THEN** a `DatabaseTransaction` effect is present

##### Scenario: async with db_conn parameter produces DatabaseTransaction
- **WHEN** a function has parameter `db_conn` and uses `async with db_conn:`
- **THEN** a `DatabaseTransaction` effect is present (name contains `conn`)

##### Scenario: async with local connection variable does NOT produce DatabaseTransaction
- **WHEN** a function creates `conn = await engine.connect()` locally and uses
  `async with conn:`
- **THEN** no `DatabaseTransaction` effect is produced (local variable, not a
  parameter)

#### Mutual exclusion: one async with, one effect

A single `async with param:` statement produces exactly one effect — either
`MutexOp` or `DatabaseTransaction` — never both.

##### Scenario: async with conn produces DatabaseTransaction not MutexOp
- **WHEN** a function has parameter `conn` and uses `async with conn:`
- **THEN** a `DatabaseTransaction` effect is present AND no `MutexOp` effect
  is produced for the same statement
