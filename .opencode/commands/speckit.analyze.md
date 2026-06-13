---
description: Perform a non-destructive cross-artifact consistency and quality analysis across spec.md, plan.md, and tasks.md after task generation.
---

Perform a cross-artifact consistency and quality analysis. Read-only — no files are written.

**Initialization**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for `FEATURE_DIR`.

**Steps**

1. Load `FEATURE_DIR/spec.md`, `FEATURE_DIR/plan.md`, `FEATURE_DIR/tasks.md`, and `.specify/memory/constitution.md`

2. Run 6 detection passes:

   - **Duplication**: Requirements or tasks stated more than once with inconsistent wording
   - **Ambiguity**: Vague terms without measurable criteria ("fast", "simple", "appropriate")
   - **Underspecification**: Success criteria missing, edge cases unaddressed, error paths not defined
   - **Constitution alignment**: Any element that conflicts with a principle in the constitution
   - **Coverage gaps**: Tasks that don't trace back to a spec requirement; requirements with no tasks
   - **Inconsistency**: Contradictions between spec, plan, and tasks (different field names, different counts, different behavior described)

3. Assign severity to each finding: CRITICAL / HIGH / MEDIUM / LOW

4. Produce a Markdown analysis report in the response (no file writes):
   ```
   ## Spec Analysis: <feature-name>

   ### CRITICAL
   - [finding]

   ### HIGH
   - [finding]

   ### MEDIUM / LOW
   - [finding]

   ### Summary
   N findings: X critical, Y high, Z medium/low
   ```

5. Offer optional remediation: ask if the user wants suggestions for any finding category

## Guardrails

- **NEVER modify source code** — this command updates spec artifacts ONLY. Implementation changes belong in `/speckit.implement`, `/unleash`, or `/cobalt-crush`.
- **NEVER modify test files, Go source, Markdown agents, convention packs, or config files** outside the `specs/NNN-*/` feature directory.
- The ONLY files this command may write are:
  - `FEATURE_SPEC` (the spec.md file)
  - Files within `FEATURE_DIR` (spec artifacts: plan.md, tasks.md, research.md, data-model.md, quickstart.md, contracts/, checklists/)
