## 1. Agent File Creation

- [x] 1.1 Read `.opencode/agents/gaze-test-generator.md` as structural reference
- [x] 1.2 Create `.opencode/agents/gazepy-test-generator.md` with valid YAML frontmatter (`mode: subagent`, `tools: read/bash/write/edit: true`) and version marker `<!-- scaffolded by gazepy 0.4.0 -->`
- [x] 1.3 Write the description field: "Test generation agent for Python projects. Consumes gazepy quality data (GapHints, Gaps, FixStrategy, AmbiguousEffects) to generate complete, runnable pytest test functions, improve documentation for classifier visibility, and restructure assertions for mapper accuracy. Works on any Python project gazepy can analyze."

## 2. Input Section

- [x] 2.1 Write the Input section describing the five inputs (source code, fix strategy, contract coverage data from `gazepy quality --format=json`, existing test file, CRAP score data)

## 3. Actions — Six Fix Strategies

- [x] 3.1 Write Action 1 `add_tests`: pytest function template with plain `assert`, `pytest.raises(ExceptionType, match="...")` for error paths, `pytest.approx(value, rel=1e-3)` for floats, table-driven via `@pytest.mark.parametrize`
- [x] 3.2 Write Action 2 `add_assertions`: insert missing asserts into existing test files; restructure for mapper visibility (direct assert on return value, not through helper)
- [x] 3.3 Write Action 3 `add_docs`: improve Google-style docstrings (CS-004) and type hints when ContractCoverageReason is `all_effects_ambiguous` and confidence near threshold; do NOT apply below threshold
- [x] 3.4 Write Action 4 `decompose_and_test`: generate `@pytest.mark.skip(reason="TODO: decompose <function> (complexity N) before testing")` skeleton with `# TODO: assert <EffectType>` comments per Gap
- [x] 3.5 Write Action 5 `decompose`: skip with message "Skipped <function> — fix strategy is `decompose` (complexity N). Reduce complexity first, then generate tests."
- [x] 3.6 Write Action 6 `verify`: run `gazepy quality --format=json <package>`, compare before/after ContractCoverage.Percentage, report delta

## 4. Convention Detection Section

- [x] 4.1 Write convention detection: read `tests/test_*.py` and `conftest.py`; detect `@pytest.fixture`, fixture names, parametrize style, naming pattern; default to `tmp_path` and plain functions if no conftest found

## 5. Quality Criteria Section

- [x] 5.1 Write Quality Criteria: assert specific values not just truthiness; `pytest.raises` for error paths; `pytest.approx` for floats; never import analyzed modules (AST-only rule); no shared mutable state; no external network/FS outside repo; each assertion maps to a specific Gap

## 6. Output Format and Constraints Sections

- [x] 6.1 Write Output Format: action taken, generated code, file target (`tests/test_*.py`), verification command (`uv run pytest --tb=short -k test_<name>`)
- [x] 6.2 Write Important Constraints: testdata isolation (AST fixture files → `tests/testdata/`, never imported); never import analyzed modules; always read function source before generating; always read existing tests before adding assertions; append-only to existing files

<!-- spec-review: passed -->
<!-- code-review: passed -->
