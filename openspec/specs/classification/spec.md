# Spec: classification

Authoritative requirements for the side-effect classification engine in
gaze-py. Sources: porting contracts CC-001 through CC-006, and the current
`classify/engine.py` implementation.

---

### Requirement: CC-001 Confidence Scoring Formula

The classifier MUST compute a confidence score using this formula:

```
score = base_confidence + tier_boost(effect.tier) + sum(signal_weights) - contradiction_penalty
```

Where:

| Component | Value | Description |
|-----------|-------|-------------|
| `base_confidence` | 50 | Neutral starting point for all effects |
| `tier_boost(P0)` | +25 | P0 effects start at 75 |
| `tier_boost(P1)` | +10 | P1 effects start at 60 |
| `tier_boost(P2–P4)` | 0 | No boost; contractual nature depends on context |
| `signal_weights` | varies | Sum of all signal weights (positive and negative) |
| `contradiction_penalty` | -20 | Applied when both positive AND negative signals exist |

Effective starting scores before signals:
- **P0 effects**: 75 (50 + 25)
- **P1 effects**: 60 (50 + 10)
- **P2–P4 effects**: 50 (50 + 0)

The score is clamped to [0, 100] after all components are summed (see CC-002).

#### Scenario: P0 baseline — no signals
- **WHEN** a P0 effect is classified with no signals
- **THEN** the score is 75 (50 base + 25 tier boost)

#### Scenario: P1 baseline — no signals
- **WHEN** a P1 effect is classified with no signals
- **THEN** the score is 60 (50 base + 10 tier boost)

#### Scenario: P2–P4 baseline — no signals
- **WHEN** a P2 effect is classified with no signals
- **THEN** the score is 50 (50 base + 0 tier boost)

#### Scenario: Positive signal adds to score
- **WHEN** a P2 effect receives a naming signal of +10
- **THEN** the score is 60 (50 + 10)

#### Scenario: Contradiction penalty applied
- **WHEN** an effect receives one positive signal (+10) and one negative signal (-10)
- **THEN** the contradiction penalty of -20 is applied, and the score is
  50 + 10 + (-10) + (-20) = 30 (for a P2 effect)

---

### Requirement: CC-002 Score Clamping

The final confidence score MUST be clamped to the range [0, 100] after all
components (base, tier boost, signal sum, contradiction penalty) are summed.
No score outside this range may be stored or returned.

#### Scenario: Score clamped at lower bound
- **WHEN** the raw computed score is negative (e.g., -5)
- **THEN** the final score is 0

#### Scenario: Score clamped at upper bound
- **WHEN** the raw computed score exceeds 100 (e.g., 120)
- **THEN** the final score is 100

#### Scenario: Score at exact boundary — zero
- **WHEN** the raw computed score is exactly 0
- **THEN** the final score is 0 (no clamping needed; boundary is inclusive)

#### Scenario: Score at exact boundary — 100
- **WHEN** the raw computed score is exactly 100
- **THEN** the final score is 100 (no clamping needed; boundary is inclusive)

---

### Requirement: CC-003 Label Thresholds

The classifier MUST assign exactly one of three labels based on the clamped
confidence score:

| Label | Condition | Default Threshold |
|-------|-----------|-------------------|
| `contractual` | score >= contractual_threshold | 80 |
| `ambiguous` | incidental_threshold <= score < contractual_threshold | [50, 80) |
| `incidental` | score < incidental_threshold | < 50 |

Both thresholds MUST be configurable. The defaults are `contractual_threshold=80`
and `incidental_threshold=50`.

Boundary semantics:
- Score exactly at `contractual_threshold` → `contractual` (>= is inclusive)
- Score exactly at `incidental_threshold` → `ambiguous` (>= incidental_threshold
  means the score is NOT incidental)

#### Scenario: Contractual label
- **WHEN** a classified effect has score 85 with default thresholds
- **THEN** the label is `"contractual"`

#### Scenario: Incidental label
- **WHEN** a classified effect has score 40 with default thresholds
- **THEN** the label is `"incidental"`

#### Scenario: Ambiguous label
- **WHEN** a classified effect has score 65 with default thresholds
- **THEN** the label is `"ambiguous"`

#### Scenario: Boundary — exactly at contractual_threshold
- **WHEN** a classified effect has score 80 with `contractual_threshold=80`
- **THEN** the label is `"contractual"` (>= is inclusive at the upper boundary)

#### Scenario: Boundary — exactly at incidental_threshold
- **WHEN** a classified effect has score 50 with `incidental_threshold=50`
- **THEN** the label is `"ambiguous"` (score 50 >= incidental_threshold → ambiguous,
  not incidental)

#### Scenario: Custom thresholds respected
- **WHEN** `ClassificationEngine` is initialized with `contractual_threshold=90`
  and a classified effect has score 85
- **THEN** the label is `"ambiguous"` (85 < 90)

---

### Requirement: CC-004 Contradiction Detection

When both positive-weight and negative-weight signals are present for the same
effect, the classifier MUST apply a contradiction penalty of -20 to the score.
The contradiction MUST be recorded as an explicit signal entry with
`source="contradiction"` and `weight=-20`.

The contradiction signal is appended to the signal list after all five
analyzer signals are collected, before the score is computed.

#### Scenario: Contradiction signal recorded
- **WHEN** an effect receives one positive signal (e.g., naming +10) and one
  negative signal (e.g., docstring -15)
- **THEN** the signal list contains an entry with `source="contradiction"` and
  `weight=-20`

#### Scenario: No contradiction without both polarities — positive only
- **WHEN** an effect has only positive signals
- **THEN** no contradiction signal is present in the signal list

#### Scenario: No contradiction without both polarities — negative only
- **WHEN** an effect has only negative signals
- **THEN** no contradiction signal is present in the signal list

#### Scenario: No contradiction with no signals
- **WHEN** an effect has no signals from any analyzer
- **THEN** no contradiction signal is present

---

### Requirement: CC-005 Five Signal Categories

The classifier MUST implement signal analyzers for exactly five categories.
All five analyzers run for every effect. An analyzer that produces no signal
for a given effect returns `None` (no signal is added to the list).

#### Signal 1: Interface Satisfaction (source: `"interface"`, max weight: +30)

Checks whether the function's receiver/class implements an interface, abstract
base class (ABC), or Protocol that declares this method.

- **Weight**: +30 when the class inherits from an ABC or Protocol
- **Weight**: 0 (no signal returned) when no interface match is found
- **Python mapping**: class inherits from `abc.ABC`, `abc.ABCMeta`, or a
  `typing.Protocol`

#### Scenario: Interface satisfaction signal — ABC
- **WHEN** a method is on a class that inherits from an ABC
- **THEN** a signal with `source="interface"` and `weight=30` is returned

#### Scenario: No interface signal — standalone function
- **WHEN** a standalone function (not a method) is classified
- **THEN** no `"interface"` signal is produced

#### Signal 2: API Visibility (source: `"visibility"`, max weight: +20)

Checks whether the function and its types are part of the public API surface.
Three independent dimensions contribute:

| Dimension | Weight | Condition |
|-----------|--------|-----------|
| Exported function | +8 | Function name does not start with `_` |
| Exported return type | +6 | Return type annotation does not start with `_` |
| Exported receiver type | +6 | Receiver/class name does not start with `_` |

The total is clamped to +20. No signal is returned when the total is 0.

#### Scenario: API visibility — fully public
- **WHEN** a public function on a public class returns a public type
- **THEN** a signal with `source="visibility"` and `weight=20` is returned
  (exported function +8, return type +6, receiver type +6, clamped to 20)

#### Scenario: API visibility — private function
- **WHEN** a function named `_internal` is classified
- **THEN** the function dimension contributes 0 (no +8 for exported function)

#### Signal 3: Caller Dependency (source: `"caller"`, max weight: +15)

Counts how many distinct modules/packages call this function.

| Caller Count | Weight |
|-------------|--------|
| 0 | 0 (no signal returned) |
| 1 | +5 |
| 2–3 | +10 |
| 4+ | +15 |

#### Scenario: Caller dependency signal weights
- **WHEN** functions with 0, 1, 2, and 4 distinct caller modules are classified
- **THEN** weights are 0 (no signal), +5, +10, +15 respectively

#### Signal 4: Naming Convention (source: `"naming"`, max weight: +30 for sentinels, +10 otherwise)

Checks the function name against community naming conventions.

**Contractual prefixes** (weight +10 when the effect type matches the prefix's
implied types):
`Get`, `Fetch`, `Load`, `Read`, `Save`, `Write`, `Update`, `Set`, `Delete`,
`Remove`, `Handle`, `Process`, `Compute`, `Analyze`, `Classify`, `Parse`,
`Build`, `New`

The signal fires only when the effect type matches the prefix's implied types.
For example, `Get*` implies `ReturnValue` is contractual; `Save*` implies
`ReceiverMutation`, `PointerArgMutation`, and `ErrorReturn`.

**Incidental prefixes** (weight -10):
`log`, `Log`, `debug`, `Debug`, `trace`, `Trace`, `print`, `Print`

**Special case — Sentinel errors** (weight +30):
Exception classes named `Err*` with type `SentinelError` receive +30 instead
of +10. This is because sentinel error declarations cannot receive interface,
visibility, or documentation signals, so a stronger naming weight is the only
path to the contractual threshold.

#### Scenario: Naming — contractual prefix fires for implied effect type
- **WHEN** a function named `GetUser` has a `ReturnValue` effect
- **THEN** a signal with `source="naming"` and `weight=10` is returned

#### Scenario: Naming — contractual prefix does NOT fire for non-implied effect type
- **WHEN** a function named `GetUser` has a `LogWrite` effect
- **THEN** no naming signal with weight=10 is returned for the LogWrite effect

#### Scenario: Naming — sentinel special case
- **WHEN** a module-level exception class named `ErrNotFound` has a `SentinelError` effect
- **THEN** a signal with `source="naming"` and `weight=30` is returned

#### Scenario: Naming — incidental prefix
- **WHEN** a function named `logRequest` has a `LogWrite` effect
- **THEN** a signal with `source="naming"` and `weight=-10` is returned

#### Signal 5: Documentation (source: `"godoc"` or `"godoc_keyword_indirect"`, max weight: +15)

Parses the function's docstring for behavioral declarations.

**Contractual keywords** (direct match → +15, indirect match → +5):
`returns`, `writes`, `modifies`, `updates`, `sets`, `persists`, `stores`,
`deletes`, `removes`

A **direct match** means the keyword implies the detected effect type.
An **indirect match** means the keyword is found but the effect type doesn't match.

**Incidental keywords** (weight -15):
`logs`, `prints`, `traces`, `debugs`

Signal source IDs MUST use the canonical cross-implementation identifiers:
- Direct match: `source="godoc"`
- Indirect match: `source="godoc_keyword_indirect"`
- Incidental keyword: `source="godoc"`

Do NOT use `"docstring"` or `"pydoc"` — these identifiers break schema
compatibility with the Go gaze reference implementation.

#### Scenario: Docstring — direct keyword match
- **WHEN** a function's docstring contains "returns" and the effect is ReturnValue
- **THEN** a signal with `source="godoc"` and `weight=15` is returned

#### Scenario: Docstring — indirect keyword match
- **WHEN** a function's docstring contains "writes" and the effect is ReturnValue
- **THEN** a signal with `source="godoc_keyword_indirect"` and `weight=5` is returned

#### Scenario: Docstring — incidental keyword
- **WHEN** a function's docstring contains "logs"
- **THEN** a signal with `source="godoc"` and `weight=-15` is returned

#### Scenario: No docstring — no signal
- **WHEN** a function has no docstring
- **THEN** no docstring signal is produced

---

### Requirement: CC-006 Signal Recording

Every signal MUST be recorded in the `ClassificationResult` with at minimum:

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Signal category identifier (canonical values below) |
| `weight` | int | Numeric contribution to the confidence score (non-zero) |

The canonical `source` identifier values are:

| Source ID | Signal |
|-----------|--------|
| `"interface"` | Interface satisfaction |
| `"visibility"` | API visibility |
| `"caller"` | Caller dependency |
| `"naming"` | Naming convention |
| `"godoc"` | Documentation (direct match or incidental keyword) |
| `"godoc_keyword_indirect"` | Documentation (indirect match) |
| `"contradiction"` | Contradiction penalty |

Implementations SHOULD also record a `reasoning` field (human-readable
explanation) and MAY record `source_file` and `excerpt` for verbose output.

#### Scenario: Signal fields present
- **WHEN** a classified effect received signals from the naming and visibility
  analyzers
- **THEN** each signal object has a `source` string field and a `weight` int
  field that is non-zero

#### Scenario: Canonical source IDs used
- **WHEN** any signal is recorded
- **THEN** the `source` field is one of the 7 canonical values listed above
  (no `"docstring"`, `"pydoc"`, or other non-canonical identifiers)

#### Scenario: Contradiction signal uses canonical source
- **WHEN** a contradiction is detected
- **THEN** the contradiction signal has `source="contradiction"` and `weight=-20`

---

### Requirement: Classification Thresholds Are Configurable

The `ClassificationEngine` MUST accept `contractual_threshold` and
`incidental_threshold` as constructor parameters. The defaults are 80 and 50
respectively. Both MUST be in the range [0, 100].

#### Scenario: Custom thresholds accepted
- **WHEN** `ClassificationEngine(contractual_threshold=90, incidental_threshold=60)` is constructed
- **THEN** effects with score 85 are labeled `"ambiguous"` (not `"contractual"`)
  and effects with score 55 are labeled `"ambiguous"` (not `"incidental"`)

---

### Requirement: ClassificationResult Structure

The `ClassificationResult` returned by `classify()` MUST be a frozen dataclass
containing:

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | One of `"contractual"`, `"ambiguous"`, `"incidental"` |
| `score` | int | Clamped confidence score in [0, 100] |
| `signals` | tuple[Signal, ...] | All signals that contributed to the score |

#### Scenario: ClassificationResult is frozen
- **WHEN** a `ClassificationResult` is returned by `classify()`
- **THEN** attempting to assign to any field raises an error (frozen dataclass)

#### Scenario: Score is an integer
- **WHEN** a `ClassificationResult` is returned
- **THEN** the `score` field is an `int` in [0, 100]
