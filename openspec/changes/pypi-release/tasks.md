## 1. pyproject.toml metadata

- [x] 1.1 Add `authors`, `keywords`, `classifiers`, and `[project.urls]`
      to `pyproject.toml` exactly as specified in design.md
- [x] 1.2 Verify `uv build` succeeds locally and produces both wheel and
      sdist in `dist/`

## 2. Release workflow

- [x] 2.1 Create `.github/workflows/release.yml` with two jobs (`preflight`
      and `publish`) as specified in design.md:
      - `workflow_dispatch` trigger with `tag` input
      - Preflight: validate format, check tag uniqueness, verify version match
      - Publish: checkout, setup-uv, git tag + push, uv build,
        pypa/gh-action-pypi-publish@6733eb7d741f0b11ec6a39b58540dab7590f9b7d
      - All action SHAs pinned (use same pins as test.yml for checkout/setup-uv)
      - `environment: pypi` on publish job
      - `permissions: {id-token: write, contents: write}` on publish job

## 3. README

- [x] 3.1 Add `## Installation` section to `README.md` immediately before
      the existing "Basic Usage" section, with `uvx`, `uv tool install`,
      and `pip install` examples

## 4. Manual setup (document only — not automatable)

- [x] 4.1 Add a `## Releasing` section to `README.md` (or a `RELEASING.md`)
      documenting the one-time pypi.org trusted publisher setup and the
      manual release trigger steps. Future maintainers must be able to
      reproduce the release without this conversation.

## 5. CI gate

- [x] 5.1 `uv run ruff check .`
- [x] 5.2 `uv run ruff format --check .`
- [x] 5.3 `uv run mypy --strict src/`
- [x] 5.4 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
