## MODIFIED Requirements

### Requirement: output-messages

`gazepy init` SHALL emit a summary of actions taken to stdout using
`click.echo()`. The summary SHALL distinguish between created, skipped,
overwritten, and updated files. A closing hint SHALL direct users to `/gaze`
and OpenSpec requirements guidance, without recommending `/speckit.testreview`.

#### Scenario: output on first run

- **WHEN** all assets are created
- **THEN** stdout includes `gazepy OpenCode integration initialized:` followed
  by `created: .opencode/<path>` for each file
- **AND** the closing hint recommends `/gaze` and OpenSpec, not Spec Kit

#### Scenario: output when already up to date

- **WHEN** all assets exist and are current
- **THEN** stdout includes `gazepy OpenCode integration already up to date:`

#### Scenario: --force hint when user files skipped

- **WHEN** one or more user-owned files were skipped
- **THEN** stdout includes the count of skipped files and suggests `--force`
  to overwrite
