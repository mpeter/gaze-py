<!--
  SYNC IMPACT REPORT
  ==================
  Version change: 1.1.0 → 1.1.1
  Amendment date: 2026-06-13

  Clarification (PATCH):
    Principle V — corrected effect taxonomy count from 37 to 38.
    The porting contracts contain a documentation bug: contracts.md EC-001
    Count column says "5" for P4 while listing 6 names; both documents state
    "37 total" in their headers but enumeration of all named rows yields 38
    (P0=5 + P1=8 + P2=10 + P3=9 + P4=6 = 38). specs.md EC-001 documents
    this and asserts 38. The constitution is updated to match.
    Filed for upstream resolution with Go gaze maintainers via specs.md note.

  Previous SYNC IMPACT REPORT (v1.1.0):
  ==================
  Version change: 1.0.0 → 1.1.0
  Amendment date: 2026-06-13
  Parent constitution: Unbound Force Org Constitution v1.2.0

  Added principles:
    VI.  Composability First — standalone installability; no hard inter-hero
         prerequisites; extension points at module interfaces
    VII. Supply Chain Integrity — committed lock file; CI actions pinned by
         commit SHA; dependency justification required before adding new deps

  Org principle scoped out:
    I. Autonomous Collaboration (org v1.2.0) — the Hero Interface Contract
       envelope format and self-describing artifact metadata requirements
       target service-to-service inter-hero artifact passing. gaze-py is a
       standalone CLI analysis tool; its JSON output is consumed directly by
       users and tooling, not routed through a hero artifact bus. This
       principle is not applicable and is intentionally omitted. If gaze-py
       ever gains a service mode or participates in a hero pipeline, this
       decision MUST be revisited.
       Org constitution location: ../unbound-force/.specify/memory/constitution.md
       (or https://github.com/unbound-force/unbound-force if available externally)

  Updated sections:
    Governance — parent_constitution field added; compliance review updated
                 to reference "all active principles" (was "all five principles")

  Templates requiring updates: none

  Follow-up TODOs:
    - Once pyproject.toml is added, run `uv sync --frozen` and commit uv.lock to
      satisfy Principle VII's lock file requirement (currently inapplicable
      as no package manifest exists yet). Track in a dedicated OpenSpec change.
    - ✅ Dependabot config added: `.github/dependabot.yml` (github-actions, weekly,
      Conventional Commits prefix, open-pull-requests-limit: 5). Completed in `opsx/constitution-v1.1.0`.
    - Add `pip` ecosystem entry to `.github/dependabot.yml` when `pyproject.toml` is
      committed in `001-initial-port`.
    - Reconcile AGENTS.md review-council list to include SRE for CI-touching changes
      and document the Tester-vs-SRE selection rule.

  Previous SYNC IMPACT REPORT (v1.0.0):
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
- The 38-type effect taxonomy (EC-001), the confidence scoring formula
  (CC-001), the CRAP/GazeCRAP formulas (SC-001/SC-002), the quadrant rules
  (SC-004), and the JSON field names (OC-002) are fixed. They MUST NOT be
  invented, renamed, or reinterpreted. Note: the porting contracts state
  "37 types" in their headers due to a documentation bug (contracts.md P4
  Count column says 5 while listing 6 names). The canonical count is 38 by
  enumeration. See specs.md EC-001 for the documented discrepancy.
- Any spec element that conflicts with a porting contract MUST be revised
  before implementation begins. The porting contract wins.

**Rationale**: gaze-py is a port, not an independent tool. Schema
compatibility with Go gaze is a first-class requirement — users and tooling
depend on consistent output across implementations.

### VI. Composability First

gaze-py MUST be independently installable and usable without any other Unbound
Force hero or external service present.

- No implementation MAY introduce a hard runtime dependency on another hero.
  Optional integrations (e.g., reading a sibling hero's output) MUST degrade
  gracefully when that hero is absent. Graceful degradation means: exit with
  code 0, emit a warning to stderr naming the unavailable integration, and
  continue with reduced functionality. Unhandled exceptions and partial or
  corrupt output are NOT acceptable degradation modes.
- Extension points (configuration loaders, output formatters, effect
  classifiers) MUST be defined at module interfaces. Callers extend behavior
  by providing alternative implementations — not by modifying internals.
- The `gazepy` CLI MUST be the sole required entry point. Users MUST NOT need
  to run another hero's binary to obtain a valid gaze-py result.

**Rationale**: A tool that silently depends on adjacent tooling is fragile and
hostile to new contributors. gaze-py earns adoption by working in isolation
from day one.

### VII. Supply Chain Integrity

gaze-py MUST maintain a verifiable, reproducible dependency graph.

- All runtime and development dependencies MUST be managed via a committed lock
  file (`uv.lock`). The lock file MUST be kept in version control and updated
  whenever dependencies change. (Prerequisite: a `pyproject.toml` must exist;
  this requirement activates once the package manifest is committed.)
- CI pipeline actions MUST be pinned by commit SHA. Floating tag references
  (e.g., `@v4`) are prohibited in `.github/workflows/`. The human-readable
  version tag MUST be preserved as an inline comment
  (e.g., `@<sha>  # v4.2.2`). Before committing a pinned SHA, the implementer
  MUST verify it maps to the stated version tag using
  `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`. SHA pins MUST be kept
  current via automated tooling (e.g., Dependabot with `ecosystem: github-actions`).
- Before adding a new dependency, the implementer MUST justify in the spec or
  PR description that the existing toolchain cannot cover the use case.
  Transitive dependency count and maintenance status MUST be considered.

**Rationale**: Floating tags and unlocked dependency graphs are silent failure
modes. A pinned, auditable supply chain makes security incidents detectable
and reproducible builds possible.

---

## Development Workflow

- **Spec-First**: All changes that modify production code, test code, agent
  prompts, embedded assets, or CI configuration MUST be preceded by a spec.
  Use the Speckit pipeline (`specs/`) for strategic changes (multiple stories
  or cross-repo scope). Use the OpenSpec pipeline (`openspec/changes/`) for
  tactical changes (single story, single repo). Spec artifacts MUST exist
  before implementation begins.
  Exempt: constitution amendments *(the content edits themselves; the PR and
  review-council process still applies per the Governance section)*, typo
  fixes, single-line formatting fixes, emergency hotfixes (retroactively
  documented within 24 hours).

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

- **Parent Constitution**: Unbound Force Org Constitution v1.2.0
- **Amendments**: Any change MUST be proposed via pull request, reviewed,
  and approved before merge. The amendment MUST include a migration plan if
  it alters or removes existing principles.
- **Versioning**:
  - MAJOR: Principle removal or incompatible redefinition.
  - MINOR: New principle or materially expanded guidance.
  - PATCH: Clarifications or non-semantic refinements.
- **Compliance Review**: At each planning phase (spec, plan, tasks), the
  Constitution Check gate MUST verify alignment with all active principles,
  with explicit sign-off on Principle V (porting contract alignment).

**Version**: 1.1.1 | **Ratified**: 2026-06-13 | **Last Amended**: 2026-06-13
