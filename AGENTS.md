# AGENTS.md

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->

## Project Overview

gaze-py is the Python-native companion to [gaze](https://github.com/unbound-force/gaze),
the Go implementation of the GazeCRAP analysis engine. It detects observable
side effects in Python functions using AST-only analysis, classifies them as
contractual or incidental, and computes CRAP and GazeCRAP scores.

- **Language**: Python 3.11+
- **Package**: `gaze-py` (PyPI name); `gaze_py` (import path)
- **Binary**: `gazepy`
- **License**: Apache 2.0
- **Layout**: `src/` layout — all source under `src/gaze_py/`, tests under `tests/`
- **Porting authority**: `../gaze/docs/porting/` — contracts.md, requirements.md,
  taxonomy-reference.md are the authoritative ground truth for what to implement

## Core Mission

gaze-py is a **port**, not an independent tool. Schema compatibility with the Go
gaze implementation is a first-class requirement. The 48-type effect taxonomy,
JSON field names, scoring formulas, and quadrant rules are fixed by the porting
contracts and MUST NOT be invented or reinterpreted. The EC-001 tier table
totals 48 (P0=6 + P1=11 + P2=16 + P3=9 + P4=6). Tests MUST assert 48. Ten of
the 48 are marked "Defined" in taxonomy-reference.md — specified in the
taxonomy but not yet detected by the reference Go implementation. Definitions
are mandatory; detection of "Defined" types follows the reference.

## Behavioral Constraints

- **Zero-Waste Mandate**: No orphaned code, unused imports, stub functions that
  silently return wrong values. Every function either works or raises explicitly.
- **Porting Contracts First**: Before writing any spec or code, read
  `../gaze/docs/porting/contracts.md`, `requirements.md`, and
  `taxonomy-reference.md`. Any element that contradicts a porting contract
  MUST be revised — the contract wins.
- **AST-Only**: Analysis MUST use Python's `ast` module. No execution of
  analyzed code, no import of analyzed modules, no runtime introspection.
- **Null Not Zero**: Fields that depend on optional capabilities MUST be
  `None`/`null` when the capability has not run — not `0.0` or `""`. Per
  porting contract OC-003.
- **No Placeholder Output**: Never emit `"test.py:?"` or `"<unknown>"` in
  production JSON. Unavailable fields serialize as `null`.

### Gatekeeping Value Protection

Agents MUST NOT modify values that serve as quality or governance gates to
make an implementation pass. The following are protected:

1. **Coverage thresholds** — `--cov-fail-under=85` in CI is a floor, not a
   target. Never lower it to make a PR pass.
2. **Porting contract IDs** — EC-001 through OC-003 in test names and comments
   are traceability markers. Never remove or rename them.
3. **Effect taxonomy** — The 48 `SideEffectType` values and their P0–P4 tier
   assignments are fixed by EC-001. Never add, remove, or reclassify them
   without a constitution amendment.

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

Skills provide specialized instructions and workflows for specific tasks.
Use the skill tool to load a skill when a task matches its description.

## Project Structure

```text
gaze-py/
├── src/gaze_py/          # All package source (src/ layout)
│   ├── __init__.py       # __version__ only
│   ├── taxonomy/         # Domain types: SideEffect, FunctionTarget, etc.
│   ├── analysis/         # AST side-effect detection engine
│   ├── quality/          # Assertion mapper, contract coverage
│   ├── crap/             # CRAP and GazeCRAP scoring formulas
│   ├── classify/         # Classification engine (ABC interface)
│   ├── config/           # .gaze.yaml configuration loading
│   ├── report/           # JSON and text formatters, JSON schemas
│   └── cli/              # Click command group (gazepy entrypoint)
├── tests/
│   ├── test_*.py         # Real tests (pytest collects these)
│   └── testdata/         # Static source fixtures for AST analysis
│       ├── analysis/     # Fixture source files for effect detection
│       └── quality/      # Fixture test files for assertion mapping
├── specs/                # Speckit strategic specs
├── openspec/             # OpenSpec tactical changes
├── .specify/             # Speckit configuration and templates
│   └── memory/
│       └── constitution.md  # Highest-authority governance document
├── .opencode/            # OpenCode agents, commands, skills, packs
├── pyproject.toml        # Build config, ruff/mypy/pytest settings
└── AGENTS.md             # This file
```

## Build & Test Commands

```bash
# Install dependencies
uv sync

# Run tests (fast — excludes slow)
uv run pytest -m "not slow"

# Full CI gate
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest --cov=gaze_py --cov-fail-under=85

# Run the CLI
uv run gazepy --help
uv run gazepy analyze src/gaze_py/ --format=text
uv run gazepy report src/gaze_py/ tests/ --format=json

# Build wheel
uv build

# Install globally
uv tool install --force dist/gaze_py-*.whl
```

## Technology Stack

- **Language**: Python 3.11+
- **Package manager**: `uv` (lockfile committed; `uv sync` to install)
- **Build tool**: `hatchling` (via `pyproject.toml`)
- **Key runtime dependencies**:
  - `click` — CLI framework (`gazepy` entrypoint)
  - `pyyaml` — `.gaze.yaml` configuration loading
  - `astroid` — AST inference for transitive call-graph pairing (quality pipeline)
- **Linter / formatter**: `ruff` (check + format), `mypy --strict`
- **Test runner**: `pytest` with `pytest-cov` (`--cov-fail-under=85`)
- **CI**: `.github/workflows/test.yml` (matrix: 3.11, 3.12, 3.13 on ubuntu-24.04),
  `.github/workflows/release.yml` (trusted PyPI publish via OIDC)

## Specification Workflow

All changes to production code, tests, agents, or CI MUST be preceded by a spec:

- **Strategic** (multiple stories, cross-repo): Speckit pipeline under `specs/`
  → `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`
- **Tactical** (single story, this repo only): OpenSpec pipeline under `openspec/changes/`
  → `/opsx-propose` → `/opsx-apply` → `/opsx-archive`

Exempt: constitution amendments, typo fixes, emergency hotfixes (retroactively documented).

**Before any spec**: Read `../gaze/docs/porting/contracts.md`,
`requirements.md`, and `taxonomy-reference.md`. Spec review includes a
porting contract alignment check (constitution Principle V).

## Review and Merge Gates

1. **Convention pack compliance**: All code MUST pass `ruff check`, `ruff format --check`, `mypy --strict`
2. **Test gate**: `pytest --cov-fail-under=85` MUST pass
3. **Review Council**: Run `/review-council` before any PR. All Divisor reviewers (Adversary, Architect, Guard, Tester) MUST APPROVE. Resolve all REQUEST CHANGES before submitting.
4. **CI**: GitHub Actions (`test.yml`) must be green before merge
5. **Direct commits to `main` are prohibited** — all work on feature branches

## Branch Protection

- `main` — protected; no direct commits
- `opsx/<name>` — OpenSpec tactical changes
- `NNN-<feature-name>` — Speckit strategic features

## Testdata Fixtures

Files under `tests/testdata/` are static source fixtures for the AST engine.
They MUST NOT import from `tests.*`, have `__init__.py` files, or be collected
by pytest. `pyproject.toml` enforces `norecursedirs = ["tests/testdata"]`.
See convention pack rule CR-002.
