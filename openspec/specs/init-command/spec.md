# Spec: init-command

`gazepy init` — scaffold OpenCode agent and command assets into the current
project's `.opencode/` directory. Idempotent by default; `--force` overwrites
user-owned files.

---

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
- `.opencode/commands/speckit.testreview.md`
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

---

### Requirement: idempotency
Running `gazepy init` multiple times SHALL produce the same result as
running it once. User-owned files SHALL NOT be overwritten on subsequent
runs without `--force`.

#### Scenario: second run without --force
- **WHEN** `gazepy init` is run a second time in the same directory
- **THEN** all user-owned files are reported as skipped
- **AND** tool-owned files are reported as up to date (no change)
- **AND** the command exits 0

---

### Requirement: force-flag
`gazepy init` SHALL support `--force` (flag, default: off). When set, all
assets (including user-owned) SHALL be overwritten regardless of whether
they already exist.

#### Scenario: --force overwrites user-owned files
- **WHEN** `--force` is passed and user-owned assets already exist
- **THEN** those files are overwritten with the bundled content
- **AND** the command reports `overwritten: .opencode/<path>`

---

### Requirement: pyproject-toml-warning
`gazepy init` SHALL check for `pyproject.toml` in the current working
directory. When absent, the command SHALL emit a warning to stderr but
SHALL continue and write assets normally.

#### Scenario: pyproject.toml present
- **WHEN** `pyproject.toml` exists in cwd
- **THEN** no warning is emitted and assets are written normally

#### Scenario: pyproject.toml absent
- **WHEN** `pyproject.toml` does not exist in cwd
- **THEN** a warning is emitted to stderr noting that gazepy works best in
  a Python project root
- **AND** assets are written normally
- **AND** the command exits 0

---

### Requirement: symlink-escape-guard
`gazepy init` SHALL validate that each output file path resolves to a path
contained within `.opencode/` in cwd before writing. If a symlink or path
traversal would cause a write outside `.opencode/`, the command SHALL emit
an error to stderr and exit 1 without writing the file.

The containment check SHALL use structural path containment
(`Path.is_relative_to()`), not string prefix matching, to prevent
path-prefix sibling bypasses.

#### Scenario: symlink escape attempt
- **WHEN** `.opencode/` is a symlink pointing outside cwd
- **THEN** the command detects the escape, emits an error to stderr, and
  exits 1 without writing any files outside the guard boundary

---

### Requirement: version-marker
Each deployed asset SHALL include a version marker of the form
`<!-- scaffolded by gazepy <version> -->` inserted after any YAML
frontmatter block, or appended at the end of the file when no frontmatter
is present. The marker is idempotent — if already present, it is not
duplicated.

#### Scenario: marker inserted after frontmatter
- **WHEN** an asset has YAML frontmatter (opening `---` and closing `---`)
- **THEN** the marker is inserted on the line immediately following the
  closing `---`

#### Scenario: marker appended when no frontmatter
- **WHEN** an asset has no YAML frontmatter
- **THEN** the marker is appended at the end of the file

#### Scenario: marker idempotency
- **WHEN** the marker is already present in the file
- **THEN** no duplicate marker is inserted

---

### Requirement: asset-embedding
Assets SHALL be embedded in the `gaze_py.cli.assets` package using
`importlib.resources`. They SHALL NOT be read from the filesystem at
runtime using `__file__`-relative paths. This ensures assets are available
when the package is installed as a wheel.

#### Scenario: assets available after wheel install
- **WHEN** `gazepy` is installed from a wheel (not editable install)
- **THEN** `gazepy init` successfully deploys all assets

---

### Requirement: output-messages
`gazepy init` SHALL emit a summary of actions taken to stdout using
`click.echo()`. The summary SHALL distinguish between created, skipped,
overwritten, and updated files. A closing hint SHALL be emitted directing
users to run `/gaze` and `/speckit.testreview`.

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

---

### Requirement: exit-codes
`gazepy init` SHALL exit 0 on success and 1 when a symlink escape is
detected. There are no other error conditions that cause a non-zero exit —
missing `pyproject.toml` is a warning, not an error.

#### Scenario: success
- **WHEN** all assets are written (or skipped) without error
- **THEN** the command exits 0

#### Scenario: symlink escape
- **WHEN** a path escape is detected
- **THEN** the command exits 1
