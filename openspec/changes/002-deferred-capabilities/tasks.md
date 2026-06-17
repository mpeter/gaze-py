<!--
  This is a TRACKING document, not an implementation task list.
  No tasks here should be checked off — each item below represents
  a future OpenSpec change that must be proposed, specced, designed,
  and tasked separately before implementation begins.

  To action an item: create openspec/changes/00N-<name>/ and write
  the four artifacts (proposal, specs, design, tasks) for that item.
  Then implement under that change, not this one.
-->

## Deferred Item Registry

### Group A — O1 Quality Assessment (highest value, highest complexity)

Implement in sequence; each step is a blocker for the next.

- [ ] A.1 O1-A — Test-target pairing (`src/gaze_py/quality/pairing.py`)
- [ ] A.2 O1-B — Assertion detection (`src/gaze_py/quality/assertions.py`)
- [ ] A.3 O1-C — Assertion → effect mapping (`src/gaze_py/quality/mapper.py`)
- [ ] A.4 O1-D — Contract coverage computation (`src/gaze_py/quality/coverage.py`)
- [ ] A.5 O1-E — Populate GazeCRAP, quadrant, fix_strategy, gaze_crapload,
      avg_contract_coverage, quadrant_counts, fix_strategy_counts in output
- [ ] A.6 O1-F — Populate `effect_confidence_range` field

### Group B — Cyclomatic Complexity Algorithm (prerequisite quality improvement)

Can be implemented independently of O1, but improves CRAP accuracy.

- [ ] B.1 Specify and implement the complexity algorithm explicitly in
      `src/gaze_py/analysis/complexity.py` (which AST nodes increment the counter,
      nested scope rules, baseline)
- [ ] B.2 Add a test that computes CRAP from a real Python function
      (not pre-supplied complexity numbers) and verifies against a known result

### Group C — CLI Enhancements (independent, low risk)

Can be implemented in any order after 001 lands.

- [ ] C.1 O5 — CI threshold flags: `--max-crapload`, `--max-gaze-crapload`
      (O1-independent portion only)
- [ ] C.2 O5 — `--min-contract-coverage` flag [BLOCKED: A.4]
- [ ] C.3 O6 full — Coverage profile reuse: support `.coverage` binary format,
      optional internal `coverage run pytest` invocation

### Group D — Classification Enhancements (independent)

- [ ] D.1 O3 — Document scanning signal (`src/gaze_py/classify/signals/docscan.py`)
- [ ] D.2 O7 full — Add `doc_scan.exclude` and `doc_scan.timeout` to
      `.gaze.yaml` config [BLOCKED: D.1]
- [ ] D.3 Revisit P3/P4 no-equivalent types — close SyncPoolOp/UnsafeMutation/
      AtomicOp permanently; evaluate WaitGroupOp and RecoverBehavior

### Group E — Output & Presentation (independent)

- [ ] E.1 O4 — Interactive TUI
- [ ] E.2 O2 — AI-powered reports adapter pattern (Claude, OpenCode, Ollama)

### Group F — Distribution (independent, external prerequisite)

- [ ] F.1 Claim `gaze-py` name on PyPI (manual — verify name is unclaimed)
- [ ] F.2 PyPI publication — GitHub Actions release workflow triggered on
      version tag

### Group G — Cleanup (revisit after 001 is stable)

- [ ] G.1 Evaluate `return None` without annotation — should it be ReturnValue?
      Check whether Go gaze maintainers clarify EC-005 on this case. If clarified
      to require detection, update specs and detector heuristic.
- [ ] G.2 Verify 37 vs 38 type count with Go gaze maintainers and update
      porting contracts upstream if 38 is confirmed.

---

## Recommended Sequencing

For maximum value delivered per change:

1. **B.1-B.2** — Complexity algorithm (improves existing CRAP scores immediately)
2. **A.1 → A.2 → A.3 → A.4** — O1 pipeline (unlocks GazeCRAP)
3. **A.5 → A.6** — Populate remaining null output fields
4. **C.1** — CI threshold flags (makes tool useful in CI pipelines)
5. **F.1 → F.2** — PyPI publication (makes tool installable for end users)
6. **D.1 → D.2** — Document scanning (improves classification accuracy)
7. **C.2** — `--min-contract-coverage` flag (completes CI enforcement)
8. Everything else in any order
