## Context

gaze-py provides `gazepy quality --format=json` which emits per-function quality data: GapHints, Gaps, FixStrategy, AmbiguousEffects, ContractCoverageReason, EffectConfidenceRange, CRAP/GazeCRAP scores, and quadrant. The Go implementation ships a companion agent (`gaze-test-generator.md`) that a developer invokes as a subagent to turn that JSON into complete, compilable Go test files. Python projects have no equivalent.

The agent lives entirely in `.opencode/agents/` — it is an instruction document for an AI subagent, not production code. It does not modify `src/gaze_py/` or `tests/`.

## Goals / Non-Goals

**Goals:**
- Produce a drop-in Python equivalent of `gaze-test-generator.md` adapted for pytest conventions.
- Support all six fix strategies: `add_tests`, `add_assertions`, `add_docs`, `decompose_and_test`, `decompose`, `verify`.
- Emit pytest-idiomatic code: `def test_<fn>_<scenario>`, plain `assert`, `pytest.raises`, `pytest.approx`, `@pytest.mark.skip`.
- Respect AST-only rule: generated tests MUST NOT import or execute the analyzed module dynamically.
- Testdata isolation: AST fixture files go under `tests/testdata/`, never imported by tests.
- Convention detection: read existing `tests/test_*.py` and `conftest.py` before generating; default to `tmp_path` fixture and plain functions.

**Non-Goals:**
- Does not modify production source, test files, pyproject.toml, or CI workflows.
- Does not introduce new runtime dependencies.
- Does not replace the existing `gaze-test-generator.md` for Go projects.
- Does not run `gazepy` itself — that is the caller's responsibility; the agent reads JSON already provided.

## Decisions

**Decision 1: File-only change (agent markdown)**
Rationale: The entire feature is an instruction document for an AI subagent. No Python module, no CLI flag, no import surface. This minimizes blast radius and avoids CI changes.

Alternatives considered: Adding a `gazepy gen-tests` CLI command. Rejected — premature; the agent approach proves value first with zero production risk.

**Decision 2: Structural port of gaze-test-generator.md**
The Go agent's six-section structure (Input, Actions 1-6, Convention Detection, Quality Criteria, Output Format, Important Constraints) translates cleanly to Python. Retaining the same section order makes diffs easy to audit.

**Decision 3: pytest over unittest**
The project already uses pytest (pyproject.toml). `pytest.raises` and `pytest.approx` are significantly more readable than `unittest.assertRaises` and `assertAlmostEqual`. No external assertion library (no testify equivalent) — plain `assert` with `pytest.raises` for errors.

**Decision 4: Google-style docstrings for add_docs**
CS-004 in the convention packs mandates Google-style docstrings. The `add_docs` action improves docstrings and type hints to feed the classifier's docstring signal (mirrors GoDoc in the Go agent).

**Decision 5: Version marker as HTML comment**
`<!-- scaffolded by gazepy 0.4.0 -->` matches the pattern already used in `.opencode/commands/*.md` headers. Non-intrusive and machine-parseable.

## Risks / Trade-offs

- [Risk] Generated tests may reference internal module symbols unavailable at test time → Mitigation: Quality Criteria section explicitly prohibits importing analyzed modules; agent MUST read function source first.
- [Risk] Convention detection may miss project-specific fixtures → Mitigation: Explicit fallback defaults (tmp_path, plain functions) documented in the agent; agent reads conftest.py if present.
- [Risk] Agent content drift from gaze-test-generator.md over time → Mitigation: Version marker and structural parity make diff-based review straightforward.
