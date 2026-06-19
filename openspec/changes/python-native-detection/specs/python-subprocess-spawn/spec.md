## ADDED Requirements

### Requirement: EC-005 Language Adaptation — subprocess GoroutineSpawn

The detector MUST detect `GoroutineSpawn` (P2) when a function calls any of
the following `subprocess` module functions:

- `subprocess.Popen(...)`
- `subprocess.run(...)`
- `subprocess.call(...)`
- `subprocess.check_output(...)`
- `subprocess.check_call(...)`

Detection is via attribute-access call: `obj_name == "subprocess"` and
`method_name in {"Popen", "run", "call", "check_output", "check_call"}`.

**Rationale for GoroutineSpawn**: `subprocess.run()` is synchronous from the
caller's perspective (it blocks until the child exits), but it still spawns a
concurrent OS process. Per EC-005 GoroutineSpawn semantics, the effect is
defined by the act of spawning a separate execution context, not by whether the
caller waits for it. `subprocess.Popen` is the explicit non-blocking form.
Both map to GoroutineSpawn because both create a child process that runs
concurrently with the Python interpreter, even if the caller subsequently joins
it.

#### Scenario: subprocess.Popen produces GoroutineSpawn
- **WHEN** a function calls `subprocess.Popen(cmd)`
- **THEN** a `GoroutineSpawn` effect is present in the result

#### Scenario: subprocess.run produces GoroutineSpawn
- **WHEN** a function calls `subprocess.run(cmd)`
- **THEN** a `GoroutineSpawn` effect is present in the result

#### Scenario: subprocess.call produces GoroutineSpawn
- **WHEN** a function calls `subprocess.call(cmd)`
- **THEN** a `GoroutineSpawn` effect is present in the result

#### Scenario: subprocess.check_output produces GoroutineSpawn
- **WHEN** a function calls `subprocess.check_output(cmd)`
- **THEN** a `GoroutineSpawn` effect is present in the result

#### Scenario: subprocess.check_call produces GoroutineSpawn
- **WHEN** a function calls `subprocess.check_call(cmd)`
- **THEN** a `GoroutineSpawn` effect is present in the result

#### Scenario: subprocess.run is synchronous but still GoroutineSpawn
- **WHEN** a function calls `subprocess.run(cmd, check=True)` and awaits its
  completion via the blocking call
- **THEN** a `GoroutineSpawn` effect is still present — the synchronous wait
  does not remove the spawn from the observable effect set

#### Scenario: Non-subprocess attribute call does not produce GoroutineSpawn
- **WHEN** a function calls `proc.run()` where `proc` is not the `subprocess`
  module (i.e., `obj_name != "subprocess"`)
- **THEN** no `GoroutineSpawn` effect is produced by this detection path
  (other paths such as threading/asyncio may still fire independently)
