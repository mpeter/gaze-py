## 1. Create Agent File

- [x] 1.1 Create `.opencode/agents/gazepy-test-generator.md` with YAML
  frontmatter (`mode: subagent`, `tools: read/bash/write/edit: true`,
  `description`) and the `<!-- scaffolded by gazepy 0.4.0 -->` comment.
- [x] 1.2 Write the Role section — Python-native equivalent of the Go agent's
  role description, referencing `gazepy quality --format=json` and pytest.
- [x] 1.3 Write the Input section — five inputs: source code, fix strategy,
  contract coverage data fields (Gaps, GapHints, DiscardedReturns,
  AmbiguousEffects, UnmappedAssertions, ContractCoverageReason,
  EffectConfidenceRange), existing test file, CRAP score data.
- [x] 1.4 Write the Actions section — all six actions translated to Python
  (per D-002 translation table): `add_tests` (plain `assert`,
  `pytest.raises`, `pytest.approx`, `@pytest.mark.parametrize`),
  `add_assertions`, `add_docs` (Google-style docstrings + type hints,
  CS-004; apply when confidence 58–69; Do NOT apply below 58),
  `decompose_and_test` (`@pytest.mark.skip` skeleton with `# TODO: assert
  <EffectType>` comments), `decompose` (skip with message), `verify`
  (`gazepy quality --format=json`, before/after delta).
- [x] 1.5 Write the Convention Detection section — detect `@pytest.fixture`,
  `conftest.py`, `tmp_path`, inline setup; defaults to plain functions and
  `tmp_path`; naming pattern `test_<function>_<scenario>`.
- [x] 1.6 Write the Quality Criteria section — specific values not just
  truthiness; `pytest.raises` for error paths; AST-only isolation (never
  import or execute testdata fixtures).
- [x] 1.7 Write the Output Format section — action taken, generated code, file
  target (`tests/test_<module>.py`), verification command
  (`uv run pytest --tb=short -k <test_name>`), summary.
- [x] 1.8 Write the Important Constraints section — NEVER unittest; ALWAYS read
  function source first; ALWAYS read existing tests first; ALWAYS verify with
  `uv run pytest --tb=short`; append-only to existing files.

## 2. CI Gate

- [x] 2.1 Run `uv run pytest -m "not slow"` and confirm no regressions (agent
  file is Markdown; no Python code changes, no coverage delta expected).
- [x] 2.2 Confirm `uv run ruff check . && uv run ruff format --check .` passes
  (Markdown file is not linted; existing Python unchanged).
- [x] 2.3 Confirm `uv run mypy src/` passes (no Python source changes).
- [x] 2.4 Confirm `uv run gazepy --help` exits 0 (smoke-test: `gazepy` binary
  is functional and CLI signature is intact).
