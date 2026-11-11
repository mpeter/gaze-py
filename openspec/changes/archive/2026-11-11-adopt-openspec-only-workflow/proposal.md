## Why

The repository ran two requirements pipelines: a strategic-spec tree (`specs/`
with its own tooling directory and commands) and OpenSpec (`openspec/`). Two sources of truth let
reviewers meet diverging answers to "what are the requirements". OpenSpec is the
single requirements authority across the owner's software projects, decided
2026-11-10; this repository adopts it exclusively.

## What Changes

- Archive the finished strategic specs 001 and 002 under `openspec/changes/archive/`, keeping their content and task state, with evidence appended to 002.
- Move the constitution from the old tooling directory to `openspec/constitution.md` and update every agent and command that reads it.
- Remove the old pipeline's commands, skill and tooling tree used by this repository's own workflow.
- Rewrite the AGENTS.md workflow section and add `openspec/config.yaml`.
- Track unfinished follow-ups (C.3, G.2, canonical spec headers) in `.backlog/`.
- Not changed: files `gazepy init` ships to users. `remove-legacy-workflow-assets` covers them.

## Capabilities

### New Capabilities

- `repository-workflow`: how requirements, history and governance are kept in this repository.

## Impact

Agent definitions, commands, AGENTS.md, `openspec/`, `.backlog/` and the removed `specs/` and old tooling trees. No runtime or CLI behavior changes.
