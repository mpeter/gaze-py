## MODIFIED Requirements

### Requirement: first-match-wins

The mapper MUST apply return binding, exception, captured stream and semantic mapping in that order. Once an assertion is matched, later passes MUST NOT re-evaluate it. The mapper MUST preserve one output entry per input assertion and prevent double-counting.

#### Scenario: return binding keeps precedence
- **WHEN** an assertion references a bound return value and a captured stream
- **THEN** the return binding keeps precedence and the assertion is not counted twice

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

### Requirement: capture-mapping-pipeline-integration

The normal quality pipeline MUST provide test context to capture-aware mapping. The repair MUST preserve taxonomy, schemas, classification and score formulas, and MUST analyze source without executing or importing it.

#### Scenario: measured contract coverage
- **WHEN** a fixture target has contractual return and stdout effects with separate direct return and attributable output assertions
- **THEN** the public quality result reports both effects covered and unrelated targets remain uncovered
