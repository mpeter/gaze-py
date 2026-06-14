## Why

gaze-py v0.2.0 is functional but not installable without a local wheel build.
Publishing to PyPI makes `uv tool install gaze-py`, `uvx gaze-py`, and
`pip install gaze-py` work for any user, enables the `gazepy-reporter.md`
agent's install fallback path, and claims the `gaze-py` name before it can
be squatted.

## What Changes

- **`pyproject.toml`** — add `authors`, `keywords`, `classifiers`, and
  `[project.urls]` required for a complete PyPI listing.
- **`.github/workflows/release.yml`** — new `workflow_dispatch` workflow:
  validates tag format and uniqueness, verifies `pyproject.toml` version
  matches the tag, creates and pushes the git tag, builds with `uv build`,
  and publishes via PyPI trusted publishing (OIDC — no stored secrets).
- **`README.md`** — add Installation section with `pip`, `uv tool install`,
  and `uvx` options.

## Capabilities

### New Capabilities

- `pypi-release`: automated release workflow triggered via
  `workflow_dispatch`. Validates pre-flight conditions, tags the commit,
  builds the wheel and sdist, and publishes to PyPI using trusted
  publishing.

### Modified Capabilities

*(none)*

## Impact

- `pyproject.toml` — metadata additions only; no dependency or build changes
- `.github/workflows/release.yml` — new file
- `README.md` — new Installation section
- One-time manual setup required on pypi.org (trusted publisher config)
  and GitHub (environment `pypi`) — documented in tasks.md
