## Context

Three code locations are inconsistent:

1. `pipeline.py:assess()` — calls `detect_and_classify(src_path, config=config)`
   with no `include_unexported` arg → defaults to `False` in `runner.py`
2. `cli/main.py:quality` command — `--include-unexported` is_flag with
   `default=False`; the flag is passed to `_run_detect_classify()` but
   `assess()` is called independently without it
3. `cli/main.py` line 1758 — `crap` hardcodes `include_unexported=True` with
   a comment "crap analyzes all functions by default"

The fix is minimal: add `include_unexported: bool = True` to `assess()` and
wire the `quality` command's flag through to it. `detect_and_classify()` in
`runner.py` keeps its `False` default — it is a general-purpose library
function. `assess()` becomes the explicit opt-in caller.

## Goals / Non-Goals

**Goals:**
- `assess()` includes private functions by default
- `gazepy quality` includes private functions by default
- `--include-unexported` becomes an opt-out (`--no-include-unexported`)
- `gazepy crap --tests` behaviour unchanged (already `True`)
- All existing tests continue to pass

**Non-Goals:**
- Changing `detect_and_classify()` or `runner.py` defaults
- Changing `gazepy analyze` or `gazepy crap` (no `assess()` involved)
- Changing visibility signal weighting for private functions

## Decisions

### D1 — Where to add `include_unexported`

Add to `assess()` signature as `include_unexported: bool = True`. Pass it
directly to `detect_and_classify()`. Do not thread it through
`_process_test_func()` or `_untested_reports()` — filtering happens at the
source detection stage, before pairing.

```python
def assess(
    src_path: Path,
    tests_path: Path,
    *,
    config: GazeConfig,
    target_func: str | None = None,
    include_unexported: bool = True,   # ← new parameter
) -> AssessResult:
```

Line 78 of `pipeline.py`:
```python
source_targets = detect_and_classify(
    src_path.resolve(),
    config=config,
    include_unexported=include_unexported,   # ← pass through
)
```

### D2 — `quality` command wiring

The `quality` command already has a `--include-unexported` flag. Its
`default=False` changes to `default=True`. The flag is currently passed to
`_run_detect_classify()` for the JSON output path. It must also be passed to
`build_contract_coverage_map()` → `assess()`.

`build_contract_coverage_map()` does not yet accept `include_unexported`
(see D5 for the required signature update). After task 1.2 adds it, pass
`include_unexported` from the `quality` command through to `assess()`
(see task 2.2).

### D3 — `--include-unexported` becomes opt-out

The Click flag `is_flag=True, default=True` with name `--include-unexported`
creates `--include-unexported` (set True) and `--no-include-unexported`
(set False). Update help text:
```
"Include underscore-prefixed (unexported) functions. Default: on.
Pass --no-include-unexported to restrict to public functions only."
```

### D4 — Test fixture impact

Some tests in `test_quality_coverage.py`, `test_quality_integration.py`,
and `test_cli.py` likely assert on specific function counts or that private
functions are absent. These need updating to reflect the new default.

Run tests first to identify which ones fail, then fix assertions. Do not
change the behaviour being tested — only update expectations to match the
corrected default.

### D5 — `build_contract_coverage_map()` in pipeline.py

This function calls `assess()`. It must accept and forward
`include_unexported`. Current signature:

```python
def build_contract_coverage_map(
    src_path: Path,
    tests_path: Path,
    config: GazeConfig,
) -> dict[str, ContractCoverageResult]:
```

Update to:
```python
def build_contract_coverage_map(
    src_path: Path,
    tests_path: Path,
    config: GazeConfig,
    *,
    include_unexported: bool = True,
) -> dict[str, ContractCoverageResult]:
```

Then pass to `assess()`. The call site in `cli/main.py` (`_run_crap`) already
passes `include_unexported=True` explicitly, so that path is unaffected.

## Risks / Trade-offs

- [Risk] Tests that assert on function count or name lists may fail
  → Mitigation: D4 — run tests first, fix assertions, no behaviour change

- [Risk] Users who relied on the old filtering behaviour get more output
  → Mitigation: `--no-include-unexported` flag exists as opt-out; CHANGELOG
  documents the change clearly

- [Risk] Pairing recall improves but precision may drop (private functions
  with ambiguous names may pair incorrectly)
  → Acceptable: more signal is better than less; users can opt out
