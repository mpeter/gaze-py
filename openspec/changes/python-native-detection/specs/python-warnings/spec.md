## ADDED Requirements

### Requirement: EC-005 Language Adaptation — warnings.warn dual effect

The detector MUST detect **two** effects from a single `warnings.warn(msg)`
call:

1. `LogWrite` (P2)
2. `GlobalMutation` (P1)

Both effects are emitted from the same AST call node. A single `warnings.warn()`
call produces exactly two `SideEffect` entries in the result, each with its own
stable `id` (computed from the same location but different effect type strings,
per EC-003).

**LogWrite rationale**: The Python `warnings` module is a structured,
filterable, developer-facing output channel. Warnings can be captured, filtered
by category, redirected to log handlers, or suppressed — all properties of a
logging system. `LogWrite` is the correct tier for structured developer-facing
output (P2), consistent with `logging.*` detection.

**GlobalMutation rationale**: `warnings.warn()` always writes to
`__warningregistry__` in the calling module's global namespace for
deduplication. This is an unconditional write to module-level global state
(the registry dict) that persists across calls. The mutation is observable:
subsequent calls with the same message/category/stacklevel are silently
suppressed because the registry entry exists. This is GlobalMutation (P1) per
EC-005 semantics.

Detection is via attribute-access call: `obj_name == "warnings"` and
`method_name == "warn"`.

#### Scenario: warnings.warn produces LogWrite
- **WHEN** a function calls `warnings.warn("deprecated")`
- **THEN** a `LogWrite` effect is present in the result

#### Scenario: warnings.warn produces GlobalMutation
- **WHEN** a function calls `warnings.warn("deprecated")`
- **THEN** a `GlobalMutation` effect is present in the result

#### Scenario: warnings.warn produces exactly two effects from one call
- **WHEN** a function calls `warnings.warn("msg", DeprecationWarning)`
- **THEN** the result contains exactly one `LogWrite` effect AND exactly one
  `GlobalMutation` effect attributable to this call (two distinct `SideEffect`
  entries with different `id` values)

#### Scenario: warnings.warn with stacklevel still produces both effects
- **WHEN** a function calls `warnings.warn("msg", stacklevel=2)`
- **THEN** both `LogWrite` and `GlobalMutation` effects are present

#### Scenario: warnings.warn does NOT produce FinalizerRegistration or CallbackInvocation
- **WHEN** a function calls `warnings.warn("msg")`
- **THEN** no `FinalizerRegistration` or `CallbackInvocation` effect is
  produced for this call
