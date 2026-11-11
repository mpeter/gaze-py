## 1. Specification

- [x] 1.1 Write proposal, design and the init-command delta.

## 2. Implementation

- [x] 2.1 Remove the retired command asset, its map and ownership entries, and its CLI docstring and hint text.
- [x] 2.2 Rewrite `gaze-fix.md` no-argument detection and `reviewer-testing.md` constitution and artifact reads; refresh the `.opencode/` copies.
- [x] 2.3 Update tests (asset list, closing hint) and add a test that an unmanaged file survives init and `--force`.
- [x] 2.4 Update `docs/reference/cli/init.md` and the CHANGELOG Unreleased section.

## 3. History and verification

- [x] 3.1 Reword archived specs and changes so they name one workflow; keep content and task state.
- [ ] 3.2 Run ruff, mypy, pytest with coverage and openspec validation at the committed HEAD.
- [ ] 3.3 Case-insensitive search of tracked files and file names for the retired workflow's names returns nothing.
