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
is implemented by `_is_db_context(name)`: word-part split on `_`, matching
`conn`, `connection`, `tx`, `transaction`, `db` as word parts, plus substring
match for `connection`, `transaction` to cover camelCase compound words.
(`conn` is word-part only — substring would match `reconnect`, `connector`.)

`session` is **excluded** from the word-part set: `session_id` (a common
HTTP/user session identifier) would otherwise be a false positive.
`db` is word-part only (not substring) to avoid matching `debug`.

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
- **THEN** a `MutexOp` effect is present (`sem` does not match any connection
  keyword → MutexOp by default; there is no positive semaphore heuristic)

##### Scenario: async with local variable does NOT produce MutexOp
- **WHEN** a function creates `lock = asyncio.Lock()` locally and uses
  `async with lock:`
- **THEN** no `MutexOp` effect is produced (local variable, not a parameter)

#### DatabaseTransaction via async with

`async with param:` where `param` is a function parameter and the variable
name matches the connection name heuristic → `DatabaseTransaction` (P2).

The connection name heuristic uses `_is_db_context(name)` — same as the MutexOp
heuristic above. Word-part matches: `conn`, `connection`, `tx`, `transaction`,
`db`. Substring matches: `connection`, `transaction` (`conn` is word-part only
— substring would match `reconnect`/`connector`). `session` is excluded (see note
above). `db` is word-part only (not substring).

##### Scenario: async with conn parameter produces DatabaseTransaction
- **WHEN** a function has parameter `conn` and uses `async with conn:`
- **THEN** a `DatabaseTransaction` effect is present

##### Scenario: async with session parameter produces MutexOp (NOT DatabaseTransaction)
- **WHEN** a function has parameter `session` and uses `async with session:`
- **THEN** a `MutexOp` effect is present (NOT `DatabaseTransaction`)
- **AND** `session` is excluded from the connection heuristic: `session_id` is a
  common HTTP/user session identifier (not a DB session), so including `session`
  would produce high-frequency false positives in web framework code

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

#### Sync visit_With alignment (MODIFIED requirement)

The synchronous `with param:` detection path (`visit_With`) MUST use the same
`_is_db_context` helper. This replaces the previous inline exact-set
`{"connection", "conn", "session", "tx", "transaction"}`.

##### Scenario: with db_conn produces DatabaseTransaction (sync, new match)
- **WHEN** a function has parameter `db_conn` and uses `with db_conn:`
- **THEN** a `DatabaseTransaction` effect is present (previously undetected)

##### Scenario: with ctx does NOT produce DatabaseTransaction (sync, regression)
- **WHEN** a function has parameter `ctx` and uses `with ctx:`
- **THEN** NO `DatabaseTransaction` effect is produced (`ctx` is not a connection name)

#### Known limitation: multi-item async with

`async with asyncio.TaskGroup() as tg, lock:` — if a TaskGroup appears before
a param-based lock in the same `async with` statement, the `break` after the
TaskGroup match exits the item loop and the `lock` item is not inspected. This
is an accepted limitation; the pattern is extremely unusual in practice.
