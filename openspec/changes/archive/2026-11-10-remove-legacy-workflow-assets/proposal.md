## Why

OpenSpec is the only requirements pipeline for this project, decided
2026-11-10. `gazepy init` still ships a command, agent text and workflow
detection written for the previous pipeline, so a freshly initialized project
is told to use tooling this project no longer supports. The shipped assets
should describe one workflow only.

## What Changes

- **BREAKING**: `gazepy init` no longer deploys the retired `testreview` command file under `.opencode/commands/`.
- `gaze-fix.md` (no-argument mode) detects only an active OpenSpec change under
  `openspec/changes/` and otherwise offers `/opsx-apply` or batch remediation.
- `reviewer-testing.md` reads the constitution from `openspec/constitution.md`
  and reviews OpenSpec change artifacts in its artifact-review mode.
- `gazepy init` closing hint points at `/gaze` and `/gaze-fix`.
- Existing projects: `gazepy init` leaves a command file it no longer manages
  where it is (see design). The repository's own `.opencode/` copies are refreshed.
- CHANGELOG entry under Unreleased; the release bump is separate (see design).
- Canonical specs gain the `## Purpose` / `## Requirements` structure OpenSpec
  validates, and archived history is reworded so it names one workflow.

## Capabilities

### Modified Capabilities

- `init-command`: asset list and closing hint no longer include the retired command.

## Impact

`src/gaze_py/cli/assets/`, `scaffold.py`, `main.py`, `tests/test_cli.py`,
`docs/reference/cli/init.md`, `.opencode/` copies, `openspec/specs/`,
archived changes, `CHANGELOG.md`, version files.
