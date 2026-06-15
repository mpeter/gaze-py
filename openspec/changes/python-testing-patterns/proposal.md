## Why

The `.opencode/skills/testing-patterns/SKILL.md` file contains Go-specific testing
conventions (db.OpenMemory, httptest, `//go:build` tags, t.Errorf) that are irrelevant
and actively misleading to agents working on this Python-only gaze-py repository. Agents
loading this skill receive wrong guidance about test naming, runner invocation, isolation
patterns, and slow-test marking.

## What Changes

- **In-place replacement** of `.opencode/skills/testing-patterns/SKILL.md` with
  Python/pytest content covering: pytest framework, snake_case test naming, `uv run pytest`
  runner, `tmp_path`/`monkeypatch`/`capsys`/`capfd` isolation, `@pytest.mark.slow` and
  `@pytest.mark.parametrize`, testdata conventions, AST-only isolation constraint, and
  coverage floor guidance.
- Frontmatter updated: `tags` from `[testing, go, patterns]` to
  `[testing, python, pytest, patterns]`; `description` from "Go testing patterns for the
  replicator project" to "Python/pytest testing patterns for gaze-py".
- No production code changes, no test file changes, no CI configuration changes.

## Capabilities

### New Capabilities

- `python-testing-patterns`: Python/pytest testing conventions skill for gaze-py —
  replaces the Go-specific SKILL.md with accurate Python/pytest guidance for agents
  working in this repository.

### Modified Capabilities

<!-- No existing spec-level requirements are changing — this change is confined to the
     .opencode/skills/ agent guidance layer. -->

## Impact

- `.opencode/skills/testing-patterns/SKILL.md` — single file replaced in-place
- No runtime code, tests, CI, or pyproject.toml touched
- Agents that load the `testing-patterns` skill will receive correct Python/pytest guidance
