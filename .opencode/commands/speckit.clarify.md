---
description: Identify underspecified areas in the current feature spec by asking up to 5 highly targeted clarification questions and encoding answers back into the spec.
---

Detect and resolve ambiguities in the current feature spec. Ask up to 5 questions, one at a time, and integrate answers directly into spec.md.

**Initialization**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for `FEATURE_DIR` and `FEATURE_SPEC`.

**Steps**

1. Read `FEATURE_SPEC` (spec.md)

2. Scan for ambiguities across 10 taxonomy categories:
   - Functional scope, data model, UX flow, non-functional requirements
   - Integration points, edge cases, constraints, terminology
   - Completion signals, placeholders (TBD, TODO, ???)

3. Select the highest-impact ambiguity. Ask ONE targeted question:
   - Provide 2–3 recommended answers with reasoning
   - Wait for the user's response before asking the next question

4. Integrate the answer directly into the relevant section of spec.md

5. Record the Q&A in a `## Clarifications` section at the end of spec.md:
   ```markdown
   ## Clarifications
   **Q**: <question>
   **A**: <answer>
   **Applied to**: <section name>
   ```

6. Repeat for up to 5 questions total, then stop and summarize changes made

## Guardrails

- **NEVER modify source code** — this command updates spec artifacts ONLY. Implementation changes belong in `/speckit.implement`, `/unleash`, or `/cobalt-crush`.
- **NEVER modify test files, Go source, Markdown agents, convention packs, or config files** outside the `specs/NNN-*/` feature directory.
- The ONLY files this command may write are:
  - `FEATURE_SPEC` (the spec.md file)
  - Files within `FEATURE_DIR` (spec artifacts: plan.md, tasks.md, research.md, data-model.md, quickstart.md, contracts/, checklists/)
