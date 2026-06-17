# Specs: shareability-cleanup

## SC-001 — Internal review markers removed from production source

**Given** `src/gaze_py/cli/main.py` exists  
**When** any human reads the file  
**Then** no comment contains `# H4 fix`, `# H6 fix`, `# H2 fix`, or `# M6`

The substantive content of each comment is preserved where it adds value;
only the review-marker suffix is removed.

Specific locations (as of the audit):
- Line 583: `# H4 fix: is_file() branch returns src_path.parent...` → remove entirely
- Line 592: `# H4 fix: return the first matching file...` → remove entirely
- Line 652: `...(H6 fix).` → strip `(H6 fix)` suffix
- Line 659: `# Summary line — M6: use typed access instead of hasattr().` → remove entirely
- Line 673: `...fields (H6 fix).` → strip `(H6 fix)` suffix from docstring
- Line 1160: `...runner (H2 fix).` → strip `(H2 fix)` suffix from docstring

## SC-002 — Stale stub comments corrected

**Given** `src/gaze_py/cli/main.py` exists  
**When** any human reads the command-section headers  
**Then** comments accurately reflect current implementation state:
- `# quality command (stub — task 3)` → `# quality command`
- `# docscan command (stub — task 4)` → `# docscan command (not yet implemented — requires O3)`
- `# report command (stub — task 5, replaces old (src, tests) signature)` → `# report command (not yet implemented — requires O2)`

## SC-003 — README badges

**Given** `README.md` exists  
**When** a reader views the README on GitHub or PyPI  
**Then** three badges appear immediately after the title line:
1. CI badge: links to `test.yml` workflow, shows pass/fail
2. PyPI version badge: shows current published version
3. Python versions badge: shows supported Python range

## SC-004 — README stale limitations removed

**Given** the `## Current limitations` section in `README.md`  
**When** a reader reviews limitations  
**Then**:
- The "GazeCRAP scoring deferred" bullet is removed (shipped in 0.3.0)
- The output field table rows for `gaze_crap` and `quadrant` no longer say
  `null (O1 deferred)` — they accurately describe when these fields are populated
- The "Effect confidence range deferred" bullet is removed (shipped in 0.3.1 —
  `effect_confidence_range` is now populated when `reason == "all_effects_ambiguous"`)
- The `## Current limitations` section is removed entirely (no remaining limitations)

## SC-005 — README quality command documented

**Given** `README.md` has a Basic usage section  
**When** a reader wants to assess test quality  
**Then** at least one `gazepy quality` usage example appears in the README,
showing the basic invocation and the `--min-contract-coverage` CI gate flag

## SC-006 — README releasing section trimmed

**Given** `README.md` has a `## Releasing` section  
**When** a reader views it  
**Then** the `### One-time setup (already done)` block is removed; only the
numbered "Releasing a new version" steps remain — these are the only
contributor-facing instructions

## SC-007 — CHANGELOG 0.1.0 entry added

**Given** `CHANGELOG.md` documents releases  
**When** a user compares 0.1.0 to 0.2.0 to understand breaking changes  
**Then** a `## [0.1.0]` entry exists at the bottom of the file documenting
the initial release scope (side-effect detection, CRAP scoring, JSON output,
CLI commands available at that release)

## SC-008 — Tautological test assertion fixed

**Given** `tests/test_quality_integration.py` tests the attribute_mutation fixture  
**When** the test runs the O1 quality pipeline on `attribute_mutation`  
**Then** the assertion at the relevant line is a concrete, non-tautological
check that would actually fail if the pipeline produced wrong output.  
The current `assert report.contract_coverage is not None or report.target_function is not None`
is always true (right arm is proven non-None two lines earlier) and must be replaced.

## SC-009 — uv.lock committed

**Given** `uv.lock` has an unstaged change (version 0.3.1 → 0.4.0, including mypy 1.x → 2.1.0 major upgrade with transitive deps ast-serialize and librt)  
**When** `git status` is run  
**Then** `uv.lock` shows no unstaged modifications

## SC-010 — Completed OpenSpec changes archived

**Given** six OpenSpec changes are complete (all tasks `[x]`), with a seventh (`constitution-v1-1-0-pr`) archived in a prior session  
**When** a developer lists `openspec/changes/`  
**Then** `001-initial-port`, `cli-parity`, `constitution-v1-1-0-pr`, `coverprofile-path-fix`,
`o1-quality-pipeline`, `pypi-release`, and `upgrade-setup-uv` are located
under `openspec/changes/archive/` (seven entries total)

**Then** `openspec/changes/` contains only:
- `002-deferred-capabilities/` (tracking document, intentionally open)
- `archive/` (completed changes)
- `effect-confidence-range/` (open change — do not archive)
- `o3-docscan/` (open change — do not archive)
- `shareability-cleanup/` (this change, currently active)

## SC-011 — Empty docs/ directory removed

**Given** `docs/` exists with only a `.gitkeep`  
**When** a developer lists the repository root  
**Then** `docs/` does not appear in the listing
