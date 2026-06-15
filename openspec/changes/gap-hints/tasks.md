<!--
  [P] marks tasks eligible for parallel execution.
  Add [P] when a task: (a) touches different files from
  other [P] tasks in the group, (b) has no dependency
  on prior tasks in the group, (c) can safely execute
  without ordering constraints.
  Do NOT add [P] when tasks modify the same file —
  parallel workers will cause merge conflicts.
  Tasks without [P] run sequentially first, then [P]
  tasks run in parallel.
-->

## 1. hints.py — pure function module

- [ ] 1.1 Create `src/gaze_py/quality/hints.py` with:
      ```python
      from gaze_py.taxonomy.effects import SideEffectType
      from gaze_py.taxonomy.models import SideEffect

      def hint_for_effect(effect: SideEffect) -> str:
          """Return a Python assertion snippet for an uncovered contractual effect.

          Port of Go gaze internal/quality/hints.go:hintForEffect.
          P0/P1 effects receive tailored Python-idiomatic hints.
          P2 effects receive semi-tailored hints.
          P3/P4 effects receive a generic fallback, except ProcessExit,
          StdoutWrite, and StderrWrite which receive tailored hints.

          Args:
              effect: The SideEffect with no mapped assertion (a gap).

          Returns:
              A short, pasteable Python snippet suggesting how to write
              an assertion for this effect. Always a non-empty string.
          """
          match effect.type:
              # P0 — Must Detect
              case SideEffectType.ReturnValue:
                  return "result = target(...)\nassert result == expected"
              case SideEffectType.ErrorReturn:
                  return "with pytest.raises(ExceptionType):\n    target(...)"
              case SideEffectType.SentinelError:
                  return "with pytest.raises(SpecificError):\n    target(...)"
              case SideEffectType.ReceiverMutation:
                  return "target(obj, ...)\n# assert obj.<attr> changed"
              case SideEffectType.PointerArgMutation:
                  return "target(arg, ...)\n# assert arg was mutated"
              # P1 — High Value
              case SideEffectType.SliceMutation:
                  return "target(items, ...)\n# assert items contains expected values"
              case SideEffectType.MapMutation:
                  return "target(mapping, ...)\n# assert mapping[key] == expected"
              case SideEffectType.GlobalMutation:
                  return "target(...)\n# assert module.global_name == expected"
              case SideEffectType.WriterOutput:
                  return "buf = io.BytesIO()\ntarget(buf, ...)\nassert buf.getvalue() == expected"
              case SideEffectType.HTTPResponseWrite:
                  return "# assert HTTP response status and body after target()"
              case SideEffectType.ChannelSend:
                  return "# assert value was sent to channel/queue after target()"
              case SideEffectType.ChannelClose:
                  return "# assert channel/queue is closed/exhausted after target()"
              case SideEffectType.DeferredReturnMutation:
                  return "result = target(...)\n# assert result (named return via captured value)"
              # P2 — Important
              case SideEffectType.FileSystemWrite:
                  return "target(...)\nassert Path(expected_path).exists()"
              case SideEffectType.FileSystemDelete:
                  return "target(...)\nassert not Path(expected_path).exists()"
              case SideEffectType.FileSystemMeta:
                  return "target(...)\n# assert file metadata (permissions, mtime) changed"
              case SideEffectType.DatabaseWrite:
                  return "target(...)\n# assert db record exists/changed after call"
              case SideEffectType.DatabaseTransaction:
                  return "target(...)\n# assert transaction committed or rolled back"
              case SideEffectType.GoroutineSpawn:
                  return "# assert thread/task was spawned after target()"
              case SideEffectType.Panic:
                  return "with pytest.raises((SystemExit, Exception)):\n    target(...)"
              case SideEffectType.CallbackInvocation:
                  return "cb = Mock()\ntarget(cb, ...)\ncb.assert_called()"
              case SideEffectType.LogWrite:
                  return ("with caplog.at_level(logging.DEBUG):\n"
                          "    target(...)\n"
                          "assert 'expected' in caplog.text")
              case SideEffectType.ContextCancellation:
                  return "# assert context/event was cancelled after target()"
              # P3 — tailored exceptions (rest fall through to generic)
              case SideEffectType.StdoutWrite:
                  return "out, _ = capsys.readouterr()\nassert 'expected' in out"
              case SideEffectType.StderrWrite:
                  return "_, err = capsys.readouterr()\nassert 'expected' in err"
              case SideEffectType.ProcessExit:
                  return ("with pytest.raises(SystemExit) as exc_info:\n"
                          "    target(...)\n"
                          "assert exc_info.value.code == expected")
              # P3/P4 — generic fallback
              case _:
                  return f"# assert {effect.type.value} side effect of target()"
      ```

## 2. Taxonomy — ContractCoverageResult fields

- [ ] 2.1 Add two fields to `ContractCoverageResult` in
      `src/gaze_py/taxonomy/models.py`:
      ```python
      gaps: tuple[SideEffect, ...] = ()
      gap_hints: tuple[str, ...] = ()
      ```
      Place after `max_confidence`. Update the class docstring to add:
      ```
      gaps: Contractual effects with no mapped assertion, in the order
          they appear in the target function's effects. Parallel to
          gap_hints. Empty when coverage is 100% or when percentage
          is None (no contractual effects, no_test_coverage, etc.).
      gap_hints: Python assertion snippets, one per gap. Parallel to
          gaps — len(gaps) == len(gap_hints) is an enforced
          postcondition. Empty when gaps is empty.
      ```

## 3. Coverage — gap collection

- [ ] 3.1 Update `compute_contract_coverage()` in
      `src/gaze_py/quality/coverage.py`:
      - Add import: `from gaze_py.quality.hints import hint_for_effect`
      - After computing `covered_count`, build gap data in a single pass
        over `contractual` (the list of classified contractual
        `SideEffect` objects), in insertion order, deduplicated by type:
        ```python
        seen_gap_types: set[SideEffectType] = set()
        gap_effects: list[SideEffect] = []
        hints: list[str] = []
        for effect in contractual:
            if effect.type not in covered_types and effect.type not in seen_gap_types:
                seen_gap_types.add(effect.type)
                gap_effects.append(effect)
                hints.append(hint_for_effect(effect))
        ```
      - Pass `gaps=tuple(gap_effects), gap_hints=tuple(hints)` to the
        returned `ContractCoverageResult`.
      - When percentage is None (early-return paths: no contractual
        effects, `no_test_coverage`, `all_effects_ambiguous`), the
        `ContractCoverageResult` is constructed without these kwargs —
        both default to `()`. No change to those paths.

## 4. JSON formatter — schema update

- [ ] 4.1 Verify `quality_to_json()` in
      `src/gaze_py/report/json_formatter.py` serialises the new fields
      correctly. `dataclasses.asdict()` already recursively converts
      nested dataclasses including `SideEffect`. Run:
      `assert "gap_hints" in quality_to_json([report])`
      on a fixture with a gap to confirm. Update the SCHEMA constant
      docstring to note that `contract_coverage` objects may now contain
      `gaps` (array of SideEffect dicts) and `gap_hints` (array of
      strings) when coverage is partial.

## 5. Tests

- [ ] 5.1 [P] Create `tests/test_quality_hints.py`:
      Build a minimal `SideEffect` fixture:
      ```python
      def _make_effect(effect_type: SideEffectType) -> SideEffect:
          return SideEffect(
              id="se-00000000",
              type=effect_type,
              tier=TIER_MAP[effect_type],
              location="test.py:1:0",
              description="test",
              target="test_func",
          )
      ```
      Tests:
      - `test_hint_for_return_value` — hint contains "result" and "assert"
      - `test_hint_for_error_return` — hint contains "pytest.raises"
      - `test_hint_for_sentinel_error` — hint contains "pytest.raises"
      - `test_hint_for_receiver_mutation` — hint contains "assert"
      - `test_hint_for_pointer_arg_mutation` — hint contains "assert"
      - `test_hint_for_writer_output` — hint contains "BytesIO" or "buf"
      - `test_hint_for_filesystem_write` — hint contains "Path" or "exists"
      - `test_hint_for_process_exit` — hint contains "SystemExit"
      - `test_hint_for_stdout_write` — hint contains "capsys"
      - `test_hint_for_stderr_write` — hint contains "capsys"
      - `test_hint_for_callback_invocation` — hint contains "Mock" or "assert_called"
      - `test_hint_for_log_write` — hint contains "caplog"
      - `test_hint_for_all_38_types_non_empty` — parametrize over all 38
        `SideEffectType` values; assert `hint_for_effect(effect)` returns
        a non-empty string for every type (guards against missing match
        arms and empty string returns)

- [ ] 5.2 [P] Append new tests to `tests/test_quality_coverage.py`
      (no modification to existing tests):
      - `test_gaps_populated_when_coverage_is_partial` — partial coverage
        (1 of 2 contractual effects covered) → `len(result.gaps) == 1`
        and `len(result.gap_hints) == 1`
      - `test_gaps_empty_when_fully_covered` — 100% coverage →
        `result.gaps == ()` and `result.gap_hints == ()`
      - `test_gaps_gap_hints_same_length` — parametrize over partial,
        full, and zero-coverage cases; assert
        `len(result.gaps) == len(result.gap_hints)` for each
      - `test_gaps_not_populated_when_percentage_is_none` — when
        `no_test_coverage=True`, `result.gaps == ()` and
        `result.gap_hints == ()`
      - `test_gap_hints_are_non_empty_strings` — for partial coverage,
        all hints in `result.gap_hints` are non-empty strings

- [ ] 5.3 Append to `tests/test_quality_integration.py`
      (no modification to existing tests):
      - `test_quality_report_includes_gap_hints` — run `assess()` on the
        `undertested` fixture (function with `ReturnValue` effect, zero
        assertions). Find the report whose `target_function == "compute_total"`.
        Assert `report.contract_coverage.gap_hints` is non-empty and
        `report.contract_coverage.gap_hints[0]` contains "result" or
        "assert" (i.e., the ReturnValue hint fires).

## 6. CI gate

- [ ] 6.1 [P] `uv run ruff check .`
- [ ] 6.2 [P] `uv run ruff format --check .`
- [ ] 6.3 [P] `uv run mypy --strict src/`
- [ ] 6.4     `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
