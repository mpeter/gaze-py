## ADDED Requirements

### Requirement: Baseline matching MUST identify a function uniquely

The baseline comparator MUST NOT score one function against a different
function's baseline entry. A match key MUST distinguish functions that share a
simple name within the same file.

Methods MUST be keyed by their receiver: `package:receiver.function`.
Module-level functions (receiver absent or null) MUST keep the unqualified
`package:function` key, so that keys are stable for the common case and
existing baselines continue to match.

Go's equivalent key is `file + ":" + function` (D2) and needs no qualifier,
because a Go method's receiver is already part of its function name. Receiver
qualification reproduces that uniqueness in Python rather than departing
from it.

#### Scenario: Same-named methods in one file do not share a key
- **GIVEN** `WriteDeclaration.to_dict` and `CommandEntry.to_dict` in `cli_registry.py`
- **WHEN** match keys are computed
- **THEN** the two keys differ, and `WriteDeclaration.to_dict` keys as `cli_registry.py:WriteDeclaration.to_dict`

#### Scenario: Module-level functions keep the unqualified key
- **GIVEN** a function `run` in `foo.py` with no receiver
- **WHEN** its match key is computed
- **THEN** the key is `foo.py:run`, identical to the pre-0.9.1 key

### Requirement: Baseline entries sharing a key MUST match one-to-one

When two or more entries still share a key after receiver qualification — two
module-level functions of the same name in one file, such as nested helpers
both named `decorator` — the comparator MUST match them one-to-one in
encounter order. It MUST NOT collapse the group to a single entry and score
every occurrence against that survivor.

Encounter order is the detector's AST walk order, which is stable for an
unchanged file.

#### Scenario: Comparing a baseline against itself reports no change
- **GIVEN** any result set containing functions that share a key
- **WHEN** that set is compared against itself
- **THEN** regressions, improvements, new functions and removed functions are all zero

#### Scenario: A genuine regression in one overload is still reported
- **GIVEN** a baseline with `A.to_dict` and `B.to_dict` both at CRAP 1.0
- **WHEN** the current run reports `B.to_dict` at CRAP 9.0
- **THEN** exactly one regression is reported, and it identifies receiver `B` with a delta of +8.0

#### Scenario: A removed overload is reported, not hidden by its namesake
- **GIVEN** a baseline with `A.to_dict` and `B.to_dict`
- **WHEN** the current run contains only `A.to_dict`
- **THEN** exactly one removed function is reported, identifying receiver `B`

### Requirement: Baselines predating receiver qualification MUST keep matching

A baseline generated before receiver qualification keys methods without a
receiver. The comparator MUST fall back to the unqualified key when the
qualified key finds no group, so upgrading does not report every method as
simultaneously removed and new.

#### Scenario: A pre-0.9.1 baseline entry matches its method
- **GIVEN** a baseline entry keyed `m.py:to_dict` with no receiver recorded
- **WHEN** the current run reports `CommandEntry.to_dict` in `m.py` at the same CRAP
- **THEN** the function is reported as unchanged, with no new or removed functions
