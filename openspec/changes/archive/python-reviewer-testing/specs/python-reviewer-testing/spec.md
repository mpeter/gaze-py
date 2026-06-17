## ADDED Requirements

### Requirement: Python-aware Code Review Mode checklist

The agent SHALL audit test files using Python/pytest conventions throughout its Code Review Mode checklist. All six checklist sections SHALL reference Python tooling, naming conventions, and isolation rules specific to gaze-py.

#### Scenario: Test Architecture section uses Python conventions

- **WHEN** the agent reviews a change that adds or modifies test files
- **THEN** it checks for `tests/test_*.py` file naming, `@pytest.mark.parametrize` for table-driven tests, `tests/testdata/` static fixture usage (no `__init__.py`, not collected by pytest per `norecursedirs`), `pytest`-only framework (no testify/gomega equivalents), `test_<function>_<scenario>` naming, and tests located under `tests/` directory

#### Scenario: Assertion Depth section uses Python constructs

- **WHEN** the agent reviews assertions in test files
- **THEN** it checks for plain `assert` statements and `pytest.raises`, and flags use of any third-party assertion libraries

#### Scenario: Test Isolation section includes AST fixture rule

- **WHEN** the agent reviews test isolation
- **THEN** it flags any test that imports from `tests/testdata/`, because testdata fixtures are parsed as AST and MUST NOT be executed or imported

#### Scenario: Convention Compliance section uses Python toolchain

- **WHEN** the agent reviews convention compliance
- **THEN** it references `uv run pytest -x --tb=short` as the local run command, `@pytest.mark.slow` for slow test guards, `uv run ruff check` and `uv run mypy --strict src/` as the static analysis gates, and the AST-only isolation rule

### Requirement: Python-aware Spec Review Mode checklist

The agent SHALL audit SpecKit artifacts using Python/pytest conventions throughout its Spec Review Mode checklist. Section 6 (Constitution Alignment) SHALL reference `.specify/memory/constitution.md` and Principle IV (Testability) in Python context.

#### Scenario: Constitution Alignment section references Python constitution

- **WHEN** the agent reviews a spec for constitution alignment
- **THEN** it verifies compliance with `.specify/memory/constitution.md` Principle IV (Testability), checking that functions are testable in isolation, coverage strategy is specified, and conformance test IDs reference porting contract IDs (EC-001, CC-001, SC-001, etc.)

### Requirement: Source Documents updated for Python context

The agent SHALL instruct reviewers to read Python-specific source documents before reviewing: `AGENTS.md`, `.specify/memory/constitution.md`, `.opencode/uf/packs/python.md`, and `python-custom.md`.

#### Scenario: Agent reads Python convention packs before reviewing

- **WHEN** the agent is invoked in either review mode
- **THEN** it reads all four source documents listed, including both Python convention packs, before evaluating any checklist item

### Requirement: Version marker updated

The agent file SHALL carry the version marker `<!-- scaffolded by gazepy 0.4.0 -->` immediately below the frontmatter delimiter.

#### Scenario: Version marker identifies correct tool version

- **WHEN** the agent file is inspected
- **THEN** the first non-frontmatter line reads `<!-- scaffolded by gazepy 0.4.0 -->` (not `gaze v1.5.0`)
