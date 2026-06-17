## Why

The review council (Iteration 1, 9 Divisor personas) identified spec artifacts
with missing mandatory sections, vague acceptance criteria, stale tracking
data, and absent traceability links. These gaps violate Constitution Principle
IV (Testability — coverage strategy required) and reduce the value of the spec
corpus as implementation reference material. Three of the eight HIGH advisories
(Advisories 3, 4, 5) address CI supply chain issues and are handled separately
in the `ci-supply-chain` change; this change addresses the remaining five
(Advisories 1, 2, 6, 7, 8).

## What Changes

- Add Coverage Strategy sections to `specs/001-gazepy-init-deploys/plan.md`
  and `openspec/changes/archive/gazepy-fix-command/proposal.md` and
  `openspec/changes/archive/gazepy-test-generator/proposal.md` (archived — update in
  archive for completeness)
- Fix CHANGELOG `[0.4.1]` terminology: "replicator init" → "uf init"
- Add numbered Acceptance Criteria (AC-N: format) to
  `openspec/changes/gap-hints/proposal.md` and
  `openspec/changes/report-command/proposal.md`
- Add `Spec:` traceability paths to every CHANGELOG entry (0.1.0 through
  Unreleased)
- Update `002-deferred-capabilities` tracking document to mark shipped items
  as SHIPPED with version numbers and retain only genuinely deferred items as
  open

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this change modifies spec artifacts and documentation only, not
production capabilities.

## Impact

- `specs/001-gazepy-init-deploys/plan.md` — add Coverage Strategy section
- `openspec/changes/gap-hints/proposal.md` — add Acceptance Criteria section
- `openspec/changes/report-command/proposal.md` — add Acceptance Criteria
  section
- `openspec/changes/archive/gazepy-fix-command/proposal.md` — add coverage
  strategy note
- `openspec/changes/archive/gazepy-test-generator/proposal.md` — add coverage
  strategy note
- `openspec/changes/002-deferred-capabilities/tasks.md` — mark shipped items
- `CHANGELOG.md` — add `Spec:` paths to each entry

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` (v1.1.3).

### I. Accuracy

**Assessment**: PASS — no detection or analysis changes.

### II. Minimal Assumptions

**Assessment**: PASS — no runtime changes.

### III. Actionable Output

**Assessment**: PASS — no output schema changes.

### IV. Testability

**Assessment**: PASS — this change adds the missing coverage strategies
required by Principle IV. Resolves the CRITICAL finding from the Tester.

### V. Porting Contract Supremacy

**Assessment**: PASS — no porting contracts affected.

### VI. Composability First

**Assessment**: PASS — no dependencies added.

### VII. Supply Chain Integrity

**Assessment**: PASS — no dependencies changed.
