## ADDED Requirements

### Requirement: SHA verified against published tag before committing
Before committing the updated action reference, the implementer SHALL verify the target SHA maps to the stated version tag using the GitHub API. The verified SHA and version tag MUST both appear in the workflow file per Principle VII.

#### Scenario: SHA verification passes
- **GIVEN** the target action is `astral-sh/setup-uv` at tag `v8.2.0`
- **WHEN** `gh api repos/astral-sh/setup-uv/git/ref/tags/v8.2.0` is run
- **THEN** the response contains `object.sha: "fac544c07dec837d0ccb6301d7b5580bf5edae39"` and `object.type: "commit"`

### Requirement: Workflow updated with verified SHA and inline version comment
The workflow file SHALL reference the new action by commit SHA with the version tag preserved as an inline comment, and the uv binary pin SHALL be updated to current stable.

#### Scenario: Action reference updated correctly
- **GIVEN** `.github/workflows/test.yml` currently pins `setup-uv` to `d4b2f3b6...` (v5.4.2)
- **WHEN** the file is edited
- **THEN** line 18 reads `uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39  # v8.2.0`

#### Scenario: uv binary pin updated
- **GIVEN** `.github/workflows/test.yml` currently pins `version: "0.7.8"`
- **WHEN** the file is edited
- **THEN** line 20 reads `version: "0.11.21"`

### Requirement: CI passes after upgrade
After the workflow edits are committed and pushed, the GitHub Actions `test.yml` workflow SHALL complete successfully on the feature branch. A red CI run MUST be resolved before the PR is opened.

#### Scenario: CI green after upgrade
- **GIVEN** the branch has been pushed with the updated `test.yml`
- **WHEN** the GitHub Actions `test.yml` workflow completes
- **THEN** all steps (lint, format check, type check, test) exit with status 0

#### Scenario: CI red — fallback to v8.1.0
- **GIVEN** CI fails after upgrading to v8.2.0
- **WHEN** the failure is attributed to the action upgrade
- **THEN** the implementer pins to v8.1.0 (`08807647e7069bb48b6ef5acd8ec9567f424441b`) instead, verifies that SHA, updates the comment, and re-runs CI

## MODIFIED Requirements

(none)

## REMOVED Requirements

(none)
