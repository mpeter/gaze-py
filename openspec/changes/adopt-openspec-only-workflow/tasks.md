## 1. Archive history

- [x] 1.1 Archive specs 002 and 001 under `openspec/changes/archive/` with content intact (commit 16f286d).
- [x] 1.2 Track C.3, G.2 and the canonical spec headers in `.backlog/` (commit ee34131).

## 2. Retire the repository workflow

- [x] 2.1 Move the constitution to `openspec/constitution.md` and update every reader (commit 549c658; testing reviewer fixed in ee34131).
- [x] 2.2 Remove the old pipeline's commands, skill and tooling tree used by this repository (commit 549c658).
- [x] 2.3 Rewrite the AGENTS.md workflow section and add `openspec/config.yaml` (commit 549c658).

## 3. Verify

- [x] 3.1 `ruff check`, `ruff format --check`, `mypy --strict` and `pytest` (95.30% against the 85% floor) pass at ee34131.
- [x] 3.2 `openspec validate --changes` passes for every change.
