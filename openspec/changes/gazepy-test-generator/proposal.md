## Why

gaze-py ships `gazepy quality --format=json` but has no agent that consumes that output and produces concrete remediation. Go projects have `gaze-test-generator.md`; Python projects have nothing. This gap means engineers must manually translate quality analysis into test code, defeating the tool's purpose.

## What Changes

- Add `.opencode/agents/gazepy-test-generator.md` — a Python-native subagent that reads `gazepy quality --format=json` output and generates pytest test functions, strengthens assertions, improves Google-style docstrings, and produces decompose skeletons.
- No production code changes; no test changes; no CI changes.

## Capabilities

### New Capabilities

- `gazepy-test-generator`: A subagent that consumes `gazepy quality --format=json` data (GapHints, Gaps, FixStrategy, AmbiguousEffects) and produces complete, runnable pytest test functions — the Python-native equivalent of `gaze-test-generator.md`.

### Modified Capabilities

<!-- None — this is a net-new agent; no existing spec requirements change. -->

## Impact

- `.opencode/agents/gazepy-test-generator.md` (new file)
- No impact on `src/gaze_py/`, `tests/`, `pyproject.toml`, or CI workflows.
