## Why

Constitution Principle VII (Supply Chain Integrity) requires SHA pins to be
kept current via automated tooling, but no Dependabot or Renovate
configuration exists. The `astroid` dependency is pinned with no upper bound
(`>=3.0`), creating silent breakage risk on major version bumps. The release
workflow's smoke test emits a warning on failure instead of failing the
workflow, meaning a broken PyPI publish can appear successful.

These were identified as HIGH findings by the SRE reviewer during the review
council Iteration 1.

## What Changes

- Create `.github/dependabot.yml` with `github-actions` and `pip` ecosystems
  (weekly schedule)
- Tighten astroid pin in `pyproject.toml` from `>=3.0` to `>=3.0,<5`
- Change the release workflow smoke test fallback from `echo "::warning::..."`
  to `exit 1` so failures are visible in workflow status

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this change modifies CI configuration and dependency metadata only,
not production capabilities.

## Impact

- `.github/dependabot.yml` — new file
- `pyproject.toml` — tighten astroid version constraint
- `.github/workflows/release.yml` — smoke test exit code change
- `uv.lock` — regenerated after `pyproject.toml` change (no functional diff
  expected since the current pinned version 4.1.2 satisfies both constraints)

## Constitution Alignment

Assessed against `.specify/memory/constitution.md` (v1.1.3).

### I. Accuracy

**Assessment**: PASS — no detection or analysis changes.

### II. Minimal Assumptions

**Assessment**: PASS — no runtime changes.

### III. Actionable Output

**Assessment**: PASS — no output schema changes.

### IV. Testability

**Assessment**: PASS — no production code changes. CI gate unchanged.

### V. Porting Contract Supremacy

**Assessment**: PASS — no porting contracts affected.

### VI. Composability First

**Assessment**: PASS — no new dependencies. Tightening astroid's upper bound
does not remove functionality.

### VII. Supply Chain Integrity

**Assessment**: PASS — this change directly satisfies VII's requirement for
automated dependency update tooling (Dependabot) and improves the dependency
pin hygiene (astroid upper bound).
