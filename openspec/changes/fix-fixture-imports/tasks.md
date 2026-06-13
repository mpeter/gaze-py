# Tasks: fix-fixture-imports

**Input**: `openspec/changes/fix-fixture-imports/proposal.md`
**Branch**: `opsx/fix-fixture-imports`
**Files**: `tests/testdata/quality/test_*.py`, `tests/testdata/quality/__init__.py`,
           `tests/testdata/analysis/__init__.py`, `pyproject.toml`

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- Mark `[x]` immediately on completion

---

## Phase 1 — pytest config

- [x] T001 `pyproject.toml`: remove `pythonpath = ["."]`; add
      `testpaths = ["tests"]` and `norecursedirs = ["tests/testdata"]`

## Phase 2 — Remove package markers [P]

- [x] T002 [P] Delete `tests/testdata/quality/__init__.py`
- [x] T003 [P] Delete `tests/testdata/analysis/__init__.py`

## Phase 3 — Fix fixture imports [P]

For each of the six fixture test files, remove the cross-package import
and add `# ruff: noqa: F821` plus a clarifying docstring note.

- [x] T004 [P] `tests/testdata/quality/test_basic.py`
- [x] T005 [P] `tests/testdata/quality/test_incidental.py`
- [x] T006 [P] `tests/testdata/quality/test_inline.py`
- [x] T007 [P] `tests/testdata/quality/test_no_assert.py`
- [x] T008 [P] `tests/testdata/quality/test_partial.py`
- [x] T009 [P] `tests/testdata/quality/test_raises.py`

## Phase 4 — Verify

- [x] T010 `uv run pytest -q` — exactly 111 tests collected, 0 failures
- [x] T011 `uv run ruff check .` — no issues
- [x] T012 `uv run mypy src/` — no issues
- [x] T013 Confirm no `__init__.py` files remain under `tests/testdata/`

---

**Completed**: 2026-06-13
