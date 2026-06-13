## Why

The gaze-py constitution was amended from v1.0.0 to v1.1.1 (MINOR v1.1.0: Principles VI and VII, parent constitution reference, SHA-pinned CI actions; PATCH v1.1.1: taxonomy count clarification 37→38) but the changes sit uncommitted on `main`. The constitution's own governance rules require all amendments to go through a feature branch, review-council approval, and PR — this change formalizes that process and gets the amendment merged correctly.

Note: although the constitution's Development Workflow section exempts "constitution amendments" from the spec-first requirement, that exemption applies to the *content* of the amendment (the edits to `constitution.md`). The *PR process itself* (branching, review-council, merge) is governed by the Governance section and is not exempt — hence this OpenSpec.

## What Changes

- Create feature branch `opsx/constitution-v1.1.0` from current `main`
- Commit exactly three files: `.specify/memory/constitution.md`, `.github/workflows/test.yml`, and `.github/dependabot.yml` — no other files
- Run `/review-council` to obtain APPROVE from all applicable Divisor reviewers (Guard, Architect, SRE, Adversary)
- Resolve any REQUEST CHANGES findings
- Open and merge the PR against `main` using a merge commit (not squash, not rebase)
- PR title: `chore: ratify gaze-py constitution v1.1.1`

## Capabilities

### New Capabilities

- `constitution-amendment-pr`: The workflow for branching, committing, reviewing, and merging a constitution amendment via PR, satisfying the governance rules defined in the constitution itself.

### Modified Capabilities

(none — no existing spec-level behavior is changing)

### Removed Capabilities

(none)

## Impact

- `.specify/memory/constitution.md` — bumped to v1.1.0, two new principles, parent constitution reference
- `.github/workflows/test.yml` — floating action tags replaced with commit-SHA pins; `uv sync` updated to use `--frozen` for reproducibility
- No production code, APIs, or test behavior is affected
- Once merged, the `opsx/constitution-v1.1.0` branch is closed; `main` reflects the ratified v1.1.0 constitution

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` v1.1.0 (the version being ratified by this change).

**Org Constitution (Unbound Force v1.2.0)**

- **I. Autonomous Collaboration**: N/A — this change produces no inter-hero artifacts and uses no Hero Interface Contract envelope format. gaze-py is a standalone CLI tool. Scope-out documented in SYNC IMPACT REPORT.
- **II. Composability First**: PASS — this change introduces no new dependencies and no inter-hero coupling. The PR process is entirely self-contained.
- **III. Observable Quality**: N/A — this change modifies no machine-parseable JSON output and adds no new observable quality claims.
- **IV. Testability**: PASS — the spec scenarios are concrete and independently verifiable. The process is auditable via git history, review-council output, and PR record.

**gaze-py Constitution Principles (v1.1.0)**

- **I. Accuracy**: N/A — no analysis code is modified.
- **II. Minimal Assumptions**: N/A — no analysis behavior is modified.
- **III. Actionable Output**: N/A — no output format is modified.
- **IV. Testability**: PASS — spec scenarios are verifiable; the governance process itself is auditable.
- **V. Porting Contract Supremacy**: N/A — no porting contract surface is affected.
- **VI. Composability First**: PASS — this change introduces no inter-hero dependencies.
- **VII. Supply Chain Integrity**: PASS — this change is the vehicle that ratifies Principle VII. The CI SHA pins being committed are the direct implementation of the principle. The `uv sync --frozen` fix ensures CI enforces lock file reproducibility.
