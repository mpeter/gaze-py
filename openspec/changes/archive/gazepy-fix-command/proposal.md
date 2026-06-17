<!-- spec-review: passed -->

## Why

gaze-py has `gazepy analyze`, `gazepy crap`, and `gazepy quality` for analysis,
but no first-class command to act on that analysis. The Go gaze project ships
`/gaze fix` — a dual-mode agent command that auto-detects the active workflow
or performs batch test-generation remediation. Python projects using gaze-py
have no equivalent, so the "detect workflow → generate tests" loop is not
available to them. This change adds `/gazepy fix` as the Python-native
equivalent of `/gaze fix`, closing that gap.

## What Changes

- **New file**: `.opencode/commands/gazepy-fix.md` — the `/gazepy fix` agent
  command.
- No modifications to any existing file. In particular, `.opencode/commands/gaze-fix.md`
  (which serves Go projects) MUST remain untouched.

## Capabilities

### New Capabilities

- `gazepy-fix-command`: An OpenCode agent command that operates in two modes:
  1. **No-args mode** — detects the active Speckit or OpenSpec workflow
     (identical detection logic to `/gaze fix`) and delegates to the
     appropriate implementation command (`/speckit.implement` or `/opsx-apply`).
  2. **Batch remediation mode** — accepts a Python source path, runs
     `gazepy crap` and `gazepy quality`, builds a prioritised target list,
     delegates to the `gazepy-test-generator` agent for each function, and
     verifies with `uv run pytest --tb=short`.

### Modified Capabilities

<!-- No existing specs are changing -->

## Impact

- **New agent command file**: `.opencode/commands/gazepy-fix.md`
- **No Python source changes**: this is a pure agent/command artifact.
- **No test changes required**: command files are not Python; the CI gate
  (`ruff`, `mypy`, `pytest`) is run to confirm no regressions from the branch.
- **Depends on**: `gazepy-test-generator` agent (already present in
  `openspec/changes/gazepy-test-generator/` or merged); `gazepy crap` and
  `gazepy quality` CLI subcommands.

## Coverage Strategy

Agent command files are Markdown, not testable Python. Behavioral verification
is manual (run the command, observe output). CI gate (`ruff`, `mypy`, `pytest`)
confirms no regressions from the branch. No automated test coverage is required
or possible for agent command Markdown files.
