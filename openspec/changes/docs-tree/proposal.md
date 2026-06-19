## Why

gaze-py ships no user-facing documentation. AGENTS.md references a `release.yml` that already exists, but the docs tree is absent — a first-time user has no install guide, no concept overview, and no CLI reference to work from. The Go sibling has a full docs tree; gaze-py should mirror it, adapted for Python specifics.

## What Changes

- Add `docs/` tree with the following structure, adapted from Go gaze:
  - `docs/index.md` — overview and navigation
  - `docs/concepts/side-effects.md` — 38-type taxonomy, P0–P4 tiers (Python AST detection status)
  - `docs/concepts/scoring.md` — CRAP and GazeCRAP formulas
  - `docs/getting-started/installation.md` — `uv`, `pip`, and global install via `uv tool`
  - `docs/getting-started/quickstart.md` — first run, interpret output
  - `docs/reference/cli/analyze.md` — `gazepy analyze` reference
  - `docs/reference/cli/crap.md` — `gazepy crap` reference
  - `docs/reference/cli/docscan.md` — `gazepy docscan` reference
  - `docs/reference/cli/init.md` — `gazepy init` reference
  - `docs/reference/cli/quality.md` — `gazepy quality` reference
  - `docs/reference/cli/report.md` — `gazepy report` reference
  - `docs/reference/cli/schema.md` — `gazepy schema` reference
  - `docs/reference/cli/self-check.md` — `gazepy self-check` reference
  - `docs/reference/configuration.md` — `.gaze.yaml` reference
  - `docs/reference/glossary.md` — canonical term definitions

Note: `release.yml` already exists and is complete. No changes needed there.

## Capabilities

### New Capabilities

- `docs-tree`: User-facing documentation covering installation, concepts (taxonomy + scoring), and full CLI reference — adapted from Go gaze docs but accurate for Python AST-only detection

### Modified Capabilities

<!-- none — this is a docs-only addition, no existing specs change -->

## Impact

- New: `docs/` directory (15 markdown files)
- No source code changes
- No test changes
- No CI changes (`release.yml` and `test.yml` are unchanged)
- `README.md` should gain a link to the docs tree once it exists (out of scope for this change — tracked separately)
