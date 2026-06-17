## ADDED Requirements

### Requirement: No-args workflow detection

When `/gazepy fix` is invoked with no arguments, it SHALL detect the active
implementation workflow (Speckit or OpenSpec) and delegate to the corresponding
implementation command. The detection logic is identical to `/gaze fix`:
Speckit check → OpenSpec check → ask user.

#### Scenario: Speckit branch detected

- **WHEN** `.specify/scripts/bash/check-prerequisites.sh --json --paths-only`
  succeeds and returns a `FEATURE_DIR` containing `tasks.md`
- **THEN** the command reads and executes `.opencode/command/speckit.implement.md`

#### Scenario: OpenSpec change detected on correct branch

- **WHEN** a directory under `openspec/changes/` (excluding `archive/`)
  contains `tasks.md` AND the current branch is `opsx/<change-name>`
- **THEN** the command reads and executes `.opencode/command/opsx-apply.md`

#### Scenario: OpenSpec change detected on wrong branch

- **WHEN** an OpenSpec change is detected AND the current branch is NOT
  `opsx/<change-name>`
- **THEN** the command stops with an error message naming the required branch

#### Scenario: No workflow detected

- **WHEN** neither a Speckit branch nor an OpenSpec change is found
- **THEN** the command asks the user to choose between `/speckit.implement`,
  `/opsx-apply`, or `/gazepy fix src/` (batch mode)

### Requirement: Batch remediation with gazepy analysis

When `/gazepy fix [path]` is invoked with a path argument, it SHALL run
`gazepy crap` and `gazepy quality` on the path, build a prioritised target
list, delegate each target to the `gazepy-test-generator` agent, and verify
with `uv run pytest --tb=short`.

#### Scenario: Successful batch run

- **WHEN** `gazepy crap --format=json src/` produces actionable targets
- **THEN** the command generates tests for each target via `gazepy-test-generator`,
  verifies with `uv run pytest --tb=short`, and reports a summary table

#### Scenario: No actionable targets

- **WHEN** `gazepy crap --format=json src/` produces no targets needing
  `add_tests`, `add_assertions`, `add_docs`, or `decompose_and_test`
- **THEN** the command reports "No functions need remediation in [path]" and exits

#### Scenario: Binary not found

- **WHEN** neither `uv run gazepy` nor `which gazepy` resolves the binary
- **THEN** the command reports an error with install instructions:
  `uv tool install gaze-py`

### Requirement: Dry-run mode

When `--dry-run` is passed, the command SHALL display the code that would be
generated but MUST NOT write any files.

#### Scenario: Dry run shows code without writing

- **WHEN** `--dry-run` is passed
- **THEN** generated test code is printed to the console and no files are modified

### Requirement: Go command file untouched

The existing `.opencode/commands/gaze-fix.md` SHALL NOT be modified by this
change.

#### Scenario: gaze-fix.md unchanged

- **WHEN** the branch is diffed against `main`
- **THEN** `git diff HEAD -- .opencode/commands/gaze-fix.md` is empty
