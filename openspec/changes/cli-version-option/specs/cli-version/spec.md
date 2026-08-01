## ADDED Requirements

### Requirement: The CLI MUST report its own version

`gazepy --version` and `gazepy -V` MUST print the installed package version
and exit 0. The output MUST contain the bare version string, because the
release pipeline greps for it.

The reported version MUST be `gaze_py.__version__`, the same value emitted as
`gaze_version` in JSON metadata — a single source, so the CLI cannot disagree
with the artifact it produces.

#### Scenario: Long and short flags both report the version
- **WHEN** `gazepy --version` or `gazepy -V` is run
- **THEN** the exit code is 0 and the output contains `gaze_py.__version__`

#### Scenario: Output satisfies the release smoke test
- **GIVEN** the release workflow runs `gazepy --version | grep -q "$VER"`
- **WHEN** the published artifact is version `$VER`
- **THEN** the version appears as a standalone token in the output

### Requirement: The release smoke test MUST NOT discard the failure reason

The smoke test SHALL capture stderr from the published artifact. When the retry
loop is exhausted it MUST report the last error rather than attributing the
failure to propagation delay alone.

When the published artifact runs successfully but reports a version other than
the tag, the step MUST fail immediately with that output rather than retrying —
that condition is not a propagation delay and will not resolve by waiting.

#### Scenario: A missing option is diagnosable
- **GIVEN** the published artifact rejects the smoke test's command
- **WHEN** the retry loop is exhausted
- **THEN** the error output names the actual failure, not only a timeout

#### Scenario: A version mismatch fails fast
- **GIVEN** the published artifact runs and prints a version
- **WHEN** that version differs from the release tag
- **THEN** the step fails immediately, reporting the observed output
