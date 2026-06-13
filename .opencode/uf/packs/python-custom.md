---
pack_id: python-custom
language: Python
version: 1.0.0
---

# Custom Rules: Python

Project-specific Python conventions that extend the canonical
Python convention pack. Rules in this file are loaded alongside
`python.md` by Cobalt-Crush (during implementation) and
all Divisor persona agents (during review).

Use the `CR-NNN` prefix for all custom rules. Use `[MUST]`,
`[SHOULD]`, or `[MAY]` severity indicators per RFC 2119.

## Custom Rules

- **CR-001** [MUST] Use flat-module layout for all source modules in this
  project. Package code lives directly under `src/gaze_py/` as `.py` files
  (`cli.py`, `analysis.py`, `quality.py`, `taxonomy.py`, etc.), not in
  subdirectories. This is a deliberate deviation from AP-006's preferred
  subpackage layout, documented as ADR-004 in
  `specs/001-gaze-py-engine/plan.md`. Rationale: the existing codebase is
  entirely flat; introducing subpackages for new modules while leaving existing
  ones flat would create an inconsistent dual convention. A future refactoring
  spec MUST bring the entire package into AP-006 subpackage compliance
  uniformly. Do NOT introduce subdirectories for new modules on this project
  without first completing that refactoring.
