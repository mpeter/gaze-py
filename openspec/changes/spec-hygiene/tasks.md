## 1. Coverage Strategy Sections

- [x] 1.1 Add Coverage Strategy section to `specs/001-gazepy-init-deploys/plan.md` after the Constitution Check section: state that this is a rename-only change with no new production logic; all existing scaffold tests updated with new filenames; 85% floor maintained via CI gate (T014, T023)
- [x] 1.2 Add Coverage Strategy note to `openspec/changes/archive/gazepy-fix-command/proposal.md`: "Agent command files are Markdown, not testable Python. Behavioral verification is manual (run the command, observe output). CI gate confirms no regressions from the branch."
- [x] 1.3 Add Coverage Strategy note to `openspec/changes/archive/gazepy-test-generator/proposal.md`: same text as 1.2

## 2. Acceptance Criteria

- [x] 2.1 Add Acceptance Criteria section to `openspec/changes/gap-hints/proposal.md` after the Impact section: AC-1 (`len(gaps) == len(gap_hints)` for all coverage computations), AC-2 (all 38 `SideEffectType` values produce a non-empty hint string), AC-3 (`quality_to_json()` output includes `gaps` and `gap_hints` arrays when coverage is partial)
- [x] 2.2 Add Acceptance Criteria section to `openspec/changes/report-command/proposal.md` after the Impact section: AC-1 (`gazepy report` without `--ai` exits 0 and emits valid JSON), AC-2 (`gazepy report --ai opencode` invokes the opencode subprocess adapter), AC-3 (`--max-gaze-crapload` enforcement exits 1 when threshold exceeded), AC-4 (provider binary not found produces a clear error with install hint); also add missing `### VII. Supply Chain Integrity` section at end of constitution alignment (PASS — no new dependencies)

## 3. CHANGELOG Traceability

- [x] 3.1 Add `- Spec: openspec/changes/archive/quality-pairing-astroid/` to CHANGELOG `[Unreleased]` section
- [x] 3.2 Add `- Spec: specs/001-gazepy-init-deploys/` to CHANGELOG `[0.4.1]` section (Speckit strategic spec for the init rename)
- [x] 3.3 Add `- Spec: openspec/changes/archive/o3-docscan/` to CHANGELOG `[0.4.0]` section
- [x] 3.4 Add `- Spec: openspec/changes/archive/effect-confidence-range/` to CHANGELOG `[0.3.1]` section
- [x] 3.5 Add `- Spec: openspec/changes/archive/o1-quality-pipeline/` to CHANGELOG `[0.3.0]` section (O1 quality assessment pipeline)
- [x] 3.6 Add `- Spec: openspec/changes/archive/cli-parity/` to CHANGELOG `[0.2.0]` section
- [x] 3.7 Add `- Spec: _(initial release — predates spec workflow)_` to CHANGELOG `[0.1.0]` section

## 4. 002-Deferred-Capabilities Status Update

Note: The tracking doc header says "No tasks here should be checked off." Use
inline `— SHIPPED 0.N.N` suffix annotations instead of checking boxes (design.md D6).

- [x] 4.1 In `openspec/changes/002-deferred-capabilities/tasks.md`, append `— SHIPPED 0.3.0` to A.1 through A.4 description lines (O1-A through O1-D)
- [x] 4.2 Append `— SHIPPED 0.3.0` to A.5 description line (GazeCRAP/quadrant/fix_strategy)
- [x] 4.3 Append `— SHIPPED 0.3.1` to A.6 description line (effect_confidence_range)
- [x] 4.4 Append `— SHIPPED 0.3.1` to B.1 and B.2 description lines (complexity algorithm)
- [x] 4.5 Append `— SHIPPED 0.2.0` to C.1 description line (O5 CI threshold flags, O1-independent portion)
- [x] 4.6 Append `— SHIPPED 0.4.0` to D.1 description line (O3 document scanning)
- [x] 4.7 Append `— SHIPPED 0.4.0` to D.2 description line (O7 doc_scan config)
- [x] 4.8 Append `— SHIPPED 0.2.0` to F.1 and F.2 description lines (PyPI publication)

## 5. CHANGELOG "replicator init" Terminology Fix

- [x] 5.1 In CHANGELOG `[0.4.1]`, change "replicator init" to "uf init" (Envoy HIGH finding — terminology consistency)

## 6. Verification

- [x] 6.1 Review all modified files for consistency — no stale references, no broken cross-links
- [x] 6.2 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest --cov=gaze_py --cov-fail-under=85` — must pass (no production code changed, but verify no regressions)

## Convention Pack Compliance

Before implementing any task, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`

<!-- spec-review: passed -->
<!-- code-review: passed -->
