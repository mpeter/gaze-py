## Why

The Go gaze tool ships with a `gaze-test-generator` subagent that turns
`gaze quality` output into complete, compilable Go test functions. gaze-py has
no equivalent, leaving Python projects without a concrete path from quality
diagnosis to remediation. Adding `gazepy-test-generator` closes this gap,
giving Python developers the same workflow their Go counterparts have today.

## What Changes

- Add a new subagent file `.opencode/agents/gazepy-test-generator.md` that
  consumes `gazepy quality --format=json` output and generates pytest test
  functions, assertion improvements, docstring enhancements, and decomposition
  skeletons.
- No production source code is added or modified.
- No test files are added or modified.
- No CI configuration is added or modified.
- No new dependencies are introduced.

## Capabilities

### New Capabilities

- `gazepy-test-generator`: A subagent that reads `gazepy quality --format=json`
  data (GapHints, Gaps, FixStrategy, AmbiguousEffects, ContractCoverageReason,
  EffectConfidenceRange) and generates complete, runnable pytest test functions.
  Supports six fix strategies: `add_tests`, `add_assertions`, `add_docs`,
  `decompose_and_test`, `decompose`, and `verify`. Outputs to
  `tests/test_<module>.py` files. Works on any Python project gazepy can analyze.

### Modified Capabilities

<!-- None — no existing capability requirements change. -->

## Impact

- **New file**: `.opencode/agents/gazepy-test-generator.md`
- **No code changes**: only an agent prompt file is created; no Python source,
  test files, or CI workflows are touched.
- **No dependencies**: the agent references standard pytest idioms; no new
  packages are required in `pyproject.toml`.
- **Structural alignment**: mirrors the Go `gaze-test-generator.md` agent in
  intent, structure, and action taxonomy — translated for Python/pytest
  conventions throughout.

## Coverage Strategy

Agent command files are Markdown, not testable Python. Behavioral verification
is manual (run the command, observe output). CI gate (`ruff`, `mypy`, `pytest`)
confirms no regressions from the branch. No automated test coverage is required
or possible for agent prompt Markdown files.

<!-- spec-review: passed -->

<!-- code-review: passed -->
