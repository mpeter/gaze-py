## 1. Coverage Strategy Sections

- [ ] 1.1 Add Coverage Strategy section to `specs/001-gazepy-init-deploys/plan.md` after the Constitution Check section: state that this is a rename-only change with no new production logic; all existing scaffold tests updated with new filenames; 85% floor maintained via CI gate (T014, T023)
- [ ] 1.2 Add Coverage Strategy note to `openspec/changes/archive/gazepy-fix-command/proposal.md`: "Agent command files are Markdown, not testable Python. Behavioral verification is manual (run the command, observe output). CI gate confirms no regressions from the branch."
- [ ] 1.3 Add Coverage Strategy note to `openspec/changes/archive/gazepy-test-generator/proposal.md`: same text as 1.2

## 2. Acceptance Criteria

- [ ] 2.1 Add Acceptance Criteria section to `openspec/changes/gap-hints/proposal.md` after the Impact section: AC-1 (`len(gaps) == len(gap_hints)` for all coverage computations), AC-2 (all 38 `SideEffectType` values produce a non-empty hint string), AC-3 (`quality_to_json()` output includes `gaps` and `gap_hints` arrays when coverage is partial)
- [ ] 2.2 Add Acceptance Criteria section to `openspec/changes/report-command/proposal.md` after the Impact section: AC-1 (`gazepy report` without `--ai` exits 0 and emits valid JSON), AC-2 (`gazepy report --ai opencode` invokes the opencode subprocess adapter), AC-3 (`--max-gaze-crapload` enforcement exits 1 when threshold exceeded), AC-4 (provider binary not found produces a clear error with install hint)

## 3. CHANGELOG Traceability

- [ ] 3.1 Add `- Spec: openspec/changes/archive/quality-pairing-astroid/` to CHANGELOG `[Unreleased]` section
- [ ] 3.2 Add `- Spec: openspec/changes/archive/001-initial-port/` to CHANGELOG `[0.4.1]` section (coordinated with `specs/001-gazepy-init-deploys/`)
- [ ] 3.3 Add `- Spec: openspec/changes/archive/o3-docscan/` to CHANGELOG `[0.4.0]` section
- [ ] 3.4 Add `- Spec: openspec/changes/archive/effect-confidence-range/` to CHANGELOG `[0.3.1]` section
- [ ] 3.5 Add `- Spec: openspec/changes/archive/001-initial-port/` to CHANGELOG `[0.3.0]` section
- [ ] 3.6 Add `- Spec: openspec/changes/archive/cli-parity/` to CHANGELOG `[0.2.0]` section
- [ ] 3.7 Add `- Spec: _(initial release — predates spec workflow)_` to CHANGELOG `[0.1.0]` section

## 4. 002-Deferred-Capabilities Status Update

- [ ] 4.1 In `openspec/changes/002-deferred-capabilities/tasks.md`, mark A.1–A.4 as `[x]` SHIPPED (0.3.0)
- [ ] 4.2 Mark A.5 as `[x]` SHIPPED (0.3.0)
- [ ] 4.3 Mark A.6 as `[x]` SHIPPED (0.3.1)
- [ ] 4.4 Mark B.1–B.2 as `[x]` SHIPPED (0.3.1)
- [ ] 4.5 Mark C.1 as `[x]` SHIPPED (0.2.0)
- [ ] 4.6 Mark D.1 as `[x]` SHIPPED (0.4.0)
- [ ] 4.7 Mark D.2 as `[x]` SHIPPED (0.4.0)
- [ ] 4.8 Mark F.1–F.2 as `[x]` SHIPPED (0.2.0)
- [ ] 4.9 Add shipped version annotations after each checked item (e.g., `[x] A.1 ... — SHIPPED 0.3.0`)

## 5. CHANGELOG "replicator init" Terminology Fix

- [ ] 5.1 In CHANGELOG `[0.4.1]`, change "replicator init" to "uf init" (Envoy HIGH finding — terminology consistency)

## 6. Verification

- [ ] 6.1 Review all modified files for consistency — no stale references, no broken cross-links
- [ ] 6.2 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest --cov=gaze_py --cov-fail-under=85` — must pass (no production code changed, but verify no regressions)

## Convention Pack Compliance

Before implementing any task, read:
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`
