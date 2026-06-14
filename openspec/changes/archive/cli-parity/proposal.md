## Why

gazepy ships with two commands (`analyze`, `report`) that combine responsibilities
Go gaze keeps separate, making agent docs, CI templates, and the UF integration
story harder than necessary. Matching Go gaze's command surface exactly lets the
same agent docs, CI workflow templates, and user muscle-memory work across both
tools — a prerequisite for adding gazepy as a first-class citizen in UF alongside
Go gaze.

## What Changes

- **BREAKING** `analyze` — strip CRAP scoring out; becomes detection + optional
  `--classify` only, matching Go gaze exactly. Adds `--classify`, `--verbose`,
  `--config`, `--contractual-threshold`, `--incidental-threshold` flags.
  Removes `--coverage-json` (moves to `crap`).
- **BREAKING** `report` — drop the current `src tests` positional signature;
  adopt Go gaze signature: optional `[path]`, `--ai`, `--model`, `--format`,
  `--coverprofile`, `--max-crapload`, `--max-gaze-crapload`,
  `--min-contract-coverage`, `--ai-timeout`. Stub body (O1+O2 deferred).
- **NEW** `crap` — real implementation. Detects side effects + computes CRAP
  scores. Runs `pytest --cov` as subprocess when no `--coverprofile` is given
  (mirrors Go gaze running `go test -coverprofile` internally). Accepts
  `--coverprofile` for pre-generated coverage.py JSON. Supports CI threshold
  flags `--max-crapload`, `--max-gaze-crapload`.
- **NEW** `quality` — stub. Accepts full Go gaze flag surface; exits 1 with
  "not yet implemented — requires O1 (change 002/A)".
- **NEW** `docscan` — stub. Accepts `--config`; exits 1 with "not yet
  implemented — requires O3".
- **NEW** `schema` — real implementation. Prints the JSON schema embedded in
  `report/json_formatter.py`. No arguments.
- **NEW** `self-check` — real implementation. Walks up from cwd to find
  `pyproject.toml` sentinel (mirrors Go gaze go.mod walk), then runs `crap`
  on `src/gaze_py/`. Flags: `--format`, `--max-crapload`.
- **NEW** `init` — real implementation. Scaffolds OpenCode agent and command
  files into `.opencode/` of the current directory. Embeds two assets:
  `gazepy-reporter.md` and `gazepy.md`. Warns if no `pyproject.toml` found.
  Supports `--force` to overwrite existing files.

## Capabilities

### New Capabilities

- `crap-command`: The `crap` subcommand — CRAP scoring with automatic pytest
  coverage collection or pre-generated `--coverprofile`, CI threshold flags,
  and text/JSON output.
- `init-command`: The `init` subcommand — scaffold engine that embeds and
  deploys `gazepy-reporter.md` and `gazepy.md` into `.opencode/` of any
  Python project.
- `stub-commands`: The `quality`, `docscan` stubs and the refactored `report`
  stub — correct flag surfaces, clear "not yet implemented" error messages,
  exit code 1.
- `schema-command`: The `schema` subcommand — prints the JSON schema constant.
- `self-check-command`: The `self-check` subcommand — dogfoods `crap` on
  gazepy's own source.

### Modified Capabilities

- `analyze`: Requirements change — CRAP scoring removed from output; new flags
  added (`--classify`, `--verbose`, `--config`, threshold overrides).

## Impact

- `src/gaze_py/cli/main.py` — all command definitions rewritten
- `src/gaze_py/cli/scaffold.py` — new module (scaffold engine)
- `src/gaze_py/cli/assets/` — new package data directory with embedded agent
  and command files
- `src/gaze_py/report/json_formatter.py` — extract schema as module-level
  constant if not already present
- `pyproject.toml` — no change needed; hatchling includes `cli/assets/` automatically via the existing `packages = ["src/gaze_py"]` directive
- `tests/test_cli.py` — update analyze tests (remove CRAP assertions), add
  crap/quality/docscan/report/schema/self-check/init tests
- Breaking change to `gazepy analyze` JSON output (CRAP fields removed)
- Breaking change to `gazepy report` CLI signature
