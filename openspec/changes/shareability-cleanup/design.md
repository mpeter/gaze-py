# Design: shareability-cleanup

All changes in this cleanup are mechanical edits with no architectural
decisions. There are no alternative approaches to evaluate. Design notes
are included only where a choice exists.

## SC-008: Tautological assertion replacement

The existing assertion:
```python
assert report.contract_coverage is not None or report.target_function is not None
```

The right arm (`report.target_function is not None`) is unconditionally true
because `report.target_function` was asserted equal to `"set_label"` two lines
earlier. This makes the entire `or` expression always true.

**Replacement approach**: Run the quality pipeline against the
`attribute_mutation` fixture (which calls `label.set("x")` — a clear
`AttributeMutation` effect) and determine what `contract_coverage` the
current pipeline produces. The fixture's test file (`test_attribute_mutation.py`)
asserts on `label.text` after calling `set_label`, which is a direct observation
of the mutation effect. The mapper should pair this assertion to the effect.

Expected: `contract_coverage > 0.0` — at minimum the attribute mutation
effect should be covered by the test assertion. The concrete assertion should be:
```python
assert report.contract_coverage is not None
assert report.contract_coverage >= 0.0
```
Or stronger if the pipeline reliably produces a specific value.

## SC-010: Archive approach

Move directories using `git mv` (not `mv`) so git tracks the rename:
```bash
git mv openspec/changes/001-initial-port openspec/changes/archive/001-initial-port
# ... repeat for each completed change
```

This preserves git history for the archived content.

## SC-011: Empty directory removal

```bash
git rm docs/.gitkeep
```

Git does not track empty directories; removing the only file removes the
directory from tracking. The `docs/` directory will disappear from the
repository.
