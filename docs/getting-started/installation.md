# Installation

gaze-py requires Python 3.11 or later.

## Install from PyPI

**Recommended: install as a global tool with `uv`**

```bash
uv tool install gaze-py
```

This installs `gazepy` on your `PATH` without affecting any project's virtual environment.

**Install with `pip`**

```bash
pip install gaze-py
```

**Install into a project with `uv`**

```bash
uv add gaze-py
```

## Install from Source

```bash
git clone https://github.com/mpeter/gaze-py
cd gaze-py
uv sync
uv run gazepy --help
```

## Verify the Installation

```bash
gazepy --version
```

Expected output: `gazepy, version 0.6.0` (or the current release).

## Requirements

- Python 3.11, 3.12, or 3.13
- `pytest` and `pytest-cov` in your project's test environment (required for coverage collection when using `gazepy crap` without `--coverprofile`)
