## 1. Frontmatter Update

- [x] 1.1 Update `tags` in SKILL.md frontmatter from `[testing, go, patterns]` to `[testing, python, pytest, patterns]`
- [x] 1.2 Update `description` in SKILL.md frontmatter from "Go testing patterns for the replicator project" to "Python/pytest testing patterns for gaze-py"

## 2. Body Content Replacement

- [x] 2.1 Replace the entire body of `.opencode/skills/testing-patterns/SKILL.md` with Python/pytest conventions covering: framework (pytest, plain assert, pytest.raises, pytest.approx), test naming (test_<function>_<scenario> snake_case), runner (uv run pytest), isolation patterns (tmp_path, monkeypatch, capsys, capfd), markers (@pytest.mark.slow, @pytest.mark.parametrize), assertion examples (specific values, exceptions, floats), testdata fixture conventions (tests/testdata/ static files, no __init__.py, norecursedirs, never imported), and AST-only isolation constraint (ast.parse, never import from testdata)
- [x] 2.2 Verify coverage section documents the --cov-fail-under=85 gate and how to check coverage locally

## 3. CI Gate

- [x] 3.1 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85` and confirm all checks pass (SKILL.md is not Python source — this gate verifies no production code was accidentally changed)

<!-- spec-review: passed -->
<!-- code-review: passed -->
