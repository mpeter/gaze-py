## ADDED Requirements

### Requirement: Amendment committed on dedicated branch
The implementation SHALL create a dedicated branch `opsx/constitution-v1.1.0` and commit only the files directly related to the constitution amendment (`.specify/memory/constitution.md`, `.github/workflows/test.yml`, and `.github/dependabot.yml`). No unrelated session changes SHALL be included in the commit. The commit MUST use a merge-commit-compatible message with a body containing the SYNC IMPACT REPORT summary.

#### Scenario: Clean branch and commit
- **GIVEN** the working tree contains modifications to both amendment files and unrelated session files (e.g., `AGENTS.md`, `python-custom.md`, `agent-file-template.md`)
- **WHEN** the branch is created and amendment files are staged explicitly by path using `git add .specify/memory/constitution.md .github/workflows/test.yml .github/dependabot.yml`
- **THEN** `git diff --cached --name-only` shows exactly `.specify/memory/constitution.md`, `.github/workflows/test.yml`, and `.github/dependabot.yml` — and no other files

#### Scenario: Unrelated files excluded after commit
- **GIVEN** the branch has been committed
- **WHEN** `git show --name-only HEAD` is run
- **THEN** exactly `.specify/memory/constitution.md`, `.github/workflows/test.yml`, and `.github/dependabot.yml` appear; `AGENTS.md`, `python-custom.md`, and `agent-file-template.md` do NOT appear

#### Scenario: Commit body contains SYNC IMPACT REPORT
- **GIVEN** the commit has been made
- **WHEN** `git log -1 --format=%B` is run
- **THEN** the commit body contains the version change (`1.0.0 → 1.1.0`), the two new principle names, and the Autonomous Collaboration scope-out note

### Requirement: CI passes on the branch before PR submission
The implementation SHALL verify that the GitHub Actions CI workflow passes green on `opsx/constitution-v1.1.0` before the PR is opened. The CI gate is a mandatory merge prerequisite per the constitution's Development Workflow section.

#### Scenario: CI passes on the branch
- **GIVEN** the branch has been pushed to origin
- **WHEN** the GitHub Actions `test.yml` workflow completes on the branch
- **THEN** all steps (lint, format check, type check, test) exit with status 0

### Requirement: Review council approval obtained
The implementation SHALL run `/review-council` on the branch and obtain APPROVE from all applicable reviewers before opening the PR. The applicable reviewers for this change type (governance + CI config, no production code) are: Guard, Architect, SRE, and Adversary. Any REQUEST CHANGES finding MUST be resolved with a new commit on the branch, and `/review-council` MUST be re-run against the updated diff — not the original.

#### Scenario: All applicable reviewers approve
- **GIVEN** the branch diff contains only the two amendment files
- **WHEN** `/review-council` runs against the branch diff
- **THEN** Divisor Guard, Architect, SRE, and Adversary all return APPROVE with no open REQUEST CHANGES items remaining

#### Scenario: REQUEST CHANGES received and resolved
- **GIVEN** a reviewer returns REQUEST CHANGES with specific flagged content
- **WHEN** the flagged content is modified on the branch and a new commit is made
- **THEN** `/review-council` is re-run against the updated diff (not the original), and the previously flagging reviewer returns APPROVE on the new diff

### Requirement: PR opened against main with full context
The implementation SHALL open a PR from `opsx/constitution-v1.1.0` to `main` with a description that summarizes the amendment, lists the new principles, notes the Autonomous Collaboration scope-out, and includes a review-council sign-off checklist. The PR MUST be merged using a merge commit (not squash, not rebase) by a human reviewer.

#### Scenario: PR created with correct base and head
- **GIVEN** the branch has been pushed and CI is green
- **WHEN** the PR is opened using `gh pr create`
- **THEN** base is `main`, head is `opsx/constitution-v1.1.0`, and the title is `chore: ratify gaze-py constitution v1.1.0`

#### Scenario: PR description complete
- **GIVEN** the PR has been created
- **WHEN** the PR description is read
- **THEN** it contains all of the following:
  - Summary of v1.1.0 changes (version bump, two new principles, parent constitution reference)
  - Names and brief descriptions of Principle VI (Composability First) and Principle VII (Supply Chain Integrity)
  - Autonomous Collaboration scope-out rationale consistent with the SYNC IMPACT REPORT in `.specify/memory/constitution.md` (lines 14–22 of the v1.1.0 header)
  - Review-council sign-off checklist naming each of the four applicable reviewers (Guard, Architect, SRE, Adversary) with their final verdict and review date

#### Scenario: PR merged with merge commit
- **GIVEN** the PR has been approved by a human reviewer
- **WHEN** the PR is merged
- **THEN** the merge uses a merge commit (`gh pr merge --merge`); squash and rebase are prohibited; the SYNC IMPACT REPORT content is preserved in `main`'s commit history

## MODIFIED Requirements

(None — this is a new capability with no existing spec-level behavior changing)

## REMOVED Requirements

(None)
