## 1. Dependabot Configuration

- [x] 1.1 Create `.github/dependabot.yml` with `github-actions` ecosystem (weekly, directory `/`) — already exists
- [x] 1.2 Add `pip` ecosystem to `.github/dependabot.yml` (weekly, directory `/`) — already present
- [x] 1.3 Verify the file is valid YAML (`python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"`) — verified by inspection

## 2. Astroid Version Constraint

- [x] 2.1 Update `pyproject.toml`: change `"astroid>=3.0"` to `"astroid>=3.0,<5"`
- [x] 2.2 Run `uv lock` to regenerate `uv.lock` (expect no functional change — 4.1.2 satisfies both constraints)
- [x] 2.3 Verify the locked astroid version is still 4.1.2: `uv run python -c "import astroid; print(astroid.__version__)"` — confirmed 4.1.2
- [x] 2.4 Update CHANGELOG `[Unreleased]` Known Limitations: change "astroid>=3.0 with no upper bound" to "astroid>=3.0,<5 (CI-verified at 4.1.2)"

## 3. Release Smoke Test

- [x] 3.1 In `.github/workflows/release.yml` line 126, change `echo "::warning::Smoke test timed out after 150s — verify manually at https://pypi.org/p/gaze-py"` to `echo "::error::Smoke test timed out after 150s — verify manually at https://pypi.org/p/gaze-py"` followed by `exit 1`

## 4. Verification

- [x] 4.1 Run full CI gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest --cov=gaze_py --cov-fail-under=85` — 605 passed, 96.78% coverage
- [x] 4.2 Verify `.github/dependabot.yml` syntax: `python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"` — valid
- [x] 4.3 Verify `uv.lock` is committed and matches `pyproject.toml` — astroid 4.1.2 locked

## Convention Pack Compliance

Before implementing any task, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`
