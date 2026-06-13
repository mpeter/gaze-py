# Tasks: rename-binary-gazepy

**Input**: `openspec/changes/rename-binary-gazepy/proposal.md`
**Branch**: `opsx/rename-binary-gazepy`
**Files**: `pyproject.toml`, `src/gaze_py/cli/__init__.py`, `README.md`, `CHANGELOG.md`

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- Mark `[x]` immediately on completion

---

## Phase 1 — Rename entry point

- [x] T001 `pyproject.toml`: change `[project.scripts]` key from `gaze-py`
      to `gazepy`

## Phase 2 — Update CLI strings [P]

- [x] T002 [P] `src/gaze_py/cli/__init__.py`: update module docstring,
      `prog_name`, group docstring, and all stub `click.echo` strings
      from `gaze-py` to `gazepy`
- [x] T003 [P] `README.md`: update all command examples in Quick Start,
      Commands table, and Installation section
- [x] T004 [P] `CHANGELOG.md`: add breaking change entry under `[Unreleased]`

## Phase 3 — Verify

- [x] T005 `uv run pytest -q` — 111 tests pass, 0 failures
- [x] T006 `uv run ruff check .` — no issues
- [x] T007 `uv run mypy src/` — no issues
- [x] T008 Rebuild wheel and reinstall: `gazepy --version` prints
      `gazepy, version 0.1.0`

---

**Completed**: 2026-06-13
