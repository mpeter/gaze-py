# Implementation Plan: gazepy init Deploys to gaze-* Names

**Branch**: `001-gazepy-init-deploys` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)

## Summary

`gazepy init` currently deploys `agents/gazepy-reporter.md` and `commands/gazepy.md`.
This creates permanent UX friction: every Python project initialized via `uf init` gets
Go-content files alongside Python-content files, and users must remember `/gazepy` instead
of `/gaze`. The fix renames the deployed assets to `gaze-reporter.md` and `gaze.md`, and
updates the `uf` scaffold sentinel to match. A local uf binary build shadows the brew
binary — no brew release required.

## Technical Context

**Language/Version**: Python 3.11+ (gaze-py); Go 1.25 (uf fork)

**Primary Dependencies**: click, hatchling (gaze-py); Go stdlib (uf)

**Storage**: N/A

**Testing**: pytest + pytest-cov (gaze-py); go test -race (uf)

**Target Platform**: Linux / macOS developer workstation

**Project Type**: CLI tool (gaze-py) + scaffold framework (uf)

**Performance Goals**: N/A — rename only, no performance-sensitive path

**Constraints**: No brew release; local binary shadow via Cellar symlink

**Scale/Scope**: 2 repos, ~20 files touched total

## Constitution Check

- [x] **I. Accuracy**: No detection targets change. Not applicable.
- [x] **II. Minimal Assumptions**: No user annotation required. Rename is transparent.
- [x] **III. Actionable Output**: N/A — no analysis output changes.
- [x] **IV. Testability**: All existing scaffold tests updated; new uf sentinel test added.
- [x] **V. Porting Contract Supremacy**: No porting contracts affected. Init scaffold is outside the analysis engine.
- [x] **VI. Composability First**: `gazepy` remains sole required entry point. No new dependencies.
- [x] **VII. Supply Chain Integrity**: No new dependencies. `uv.lock` unchanged.

## Coverage Strategy

This is a rename-only change — no new production logic is introduced and no
new functions are added. Coverage strategy is minimal:

1. All existing scaffold tests in `tests/test_cli.py` are updated to assert
   the new filenames (`gaze-reporter.md`, `gaze.md`). No new test functions
   are required beyond path/content assertion updates.
2. SC-001 and SC-002 (verifying the correct files are created/absent after
   `gazepy init`) are verified by existing test functions, updated in place.
3. The 85% coverage floor is maintained via the CI gate (`pytest
   --cov-fail-under=85`). With no new production code paths added, no new
   coverage gaps are introduced.

## Project Structure

### Documentation (this feature)

```text
specs/001-gazepy-init-deploys/
├── spec.md
├── plan.md              ← this file
└── tasks.md             ← created by /speckit.tasks
```

### Source Code — two repos

**Repo A: `mpeter/unbound-force` (uf fork)**

```text
internal/scaffold/
├── scaffold.go          # 1-line sentinel change
└── scaffold_test.go     # 1 new test: TestInitSubTools_GazepySkippedWhenSentinelPresent
```

**Repo B: `mpeter/gaze-py` (this repo)**

```text
src/gaze_py/cli/
├── scaffold.py                       # _ASSET_MAP: 2 path changes
├── main.py                           # init docstring: 2 filename refs
└── assets/
    ├── agents/
    │   ├── gazepy-reporter.md  →  gaze-reporter.md   (rename + content update)
    │   └── [gaze-reporter.md]                        (new canonical name)
    └── commands/
        ├── gazepy.md  →  gaze.md                     (rename + content update)
        └── [gaze.md]                                  (new canonical name)

tests/
└── test_cli.py          # 14 path/content references updated

.opencode/
├── agents/
│   ├── gaze-reporter.md        DELETE (Go content)
│   ├── gaze-test-generator.md  DELETE (Go content)
│   ├── gazepy-reporter.md   →  gaze-reporter.md   (rename)
│   └── gazepy-test-generator.md → gaze-test-generator.md (rename)
├── commands/
│   ├── gaze.md                 DELETE (Go content)
│   ├── gaze-fix.md             DELETE (Go content)
│   ├── gazepy.md            →  gaze.md            (rename)
│   └── gazepy-fix.md        →  gaze-fix.md        (rename)
└── commands/review-council.md  UPDATE (Phase 1b: binary check + install hint)
agents/cobalt-crush-dev.md      UPDATE (install hint + coverage artifact name)
```

## Implementation Phases

### Phase 1 — uf fork (must complete before gaze-py source changes)

1. Edit `internal/scaffold/scaffold.go`: change `gazepy` sentinel from
   `agents/gazepy-reporter.md` → `agents/gaze-reporter.md`
2. Add `TestInitSubTools_GazepySkippedWhenSentinelPresent` to `scaffold_test.go`
3. Run `go test -race ./internal/scaffold/...` — must pass
4. `make install` → `~/go/bin/unbound-force` rebuilt
5. Shadow brew binary: `chmod u+w Cellar binary; ln -sf ~/go/bin/unbound-force Cellar binary`
6. Verify `uf version` shows `vdev`
7. Commit to `mpeter/unbound-force` fork on `main`

### Phase 2 — gaze-py source (scaffold.py, assets, tests)

1. Rename `cli/assets/agents/gazepy-reporter.md` → `gaze-reporter.md`
   — Update `# gazepy-reporter` heading → `# gaze-reporter`
   — Update self-reference at line 72
2. Rename `cli/assets/commands/gazepy.md` → `gaze.md`
   — `agent: gazepy-reporter` → `agent: gaze-reporter`
   — `# /gazepy` → `# /gaze`; example commands `gazepy` → `gaze`
3. Update `scaffold.py` `_ASSET_MAP`: both paths to `gaze-reporter.md` / `gaze.md`
4. Update `main.py` init docstring: 2 filename references
5. Update `tests/test_cli.py`: 14 references
6. Bump version to `0.4.1` in `pyproject.toml`
7. Run `uv run pytest --tb=short` — must pass ≥ 85% coverage

### Phase 3 — .opencode cleanup

1. Delete: `agents/gaze-reporter.md`, `agents/gaze-test-generator.md`,
   `commands/gaze.md`, `commands/gaze-fix.md`
2. Rename: `agents/gazepy-reporter.md` → `agents/gaze-reporter.md`
3. Rename: `commands/gazepy.md` → `commands/gaze.md`
4. Rename: `agents/gazepy-test-generator.md` → `agents/gaze-test-generator.md`
5. Rename: `commands/gazepy-fix.md` → `commands/gaze-fix.md`
6. Update `commands/review-council.md` Phase 1b:
   - `which gaze` → `uv run gazepy --version 2>/dev/null`
   - install hint → `uv tool install gaze-py`
7. Update `agents/cobalt-crush-dev.md`:
   - install hint → `uv tool install gaze-py`
   - `coverage.out` → `.coverage` / `coverage.json`
8. Verify `uf init` on gaze-py reports all files skipped (sentinel found)
9. Verify `uv run gazepy init` in a temp dir creates `gaze-reporter.md` and `gaze.md`

## Complexity Tracking

No constitution violations. This is a rename-only change with no logic modifications.
