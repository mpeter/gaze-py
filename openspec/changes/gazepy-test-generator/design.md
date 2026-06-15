## Context

The Go gaze repository ships `.opencode/agents/gaze-test-generator.md`, a
subagent that drives a `gaze quality → test generation` workflow for Go
projects. The gaze-py repository has no equivalent. This change ports that
agent to Python/pytest, translating all Go-specific idioms while preserving
the same six-action taxonomy and structural layout. The structural reference
is `.opencode/agents/gaze-test-generator.md`.

The agent is a plain Markdown prompt file; it contains no executable Python,
no imports, and no CI hooks. It is invoked as an OpenCode subagent via the
Task tool by callers who already have `gazepy quality --format=json` output.

## Goals / Non-Goals

**Goals:**

- Create `.opencode/agents/gazepy-test-generator.md` with correct frontmatter
  (`mode: subagent`, `tools: read/bash/write/edit: true`) and full agent
  content translated for Python/pytest.
- Mirror the Go agent's six-action taxonomy: `add_tests`, `add_assertions`,
  `add_docs`, `decompose_and_test`, `decompose`, `verify`.
- Document all input fields drawn from `gazepy quality --format=json`:
  Gaps, GapHints, DiscardedReturns, AmbiguousEffects, UnmappedAssertions,
  ContractCoverageReason, EffectConfidenceRange.
- Specify pytest-native output: `def test_<fn>_<scenario>():` with plain
  `assert`, `pytest.raises`, `pytest.approx`, `@pytest.mark.parametrize`.
- Specify convention detection: `@pytest.fixture`, `conftest.py`, `tmp_path`,
  naming pattern `test_<function>_<scenario>`.
- Specify AST-only isolation constraint: never import or execute testdata
  fixtures.
- Pass CI gate (ruff check, ruff format, mypy — all irrelevant for a `.md`
  file; pytest suite must remain green; no coverage delta expected since
  no production code changes).

**Non-Goals:**

- No Python production code is written.
- No pytest test files are created.
- No CI workflow changes.
- No new Python package dependencies.
- No port of the Go agent's `add_docs` GoDoc format — translate to
  Google-style docstrings (CS-004) and Python type hints instead.

## Decisions

### D-001: Single file, pure Markdown

**Decision**: The entire agent is a single `.md` file with YAML frontmatter.
No Python shim, no shell script, no `__init__.py`.

**Rationale**: This matches the convention established by
`gaze-test-generator.md`, `gaze-reporter.md`, and all other agents in
`.opencode/agents/`. OpenCode subagents are prompt files, not executables.
The file is the agent.

**Alternative considered**: A Python helper script invoked by the agent.
Rejected — adds a code artifact that requires testing and maintenance for no
additional capability.

### D-002: Translate all Go idioms to Python/pytest equivalents

| Go concept | Python/pytest equivalent |
|---|---|
| `func TestFoo_Bar(t *testing.T)` | `def test_foo_bar():` |
| `t.Errorf` / `t.Fatalf` | plain `assert` |
| `errors.Is(err, target)` | `pytest.raises(ExceptionType, match="...")` |
| float equality | `pytest.approx(value, rel=1e-3)` |
| table-driven `tt` slice | `@pytest.mark.parametrize` |
| `package foo_test` | top-level `tests/test_<module>.py` |
| `go test -race -run ...` | `uv run pytest --tb=short -k <test_name>` |
| GoDoc comment | Google-style docstring + type hints |
| `gaze quality --format=json` | `gazepy quality --format=json` |
| `*_test.go` | `tests/test_<module>.py` |

### D-003: `add_docs` threshold unchanged but translated

**Decision**: Apply `add_docs` when `ContractCoverageReason` is
`all_effects_ambiguous` AND `EffectConfidenceRange` shows confidence in the
58–69 range (close to the 70 contractual threshold). The action improves
Google-style docstrings (CS-004) and type hints.

**Rationale**: The Go agent's threshold logic is defined by the porting
contract; the threshold value (70) is not language-specific — it is derived
from the classifier's confidence scoring, which is identical in gaze-py. Only
the output format changes (docstring instead of GoDoc).

### D-004: AST-only isolation explicitly documented

**Decision**: The agent's Important Constraints section must include: "NEVER
import or execute files under `tests/testdata/` — they are static AST fixtures,
not runnable test files. Only read their source text."

**Rationale**: This mirrors the Go agent's warning about avoiding runtime
execution of analyzed packages. In gaze-py, testdata files under
`tests/testdata/` contain intentionally bare call sites and would fail at
import time (CR-002). The agent must not attempt to execute them.

## Risks / Trade-offs

- **[Risk] Agent drift from Go counterpart** — Future changes to
  `gaze-test-generator.md` may not propagate to this file.
  **Mitigation**: The file header references the Go agent as structural
  reference. The spec review council's Guard persona enforces intent fidelity
  and can flag significant divergence.

- **[Risk] Incorrect `gazepy` CLI invocation** — If the `gazepy quality`
  command signature changes, the agent's verify action will produce wrong
  commands.
  **Mitigation**: The agent is a prompt file, not code; updating it is a
  one-line edit. The CI gate for this change verifies the `gazepy` binary
  exists and `--help` works, providing a basic sanity check.

- **[Risk] Convention detection divergence** — Python projects use diverse
  fixture patterns. The agent's convention detection section may not cover
  all variants.
  **Mitigation**: The defaults (plain functions, `tmp_path`, `test_<fn>_<scenario>`)
  follow the project's own python.md TC-004/TC-005 conventions and will be
  correct for this codebase. The agent explicitly reads existing tests before
  generating new ones, so it adapts to project-specific patterns at invocation
  time.

## Open Questions

None — all design decisions have been resolved.
