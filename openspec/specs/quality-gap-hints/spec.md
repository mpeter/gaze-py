# Spec: quality-gap-hints

Gap hints for the O1 quality assessment pipeline. Identifies which
contractual effects have no mapped assertion (gaps) and generates a parallel
list of Python assertion snippets suggesting how to cover each gap.

Port of Go gaze `internal/quality/hints.go` and the `Gaps`/`GapHints` fields
in `ContractCoverage`.

---

### Requirement: gaps-and-gap-hints-fields

`ContractCoverageResult` MUST carry two parallel fields:
- `gaps: tuple[SideEffect, ...]` — contractual effects with no mapped
  assertion, in the order they appear in the target function's effects list,
  deduplicated by `SideEffectType` (one entry per distinct uncovered type).
- `gap_hints: tuple[str, ...]` — Python assertion snippets, one per gap.

The postcondition `len(gaps) == len(gap_hints)` MUST hold for every
`ContractCoverageResult` instance. Both fields MUST be populated in lockstep
(they grow together in a single pass over contractual effects).

#### Scenario: gaps and gap_hints are co-indexed
- **WHEN** coverage is 50% with 2 uncovered contractual effect types
- **THEN** `len(result.gaps) == len(result.gap_hints) == 2`

#### Scenario: 100% coverage produces empty gaps
- **WHEN** all contractual effects have at least one mapped assertion
- **THEN** `result.gaps == ()` and `result.gap_hints == ()`

#### Scenario: None percentage produces empty gaps
- **WHEN** `percentage is None` (any reason code)
- **THEN** `result.gaps == ()` and `result.gap_hints == ()`

---

### Requirement: gaps-deduplication

Gaps MUST be deduplicated by `SideEffectType`. When a function has multiple
`SideEffect` objects of the same type and that type is uncovered, only the
first occurrence (in `target.effects` order) MUST appear in `gaps`. The
corresponding `gap_hints` entry is generated from that first occurrence.

#### Scenario: duplicate uncovered effect type deduplicated
- **WHEN** a function has two `ReturnValue` effects and neither is covered
- **THEN** `gaps` contains exactly one `SideEffect` of type `ReturnValue`,
  and `gap_hints` has one corresponding hint

---

### Requirement: hint-for-effect-completeness

`hint_for_effect(effect: SideEffect) -> str` MUST return a non-empty string
for every one of the 38 `SideEffectType` values (EC-001). No `SideEffectType`
value may produce an empty string or fall through to a silent default.

#### Scenario: all 38 effect types produce non-empty hints
- **WHEN** `hint_for_effect()` is called with each of the 38 `SideEffectType`
  values
- **THEN** every call returns a non-empty string

---

### Requirement: hint-content-by-tier

`hint_for_effect()` MUST produce tailored Python-idiomatic hints for P0 and
P1 effect types, semi-tailored hints for P2 types, and a generic fallback
for most P3/P4 types. Three P3 types receive tailored hints:
`StdoutWrite`, `StderrWrite`, and `ProcessExit`.

Specific required hint content:

| Effect Type | Required hint content |
|---|---|
| `ReturnValue` | Uses `result = target(...)` and `assert result == expected` |
| `ErrorReturn` | Uses `pytest.raises(ExceptionType)` |
| `SentinelError` | Uses `pytest.raises(SpecificError)` |
| `ReceiverMutation` | Mentions asserting `obj.<attr>` changed |
| `PointerArgMutation` | Mentions asserting `arg` was mutated |
| `SliceMutation` | Mentions asserting `items` contains expected values |
| `MapMutation` | Mentions asserting `mapping[key] == expected` |
| `GlobalMutation` | Mentions asserting `module.global_name == expected` |
| `WriterOutput` | Uses `io.BytesIO()` and `buf.getvalue()` |
| `FileSystemWrite` | Uses `Path(expected_path).exists()` |
| `FileSystemDelete` | Uses `not Path(expected_path).exists()` |
| `CallbackInvocation` | Uses `Mock()` and `cb.assert_called()` |
| `LogWrite` | Uses `caplog.at_level` and `caplog.text` |
| `StdoutWrite` | Uses `capsys.readouterr()` and checks `out` |
| `StderrWrite` | Uses `capsys.readouterr()` and checks `err` |
| `ProcessExit` | Uses `pytest.raises(SystemExit)` and `exc_info.value.code` |
| `Panic` | Uses `pytest.raises((SystemExit, Exception))` |

#### Scenario: ReturnValue hint is pasteable
- **WHEN** `hint_for_effect()` is called with a `ReturnValue` effect
- **THEN** the hint contains `result = target(...)` and `assert result == expected`

#### Scenario: StdoutWrite hint uses capsys
- **WHEN** `hint_for_effect()` is called with a `StdoutWrite` effect
- **THEN** the hint contains `capsys.readouterr()` and checks `out`

#### Scenario: P4 effect gets generic fallback
- **WHEN** `hint_for_effect()` is called with a P4 effect type (e.g.,
  `NetworkCall`, `ExternalServiceCall`)
- **THEN** the hint is a non-empty generic comment referencing the effect type

---

### Requirement: hint-for-effect-pure-function

`hint_for_effect()` MUST be a pure function with no configuration, no
engine, no network access, and no side effects. It MUST depend only on
`effect.type` (the `SideEffectType` enum value) and `effect` (for the
generic fallback that uses `effect.type.value`).

#### Scenario: same effect type always produces same hint
- **WHEN** `hint_for_effect()` is called twice with effects of the same type
- **THEN** both calls return identical strings

---

### Requirement: gap-hints-in-json-output

`quality_to_json()` MUST include `gaps` (array of effect objects) and
`gap_hints` (array of strings) in the JSON output for each report entry.
Both MUST be empty arrays (`[]`) when `percentage is None` or when coverage
is 100% (no gaps). They MUST be non-empty arrays when coverage is partial.

#### Scenario: partial coverage includes gaps and hints in JSON
- **WHEN** a function has 50% coverage with one uncovered contractual effect
- **THEN** JSON output contains `"gaps": [<effect object>]` and
  `"gap_hints": ["<hint string>"]`

#### Scenario: no_test_coverage produces empty arrays
- **WHEN** `reason="no_test_coverage"` (percentage is None)
- **THEN** JSON output contains `"gaps": []` and `"gap_hints": []`

#### Scenario: 100% coverage produces empty arrays
- **WHEN** all contractual effects are covered
- **THEN** JSON output contains `"gaps": []` and `"gap_hints": []`
