## Context

The Go gaze project ships `/gaze fix`, a dual-mode agent command. Python
projects using gaze-py have no equivalent. The `/gazepy fix` command is the
Python-native port of `/gaze fix`. The only deliverable is a new OpenCode
agent command file at `.opencode/commands/gazepy-fix.md`; there are no Python
source changes in this change.

The existing `.opencode/commands/gaze-fix.md` serves Go projects and MUST
remain unmodified.

## Goals / Non-Goals

**Goals:**

- Provide a `/gazepy fix` command that is structurally equivalent to `/gaze fix`
  while using Python-specific tooling (`uv run gazepy`, `uv run pytest`).
- Preserve the language-agnostic no-args workflow detection logic verbatim
  from `/gaze fix`: check for Speckit feature branch → check for OpenSpec
  active change → ask user.
- Replace all Go-specific elements with Python equivalents:
  - `gaze` binary → `uv run gazepy` (or `which gazepy`)
  - `./...` package pattern → source path (e.g., `src/`)
  - `gaze-test-generator` agent → `gazepy-test-generator` agent
  - `go test -race -count=1 -run ...` → `uv run pytest --tb=short -k ...`
  - `*_test.go` test file lookup → `tests/test_<module>.py` lookup
  - `package` field in CRAP JSON → absent (Python CRAP JSON uses `file`/`line`)
- Delegate batch test generation to the `gazepy-test-generator` agent (already
  defined in the repository).
- Include clear error handling: binary not found, no actionable targets,
  syntax errors in generated tests, failing generated tests.

**Non-Goals:**

- Modifying `.opencode/commands/gaze-fix.md`.
- Adding or changing Python source code in `src/gaze_py/`.
- Adding new pytest tests (command files are not Python).
- Implementing a new gazepy-test-generator agent (already exists).

## Decisions

### D-001: Single file, no shared includes

The `/gaze fix` command is self-contained in one Markdown file. `/gazepy fix`
follows the same pattern. There is no mechanism for shared includes between
command files, and splitting the language-agnostic no-args logic into a
separate file would complicate the command invocation model.

**Alternative considered**: Extract the no-args workflow detection into a
separate include file referenced by both. Rejected — OpenCode command files
do not support includes; agents read the full command file.

### D-002: Binary resolution order

Resolve `gazepy` by checking `uv.lock` first (use `uv run gazepy`), then
fall back to `which gazepy`. This matches how the repository uses `uv` as
the primary toolchain per AGENTS.md.

**Alternative considered**: `which gazepy` only. Rejected — in a `uv`-managed
project, the binary may not be globally installed.

### D-003: Path argument instead of package pattern

`/gaze fix` uses Go's `./...` package pattern. Python has no equivalent;
the path is a filesystem directory (e.g., `src/`, `src/gaze_py/`). The
default is `src/` to match the project's `src/` layout.

### D-004: Test file lookup convention

`/gaze fix` looks for `*_test.go` in the same directory as the source file.
`/gazepy fix` looks for `tests/test_<module>.py` relative to the project
root, where `<module>` is the stem of the source file. This follows pytest
naming conventions documented in the Python convention pack (TC-003).

## Risks / Trade-offs

- **[Risk] gazepy-test-generator agent not present** → Mitigation: the agent
  is defined in the repository; document its name explicitly in the command so
  the dependency is visible. The command fails with a clear error if the agent
  is not found.
- **[Risk] CRAP JSON schema differences between Go and Python** → Mitigation:
  document the exact Python CRAP JSON fields used in the command; omit `package`
  (absent in Python output) and confirm `file`, `line`, `fix_strategy`,
  `crap`, `gaze_crap`, `quadrant`, `contract_coverage`,
  `contract_coverage_reason`, `effect_confidence_range` are present.
- **[Risk] Command file becomes stale if gazepy CLI interface changes** →
  Mitigation: command files are documentation/agent-instruction artifacts, not
  compiled code. Staleness is a maintenance concern, not a CI failure.

## Open Questions

None — the design is fully specified by the structural reference (`gaze-fix.md`)
and the Python-specific substitutions listed in Goals above.
