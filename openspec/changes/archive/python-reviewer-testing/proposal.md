<!-- spec-review: passed -->

## Why

The `.opencode/agents/reviewer-testing.md` agent file is a verbatim copy of the Go gaze v1.5.0 template. It references Go-specific constructs (`*_test.go`, `testing.Short()`, `-race -count=1`, `go build`, `testdata/src/` loaded via `go/packages`) that are meaningless or misleading in the gaze-py Python/pytest context. Every review invocation wastes cycles identifying Go artifacts that don't apply, and misses Python-specific issues (missing `@pytest.mark.parametrize`, `tests/testdata/` fixture isolation violations, `uv run mypy --strict` gate).

## What Changes

- Replace the body of `.opencode/agents/reviewer-testing.md` with a Python/pytest-adapted version.
- Keep all YAML frontmatter fields exactly as-is (`mode: subagent`, `model`, `temperature`, `tools` block).
- Keep the dual-mode structure (Code Review Mode / Spec Review Mode), the 6-section audit checklist in each mode, the severity levels (CRITICAL/HIGH/MEDIUM/LOW), the output format block, and the APPROVE/REQUEST CHANGES decision criteria.
- Translate every Go-specific reference to its Python equivalent (see design.md for the full mapping).
- Update the version marker from `gaze v1.5.0` to `gazepy 0.4.0`.

## Capabilities

### New Capabilities

- `python-reviewer-testing`: Python/pytest-adapted testing auditor agent — replaces Go-specific content in both Code Review Mode and Spec Review Mode checklists with `pytest`, `@pytest.mark.parametrize`, `tests/testdata/` fixture isolation rules, `uv run pytest`/`ruff`/`mypy` gate references, and gaze-py-specific convention rules (CR-002, TC-005, TC-011).

### Modified Capabilities

<!-- No requirement-level spec changes; this change modifies an agent prompt file only. -->

## Impact

- **File modified**: `.opencode/agents/reviewer-testing.md` (agent prompt body only; frontmatter unchanged)
- **No code changes**: This is a pure agent-prompt update. No production Python files, tests, or CI configuration are modified.
- **Downstream**: All review-council sessions that invoke the Tester divisor will use the corrected Python-aware checklist from the next invocation onward.
