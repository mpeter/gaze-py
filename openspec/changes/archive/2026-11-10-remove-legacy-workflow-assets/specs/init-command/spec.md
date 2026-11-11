## MODIFIED Requirements

### Requirement: asset-deployment
`gazepy init` SHALL deploy the following assets into `.opencode/` of the
current working directory:

**User-owned assets** (skipped if already present, unless `--force`):
- `.opencode/agents/gaze-reporter.md`
- `.opencode/agents/reviewer-testing.md`
- `.opencode/commands/gaze.md`

**Tool-owned assets** (overwritten automatically when content changes):
- `.opencode/agents/gaze-test-generator.md`
- `.opencode/commands/gaze-fix.md`
- `.opencode/references/doc-scoring-model.md`
- `.opencode/references/example-report.md`

#### Scenario: first run
- **WHEN** `gazepy init` is invoked in a directory with no existing
  `.opencode/` assets
- **THEN** all assets are created
- **AND** the command reports each created file with `created: .opencode/<path>`
- **AND** the command exits 0

#### Scenario: assets already exist (user-owned)
- **WHEN** `gazepy init` is invoked and user-owned assets already exist
- **THEN** existing user-owned files are skipped
- **AND** the command reports each skipped file with `skipped: .opencode/<path> (already exists)`
- **AND** the command exits 0

#### Scenario: tool-owned assets have changed content
- **WHEN** `gazepy init` is invoked and a tool-owned asset exists but its
  content differs from the bundled version
- **THEN** the file is overwritten with the new content
- **AND** the command reports `updated: .opencode/<path> (content changed)`

#### Scenario: file not in the asset list
- **WHEN** `gazepy init` or `gazepy init --force` is invoked and `.opencode/`
  contains a file that is not in the asset list above, such as a command
  deployed by an earlier release
- **THEN** that file is not modified, removed or reported
- **AND** the command exits 0

### Requirement: output-messages
`gazepy init` SHALL emit a summary of actions taken to stdout using
`click.echo()`. The summary SHALL distinguish between created, skipped,
overwritten, and updated files. A closing hint SHALL be emitted directing
users to run `/gaze` and `/gaze-fix`.

#### Scenario: output on first run
- **WHEN** all assets are created
- **THEN** stdout includes `gazepy OpenCode integration initialized:`
  followed by `created: .opencode/<path>` for each file

#### Scenario: output when already up to date
- **WHEN** all assets exist and are current
- **THEN** stdout includes `gazepy OpenCode integration already up to date:`

#### Scenario: --force hint when user files skipped
- **WHEN** one or more user-owned files were skipped
- **THEN** stdout includes a message indicating the count of skipped files
  and suggesting `--force` to overwrite

#### Scenario: closing hint
- **WHEN** the command completes
- **THEN** stdout includes a hint to run `/gaze` and `/gaze-fix`
