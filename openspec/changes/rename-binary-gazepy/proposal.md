## Why

The `gaze-py` entry point name is a poor binary name for two reasons:

1. **Hyphens are awkward at the shell.** Convention for CLI tools is one
   word: `grep`, `ruff`, `mypy`, `pytest`. `gaze-py` forces users to type
   a hyphen and looks like a PyPI package reference rather than a command.

2. **Co-installation with Go `gaze` is not an edge case.** Users working
   on mixed-language projects — or on gaze-py itself — have both the Go
   `gaze` binary and the Python companion installed. Using `gaze` as the
   Python binary name would collide. `gazepy` is unambiguous and
   co-exists cleanly.

The `-py` suffix exists to distinguish the PyPI package from any future
Go `gaze` PyPI package. That is a packaging concern, not a UX concern.
At the shell prompt it is noise.

## What Changes

### `pyproject.toml`

```toml
# Before
[project.scripts]
gaze-py = "gaze_py.cli:main"

# After
[project.scripts]
gazepy = "gaze_py.cli:main"
```

### `src/gaze_py/cli/__init__.py`

- Module docstring: `gaze-py CLI` → `gazepy CLI`
- `prog_name="gaze-py"` → `prog_name="gazepy"` in `@click.version_option`
- Group docstring: `gaze-py: Python-native...` → `gazepy: Python-native...`
- Stub `click.echo` strings updated from `gaze-py <cmd>: not yet implemented`
  to `gazepy <cmd>: not yet implemented`

### `README.md`

All command examples updated: `gaze-py analyze`, `gaze-py report`, etc.
→ `gazepy analyze`, `gazepy report`, etc.

### `CHANGELOG.md`

Breaking change entry added under `[Unreleased]`.

## What Does Not Change

- PyPI package name: `gaze-py` (unchanged)
- Python import path: `gaze_py` (unchanged)
- Repository name: `gaze-py` (unchanged)
- All source files, tests, and domain types (unchanged)

## Breaking Change

Users with `gaze-py` on PATH or in scripts must update to `gazepy`.
This change is made before v0.1.0 is published to PyPI, so no
published users are affected.

## Success Criteria

- `gazepy --version` prints `gazepy, version 0.1.0`
- `gazepy report src/ tests/` runs the full pipeline
- `gaze-py` is not installed as an entry point
- 111 tests pass, coverage ≥ 85%, ruff ✓, mypy strict ✓
