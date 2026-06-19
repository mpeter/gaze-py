# Spec: output-formatting

Authoritative requirements for JSON and text output formatting in gaze-py.
Sources: porting contracts OC-001 through OC-003, ECR-001 through ECR-004
(effect-confidence-range change), taxonomy-reference.md JSON field name
reference, and the current `report/json_formatter.py` implementation.

---

### Requirement: OC-001 Dual Format

The implementation MUST support at minimum two output formats:

- **JSON** (`--format=json`): Machine-readable, schema-validated output for
  CI pipelines and tooling. Parseable by `json.loads()`.
- **Text** (`--format=text`): Human-readable terminal output. Not JSON.

Both formats MUST be available for the `analyze`, `crap`, and `report`
commands.

#### Scenario: JSON format produces valid JSON
- **WHEN** `--format=json` is specified
- **THEN** the output is valid JSON parseable by `json.loads()`

#### Scenario: Text format produces non-JSON output
- **WHEN** `--format=text` is specified
- **THEN** the output is a non-empty human-readable string that is NOT valid JSON

#### Scenario: CLI failure — invalid path
- **WHEN** `gazepy analyze /nonexistent/path` is run
- **THEN** exit code is non-zero and stderr contains an error message

#### Scenario: CLI failure — malformed coverage-json
- **WHEN** `gazepy analyze <path> --coverage-json <invalid_file>` is run
  where `<invalid_file>` exists but is not valid JSON
- **THEN** exit code is non-zero and stderr contains the file path and parse error

---

### Requirement: OC-002 JSON Schema and Field Names

JSON output MUST use `snake_case` field names. The canonical field names from
the reference implementation MUST be preserved for cross-implementation
compatibility.

**Top-level structure**:
```json
{
  "functions": [...],
  "summary": {...}
}
```

**Function object fields** (flattened from the `Score` dataclass):

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Function name |
| `file_path` | string | Project-relative file path |
| `line` | integer | Line number of the function definition |
| `complexity` | integer | McCabe cyclomatic complexity |
| `side_effects` | array | Detected side effects (renamed from `effects`) |
| `line_coverage` | number or null | Line coverage fraction [0.0, 1.0] |
| `crap` | number or null | CRAP score |
| `gaze_crap` | number or null | GazeCRAP score (null when O1 not run) |
| `contract_coverage` | number or null | Contract coverage % (null when O1 not run) |
| `contract_coverage_reason` | string or null | Reason code when coverage is 0 or special |
| `fix_strategy` | string or null | Fix strategy (null when CRAP null or below threshold) |
| `quadrant` | string or null | Quadrant label (null when O1 not run) |
| `effect_confidence_range` | array or null | [min, max] confidence range (see ECR-001–ECR-004) |

**Summary object fields**:

| Field | Type | Description |
|-------|------|-------------|
| `function_count` | integer | Total analyzed functions |
| `crapload` | integer or null | Count of functions with CRAP >= threshold |
| `gaze_crapload` | integer or null | Count with GazeCRAP >= threshold; null when O1 not run |
| `avg_line_coverage` | number or null | Mean line coverage |
| `avg_contract_coverage` | number or null | Mean contract coverage; null when O1 not run |
| `quadrant_counts` | object or null | Per-quadrant function counts; null when O1 not run |
| `fix_strategy_counts` | object or null | Per-strategy function counts |
| `recommended_actions` | array or null | Prioritized action list |
| `crap_threshold` | number | Always non-null |
| `gaze_crap_threshold` | number | Always non-null |

The `Score` dataclass fields MUST be **flattened** into the function object
in JSON output — they MUST NOT appear as a nested `"score"` object.

The internal field name `effects` MUST be renamed to `side_effects` in JSON
output per the canonical field name table.

#### Scenario: Required function fields present
- **WHEN** a complete analysis result is serialized to JSON
- **THEN** each function object contains at minimum: `name`, `file_path`,
  `line`, `complexity`, `side_effects`, `line_coverage`, `crap`, `gaze_crap`,
  `contract_coverage`, `fix_strategy`, `quadrant`, `effect_confidence_range`

#### Scenario: snake_case enforcement
- **WHEN** any JSON output field name is inspected
- **THEN** no camelCase names appear (e.g., `sideEffects` would be a violation)

#### Scenario: effects renamed to side_effects
- **WHEN** a function with detected effects is serialized
- **THEN** the field name is `"side_effects"`, not `"effects"`

#### Scenario: Score fields flattened
- **WHEN** a function is serialized to JSON
- **THEN** `line_coverage`, `crap`, `gaze_crap`, etc. appear at the function
  level, NOT nested under a `"score"` key

---

### Requirement: OC-003 Nullable Fields (Null Not Zero)

Fields that depend on optional capabilities MUST be `null` in JSON output
when the capability has not run — not `0.0`, `0`, or `""`. This allows
consumers to distinguish "not computed" from "computed as zero."

| Field | Null when |
|-------|-----------|
| `line_coverage` | `--coverage-json` not provided |
| `crap` | `line_coverage` is null |
| `gaze_crap` | O1 quality pipeline not run |
| `contract_coverage` | O1 not run |
| `contract_coverage_reason` | O1 not run AND effects exist (see exception below) |
| `fix_strategy` | CRAP is null or CRAP < threshold |
| `quadrant` | Either coverage value is null |
| `gaze_crapload` | O1 not run |
| `avg_contract_coverage` | O1 not run |
| `quadrant_counts` | O1 not run |
| `effect_confidence_range` | Not all-ambiguous (see ECR-001–ECR-004) |

**Exception for `contract_coverage_reason`**: When a function has zero
detected side effects, `contract_coverage_reason` MUST be
`"no_effects_detected"` regardless of whether O1 has run. This is the one
reason code determinable from the detector alone.

**`recommended_actions` semantics**:
- `null` when CRAP is not computed (no coverage data)
- `[]` (empty list) when CRAP is computed but no functions are in the CRAPload

#### Scenario: Coverage absent — null not zero
- **WHEN** analysis runs without `--coverage-json`
- **THEN** `line_coverage` is `null` (NOT `0.0`) and `crap` is `null`

#### Scenario: GazeCRAP null without O1
- **WHEN** analysis runs without quality assessment
- **THEN** `gaze_crap` is `null`, `contract_coverage` is `null`, `quadrant` is `null`

#### Scenario: recommended_actions empty list when no CRAPload functions
- **WHEN** CRAP is computed but all functions are below the threshold
- **THEN** `recommended_actions` is `[]` (empty list, NOT null)

#### Scenario: contract_coverage_reason for zero effects
- **WHEN** a function has no detected side effects
- **THEN** `contract_coverage_reason` is `"no_effects_detected"`

#### Scenario: contract_coverage_reason null when O1 deferred and effects exist
- **WHEN** a function has detected side effects and O1 has not run
- **THEN** `contract_coverage_reason` is `null`

---

### Requirement: ECR-001 effect_confidence_range Populated for All-Ambiguous Functions

`Score.effect_confidence_range` MUST be populated as a `[min, max]` tuple
(serialized as a two-element integer array in JSON) when a function's
`contract_coverage.reason` is `"all_effects_ambiguous"` — that is, when all
detected effects are classified as ambiguous (none contractual, none incidental).

The values are the minimum and maximum `ClassificationResult.score` integers
across all effects on that function.

#### Scenario: effect_confidence_range populated for all-ambiguous function
- **WHEN** a function has effects where all are classified as ambiguous
  (reason is `"all_effects_ambiguous"`)
- **THEN** `effect_confidence_range` is a `[min_confidence, max_confidence]`
  two-element integer array where both values are the observed min and max
  `ClassificationResult.score` values

#### Scenario: effect_confidence_range reflects actual min/max
- **WHEN** a function has three ambiguous effects with scores 55, 65, 70
- **THEN** `effect_confidence_range` is `[55, 70]`

---

### Requirement: ECR-002 effect_confidence_range Null in All Other Cases

`Score.effect_confidence_range` MUST be `None` (serialized as `null`) in all
cases where the reason is NOT `"all_effects_ambiguous"`. This includes:

- `reason` is `None` (normal coverage computed)
- `reason` is `"no_effects_detected"` (function has no side effects)
- `reason` is `"no_contractual_effects"` (effects exist but all are incidental)
- Any normal coverage computation (some contractual effects exist)

#### Scenario: effect_confidence_range null when no effects
- **WHEN** a function has no detected side effects
- **THEN** `effect_confidence_range` is `null`

#### Scenario: effect_confidence_range null for normal coverage
- **WHEN** a function has contractual effects with normal coverage
- **THEN** `effect_confidence_range` is `null`

#### Scenario: effect_confidence_range null when all effects incidental
- **WHEN** a function has effects but all are classified as incidental
  (reason is `"no_contractual_effects"`)
- **THEN** `effect_confidence_range` is `null`

---

### Requirement: ECR-003 ContractCoverageResult Carries Min/Max Confidence

The `compute_contract_coverage()` function MUST populate `min_confidence` and
`max_confidence` fields on the returned `ContractCoverageResult` when the
reason is `"all_effects_ambiguous"`. Both fields MUST be `None` when the
reason is anything else.

**Valid `contract_coverage_reason` values**:

| Reason | Meaning |
|--------|---------|
| `None` | Normal coverage computed |
| `"no_effects_detected"` | Function has no side effects at all |
| `"no_contractual_effects"` | Effects exist but all are incidental |
| `"all_effects_ambiguous"` | Effects exist but all are ambiguous |

The `"all_effects_ambiguous"` branch requires splitting the `if not contractual:`
branch in `coverage.py`:
- `target.effects` is empty → `"no_effects_detected"`
- All effects are incidental (none ambiguous) → `"no_contractual_effects"`
- All effects are ambiguous (none contractual, none incidental) →
  `"all_effects_ambiguous"` with `min_confidence`/`max_confidence` populated

> **Go divergence (documented)**: The Go reference uses non-nullable `int`
> (zero-value sentinel) for `MinConfidence`/`MaxConfidence`. Python uses
> `int | None`; the guard `min_confidence is not None` is the Python equivalent
> of Go's `effectCount > 0`. This is a deliberate language adaptation.

#### Scenario: ContractCoverageResult has min/max for all-ambiguous
- **WHEN** `compute_contract_coverage()` classifies all effects as ambiguous
- **THEN** the result has `min_confidence` and `max_confidence` set to the
  observed min and max `ClassificationResult.score` values

#### Scenario: ContractCoverageResult min/max null for other reasons
- **WHEN** the reason is not `"all_effects_ambiguous"`
- **THEN** both `min_confidence` and `max_confidence` are `None`

---

### Requirement: ECR-004 effect_confidence_range Is Per-Function

`effect_confidence_range` is a **per-function** field on the `Score` object.
It is NOT an aggregate across all functions in the analysis result. Each
function independently determines whether its effects are all-ambiguous and
computes its own min/max range.

#### Scenario: effect_confidence_range is per-function, not aggregate
- **WHEN** an analysis result contains two functions — one all-ambiguous and
  one with contractual effects
- **THEN** the all-ambiguous function has a non-null `effect_confidence_range`
  and the other function has `null`

#### Scenario: JSON serialization — tuple serializes as array
- **WHEN** `Score.effect_confidence_range == (60, 85)`
- **THEN** the JSON output contains `"effect_confidence_range": [60, 85]`
  (two-element integer array, not null)

---

### Requirement: JSON Enum Serialization

Enum values in the output MUST be serialized as their string `.value`, not
as their Python enum representation. `SideEffectType` values (which are
`StrEnum`) MUST serialize as plain strings (e.g., `"ReturnValue"`, not
`"SideEffectType.ReturnValue"`).

#### Scenario: SideEffectType serializes as string
- **WHEN** a side effect with type `SideEffectType.ReturnValue` is serialized
- **THEN** the JSON contains `"type": "ReturnValue"` (not `"ReturnValue"` with
  enum wrapper)

#### Scenario: Tier serializes as string
- **WHEN** a side effect with tier `Tier.P0` is serialized
- **THEN** the JSON contains `"tier": "P0"`

---

### Requirement: JSON Schema Availability

The JSON output schema MUST be available as a module-level constant `SCHEMA`
in `report/json_formatter.py`. The `gazepy schema` CLI command MUST emit this
schema to stdout.

The schema MUST be a valid JSON Schema (draft-07) string that describes the
`AnalysisResult` output structure, including all nullable fields.

#### Scenario: Schema is valid JSON
- **WHEN** `SCHEMA` is imported from `report.json_formatter`
- **THEN** `json.loads(SCHEMA)` succeeds without error

#### Scenario: gazepy schema command
- **WHEN** `gazepy schema` is run
- **THEN** stdout contains valid JSON Schema output

---

### Requirement: Tuple Serialization

Python tuples in the output MUST serialize as JSON arrays. The custom JSON
encoder MUST convert tuples to lists. This applies to:

- `effect_confidence_range: tuple[int, int]` → `[int, int]`
- Any other tuple fields in frozen dataclasses

#### Scenario: Tuple serializes as JSON array
- **WHEN** `effect_confidence_range` is a Python tuple `(60, 85)`
- **THEN** the JSON output is `[60, 85]` (array, not object)

---

### Requirement: frozenset Serialization

`frozenset` fields (e.g., `AssertionSite.referenced_names`) MUST serialize
as sorted JSON arrays for deterministic output.

#### Scenario: frozenset serializes as sorted array
- **WHEN** a `frozenset` field is serialized
- **THEN** the JSON output is a sorted array (deterministic across runs)
