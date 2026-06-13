<!--
  SYNC IMPACT REPORT
  ==================
  Version change: (template) → 1.0.0 (initial ratification)
  Ratification date: 2026-06-13

  Added principles:
    I.   Accuracy — zero false negatives on P0 effects; porting contract EC-002
    II.  Minimal Assumptions — AST-only, no execution, no annotation requirement
    III. Actionable Output — specific test/function/effect; null not zero (OC-003)
    IV.  Testability — contracts over implementation; conformance test IDs required
    V.   Porting Contract Supremacy — contracts.md/requirements.md/taxonomy-reference.md
         are ground truth; any spec that contradicts them must be revised

  Added sections:
    Development Workflow — spec-first, porting-contracts-first, convention packs,
    branching, review council gate, CI gate
    Governance — amendment procedure, versioning policy, compliance review

  Templates requiring updates:
    ✅ plan-template.md — Constitution Check gate references updated to include
       porting contract alignment check
    ✅ spec-template.md — Success Criteria section updated to reference SC-NNN
       from contracts.md; Porting Contract Compliance added as mandatory section
    ✅ tasks-template.md — no structural changes needed; convention pack
       reference added to Implementation Strategy

  Follow-up TODOs: none
-->

# gaze-py Constitution

## Core Principles

### I. Accuracy

gaze-py MUST correctly identify all observable side effects produced by a
Python function. An observable side effect includes return values, exceptions
raised, mutations to `self` or argument objects, global state writes, I/O
operations, and any other externally detectable change.

- Every reported effect MUST correspond to a real observable side effect.
  False positives erode trust and MUST be treated as bugs.
- Every actual observable side effect that goes unreported is a false negative.
  False negatives MUST be tracked, measured, and driven toward zero.
- P0 effects (ReturnValue, ErrorReturn, SentinelError, ReceiverMutation,
  PointerArgMutation) MUST be detected with zero false negatives and zero false
  positives per porting contract EC-002.
- Accuracy claims MUST be backed by automated regression tests using fixture
  source files with known expected effects.

**Rationale**: The entire value of gaze-py depends on users trusting its
output. Inaccurate results — in either direction — make the tool worse than
useless.

### II. Minimal Assumptions

gaze-py MUST operate with the fewest possible assumptions about the host
project's test framework, coding style, or project structure.

- Analysis MUST NOT require users to annotate or restructure their existing
  Python code.
- gaze-py MUST use AST-only analysis. No execution of analyzed code, no import
  of analyzed modules, no runtime introspection.
- When assumptions are unavoidable (e.g., supported Python versions, pytest
  naming conventions), they MUST be explicit in documentation and enforced at
  analysis entry points — never silently ignored.

**Rationale**: A test-quality tool that demands setup or convention changes
creates friction. gaze-py earns trust by working with what already exists.

### III. Actionable Output

Every piece of output gaze-py produces MUST guide the user toward a concrete
improvement in their test suite.

- Reports MUST identify the specific test, the specific target function, and
  the specific unasserted contractual effect — not just aggregate scores.
- Output MUST support both human-readable (text) and machine-readable (JSON)
  formats. JSON output MUST be schema-compatible with Go gaze per porting
  contracts EC-004 and OC-002.
- Fields that depend on optional capabilities (GazeCRAP, contract coverage,
  quadrant) MUST be null/absent when the capability has not run — not
  zero-valued (porting contract OC-003). Zero and "not computed" are distinct
  states and MUST NOT be conflated.
- No hardcoded placeholder strings (e.g., `"test.py:?"`, `"<unknown>"`) MUST
  appear in production output. Unavailable fields serialize as `null`.

**Rationale**: Metrics without actionable detail are vanity numbers. gaze-py
exists to help developers write better tests, and that requires telling them
exactly what to fix.

### IV. Testability

Every function gaze-py analyzes, and every function within gaze-py itself,
MUST be testable in isolation without requiring external services or shared
mutable state.

- Test contracts MUST verify observable side effects (return values, raised
  exceptions, emitted output), not implementation details or private state.
- Conformance tests MUST reference porting contract IDs (EC-001, CC-001,
  SC-001, OC-001, etc.) so the test suite demonstrates compliance explicitly.
- Coverage strategy MUST be specified in the implementation plan for all new
  code. Missing coverage strategy is a CRITICAL finding and MUST be resolved
  before implementation begins.
- Coverage ratchets MUST be enforced by CI; regression below the threshold
  MUST be treated as a build failure.

**Rationale**: gaze-py is a test-quality tool. If its own tests are poorly
structured, it undermines the credibility of its assessments.

### V. Porting Contract Supremacy

The Go gaze porting documents are the authoritative ground truth for what
gaze-py MUST implement. No spec, plan, or implementation MAY contradict them.

- Before writing any spec, the implementer MUST read
  `docs/porting/contracts.md`, `docs/porting/requirements.md`, and
  `docs/porting/taxonomy-reference.md` from the Go gaze repository at
  `../gaze/`.
- The 37-type effect taxonomy (EC-001), the confidence scoring formula
  (CC-001), the CRAP/GazeCRAP formulas (SC-001/SC-002), the quadrant rules
  (SC-004), and the JSON field names (OC-002) are fixed. They MUST NOT be
  invented, renamed, or reinterpreted.
- Any spec element that conflicts with a porting contract MUST be revised
  before implementation begins. The porting contract wins.

**Rationale**: gaze-py is a port, not an independent tool. Schema
compatibility with Go gaze is a first-class requirement — users and tooling
depend on consistent output across implementations.

---

## Development Workflow

- **Spec-First**: All changes that modify production code, test code, agent
  prompts, embedded assets, or CI configuration MUST be preceded by a spec.
  Use the Speckit pipeline (`specs/`) for strategic changes (multiple stories
  or cross-repo scope). Use the OpenSpec pipeline (`openspec/changes/`) for
  tactical changes (single story, single repo). Spec artifacts MUST exist
  before implementation begins.
  Exempt: constitution amendments, typo fixes, single-line formatting fixes,
  emergency hotfixes (retroactively documented within 24 hours).

- **Porting Contracts First**: Before writing any spec, read
  `../gaze/docs/porting/contracts.md`, `requirements.md`, and
  `taxonomy-reference.md`. These documents are the authoritative source.
  Spec review MUST include a porting contract alignment check.

- **Convention Packs**: All agents MUST read
  `.opencode/uf/packs/python.md` and `.opencode/uf/packs/python-custom.md`
  before writing or reviewing any Python code. The 15 rules
  (CS-014–016, AP-007–008, TC-013, CR-001–004, and the rules promoted into
  the canonical pack) are non-negotiable.

- **Branching**: All work MUST occur on feature branches. Direct commits to
  `main` are prohibited except for trivial documentation fixes.

- **Code Review**: Every pull request MUST receive at least one approving
  review before merge.

- **Review Council Gate**: Before submitting a pull request, agents MUST run
  `/review-council` and receive APPROVE from all reviewers. Any REQUEST
  CHANGES findings MUST be resolved before PR submission. There MUST be
  minimal to no code changes between APPROVE and PR submission.

- **CI Gate**: The CI pipeline MUST pass before a pull request is eligible
  for merge. CI includes: `ruff check`, `ruff format --check`, `mypy --strict`,
  `pytest --cov-fail-under=85`.

- **Releases**: Follow semantic versioning (MAJOR.MINOR.PATCH). Breaking
  changes to public APIs, JSON output schemas, or analysis behavior require
  a MAJOR bump.

- **Commit Messages**: Use Conventional Commits (`type: description`).

---

## Governance

This constitution is the highest-authority document for gaze-py. All
development practices, pull request reviews, and architectural decisions
MUST be consistent with the principles defined above.

- **Amendments**: Any change MUST be proposed via pull request, reviewed,
  and approved before merge. The amendment MUST include a migration plan if
  it alters or removes existing principles.
- **Versioning**:
  - MAJOR: Principle removal or incompatible redefinition.
  - MINOR: New principle or materially expanded guidance.
  - PATCH: Clarifications or non-semantic refinements.
- **Compliance Review**: At each planning phase (spec, plan, tasks), the
  Constitution Check gate MUST verify alignment with all five principles,
  with explicit sign-off on Principle V (porting contract alignment).

**Version**: 1.0.0 | **Ratified**: 2026-06-13 | **Last Amended**: 2026-06-13
