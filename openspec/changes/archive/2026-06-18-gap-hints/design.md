## Context

`compute_contract_coverage()` already identifies gaps implicitly:
`contractual_types - covered_types` is the set of uncovered effect
types. The current code discards this set after computing the percentage.
This change collects the gap `SideEffect` objects and calls
`hint_for_effect()` for each, then attaches the results to
`ContractCoverageResult`.

## Goals / Non-Goals

### Goals

- `ContractCoverageResult.gaps` — tuple of uncovered contractual
  `SideEffect` objects, in the order they appear in `target.effects`
- `ContractCoverageResult.gap_hints` — parallel tuple of Python
  code snippet strings; `len(gaps) == len(gap_hints)` is enforced
- All 38 `SideEffectType` values covered by `hint_for_effect()`
- Surfaced in `quality_to_json()` output; invisible in `crap` output

### Non-Goals

- AI-enhanced hints
- `DiscardedReturns` / `DiscardedReturnHints` (Go O2 feature)
- Over-specification hints
- Any change to how coverage percentage is computed

## Decisions

### D1: `hints.py` — pure function, no imports from pipeline

`hint_for_effect(effect: SideEffect) -> str` takes one `SideEffect`
and returns one string. No config, no engine, no IO. Importable
without the CLI. Uses `match` statement on `effect.type`
(a `SideEffectType` StrEnum).

`SideEffect.target` in gaze-py is the containing function's qualified
name, not the affected entity (field, variable, return type) as in Go.
Therefore hints do not interpolate `target` for specificity — they use
the effect type and Python-idiomatic boilerplate instead. This is the
correct Python-native adaptation.

### D2: Effect type → hint mapping (all 38) <!-- id: f7ea3b9d-1d72-041d-7d09-63263d284c72 -->

P0 — Must Detect (5 types, tailored):

| Type | Hint |
|---|---|
| `ReturnValue` | `result = target(...)\nassert result == expected` |
| `ErrorReturn` | `with pytest.raises(ExceptionType):\n    target(...)` |
| `SentinelError` | `with pytest.raises(SpecificError):\n    target(...)` |
| `ReceiverMutation` | `target(obj, ...)\n# assert obj.<attr> changed` |
| `PointerArgMutation` | `target(arg, ...)\n# assert arg was mutated` |

P1 — High Value (8 types, tailored):

| Type | Hint |
|---|---|
| `SliceMutation` | `target(items, ...)\n# assert items contains expected values` |
| `MapMutation` | `target(mapping, ...)\n# assert mapping[key] == expected` |
| `GlobalMutation` | `target(...)\n# assert module.global_name == expected` |
| `WriterOutput` | `buf = io.BytesIO()\ntarget(buf, ...)\nassert buf.getvalue() == expected` |
| `HTTPResponseWrite` | `# assert HTTP response status and body after target()` |
| `ChannelSend` | `# assert value was sent to channel/queue after target()` |
| `ChannelClose` | `# assert channel/queue is closed/exhausted after target()` |
| `DeferredReturnMutation` | `result = target(...)\n# assert result (named return via captured value)` |

P2 — Important (10 types, semi-tailored):

| Type | Hint |
|---|---|
| `FileSystemWrite` | `target(...)\nassert Path(expected_path).exists()` |
| `FileSystemDelete` | `target(...)\nassert not Path(expected_path).exists()` |
| `FileSystemMeta` | `target(...)\n# assert file metadata (permissions, mtime) changed` |
| `DatabaseWrite` | `target(...)\n# assert db record exists/changed after call` |
| `DatabaseTransaction` | `target(...)\n# assert transaction committed or rolled back` |
| `GoroutineSpawn` | `# assert thread/task was spawned after target()` |
| `Panic` | `with pytest.raises((SystemExit, Exception)):\n    target(...)` |
| `CallbackInvocation` | `cb = Mock()\ntarget(cb, ...)\ncb.assert_called()` |
| `LogWrite` | `with caplog.at_level(logging.DEBUG):\n    target(...)\nassert 'expected' in caplog.text` |
| `ContextCancellation` | `# assert context/event was cancelled after target()` |

P3–P4 — generic fallback (12 types):

```python
f"# assert {effect.type.value} side effect of target()"
```

Applied to: `EnvVarMutation`, `MutexOp`,
`WaitGroupOp`, `AtomicOp`, `TimeDependency`,
`RecoverBehavior`, `ReflectionMutation`, `UnsafeMutation`, `CgoCall`,
`FinalizerRegistration`, `SyncPoolOp`, `ClosureCaptureMutation`.

Exception: `ProcessExit` and `StdoutWrite`/`StderrWrite` get tailored
hints despite being P3:

| Type | Hint |
|---|---|
| `ProcessExit` | `with pytest.raises(SystemExit) as exc_info:\n    target(...)\nassert exc_info.value.code == expected` |
| `StdoutWrite` | `out, _ = capsys.readouterr()\nassert 'expected' in out` |
| `StderrWrite` | `_, err = capsys.readouterr()\nassert 'expected' in err` |

### D3: Gap collection in `coverage.py`

The current code deduplicates by `SideEffectType` (one coverage count
per distinct type). The gap collection does the same: for each
uncovered contractual type, select the first `SideEffect` of that type
from `contractual` (the list built during classification). This
preserves the existing deduplication semantics while providing a
concrete effect object for the hint generator.

Build both `gap_effects` and `gap_hints` in a single pass over the
uncovered types, in the order they appear in `contractual` (insertion
order). Both lists are built in lockstep — no possibility of
length mismatch.

### D4: Fields on `ContractCoverageResult`

```python
gaps: tuple[SideEffect, ...] = ()
gap_hints: tuple[str, ...] = ()
```

Both default to empty tuple — zero-impact on existing callers.
`gaps` is `None`-safe: when `percentage is None` (no contractual
effects, `no_test_coverage`, etc.), the early-return path leaves
both as `()`.

### D5: JSON serialization

`quality_to_json()` uses `dataclasses.asdict()` which recursively
converts nested dataclasses. `SideEffect` converts cleanly: `id` (str),
`type` (StrEnum → str), `tier` (StrEnum → str), `location` (str),
`description` (str), `target` (str). `gap_hints` is a tuple of strings
→ JSON array. Both fields appear within the `contract_coverage` object
in the quality JSON output.

`crap` JSON output (`to_json()`) is unchanged — it reads from `Score`
fields on `FunctionTarget`, not from `ContractCoverageResult` directly.

### D6: Schema update

Add to the `quality_to_json()` schema documentation:
- `gaps`: array of SideEffect objects (id, type, tier, location,
  description, target) — effects with no mapped assertion
- `gap_hints`: array of strings — parallel to `gaps`

## Risks / Trade-offs

**Risk: `gaps` serialization adds payload size.** Each `SideEffect`
is ~5 string fields. A function with 3 gaps adds ~300 bytes to the
quality JSON. Acceptable for the use case (agent consumption, not
stream rendering). `/gaze-fix` needs the full object.

**Risk: P3/P4 hints are generic.** These effect types are rare in
Python (Go-isms like `WaitGroupOp`, `SyncPoolOp`) and have no clean
Python assertion pattern. The generic fallback is correct — it signals
to the user that an assertion is needed without prescribing a
language-inappropriate pattern.
