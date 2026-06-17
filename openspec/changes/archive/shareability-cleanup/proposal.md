# Proposal: shareability-cleanup

## Summary

Polish the codebase to a standard comfortable for public sharing. This is a
pure cleanup change — no behaviour changes, no new features, no API additions.
The changes fall into four buckets: (1) remove internal review-marker comments
that leaked into production code, (2) update the README to reflect shipped
capabilities and add standard badges, (3) complete the CHANGELOG with the
missing 0.1.0 entry, and (4) housekeeping (archive completed OpenSpec changes,
remove empty docs/ directory, commit the uv.lock version bump, fix a
tautological test assertion).

## Motivation

gaze-py 0.3.0 is published on PyPI. The codebase has several artefacts from the
development process that are visible to anyone who reads the source on GitHub:

- Six comments referencing internal code-review markers (`# H4 fix`, `# H6 fix`,
  `# H2 fix`, `# M6`) — meaningless to external readers, exposes internal process
- Stale comments (`# quality command (stub — task 3)`) that contradict the current
  state (quality is shipped and real)
- README that still says "GazeCRAP scoring deferred" and has no mention of the
  `quality` command shipped in 0.3.0
- No CI badge or PyPI badge on the README
- CHANGELOG missing the 0.1.0 initial release entry
- A tautological test assertion that always passes regardless of pipeline output
- Six completed OpenSpec changes not archived, making the changes/ directory
  unreadable at a glance
- Stale build artefacts in dist/ and an uncommitted uv.lock version bump

## Scope

**In scope:**
- Remove/clean internal review marker comments from `cli/main.py`
- Fix stale stub comments in `cli/main.py`
- Update README: badges, stale limitations section, quality command example,
  trim internal releasing notes
- Add CHANGELOG 0.1.0 entry
- Fix tautological assertion in `tests/test_quality_integration.py`
- Commit uv.lock version bump
- Archive completed openspec changes (move to openspec/changes/archive/)
- Delete docs/.gitkeep (empty directory)
- Delete stale dist/ artefacts (not tracked by git, cleanup only)

**Out of scope:**
- Any behaviour changes
- New features
- Refactoring visit_Call (flagged but out of scope)
- Issue/PR templates (nice-to-have, separate change)
- constitution-v1-1-0-pr (separate change)

## Acceptance Criteria

1. `ruff check .` passes with zero violations
2. `mypy --strict src/` passes with zero violations
3. `pytest --cov=gaze_py --cov-fail-under=85` passes
4. No `# H4 fix`, `# H6 fix`, `# H2 fix`, `# M6` strings appear in any file
   under `src/`
5. README contains CI badge, PyPI badge, Python badge
6. README does not contain "GazeCRAP scoring deferred" or "O1 deferred" in the
   limitations section
7. README contains a `gazepy quality` usage example
8. CHANGELOG contains a 0.1.0 entry
9. `openspec/changes/archive/` contains seven completed changes: `001-initial-port/`, `cli-parity/`, `constitution-v1-1-0-pr/`, `coverprofile-path-fix/`, `o1-quality-pipeline/`, `pypi-release/`, `upgrade-setup-uv/`
10. `tests/test_quality_integration.py` has no `or report.target_function is not None`
    tautology
11. `uv.lock` is committed with version 0.4.0 (bump from 0.3.1, includes mypy 1.x → 2.1.0 major upgrade)
