## Context

`.opencode/agents/reviewer-testing.md` is the Tester divisor agent — invoked by the review council to audit tests and specs for quality, coverage, and convention compliance. The current file is a verbatim transplant from the Go gaze v1.5.0 agent template. It contains at least eight Go-specific references that are meaningless or incorrect in the Python/pytest context of gaze-py:

| Go reference | Problem |
|---|---|
| `*_test.go` | Python test files are `tests/test_*.py` |
| `testdata/src/` loaded via `go/packages` | gaze-py uses `tests/testdata/` static `.py` fixtures parsed via `ast`; `go/packages` doesn't exist |
| Standard `testing` package | gaze-py uses `pytest` exclusively (TC-001) |
| `TestXxx_Description` naming | gaze-py uses `test_<function>_<scenario>` (TC-003) |
| `TestSC001_ComprehensiveDetection` | Python acceptance tests are `test_ec001_taxonomy_count` style |
| `t.Errorf` / `t.Fatalf` | gaze-py uses plain `assert` and `pytest.raises` (TC-002) |
| `-race -count=1` | gaze-py runs `uv run pytest -x --tb=short` |
| `testing.Short()` | gaze-py uses `@pytest.mark.slow` (TC-010) |
| 80-column output width check | Not applicable to gaze-py |
| `go build` | gaze-py uses `uv run ruff check` + `uv run mypy --strict src/` |
| Benchmarks in `bench_test.go` | No benchmark convention in gaze-py |

The frontmatter is correct and must remain unchanged.

## Goals / Non-Goals

**Goals:**

- Replace all Go-specific content in both review modes with Python/pytest equivalents.
- Keep the dual-mode structure, 6-section checklists, severity levels, output format, and verdict mechanism exactly as designed.
- Add gaze-py-specific rules absent from the Go template: CR-002 testdata isolation, TC-005 parametrize-over-loops, TC-011 norecursedirs, AST-only isolation constraint, JSON schema validation tests.
- Update version marker to `gazepy 0.4.0`.
- The resulting agent must be immediately usable without further edits by any future review-council session.

**Non-Goals:**

- Do not change the YAML frontmatter (mode, model, temperature, tools).
- Do not restructure the checklist (section count, section numbering, or ordering must remain identical).
- Do not add new sections beyond what the Go template has.
- Do not modify any production Python source files, tests, or CI configuration.

## Decisions

### Decision 1: Full body replacement, not patch

**Chosen**: Replace the entire file body below the frontmatter delimiter.

**Alternative**: Patch individual lines in-place.

**Rationale**: The Go-to-Python translation touches every section of both review modes. An in-place patch would require tracking 15+ surgical edits across a 170-line file with high risk of leaving residual Go references. A clean replacement from a known-correct template eliminates all residual content.

### Decision 2: Frontmatter preserved exactly

**Chosen**: Copy all six frontmatter fields verbatim from the existing file.

**Rationale**: The frontmatter controls agent invocation semantics (subagent mode, model, temperature, no write/edit/bash tools). Any accidental change would alter review council behavior. No frontmatter content is Go-specific.

### Decision 3: Go → Python translation mapping

Complete mapping used during implementation:

| Go content | Python replacement |
|---|---|
| Role description | gaze-py Python-native port; AST-only static analysis; five-signal confidence engine; CRAP and GazeCRAP scores |
| Source Documents | AGENTS.md, `.specify/memory/constitution.md`, `.opencode/uf/packs/python.md`, `python-custom.md` |
| Review Scope (code) | `tests/test_*.py` and production code under `src/gaze_py/` |
| Test Architecture | `@pytest.mark.parametrize`; `tests/testdata/` static `.py` fixtures; `pytest` only; `test_<function>_<scenario>` names; tests under `tests/` directory; no benchmark convention |
| Coverage Strategy | `test_ec001_taxonomy_count` acceptance naming |
| Assertion Depth | plain `assert`, `pytest.raises`; no third-party assertion libraries |
| Test Isolation | Add: "Tests MUST NOT import from `tests/testdata/` — fixtures are analyzed via AST, never executed" |
| Regression Protection | Add: "JSON schema validation tests for `gazepy schema` output" |
| Convention Compliance | `uv run pytest -x --tb=short`; `@pytest.mark.slow`; remove 80-column check; `uv run ruff check` + `uv run mypy --strict src/`; add AST-only isolation rule |
| Spec Review — Constitution | `.specify/memory/constitution.md`; Principle IV (Testability) in Python context |
| Version marker | `<!-- scaffolded by gazepy 0.4.0 -->` |

### Decision 4: No new sections

The Go template's six-section structure is the established review council contract. Adding sections would change the review surface area and require corresponding updates to the other divisor agents. Out of scope for this change.

## Risks / Trade-offs

- **Risk**: A future Go-template update could make this file diverge silently.
  **Mitigation**: The version marker `<!-- scaffolded by gazepy 0.4.0 -->` makes the derivation explicit. Any future sync should be intentional.

- **Risk**: A missed Go reference survives the replacement.
  **Mitigation**: The code review council (all 5 divisors in Code Review Mode) runs against the final file before commit. Any residual Go term will be flagged.

## Open Questions

None. The translation mapping is fully defined above and all decisions are resolved.
