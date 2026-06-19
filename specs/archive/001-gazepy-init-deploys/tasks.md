# Tasks: gazepy init Deploys to gaze-* Names

**Branch**: `001-gazepy-init-deploys`
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: uf fork — sentinel change + binary shadow [US2]

**Purpose**: Update `uf` so it uses `gaze-reporter.md` as the gazepy sentinel and
shadow the brew binary locally. MUST complete before Phase 2 (gaze-py source changes
are meaningless until uf sentinel matches).

- [ ] T001 [US2] Edit `internal/scaffold/scaffold.go` in `mpeter/unbound-force`: change gazepy sentinel from `agents/gazepy-reporter.md` → `agents/gaze-reporter.md` (1 line)
- [ ] T002 [US2] Add `TestInitSubTools_GazepySkippedWhenSentinelPresent` to `internal/scaffold/scaffold_test.go`: Python project + `gaze-reporter.md` present → `gazepy init` NOT called
- [ ] T003 [US2] Run `go test -race ./internal/scaffold/...` in uf fork — must pass
- [ ] T004 [US2] Run `make install` in uf fork to build `~/go/bin/unbound-force`
- [ ] T005 [US2] Shadow brew binary: `chmod u+w` Cellar binary, replace with symlink to `~/go/bin/unbound-force`
- [ ] T006 [US2] Verify `uf version` shows `vdev` and `which uf` resolves to brew path (shadowed)
- [ ] T007 [US2] Commit uf fork changes to `mpeter/unbound-force` on `main`

**Checkpoint**: `uf version` shows vdev. `uf init` on Python project with `gaze-reporter.md`
present → skips gazepy init.

---

## Phase 2: gaze-py source — asset rename + scaffold + tests [US1]

**Purpose**: Change what `gazepy init` deploys. After this phase, running `gazepy init`
in any fresh Python project produces `gaze-reporter.md` and `gaze.md`.

- [ ] T008 [P] [US1] Rename `src/gaze_py/cli/assets/agents/gazepy-reporter.md` → `gaze-reporter.md`; update `# gazepy-reporter` heading → `# gaze-reporter`; update cross-link at line 72 (remove stale reference to Go canonical)
- [ ] T009 [P] [US1] Rename `src/gaze_py/cli/assets/commands/gazepy.md` → `gaze.md`; update `agent: gazepy-reporter` → `agent: gaze-reporter`; `# /gazepy` → `# /gaze`; example commands `gazepy` → `gaze`
- [ ] T010 [US1] Update `src/gaze_py/cli/scaffold.py` `_ASSET_MAP`: both tuples — `gazepy-reporter.md` → `gaze-reporter.md`, `gazepy.md` → `gaze.md` (2 string changes)
- [ ] T011 [US1] Update `src/gaze_py/cli/main.py` init docstring: `agents/gazepy-reporter.md` → `agents/gaze-reporter.md`, `commands/gazepy.md` → `commands/gaze.md`
- [ ] T012 [US1] Update `tests/test_cli.py`: replace all 14 occurrences of `gazepy-reporter.md` → `gaze-reporter.md` and `gazepy.md` → `gaze.md`; update content assertion `b"gazepy-reporter"` → `b"gaze-reporter"`
- [ ] T013 [US1] Bump version in `pyproject.toml`: `0.4.0` → `0.4.1`
- [ ] T014 [US1] Run `uv run pytest --tb=short -q` — must pass ≥ 85% coverage (all scaffold tests green)

**Checkpoint**: `uv run gazepy init` in a temp dir creates `agents/gaze-reporter.md`
and `commands/gaze.md`. Test suite passes.

---

## Phase 3: .opencode cleanup — delete Go files, rename Python files [US1 + US2]

**Purpose**: Remove stale Go-content files from this repo's `.opencode/` and rename the
existing Python-content `gazepy-*` files to `gaze-*`. After this phase, no Go artifacts
remain and `/gaze` commands correctly delegate to Python agents.

- [ ] T015 [P] [US1] Delete Go-content files: `.opencode/agents/gaze-reporter.md`, `.opencode/agents/gaze-test-generator.md`, `.opencode/commands/gaze.md`, `.opencode/commands/gaze-fix.md`
- [ ] T016 [P] [US1] Rename Python-content files: `agents/gazepy-reporter.md` → `agents/gaze-reporter.md`, `commands/gazepy.md` → `commands/gaze.md`, `agents/gazepy-test-generator.md` → `agents/gaze-test-generator.md`, `commands/gazepy-fix.md` → `commands/gaze-fix.md`
- [ ] T017 [US1] Update `agents/gaze-test-generator.md` (formerly `gazepy-test-generator.md`): update any internal self-references from `gazepy-test-generator` → `gaze-test-generator`
- [ ] T018 [US1] Update `commands/gaze-fix.md` (formerly `gazepy-fix.md`): update internal refs from `gazepy-test-generator` → `gaze-test-generator`, `gazepy-fix` → `gaze-fix`, `/gazepy fix` → `/gaze fix`
- [ ] T019 [US1] Update `commands/review-council.md` Phase 1b: `which gaze` → `uv run gazepy --version 2>/dev/null`; install hint → `uv tool install gaze-py`; `subagent_type: gaze-reporter` stays correct
- [ ] T020 [US1] Update `agents/cobalt-crush-dev.md` Gaze Feedback Loop: install hint → `uv tool install gaze-py`; `coverage.out` → `.coverage` / `coverage.json`
- [ ] T021 [US1] Verify `uf init` on gaze-py shows all files skipped (sentinel `gaze-reporter.md` found, no Go content deployed)
- [ ] T022 [US1] Verify `uv run gazepy init` in fresh temp dir creates `agents/gaze-reporter.md` and `commands/gaze.md` and NOT `gazepy-reporter.md` or `gazepy.md`

**Checkpoint**: No `gazepy-*` files in `.opencode/`. All commands use `gaze-*` names.
`/gaze` delegates to Python reporter. `uf init` is idempotent.

---

## Phase 4: Polish — CI gate + commit

- [ ] T023 Run full CI gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest --cov=gaze_py --cov-fail-under=85`
- [ ] T024 Commit all changes with message: `fix(init): gazepy init deploys to gaze-* names — coordinated with uf sentinel change`
- [ ] T025 Push branch `001-gazepy-init-deploys` to `origin`

---

## Dependencies & Execution Order

- **Phase 1** (T001–T007): No dependencies — start immediately. uf fork only.
- **Phase 2** (T008–T014): Depends on Phase 1 completing (binary must be shadowed before verifying uf behavior)
  - T008 and T009 are `[P]` — can run simultaneously (different files)
  - T010, T011, T012 follow T008+T009
  - T013, T014 follow T010–T012
- **Phase 3** (T015–T022): Depends on Phase 2 completing (tests must pass first)
  - T015 and T016 are `[P]` — can run simultaneously (different file sets)
  - T017, T018 follow T016
  - T019, T020 are independent
  - T021, T022 are verification steps after all renames
- **Phase 4** (T023–T025): Depends on Phase 3 completing

## Convention Pack Compliance

Before implementing any task, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`
