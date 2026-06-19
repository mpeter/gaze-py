## 1. Root and concepts

- [x] 1.1 Create `docs/index.md` — intro paragraph, command list with one-liners, navigation links to concepts/getting-started/reference
- [x] 1.2 Create `docs/concepts/side-effects.md` — why side effects matter, 38-type taxonomy table grouped by tier with Python AST detection status per type
- [x] 1.3 Create `docs/concepts/scoring.md` — CRAP formula, GazeCRAP formula, CRAPload definition, how to read scores

## 2. Getting started

- [x] 2.1 Create `docs/getting-started/installation.md` — `uv tool install gaze-py`, `pip install gaze-py`, from-source via `uv sync`, version verification
- [x] 2.2 Create `docs/getting-started/quickstart.md` — first run with `gazepy crap` on a sample file, annotated text output, pointers to next steps

## 3. CLI reference

- [x] 3.1 Create `docs/reference/cli/analyze.md` — synopsis, description, options table, output format, example
- [x] 3.2 Create `docs/reference/cli/crap.md` — synopsis, description, options table (note --baseline stub), output format, example
- [x] 3.3 Create `docs/reference/cli/docscan.md` — synopsis, description, options table, output format, example
- [x] 3.4 Create `docs/reference/cli/init.md` — synopsis, description, created files table (user-owned vs. tool-owned), options table, example
- [x] 3.5 Create `docs/reference/cli/quality.md` — synopsis, description, options table, output format, example
- [x] 3.6 Create `docs/reference/cli/report.md` — synopsis, description, options table (note --ai requires O1+O2), output format, example
- [x] 3.7 Create `docs/reference/cli/schema.md` — synopsis, description, example output snippet
- [x] 3.8 Create `docs/reference/cli/self-check.md` — synopsis, description, options table, when to use, example

## 4. Reference

- [x] 4.1 Create `docs/reference/configuration.md` — all 7 GazeConfig keys (contractual_threshold, incidental_threshold, crap_threshold, gaze_crap_threshold, doc_scan_exclude, doc_scan_include, doc_scan_timeout) with type, default, valid range, and effect
- [x] 4.2 Create `docs/reference/glossary.md` — side effect, contractual effect, incidental effect, CRAP score, GazeCRAP score, CRAPload, contract coverage, tier (P0–P4), AST analysis
