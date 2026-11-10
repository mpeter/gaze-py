## Why

gaze-py now uses OpenSpec as its only repository requirements pipeline, but
`gazepy init` still ships Spec Kit commands, agent guidance, and workflow
detection. Downstream users may rely on these assets. Removing them is a
separate user-visible change, not part of retiring this repository's workflow.

## What Changes

- Propose removing `speckit.testreview.md` from scaffolded assets and CLI output.
- Propose replacing Spec Kit detection in `gaze-fix.md` with OpenSpec guidance.
- Propose migrating shipped `reviewer-testing.md` constitution/artifact reads.
- Define upgrade behavior for existing tool-owned files and communicate the
  compatibility impact before changing product behavior.

## Capabilities

### Modified Capabilities

- `init-command`: remove Spec Kit scaffolding and update user-facing guidance.

## Impact

Future implementation touches `src/gaze_py/cli/assets/`, `scaffold.py`,
`main.py`, CLI tests, product specifications, and `docs/reference/cli/init.md`.
Repository tool-owned copies must be refreshed consistently. This proposal
does not implement any removal; existing assets and behavior stay unchanged.
