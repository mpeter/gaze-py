## MODIFIED Requirements

### Requirement: first-match-wins

The mapper MUST apply valid return binding, exception, captured stream and semantic mapping in that order. With test context, binding precedence MUST use assertion-time evidence; unsupported or unreachable capture assertions MUST remain unmapped before legacy fallback. Once an assertion is matched, later passes MUST NOT re-evaluate it. The mapper MUST preserve one output entry per input assertion and prevent double-counting.

#### Scenario: return binding keeps precedence
- **WHEN** an assertion references a live bound return value and a supported attributable captured stream
- **THEN** the return binding keeps precedence and the assertion is not counted twice

#### Scenario: blocked capture overrides return precedence
- **WHEN** an assertion references both a live return value and unsupported capture provenance
- **THEN** the assertion MUST remain unmapped rather than bypass the blocked capture through return matching

#### Scenario: captured stream precedes semantic overlap
- **WHEN** a remaining assertion checks an attributable captured stdout value
- **THEN** it maps to the target's StdoutWrite effect rather than a coincidental name match

## ADDED Requirements

### Requirement: capture-stream-provenance

When test AST context is available, the mapper MUST recognize pytest capture fixture output in tuple unpacking, assigned capture-result attributes, directly assigned stream attributes and inline stream attributes. It MUST distinguish `.out`/tuple index zero as StdoutWrite from `.err`/tuple index one as StderrWrite, and MUST only map effects present on the production target. Existing callers without test context MUST remain supported.

#### Scenario: documented tuple capture
- **WHEN** the test calls the target, binds `out, err = capsys.readouterr()` and separately asserts on `out` and `err`
- **THEN** each assertion maps only to its corresponding detected stream effect

#### Scenario: attribute and inline capture
- **WHEN** a target call is followed by an assertion on `captured.out`, directly assigned `capsys.readouterr().out`, or inline `capsys.readouterr().out`
- **THEN** the mapper credits StdoutWrite when the value is attributable to that target

#### Scenario: real JSON assertion
- **WHEN** the test asserts on JSON parsed directly from attributable captured stdout
- **THEN** the mapper recognizes the stream provenance without requiring a variable name tied to the production function

### Requirement: reject-unrelated-capture-credit

The mapper MUST NOT give stream credit for output captured before the target call, after a draining read without a new call, from a reassigned value or fixture, from an unrelated capture object, or from a nested function/class/lambda body that has not run. Ambiguous producer ordering or unsupported control flow MUST remain unmapped rather than inflate coverage. A stdout assertion MUST NOT credit StderrWrite or vice versa, including through semantic fallback.

#### Scenario: capture precedes target
- **WHEN** a test captures output before calling the target and later asserts the saved output
- **THEN** no target stream effect is credited

#### Scenario: read drains attribution
- **WHEN** a test calls the target, drains the fixture, then asserts a second read with no intervening target call
- **THEN** the second capture is not credited to the target

#### Scenario: overwritten binding
- **WHEN** a captured value is overwritten with an unrelated value before its assertion
- **THEN** the assertion does not credit the former stream

#### Scenario: unrelated producer
- **WHEN** another producer makes a capture ambiguous between the target call and the capture
- **THEN** the capture does not credit either target without established provenance

#### Scenario: wrong stream or nested call
- **WHEN** only stderr is asserted for a stdout-only target, or the target call appears only in an unexecuted nested definition
- **THEN** no stdout coverage is credited

#### Scenario: qualified target identity
- **WHEN** a qualified call uses a statically resolved, unshadowed import alias for the exact target module
- **THEN** its captured stream can be attributed to that target

#### Scenario: same-name collision or shadowed alias
- **WHEN** a qualified call names an unrelated receiver, a different module with the same basename, an unresolved import, or an alias shadowed in the test
- **THEN** matching the target function name alone MUST NOT credit its stream effect

### Requirement: capture-mapping-pipeline-integration

The normal quality pipeline MUST provide test context to capture-aware mapping. The repair MUST preserve taxonomy, schemas, classification and score formulas, and MUST analyze source without executing or importing it.

#### Scenario: measured contract coverage
- **WHEN** a fixture target has contractual return and stdout effects with separate direct return and attributable output assertions
- **THEN** the public quality result reports both effects covered and unrelated targets remain uncovered

### Requirement: ordered-execution-evidence

The context-aware mapper MUST use one ordered analysis for live return roles and capture provenance. Structural inspection of unsupported or deferred syntax MUST NOT establish executed target calls or drains. Possible producers MUST taint pending output independently of capture-value propagation. Unsupported capture assertions MUST remain blocked from legacy fallback.

#### Scenario: unreachable or deferred target
- **WHEN** a target or capture assertion occurs after unconditional return/raise, in unsupported conditional/loop syntax, or only in a deferred lambda body
- **THEN** that syntax MUST NOT establish target coverage, and contained capture assertions MUST remain unmapped

#### Scenario: uncertain drain cannot clean a window
- **WHEN** a possible producer taints a window and a conditional or deferred read precedes the target
- **THEN** the read MUST NOT clear ambiguity and the subsequent capture MUST remain unmapped

#### Scenario: definite drain restores isolation
- **WHEN** a supported definite fixture drain follows an unknown producer or context entry, then an exact target call precedes a saved capture
- **THEN** the saved snapshot MAY credit its stream despite a later context exit or drain

#### Scenario: possible drain consumes pending output
- **WHEN** a target call is followed by a conditional capture read and then another asserted capture read
- **THEN** the possible drain MUST invalidate pending target attribution without establishing a clean window

#### Scenario: definition header producer
- **WHEN** a definition default, decorator or annotation can emit output, including positional-only, vararg or kwarg annotations
- **THEN** it MUST taint the pending capture window without executing the nested body

### Requirement: canonical-scoped-capture-identity

Capture attribution MUST use canonical import-root/module identity and ordered lexical bindings. Unknown bare names, suffix matches and known conflicting bindings MUST NOT prove target identity. Attribute writes MUST distinguish rebinding a module name from replacing its target callable. Namespace-package capture identity MUST remain unsupported without an authoritative root.

#### Scenario: canonical package identity
- **WHEN** the file is `/project/src/pkg/example.py` with import root `/project/src`
- **THEN** exact `pkg.example` imports MAY prove identity and `example` or `src.pkg.example` imports MUST NOT

#### Scenario: direct local import and lexical shadowing
- **WHEN** a supported local import binds the exact target before its call
- **THEN** it MAY prove identity, while unrelated imports, parameters of any kind, definitions, conditional imports or a not-yet-assigned local name MUST NOT

#### Scenario: module member writes
- **WHEN** a test writes an unrelated module attribute and then definitely drains the fixture before calling the imported target
- **THEN** the module alias MAY still establish identity, but replacement of the target member MUST invalidate that callable

### Requirement: assertion-time-value-provenance

The mapper MUST evaluate RHS provenance before updating assignment destinations and use live roles at each assertion. Unsupported storage and transformations MUST retain blocked capture provenance. Mutable parsed JSON aliases MUST lose trusted provenance after mutation or escape to an unknown call. Such calls MUST also taint pending output.

#### Scenario: capture overwrites return
- **WHEN** `result` first receives a target return and then a fixture capture before `assert result.out`
- **THEN** the assertion MUST map only to attributable StdoutWrite, never the stale ReturnValue

#### Scenario: unsupported storage cannot revive credit
- **WHEN** capture output passes through chained assignment, attribute/subscript storage or an arbitrary receiver method
- **THEN** assertions on that value MUST NOT regain stream credit through semantic fallback

#### Scenario: parsed JSON alias mutation
- **WHEN** a saved JSON value derived from capture, or a nested descendant reached by indexing, is mutated through an alias or passed to an unknown helper
- **THEN** subsequent assertions through the parent containers, descendants and aliases in that parse's provenance family MUST NOT credit its former stream provenance

#### Scenario: bounded JSON support
- **WHEN** an unshadowed `import json` binding supplies `json.loads(stream)` with one positional argument and no keywords, followed by read-only indexing or equality/membership checks
- **THEN** a single attributable stream MAY retain provenance; hooks, shadowed bindings, arbitrary methods and mixed streams MUST remain unsupported
