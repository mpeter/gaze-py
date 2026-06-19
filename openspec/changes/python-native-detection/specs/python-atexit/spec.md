## ADDED Requirements

### Requirement: EC-005 Language Adaptation — atexit.register GlobalMutation

The detector MUST detect `GlobalMutation` (P1) when a function calls
`atexit.register(func)`.

**Classification rationale**: `atexit.register()` mutates the
interpreter-global atexit handler list — a module-level data structure
maintained by the Python runtime. This is module-level global state per the
EC-005 GlobalMutation definition. The effect is observable to any code that
subsequently inspects `atexit._atexit` or calls `atexit.unregister()`.

**Why not FinalizerRegistration (P4)**: `FinalizerRegistration` is reserved
for `weakref.finalize()`, which registers a callback triggered by garbage
collection of a specific object. `atexit.register()` is triggered by
interpreter shutdown, not by GC of any particular object. The trigger
mechanism and semantics are categorically different.

**Why not CallbackInvocation (P2)**: `atexit.register()` registers a callback
for future invocation — it does not invoke the callback at the call site.
`CallbackInvocation` requires that the parameter is called directly (`param(...)`).

Detection is via attribute-access call: `obj_name == "atexit"` and
`method_name == "register"`.

#### Scenario: atexit.register produces GlobalMutation
- **WHEN** a function calls `atexit.register(cleanup_fn)`
- **THEN** a `GlobalMutation` effect is present in the result

#### Scenario: atexit.register with lambda produces GlobalMutation
- **WHEN** a function calls `atexit.register(lambda: do_cleanup())`
- **THEN** a `GlobalMutation` effect is present

#### Scenario: atexit.register does NOT produce FinalizerRegistration
- **WHEN** a function calls `atexit.register(fn)`
- **THEN** no `FinalizerRegistration` effect is produced for this call

#### Scenario: atexit.register does NOT produce CallbackInvocation
- **WHEN** a function calls `atexit.register(fn)`
- **THEN** no `CallbackInvocation` effect is produced for this call
  (the callback is registered, not invoked)

#### Scenario: atexit.unregister does NOT produce GlobalMutation
- **WHEN** a function calls `atexit.unregister(fn)`
- **THEN** no `GlobalMutation` effect is produced by this detection path
  (only `atexit.register` is in scope for this requirement)
