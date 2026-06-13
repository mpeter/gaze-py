---
description: Generate a custom checklist for the current feature based on user requirements.
---

Generate a requirements quality checklist — "unit tests for English". Tests REQUIREMENTS quality, not implementation behavior.

**Initialization**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for `FEATURE_DIR`.

**Steps**

1. Ask up to 3 clarifying questions about the checklist scope before generating:
   - Which domain to focus on (e.g., data model, error handling, security, performance)?
   - Which artifact to validate (spec, plan, tasks, or all)?
   - Any specific concerns to prioritize?

2. Generate checklist items in question format:
   - "Are [X] defined for [Y]?"
   - "Is [behavior] specified for [edge case]?"
   - Each item includes a quality dimension tag: `[Completeness]`, `[Clarity]`, `[Consistency]`, `[Measurability]`, `[Coverage]`

3. Write to `FEATURE_DIR/checklists/<domain>.md` — each run creates a NEW file, never overwrites existing ones. If a file exists for that domain, append a timestamp suffix.

**Output format**:
```markdown
# Requirements Checklist: <domain>
Generated: <date>

## [Completeness]
- [ ] Are all error paths defined for <X>?
- [ ] Are retry/timeout behaviors specified?

## [Clarity]
- [ ] Are success criteria measurable (not "fast" or "simple")?
```

## Guardrails

- **NEVER modify source code** — this command updates spec artifacts ONLY. Implementation changes belong in `/speckit.implement`, `/unleash`, or `/cobalt-crush`.
- **NEVER modify test files, Go source, Markdown agents, convention packs, or config files** outside the `specs/NNN-*/` feature directory.
- The ONLY files this command may write are:
  - `FEATURE_SPEC` (the spec.md file)
  - Files within `FEATURE_DIR` (spec artifacts: plan.md, tasks.md, research.md, data-model.md, quickstart.md, contracts/, checklists/)
