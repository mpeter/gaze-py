## Why

The fixture files under `tests/testdata/quality/` import their source
counterparts via a cross-package import:

```python
from tests.testdata.quality.src_basic import compute
```

This caused two cascading problems:

1. **`tests/` had to be a package.** The import requires `tests/__init__.py`
   and all intermediate `__init__.py` files. When `tests/__init__.py` was
   removed (correct practice for a `src/` layout), the fixtures broke.

2. **The workaround was wrong.** Adding `pythonpath = ["."]` to pytest config
   made `tests` importable without `__init__.py`, but this is a `sys.path`
   hack that papers over the real problem rather than fixing it.

**Root cause**: the fixture `test_*.py` files do not need to be importable
or executable. They exist solely as source text for the quality engine to
parse as AST. `_extract_called_names()` detects function calls by scanning
`ast.Call` nodes — it does not resolve imports. The imports in the fixtures
were dead weight that created a false package dependency.

**Secondary symptom**: because the fixture files matched the `test_*.py`
naming pattern and pytest could import them (via `pythonpath = ["."]`),
pytest was collecting and executing them as real tests. 6 of the 117
previously reported passing tests were fixture files accidentally running.
The real test count is 111.

## What Changes

### `tests/testdata/quality/test_*.py` (all six files)

Remove the `from tests.testdata.quality.src_* import ...` statement.
Add `# ruff: noqa: F821` file-level comment so ruff does not flag the
bare call sites (`compute(1, 2)`, `divide(1, 0)`, etc.) as undefined names.
Add a clarifying docstring note that the file is parsed as AST and never
executed.

### `tests/testdata/quality/__init__.py`

Delete. The directory is not a package; the file existed only to support
the broken import pattern.

### `tests/testdata/analysis/__init__.py`

Delete. Also empty and unneeded — analysis fixtures are referenced by
`Path` objects in tests, never imported.

### `pyproject.toml`

- Remove `pythonpath = ["."]` — the workaround is no longer needed.
- Add `testpaths = ["tests"]` — explicit, documents intent.
- Add `norecursedirs = ["tests/testdata"]` — prevents pytest from
  collecting fixture files as real tests.

## What Does Not Change

- All fixture `src_*.py` files (unchanged — they are never imported)
- `tests/test_quality.py` — uses `Path(__file__).parent / "testdata" / "quality"`
  and reads fixtures as text; no import change needed
- All other tests (unchanged)
- Source code under `src/gaze_py/` (unchanged)

## Success Criteria

- `uv run pytest -q` collects exactly 111 tests (no fixture files)
- `uv run pytest -q` — 111 pass, 0 failures
- `tests/testdata/` contains no `__init__.py` files
- `pyproject.toml` contains no `pythonpath` setting
- `uv run ruff check .` — no issues
- `uv run mypy src/` — no issues
