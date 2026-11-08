## ADDED Requirements

### Requirement: Recorded subprocess invocation evidence

The mapper MUST credit GoroutineSpawn only when the selected production function
contains one unshadowed direct subprocess.run call, a live pytest monkeypatch
connects that boundary to a nested fake, and that fake records its received
positional argument and keyword arguments in a local dictionary. Attribution MUST
require an exact selected-target call followed by direct record equality.

#### Scenario: Invocation and stdout asserted together
- **GIVEN** the supported straight-line fake and live patch
- **WHEN** the selected target is exercised and its return and record are asserted
- **THEN** the return assertion MUST map to ReturnValue and the record assertion
  MUST map to GoroutineSpawn

#### Scenario: Deferred body, escaped record or state-changing annotation
- **GIVEN** a generator production function, a record passed into the selected
  target, or a fake header outside the bounded inert annotation grammar
- **WHEN** the test constructs the target result and asserts the record
- **THEN** the invocation matcher MUST NOT grant GoroutineSpawn coverage

#### Scenario: Record name rebound to the target return
- **GIVEN** an earlier record/fake/patch setup
- **WHEN** the record name is rebound to the selected target's return and asserted
- **THEN** independent ReturnValue evidence MUST remain mapped and the invocation
  matcher MUST NOT override it with either spawn evidence or an unmapped entry

#### Scenario: Missing or ambiguous provenance
- **GIVEN** an unrelated target or record, unused fake, overwritten or rebound
  record, wrong or shadowed patch target, or multiple calls sharing a fake
- **WHEN** the record is asserted
- **THEN** the new matcher MUST NOT grant spawn coverage

### Requirement: Existing metric policy

Classification confidence, effect taxonomy, max-per-test reduction, thresholds,
and baselines MUST NOT change. An added mapping MUST NOT cover ErrorReturn in a
success test or union independent tests.

#### Scenario: Caller confidence promotes spawn
- **GIVEN** zero, one, or two caller modules and separate success and error tests
- **WHEN** invocation evidence is mapped
- **THEN** spawn confidence MUST remain 69, 74, or 79 respectively and the maximum
  per-test coverage MUST be 50%, 50%, or two thirds respectively
