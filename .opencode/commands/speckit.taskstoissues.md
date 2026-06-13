---
description: Convert existing tasks into actionable, dependency-ordered GitHub issues for the feature based on available design artifacts.
tools: ['github/github-mcp-server/issue_write']
---

Convert tasks.md into GitHub issues, one per task, in dependency order.

**Initialization**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for `FEATURE_DIR`.

**Steps**

1. Read `FEATURE_DIR/tasks.md`

2. Validate GitHub remote:
   - Run `git remote get-url origin` to get the repo URL
   - Confirm with the user before creating any issues: "I'll create issues in <repo>. Proceed?"
   - **NEVER create issues in repos that don't match the remote URL**

3. Parse tasks into issues:
   - Each `- [ ] T###` task becomes one GitHub issue
   - Title: task description
   - Body: include task ID, spec reference if present, and any subtasks as a checklist
   - Labels: derive from task type (feat, fix, chore, test)
   - Dependency ordering: tasks with no dependencies first

4. Create issues via the GitHub MCP server (`issue_write` tool)

5. After creation, update tasks.md to add the issue number next to each task:
   `- [ ] T001 Description (#42)`

## Guardrails

- **NEVER modify source code** — this command updates spec artifacts ONLY. Implementation changes belong in `/speckit.implement`, `/unleash`, or `/cobalt-crush`.
- **NEVER modify test files, Go source, Markdown agents, convention packs, or config files** outside the `specs/NNN-*/` feature directory.
- The ONLY files this command may write are:
  - `FEATURE_SPEC` (the spec.md file)
  - Files within `FEATURE_DIR` (spec artifacts: plan.md, tasks.md, research.md, data-model.md, quickstart.md, contracts/, checklists/)
