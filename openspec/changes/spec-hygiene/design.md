## Context

The review council (9 Divisor personas, Spec Review Mode) identified 8 HIGH
advisories across the spec corpus. Five of those (Advisories 1, 2, 6, 7, 8)
are spec-artifact quality issues that do not require production code changes.
This design addresses all five.

Current state:
- `specs/001-gazepy-init-deploys/plan.md` has no Coverage Strategy section
  (Constitution IV violation — Tester rated CRITICAL)
- `gap-hints/proposal.md` and `report-command/proposal.md` have no numbered
  acceptance criteria (Tester rated HIGH)
- `gazepy-fix-command` and `gazepy-test-generator` proposals state "no test
  changes required" without explaining how behavior is verified (Tester HIGH)
- CHANGELOG entries have no `Spec:` traceability paths (Scribe HIGH)
- `002-deferred-capabilities/tasks.md` lists shipped items as still open
  (Herald HIGH)

## Goals / Non-Goals

**Goals:**
- Resolve all 5 spec-hygiene advisories from review council Iteration 1
- Bring all spec artifacts into Constitution IV compliance (coverage strategy)
- Enable traceability from CHANGELOG entries to authorizing specs
- Make the 002-deferred-capabilities tracking document reflect current reality

**Non-Goals:**
- No production code changes
- No CI configuration changes (covered by `ci-supply-chain`)
- No new features or capabilities
- Not creating missing `specs.md` for changes that lack them (that would be
  a separate, larger effort)

## Decisions

### D1 — Coverage Strategy for rename-only change (001)

Add a minimal Coverage Strategy section to `plan.md` stating: (1) no new
production logic introduced, (2) all existing scaffold tests updated with
new filenames, (3) 85% floor maintained via CI gate. This is sufficient
for a rename-only change — a full strategy with unit/integration/e2e
breakdown would be over-specification.

### D2 — Acceptance Criteria format

Use numbered `AC-N:` format with measurable assertions, not full
Given/When/Then scenarios. The proposals are already compact documents;
adding verbose Gherkin would bloat them. The specs (design.md and tasks.md)
already have detailed scenarios. The proposal acceptance criteria serve as
a quick-check contract.

Gap-hints acceptance criteria:
- AC-1: `len(result.gaps) == len(result.gap_hints)` for all coverage
  computations
- AC-2: All 38 `SideEffectType` values produce a non-empty hint string
- AC-3: `quality_to_json()` output includes `gaps` and `gap_hints` arrays
  when coverage is partial

Report-command acceptance criteria:
- AC-1: `gazepy report` without `--ai` exits 0 and emits valid JSON payload
- AC-2: `gazepy report --ai opencode` invokes the opencode subprocess adapter
- AC-3: `--max-gaze-crapload` enforcement exits 1 when threshold exceeded
- AC-4: Provider binary not found produces a clear error with install hint

### D3 — Agent-only coverage strategy notes

For `gazepy-fix-command` and `gazepy-test-generator` (both archived), add a
Coverage Strategy note acknowledging: (a) agent command files are Markdown,
not testable Python, (b) behavioral verification is manual (run the command,
observe output), (c) the CI gate confirms no regressions from the branch.
Update in archive for completeness — these are closed changes but the
documentation gap should be resolved for future reference.

### D4 — CHANGELOG `Spec:` format

Append a `- Spec: openspec/changes/<name>/` line after each version's
content. For 0.1.0 (initial release predating the spec workflow), use
`- Spec: _(initial release — predates spec workflow)_`. For Unreleased,
reference `openspec/changes/archive/quality-pairing-astroid/`.

### D5 — CHANGELOG terminology fix

In CHANGELOG `[0.4.1]`, the phrase "replicator init" refers to the `uf`
scaffold tool — it should be "uf init" to match the consistent terminology
used in the spec and plan for `001-gazepy-init-deploys`. This is a one-line
factual correction with no design ambiguity.

### D6 — 002-deferred-capabilities status update

The `002-deferred-capabilities/tasks.md` file carries an explicit header
comment: *"No tasks here should be checked off."* To avoid conflicting with
this convention, shipped items will be annotated with an inline suffix rather
than checked off:

- Append `— SHIPPED 0.N.N` to the task description text for each shipped item.
- The checkbox remains `[ ]` — the item is "shipped" but the tracking document's
  own structural convention is preserved.
- The header comment is NOT modified — the annotation approach makes it
  self-evident without changing the document's stated semantics.

Items to annotate SHIPPED:
- A.1–A.4 (O1 pipeline) — shipped 0.3.0
- A.5 (GazeCRAP/quadrant/fix_strategy) — shipped 0.3.0
- A.6 (effect_confidence_range) — shipped 0.3.1
- B.1–B.2 (complexity algorithm) — shipped 0.3.1
- C.1 (O5 threshold flags, O1-independent) — shipped 0.2.0
- D.1 (O3 document scanning) — shipped 0.4.0
- D.2 (O7 doc_scan config) — shipped 0.4.0
- F.1–F.2 (PyPI publication) — shipped 0.2.0

Items that remain open:
- C.2 (--min-contract-coverage flag) — partially shipped in quality command
- C.3 (O6 full — .coverage binary support)
- D.3 (P3/P4 no-equivalent types)
- E.1 (O4 Interactive TUI)
- E.2 (O2 AI-powered reports) — partially covered by report-command change
- G.1 (return None evaluation)
- G.2 (37 vs 38 verification) — upstream still unresolved

## Risks / Trade-offs

- [Risk] Editing archived changes may cause confusion about what's "active"
  → Mitigation: Changes remain in archive/; edits are documentation-only
  additions, not reopening the change for implementation.

- [Risk] CHANGELOG `Spec:` paths add noise to an otherwise clean format
  → Mitigation: Single line per version, collapsed at end of section.
  The traceability benefit outweighs the visual cost.
