## ADDED Requirements

### Requirement: Agent file exists and is loadable as a subagent
The system SHALL provide `.opencode/agents/gazepy-test-generator.md` with valid YAML frontmatter (`mode: subagent`, `tools: read/bash/write/edit: true`) so OpenCode can invoke it as a subagent.

#### Scenario: Frontmatter is valid
- **WHEN** the agent file is read
- **THEN** frontmatter contains `mode: subagent` and all four tool flags set to `true`

#### Scenario: Version marker present
- **WHEN** the agent file is read
- **THEN** an HTML comment `<!-- scaffolded by gazepy 0.4.0 -->` appears below the frontmatter

### Requirement: add_tests action generates runnable pytest functions
The agent SHALL, when fix_strategy is `add_tests`, generate a `def test_<function>_<scenario>(...)` function with plain `assert` statements for each Gap and `pytest.raises(ExceptionType, match="...")` for error paths.

#### Scenario: Gap produces assert statement
- **WHEN** the GapHints array is non-empty
- **THEN** each hint is translated to a corresponding `assert` expression targeting the function's return value or side effect

#### Scenario: Error path produces pytest.raises
- **WHEN** a Gap corresponds to an exception-raising path
- **THEN** the generated test uses `pytest.raises(ExceptionType, match="...")`

#### Scenario: Float comparison uses pytest.approx
- **WHEN** a Gap involves a float return value
- **THEN** the generated assertion uses `pytest.approx(value, rel=1e-3)`

### Requirement: add_assertions action strengthens existing tests
The agent SHALL, when fix_strategy is `add_assertions`, insert missing assert statements into existing `test_*.py` files without deleting or modifying existing test content.

#### Scenario: Assertions appended near call site
- **WHEN** an existing test calls the target function but lacks contract assertions
- **THEN** the agent inserts assertions immediately after the call site, preserving all existing content

### Requirement: add_docs action improves Python docstrings
The agent SHALL, when ContractCoverageReason is `all_effects_ambiguous` and EffectConfidenceRange is near threshold, add or improve Google-style docstrings and type hints on the target function.

#### Scenario: Docstring describes observable effects
- **WHEN** the function has side effects that are ambiguous to the classifier
- **THEN** the generated docstring names each effect (Returns:, raises, mutates) in Google-style format per CS-004

#### Scenario: Type hints added
- **WHEN** the function lacks type annotations
- **THEN** the agent adds parameter and return type hints compatible with `mypy --strict`

### Requirement: decompose_and_test action generates skip skeleton
The agent SHALL, when fix_strategy is `decompose_and_test`, generate a `@pytest.mark.skip(reason="TODO: decompose <function> (complexity N) before testing")` test skeleton with TODO comments for each Gap.

#### Scenario: Skip decorator present
- **WHEN** fix_strategy is decompose_and_test
- **THEN** generated function is decorated with `@pytest.mark.skip` and the reason contains the function name and complexity

#### Scenario: TODO comments for each Gap
- **WHEN** Gaps array is non-empty
- **THEN** each Gap produces one `# TODO: assert <EffectType> — hint: ...` comment inside the skeleton

### Requirement: decompose action skips with message
The agent SHALL, when fix_strategy is `decompose`, emit a human-readable skip message and generate no test code.

#### Scenario: Skip message emitted
- **WHEN** fix_strategy is decompose
- **THEN** the agent reports "Skipped <function> — fix strategy is `decompose` (complexity N). Reduce complexity first, then generate tests."

### Requirement: verify action measures coverage improvement
The agent SHALL, when action is `verify`, run `gazepy quality --format=json <package>` and compare before/after ContractCoverage.Percentage for the target function.

#### Scenario: Coverage improved
- **WHEN** post-generation quality JSON shows higher coverage
- **THEN** agent reports "Contract coverage: X% → Y% (+Z%)"

#### Scenario: Coverage unchanged
- **WHEN** post-generation quality JSON shows same coverage
- **THEN** agent reports "Contract coverage unchanged at X% — review generated assertions for mapping to the function's side effects"

### Requirement: Convention detection defaults to tmp_path
The agent SHALL read existing `tests/test_*.py` and `conftest.py` before generating code, and default to `tmp_path` fixture and plain functions (no conftest dependency) when no conftest is found.

#### Scenario: conftest.py absent — default fixtures used
- **WHEN** no `conftest.py` exists in the tests directory
- **THEN** generated tests use `tmp_path` for filesystem access and plain function bodies without custom fixture dependencies

#### Scenario: conftest.py present — fixtures detected
- **WHEN** `conftest.py` exists
- **THEN** generated tests may reference detected fixtures from that file

### Requirement: AST-only constraint enforced
The agent's Quality Criteria section SHALL explicitly state that generated tests MUST NOT import or execute the analyzed module — analysis is AST-only.

#### Scenario: No module import in generated tests
- **WHEN** the agent generates test code
- **THEN** no generated code contains a dynamic import of the analyzed module via `importlib` or `__import__`

### Requirement: Testdata isolation rule documented
The agent SHALL document that if generated tests require source fixture files for AST analysis, those files go under `tests/testdata/`, never under `tests/`, and are never imported by test modules.

#### Scenario: Fixture files placed in testdata
- **WHEN** the agent creates an AST input fixture
- **THEN** the file path is under `tests/testdata/`, not `tests/`

### Requirement: Verification uses correct command
The agent's verify action SHALL use `uv run pytest --tb=short -k test_<generated_name>` to run generated tests, not `go test`.

#### Scenario: Pytest command used for verification
- **WHEN** the agent verifies generated tests
- **THEN** it runs `uv run pytest --tb=short -k <test_name>` and reports pass/fail
