# gaze-py Constitution

## Core Principles

### I. Accuracy

gaze-py MUST correctly identify all observable side effects produced by a
Python function. An observable side effect includes return values, exceptions
raised, mutations to `self` or argument objects, global state writes, I/O
operations, and any other externally detectable change.

- Every reported effect MUST correspond to a real observable side effect;
  false positives erode trust and MUST be treated as bugs.
- Every actual observable side effect that goes unreported is a false
  negative; false negatives MUST be tracked, measured, and driven toward zero.
- Accuracy claims MUST be backed by automated regression tests using fixture
  source files with known expected effects.
- P0 effects (ReturnValue, ErrorReturn, SentinelError, ReceiverMutation,
  PointerArgMutation) MUST be detected with zero false negatives and zero
  false positives per porting contract EC-002.

**Rationale**: The entire value of gaze-py depends on users trusting its
output. Inaccurate results — in either direction — make the tool worse than
useless.

### II. Minimal Assumptions

gaze-py MUST operate with the fewest possible assumptions about the host
project's test framework, coding style, or project structure.

- Analysis MUST NOT require users to annotate or restructure their existing
  Python code.
- When assumptions are unavoidable (e.g., supported Python versions,
  pytest-style test naming), they MUST be explicit in documentation and
  enforced at analysis entry points — never silently ignored.
- gaze-py MUST use AST-only analysis. No execution of analyzed code, no
  import of analyzed modules, no runtime introspection.

**Rationale**: A test-quality tool that demands setup or convention changes
creates friction. gaze-py earns trust by working with what already exists.

### III. Actionable Output

Every piece of output gaze-py produces MUST guide the user toward a
concrete improvement in their test suite.

- Reports MUST identify the specific test, the specific target function,
  and the specific unasserted contractual effect — not just aggregate scores.
- Output MUST support both human-readable (text) and machine-readable (JSON)
  formats. JSON output MUST be schema-compatible with Go gaze per porting
  contracts EC-004 and OC-002.
- Metrics MUST be comparable across runs so users can measure progress.
- Fields that depend on optional capabilities (GazeCRAP, contract coverage,
  quadrant) MUST be null/absent when the capability has not run — not
  zero-valued (porting contract OC-003).

**Rationale**: Metrics without actionable detail are vanity numbers. gaze-py
exists to help developers write better tests, and that requires telling them
exactly what to fix.

### IV. Testability

Every function gaze-py analyzes, and every function within gaze-py itself,
MUST be testable in isolation without requiring external services or shared
mutable state.

- Test contracts MUST verify observable side effects (return values, raised
  exceptions, emitted output), not implementation details or private state.
- Coverage strategy MUST be specified in the implementation plan for all
  new code. Missing coverage strategy in a spec or plan is a CRITICAL finding
  and MUST be resolved before implementation begins.
- Coverage ratchets MUST be enforced by CI; coverage regression MUST be
  treated as a test failure.
- Conformance tests MUST reference porting contract IDs (EC-001, CC-001,
  SC-001, etc.) so the test suite demonstrates compliance.

**Rationale**: gaze-py is a test-quality tool. If its own tests are poorly
structured, it undermines the credibility of its assessments.

---

## Development Workflow

- **Spec-First**: All changes that modify production code, test code, agent
  prompts, embedded assets, or CI configuration MUST be preceded by a spec.
  Use the Speckit pipeline (`specs/`) for strategic changes (≥ 3 stories or
  cross-repo). Use the OpenSpec pipeline (`openspec/changes/`) for tactical
  changes (< 3 stories, single repo). Spec artifacts MUST exist before
  implementation begins. Exempt: constitution amendments, typo fixes,
  single-line formatting fixes, emergency hotfixes (retroactively documented).

- **Porting Contracts First**: Before writing any spec, the implementer MUST
  read `docs/porting/contracts.md`, `docs/porting/requirements.md`, and
  `docs/porting/taxonomy-reference.md` in the Go gaze repository. These
  documents are the authoritative source for what gaze-py MUST implement.
  Any spec that contradicts or ignores the porting contracts MUST be revised
  before implementation begins.

- **Branching**: All work MUST occur on feature branches. Direct commits to
  `main` are prohibited except for trivial documentation fixes.

- **Convention Packs**: Agents MUST read `.opencode/uf/packs/python.md` and
  `.opencode/uf/packs/python-custom.md` before writing or reviewing any
  Python code. All 15 custom rules (CR-001 through CR-004, plus the rules
  promoted to the canonical pack) are non-negotiable.

- **Code Review**: Every pull request MUST receive at least one approving
  review before merge.

- **Review Council Gate**: Before submitting a pull request, agents MUST run
  `/review-council` and receive APPROVE from all reviewers. Any REQUEST
  CHANGES findings MUST be resolved before PR submission. There MUST be
  minimal to no code changes between APPROVE and PR submission.

- **CI Gate**: The CI pipeline (ruff, mypy strict, pytest --cov-fail-under=85)
  MUST pass before a pull request is eligible for merge.

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
  and approved before merge.
- **Versioning**:
  - MAJOR: Principle removal or incompatible redefinition.
  - MINOR: New principle or materially expanded guidance.
  - PATCH: Clarifications or non-semantic refinements.
- **Compliance Review**: At each planning phase (spec, plan, tasks), the
  Constitution Check gate MUST verify alignment with all active principles.

**Version**: 1.0.0 | **Ratified**: 2026-06-13
