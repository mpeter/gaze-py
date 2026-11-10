---
title: Give canonical specs the Purpose and Requirements headers OpenSpec validates
type: chore
severity: medium
status: open
created: 2026-11-10
labels: []
---
`openspec validate --specs` fails 20 of 21 canonical specs under `openspec/specs/`
(identical on origin/main f0451f3, 2026-11-10): they lack the `## Purpose` and
`## Requirements` headers, so OpenSpec cannot see their requirements, e.g.
`analyze-command: Spec must have a Purpose section`. Active changes validate.

**Done when:** `openspec validate --specs --no-interactive` passes with requirement
content unchanged.
