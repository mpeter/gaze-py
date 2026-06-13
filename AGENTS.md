## Project Overview

gaze-py is a Python-native GazeCRAP analysis engine — the Python companion to [gaze](https://github.com/unbound-force/gaze). It detects observable side effects in Python functions, classifies them as contractual or incidental, and computes GazeCRAP scores that measure both complexity and meaningful test coverage.

- **Language**: Python 3.12+
- **Module**: `gaze-py` (package: `gaze_py`)
- **License**: Apache 2.0
- **Package Manager**: uv

## Core Mission

- **Strategic Architecture**: Engineers shift from manual coding to directing an "infinite supply of junior developers" (AI agents).
- **Outcome Orientation**: Focus on conveying business value and user intent rather than low-level technical sub-tasks.
- **Intent-to-Context**: Treat specs and rules as the medium through which human intent is manifested into code.

## Build & Test Commands

```bash
# Install dependencies
uv sync

# Build
uv build

# Run all tests
uv run pytest

# Run tests with short output (stop on first failure)
uv run pytest -x --tb=short

# Run a specific test
uv run pytest tests/test_foo.py::test_name

# Run tests with coverage
uv run pytest --cov=gaze_py --cov-report=term-missing

# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Format (auto-fix)
uv run ruff format .

# Lint (auto-fix)
uv run ruff check --fix .

# Type check
uv run mypy src/
```

## Architecture

Source layout using the `src/` convention:

```text
src/gaze_py/
  __init__.py      Package root
  cli.py           CLI layer (click commands)
  taxonomy.py      Domain types: SideEffect, AnalysisResult, Tier,
                   QualityReport, ContractCoverage,
                   OverSpecificationScore, PackageSummary,
                   AssertionMapping, etc.
  classify.py      Contractual classification engine
  config.py        Configuration file handling (.gaze.yaml)
  crap.py          CRAP score computation and reporting
  analysis.py      AST side-effect detection engine (S1)
  quality.py       Assertion mapper and contract coverage (S2)
  report/          JSON (schema-compatible with Go gaze) and text
                   formatters (S3)
tests/
  testdata/        Test fixture packages for analysis
```

All business logic lives under `src/gaze_py/` and is importable as `gaze_py.*`.

### Key Patterns

- **AST-based analysis**: Python's `ast` module for detecting side effects, return patterns, and mutations. Implemented in `analysis.py`.
- **Assertion mapping**: `quality.py` maps detected side effects to test assertions, computing contract coverage per function.
- **Report formatters**: `report/` provides JSON output (schema-compatible with Go gaze, Draft 2020-12) and human-readable text output.
- **Dataclass domain types**: All domain objects (SideEffect, Score, etc.) are `@dataclass` classes with JSON serialization support.
- **Testable CLI pattern**: Click commands delegate to core functions. Core functions accept typed parameters and return result objects — no business logic in the CLI layer.
- **Options dataclasses**: Configurable behavior uses dataclass options rather than long parameter lists.
- **Tiered effect taxonomy**: Side effects are organized into priority tiers P0-P4 (matching Go gaze's taxonomy).

## Coding Conventions

- **Formatting**: `ruff format` (enforced by CI).
- **Linting**: `ruff check` with standard rules.
- **Type checking**: `mypy` in strict mode.
- **Naming**: PEP 8 — `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- **Docstrings**: Google-style docstrings on all public functions, classes, and modules.
- **Error handling**: Raise specific exception types with descriptive messages. Wrap errors with context.
- **Import grouping**: Standard library, then third-party, then internal packages (separated by blank lines). Enforced by ruff.
- **No global state**: Prefer functional style and dependency injection.
- **Constants**: Use `StrEnum` or typed constants for enumerations (`SideEffectType`, `Tier`, `Quadrant`).
- **JSON serialization**: All domain types include `to_dict()` methods. JSON output MUST be schema-compatible with Go gaze.

## Testing Conventions

- **Framework**: pytest only. No unittest.TestCase style.
- **Assertions**: Use `assert` statements directly. No assertion helper libraries.
- **Test naming**: `test_xxx_description` (e.g., `test_formula_zero_coverage`, `test_returns_pure_function`).
- **Test files**: `tests/test_*.py` at the project root.
- **Test fixtures**: Sample Python packages in `tests/testdata/` directories.
- **Parametrize**: Use `@pytest.mark.parametrize` for table-driven tests.
- **Fixtures**: Use `@pytest.fixture` for shared setup. Prefer function-scoped fixtures.
- **Acceptance tests**: Named after spec success criteria (e.g., `test_sc001_comprehensive_detection`).
- **JSON Schema validation**: Tests validate JSON output against the shared JSON Schema (Draft 2020-12), ensuring parity with Go gaze.

## Core Principles

These principles (from the project constitution) guide all development:

1. **Accuracy**: gaze-py MUST correctly identify all observable side effects. False positives erode trust and MUST be treated as bugs. False negatives MUST be tracked, measured, and driven toward zero. Accuracy claims MUST be backed by automated regression tests.
2. **Minimal Assumptions**: gaze-py MUST operate with the fewest possible assumptions about the host project's test framework or coding style. No source annotation or restructuring required. When assumptions are unavoidable, they MUST be explicit and enforced.
3. **Actionable Output**: Every piece of output MUST guide the user toward a concrete improvement. Reports MUST identify specific test, target, and unasserted change. Output formats MUST support human-readable and machine-readable (JSON). Metrics MUST be comparable across runs.
4. **Testability**: Every function gaze-py analyzes, and every function within gaze-py itself, MUST be testable in isolation. Test contracts MUST verify observable side effects, not implementation details. Coverage strategy MUST be specified in plans for new code.

## Specification Workflow

All non-trivial changes MUST be preceded by a spec workflow. The constitution (`.specify/memory/constitution.md`) is the highest-authority document in this project — all work must align with it.

| Tier | Tool | When | Artifacts |
|------|------|------|-----------|
| Strategic | Speckit | >= 3 stories, cross-repo | `specs/NNN-*/` |
| Tactical | OpenSpec | < 3 stories, single-repo | `openspec/changes/*/` |

Pipeline: `constitution → specify → clarify → plan → tasks →
analyze → checklist → implement`

**Ordering**: Constitution before specs. Spec before plan. Plan before tasks. Tasks before implementation. Spec artifacts MUST be committed/pushed before implementation begins.

**Branches**: Speckit: `NNN-<name>`. OpenSpec: `opsx/<name>`.

**Task bookkeeping**: Mark checkboxes `[x]` immediately on completion. `[P]` marks parallel-eligible tasks.

**When in doubt**: Start with OpenSpec. Escalate to Speckit if scope grows beyond 3 stories or crosses repo boundaries.

**What requires a spec**: New features, refactoring that changes signatures, test additions across multiple functions, agent changes, CI changes, data model changes.

**Exempt**: Constitution amendments, typo fixes, emergency hotfixes (retroactively documented).

## Behavioral Rules

These rules are non-negotiable. Violations are CRITICAL severity.

- **Gatekeeping**: MUST NOT modify quality/governance gates
  (coverage thresholds, CRAP scores, severity definitions,
  CI flags, agent settings, constitution MUST rules, review
  limits, workflow markers). Stop and report instead.
- **Phase boundaries**: MUST NOT cross workflow phase boundaries.
  Spec phases: spec artifacts only. Implement: source code.
  Review: fixes only. Violation = process error, stop immediately.
- **CI parity**: MUST replicate CI checks locally before marking
  tasks complete. Derive commands from `.github/workflows/`.
- **Review council**: MUST run `/review-council` before PR
  submission. Resolve all REQUEST CHANGES. No code changes
  between APPROVE and PR. Exempt: constitution amendments,
  docs-only, emergency hotfixes.
- **Branch protection**: MUST NOT commit directly to `main`.
  All changes via feature branches and PRs.
- **Documentation gate**: Before marking a task complete,
  assess documentation impact: `CHANGELOG.md` for change
  entries, `AGENTS.md` for structural updates (project
  structure, conventions, build commands), `README.md` for
  description changes.
- **Website gate**: MUST file `unbound-force/website` issue
  for user-facing changes before PR merge. Exempt: internal
  refactoring, test-only, CI-only, spec artifacts.
- **Zero-waste**: No orphaned specs, unused standards, or
  aspirational documents that do not map to actionable work.

### PR Review Commands

| Command | When | Scope |
|---------|------|-------|
| `/review-council` | Pre-PR (local) | 5+ Divisor agents |
| `/review-pr [N]` | Post-PR (GitHub) | Single agent, CI analysis |

## Knowledge Retrieval

Prefer Dewey MCP tools over grep/glob/read for cross-repo
context and architectural patterns.

| Intent | Tool |
|--------|------|
| Conceptual | `dewey_semantic_search` |
| Keyword | `dewey_search` |
| Navigation | `dewey_traverse`, `dewey_get_page` |
| Discovery | `dewey_find_connections`, `dewey_similar` |

**Fallback**: Use Read/Grep/Glob when Dewey is unavailable,
for exact string matching, known file paths, or non-Markdown
content (Go source, JSON, YAML).

## Git & Workflow

- **Commit format**: Conventional Commits — `type: description` (e.g., `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
- **Code review**: Required before merge.
- **Semantic versioning**: For releases.

## CI/CD

GitHub Actions workflows:

1. **Test**: Build + test with `uv run pytest` on push/PR to `main`.
2. **MegaLinter**: Runs ruff, mypy, markdownlint, yamllint, and gitleaks on push/PR to `main`.
3. **Release**: Triggered on `v*` tag push. Builds and publishes to PyPI.

## JSON Schema Parity

gaze-py MUST produce JSON output that is schema-compatible with Go gaze. The shared JSON schemas (Draft 2020-12) define the contract between the two implementations. When adding new fields or types, update both implementations to maintain parity.

## Convention Packs

This repository uses convention packs scaffolded by
unbound-force. Agents MUST read the applicable pack(s)
before writing or reviewing code.

- `.opencode/uf/packs/default.md`
- `.opencode/uf/packs/default-custom.md`
- `.opencode/uf/packs/severity.md`
- `.opencode/uf/packs/content.md`
- `.opencode/uf/packs/content-custom.md`
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`
