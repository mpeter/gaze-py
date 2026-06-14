# Proposal: o3-docscan

## Summary

Implement O3: Document Scanning. Makes `gazepy docscan` a real command and
wires document content into Signal 5 (Documentation) of the classification
engine, augmenting per-function docstring signals with project-wide behavioral
declarations from `.md` files.

## Motivation

`gazepy docscan` currently exits 1 with "requires O3". The porting contract
`requirements.md` defines O3 as scanning project documentation files for
behavioral declarations that contribute to the documentation signal (CC-005,
Signal 5). This improves classification accuracy when functions lack docstrings
but are described in README or architecture docs.

## Scope

**In scope:**
- New `src/gaze_py/analysis/docscan.py` — scanner module (`DocEntry`, `scan_docs()`)
- `src/gaze_py/config/loader.py` — add `doc_scan_exclude`, `doc_scan_include`,
  `doc_scan_timeout` to `GazeConfig`
- `src/gaze_py/classify/engine.py` — `ClassificationEngine` accepts optional
  `project_docs_text: str | None`; passes combined text to Signal 5
- `src/gaze_py/analysis/runner.py` — `detect_and_classify()` optionally accepts
  and passes `docs_text`
- `src/gaze_py/cli/main.py` — replace `docscan` stub; wire doc scanning into
  `analyze` and `crap` commands
- Tests and testdata fixtures

**Out of scope:**
- AI report integration (O2)
- Signal weights or taxonomy changes
- Timeout enforcement with SIGALRM (Linux-only; use threading instead)

## Acceptance Criteria

1. `gazepy docscan [PATH]` exits 0 and emits a JSON array of
   `{path, content, priority}` objects (or text summary with `--format=text`)
2. Priority assignment: same directory as source = 1, repo root = 2, other = 3
3. Default exclude globs match Go reference: vendor/**, node_modules/**, .git/**,
   testdata/**, CHANGELOG.md, CONTRIBUTING.md
4. `GazeConfig` supports `classification.doc_scan.exclude/include/timeout`
5. When `gazepy analyze` or `gazepy crap` runs, doc content is passed to
   `docstring_signal()` augmenting per-function classification
6. All existing tests continue to pass; `pytest --cov-fail-under=85` passes
7. `ruff check`, `ruff format --check`, `mypy --strict` all pass
