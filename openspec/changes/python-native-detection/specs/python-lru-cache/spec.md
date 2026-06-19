## ADDED Requirements

### Requirement: EC-005 Language Adaptation — @lru_cache / @cache GlobalMutation

The detector MUST detect `GlobalMutation` (P1) when a function definition is
decorated with any of the following decorators:

| Decorator form | Matches |
|----------------|---------|
| `@lru_cache` | bare name, no call |
| `@lru_cache(maxsize=N)` | called with arguments |
| `@cache` | bare name, no call |
| `@functools.lru_cache` | attribute access, no call |
| `@functools.lru_cache(maxsize=N)` | attribute access, called with arguments |
| `@functools.cache` | attribute access, no call |
| `@functools.cache(...)` | attribute access, called with arguments |

**Detection site**: The effect is annotated at the **function definition site**
(decoration time), not at call sites. The `SideEffect` location points to the
`ast.FunctionDef` or `ast.AsyncFunctionDef` node (or its decorator), not to
any invocation of the decorated function. Detection is implemented in
`FileDetector.detect()` by inspecting `fn_node.decorator_list` in the function
definition loop.

**GlobalMutation rationale**: The memoization cache created by `@lru_cache` or
`@cache` is persistent global-like state shared across all callers. It is
attached to the function object (which is module-level) and persists for the
lifetime of the module. Any caller that invokes the decorated function can
observe the cache's effect (repeated calls with the same arguments return
cached results). This is GlobalMutation (P1) per EC-005 semantics — the
decoration mutates the function's observable behaviour by attaching shared
mutable state.

**Why not at call sites**: The cache is created once at decoration time. Each
call site does not independently create new global state — it reads from or
writes to the already-created cache. The mutation of global state occurs at
decoration, making the definition site the correct annotation point.

#### Scenario: @lru_cache (bare) produces GlobalMutation
- **WHEN** a function is decorated with `@lru_cache` (no call parentheses)
- **THEN** a `GlobalMutation` effect is present, attributed to that function

#### Scenario: @lru_cache(maxsize=128) produces GlobalMutation
- **WHEN** a function is decorated with `@lru_cache(maxsize=128)`
- **THEN** a `GlobalMutation` effect is present, attributed to that function

#### Scenario: @cache produces GlobalMutation
- **WHEN** a function is decorated with `@cache`
- **THEN** a `GlobalMutation` effect is present, attributed to that function

#### Scenario: @functools.lru_cache produces GlobalMutation
- **WHEN** a function is decorated with `@functools.lru_cache`
- **THEN** a `GlobalMutation` effect is present, attributed to that function

#### Scenario: @functools.lru_cache(maxsize=None) produces GlobalMutation
- **WHEN** a function is decorated with `@functools.lru_cache(maxsize=None)`
- **THEN** a `GlobalMutation` effect is present, attributed to that function

#### Scenario: @functools.cache produces GlobalMutation
- **WHEN** a function is decorated with `@functools.cache`
- **THEN** a `GlobalMutation` effect is present, attributed to that function

#### Scenario: Effect is at definition site, not call site
- **WHEN** a decorated function `@lru_cache\ndef compute(x): ...` is defined
  and called three times in other functions
- **THEN** the `GlobalMutation` effect appears on `compute`'s own
  `FunctionTarget`, not on the calling functions' targets

#### Scenario: Unrelated decorators do not produce GlobalMutation via this path
- **WHEN** a function is decorated with `@staticmethod` or `@property`
- **THEN** no `GlobalMutation` effect is produced by the decorator detection
  path (other detection paths may still fire for the function body)
