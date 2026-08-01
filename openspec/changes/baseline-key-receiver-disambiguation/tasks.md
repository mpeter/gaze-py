<!--
  All tasks are sequential by nature; no [P] markers are used.
-->

## 1. Reproduce

- [x] 1.1 Confirm `score_key` is `package:function` with no receiver (`compare.py:241` pre-fix)
- [x] 1.2 Confirm `baseline_map` is a dict comprehension, so only the last entry per key survives
- [x] 1.3 Enumerate duplicate keys in a real consumer (`fieldkit-cmd`, 1524 functions): 7 duplicate `(package, function)` keys, of which 2 have differing CRAP under 0.9.0 (`cli_registry.py::to_dict` ×4, `shadowbot/client.py::query` ×2)
- [x] 1.4 Confirm it was latent on 0.8.2: under file-level coverage only `query` differed (by complexity, not coverage) and produced an *improvement*, which does not fail the gate. `to_dict` was uniform, so main stayed green
- [x] 1.5 Hand-simulate the aliasing and reproduce the exact observed output — `WriteDeclaration.to_dict` (CRAP 2.0) vs kept `CommandEntry.to_dict` (CRAP 1.0) = +1.00 regression; `query` = −3.00 improvement. Matches `Regressions: 1 Improvements: 1` exactly

## 2. Implement

- [x] 2.1 Qualify `score_key` by receiver: `package:receiver.function` for methods, unchanged for module-level functions
- [x] 2.2 Add `legacy_score_key` (the unqualified form) for baselines predating this change
- [x] 2.3 Group baseline entries by key into lists instead of collapsing with a dict comprehension
- [x] 2.4 Match one-to-one within a group in encounter order, tracking consumption per key
- [x] 2.5 Fall back to the legacy group when the qualified lookup misses
- [x] 2.6 Key removed-function detection on identity, so a removed overload is not hidden by a surviving namesake

## 3. Tests

- [x] 3.1 `score_key` qualifies methods by receiver
- [x] 3.2 `score_key` leaves module-level functions unqualified and equal to `legacy_score_key`
- [x] 3.3 Four same-named methods compared against themselves report no regressions (the reported defect)
- [x] 3.4 Two same-named module-level functions match one-to-one (receiver cannot disambiguate these)
- [x] 3.5 A genuine regression in one overload is still caught, and identifies the right receiver
- [x] 3.6 A pre-0.9.1 unqualified baseline still matches via the legacy key
- [x] 3.7 A removed overload is reported individually

## 4. Gates

- [x] 4.1 `uv run ruff check .` — all checks passed; `ruff format --check .` — 63 files already formatted
- [x] 4.2 `uv run mypy --strict src/` — success, 42 source files
- [x] 4.3 `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85` — **1117 passed, 95.50%**. Threshold untouched
- [x] 4.4 End-to-end against the real consumer: `fieldkit-cmd`'s 1524-function baseline compared against the data that produced it now yields `regressions=0 improvements=0 unchanged=1524 new=0 removed=0` (was 1 regression + 1 improvement)
- [ ] 4.5 `/review-council`

## 5. Release 0.9.1

- [x] 5.1 CHANGELOG entry
- [x] 5.2 Bump `pyproject.toml`, `src/gaze_py/__init__.py`, refresh `uv.lock` — separate commit
- [ ] 5.3 PR, green CI, merge, tag

## 6. Findings for follow-up (not fixed here)

- [ ] 6.1 Encounter-order matching within an ambiguous group is order-dependent: inserting a method between two same-named module-level functions shifts the pairing by one and can report a spurious delta alongside the legitimate new function. Receiver qualification removes this for methods, which is the common case; the residual affects only same-name-same-scope duplicates. A stabler key (enclosing qualified name) would close it but is a larger change to the baseline schema.
- [ ] 6.2 The `crapload >= 15.0` vs `new_violations > 15.0` asymmetry (`scorer.py:66` vs `compare.py`) is still open — carried over from the per-function-line-coverage change's §8.2.
