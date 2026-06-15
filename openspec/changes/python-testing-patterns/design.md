## Context

`.opencode/skills/testing-patterns/SKILL.md` was scaffolded from a Go template for the
`replicator` project and never updated for gaze-py. It references Go idioms
(db.OpenMemory(), httptest.NewServer, `//go:build parity`, t.TempDir, t.Errorf,
reflect.DeepEqual) that have no meaning in this Python codebase. Any agent that loads this
skill while working on gaze-py receives actively wrong guidance.

gaze-py uses:
- `pytest` as the sole test runner (via `uv run pytest`)
- `assert` statements directly (not t.Errorf)
- `tmp_path`, `monkeypatch`, `capsys`, `capfd` fixtures for isolation
- `@pytest.mark.slow` to split fast/slow test runs
- `@pytest.mark.parametrize` for table-driven tests
- `tests/testdata/` for static AST fixture files (never imported, never executed)
- `--cov-fail-under=85` as the coverage gate

The change is a **single-file in-place replacement**. No architecture is changing.

## Goals / Non-Goals

**Goals:**

- Replace all Go-specific content in `SKILL.md` with accurate Python/pytest equivalents
- Cover every convention documented in the Python convention pack (TC-001 through TC-013)
- Document the AST-only constraint that is unique to this project (no importing of analyzed
  modules in tests)
- Reflect the actual `uv run pytest` runner and CI gate commands
- Update frontmatter tags and description to accurately reflect the Python context

**Non-Goals:**

- Changes to any production source under `src/gaze_py/`
- Changes to any test file under `tests/`
- Changes to CI workflow files (`.github/workflows/`)
- Changes to `pyproject.toml`
- Any new Python code, imports, or runtime behavior

## Decisions

### Single-file replacement, no intermediate state

**Decision**: Write the new content directly over the existing SKILL.md; no rename,
no backup file, no parallel file.

**Rationale**: Skill files are agent guidance, not tracked runtime state. The Go content
is entirely wrong; there is no value in preserving any of it. A clean replacement is
simpler and avoids dead files.

**Alternative considered**: Create a new file and delete the old — functionally identical
but adds two git operations instead of one diff.

### Cover all TC-001–TC-013 rules, plus AST-only constraint

**Decision**: The SKILL.md body mirrors every testing convention from
`.opencode/uf/packs/python.md` (TC-001 through TC-013), supplemented by the
gaze-py–specific AST-only isolation requirement.

**Rationale**: An agent loading the skill must have complete guidance. Gaps force the
agent to fall back to guessing or loading additional context. The AST-only constraint
(never import testdata files — analyze them via `ast.parse`) is project-critical and
absent from the generic convention pack.

**Alternative considered**: Link back to the convention pack instead of repeating rules —
rejected because skills are loaded in isolation and the agent may not have the pack in
context.

### Frontmatter tags updated to Python/pytest identifiers

**Decision**: Change `tags: [testing, go, patterns]` to
`tags: [testing, python, pytest, patterns]` and update `description`.

**Rationale**: Tags are used by skill-loading machinery for discovery and filtering.
A skill tagged `go` in a Python repository will confuse routing logic and agents.

## Risks / Trade-offs

- **Risk**: Agents or tools that previously depended on Go-specific examples may break.
  → **Mitigation**: There are no Go files in gaze-py. No existing agent or test file
  imports from the Go content. The replacement is safe.

- **Risk**: Missing a Python convention that an agent later needs.
  → **Mitigation**: The SKILL.md content is derived directly from the authoritative
  convention pack (TC-001–TC-013) plus AGENTS.md testdata rules, so coverage is complete
  relative to the current pack version. Future pack amendments update the pack first;
  the skill is updated via a subsequent change.

- **Trade-off**: SKILL.md duplicates some content from the convention pack.
  → This is intentional; skills are designed to be loaded standalone. Redundancy
  between skill and pack is preferable to an incomplete skill.
