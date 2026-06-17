# Feature Specification: gazepy init Deploys to gaze-* Names

**Feature Branch**: `001-gazepy-init-deploys`

**Created**: 2026-06-15

**Status**: Approved

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Zero-friction init in a Python project (Priority: P1)

A developer runs `uf init` (or `gazepy init`) in a new Python project. Afterwards
they have exactly one set of quality tooling files — named identically to what
`gaze init` would produce — and the `/gaze` command works without any manual
cleanup or renaming step.

**Why this priority**: This is the root cause of the friction. Every new Python
project initialized today requires the developer to manually delete four Go-
content files and remember to use `/gazepy` instead of `/gaze`. Fixing this
eliminates the undocumented manual step entirely.

**Independent Test**: Run `gazepy init` in a fresh temp directory, observe that
`agents/gaze-reporter.md` and `commands/gaze.md` are created, and that
`agents/gazepy-reporter.md` and `commands/gazepy.md` are NOT created.

**Acceptance Scenarios**:

1. **Given** a fresh Python project directory, **When** `gazepy init` is run,
   **Then** `.opencode/agents/gaze-reporter.md` and `.opencode/commands/gaze.md`
   exist and `agents/gazepy-reporter.md` and `commands/gazepy.md` do not exist.

2. **Given** a Python project where `gazepy init` has already run, **When**
   `uf init` is run, **Then** `uf init` sees `agents/gaze-reporter.md` as the
   sentinel and skips `gazepy init` (no duplicate files created, no Go content
   deployed).

3. **Given** a Python project where `gaze init` previously ran (Go content),
   **When** `gazepy init --force` is run, **Then** `agents/gaze-reporter.md`
   is overwritten with Python content and the `/gaze` command correctly delegates
   to the Python reporter.

---

### User Story 2 - uf sentinel alignment (Priority: P1)

The `uf` tool recognises `agents/gaze-reporter.md` as proof that `gazepy init`
has already run on a Python project, so it does not call `gazepy init` a second
time and does not call `gaze init` (which would deploy Go content).

**Why this priority**: Without this change, `uf init` uses `gazepy-reporter.md`
as its sentinel. After the rename, the sentinel must match the new filename or
`uf init` breaks idempotency.

**Independent Test**: Run `uf init` on a Python project that already has
`agents/gaze-reporter.md`. Observe that neither `gaze init` nor `gazepy init`
is called.

**Acceptance Scenarios**:

1. **Given** a Python project with `agents/gaze-reporter.md` present,
   **When** `uf init` runs, **Then** neither `gaze init` nor `gazepy init` is
   invoked (sentinel found, tool skipped).

2. **Given** a Python project with no `agents/gaze-reporter.md`, **When**
   `uf init` runs with `gazepy` on PATH, **Then** `gazepy init` is invoked and
   `agents/gaze-reporter.md` is created.

---

### Edge Cases

- `gaze init --force` run manually in a Python project after `gazepy init` has
  run: `gaze-reporter.md` is user-owned by gaze (skip-if-present without
  `--force`), so with `--force` it would overwrite. This is an explicit manual
  override and acceptable; the uf-init path never does this.
- Both `gaze` and `gazepy` on PATH in a Python project: uf sees
  `gaze-reporter.md` present for both sentinels and skips both inits.
- Running `gazepy init` twice without `--force`: second run skips all files
  (idempotent).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `gazepy init` MUST deploy assets to `agents/gaze-reporter.md`
  and `commands/gaze.md` (not `agents/gazepy-reporter.md` and `commands/gazepy.md`).

- **FR-002**: The `uf` scaffold MUST use `agents/gaze-reporter.md` as the
  sentinel for the `gazepy` tool entry (replacing `agents/gazepy-reporter.md`).

- **FR-003**: The deployed `commands/gaze.md` MUST delegate to the
  `gaze-reporter` subagent and expose the `/gaze` command (not `/gazepy`).

- **FR-004**: The deployed `agents/gaze-reporter.md` MUST contain Python-
  specific binary resolution (`uv run gazepy` / `which gazepy`) and Python
  output format — not Go-specific content.

- **FR-005**: All existing `gazepy init` behaviour (idempotency, `--force`,
  version marker insertion, symlink guard, pyproject.toml warning) MUST be
  preserved unchanged.

- **FR-006**: `uf init` run on a Python project with `gaze-reporter.md` already
  present MUST skip both `gaze init` and `gazepy init` without error.

- **FR-007**: The `uf` binary used in this project MUST be shadowed locally
  (built from fork source) so no brew release is required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `gazepy init` in a fresh directory produces exactly
  `agents/gaze-reporter.md` and `commands/gaze.md` — verified by test.

- **SC-002**: Running `uf init` on a Python project with `gaze-reporter.md`
  present produces no new files and calls neither `gaze init` nor `gazepy init`
  — verified by uf scaffold test.

- **SC-003**: All 531+ existing `gaze-py` pytest tests continue to pass at
  ≥ 85% coverage after the source changes.

- **SC-004**: All `uf` scaffold tests pass after the sentinel change.

- **SC-005**: `/gaze` command in the gaze-py `.opencode/` delegates to the
  Python `gaze-reporter` agent (no Go files present in `.opencode/`).

## Porting Contract Compliance *(mandatory for gaze-py)*

This feature touches the `gazepy init` scaffold command only — not the analysis
engine, taxonomy, scoring, or CLI analysis commands. No porting contracts are
affected.

| Contract ID | Description | Status |
|-------------|-------------|--------|
| — | No porting contracts affected | N/A |

## Assumptions

- The `uf` fork at `mpeter/unbound-force` is the deployment target; no upstream
  brew release is required. The locally built binary shadows the brew binary via
  a symlink replacement in the Cellar.
- `gaze init --force` run manually in a Python project is an accepted foot-gun
  that does not need to be defended against in this change.
- The `uf` sentinel change is a one-line edit; no new uf features are needed.
- The gaze-py source version is bumped to 0.4.1 to signal the init output change.
- The cross-repo nature (gaze-py + uf fork) qualifies for the hotfix exemption
  in the constitution (correcting a wrong design decision from `cli-parity`).
