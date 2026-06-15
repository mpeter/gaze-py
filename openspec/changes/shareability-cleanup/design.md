# Design: shareability-cleanup

All changes in this cleanup are mechanical edits with no architectural
decisions. There are no alternative approaches to evaluate. Design notes
are included only where a choice exists.

## SC-008: Tautological assertion replacement (resolved)

The tautological assertion has been replaced in a prior session. The test
`test_attribute_mutation_fixture_coverage` in `tests/test_quality_integration.py`
now asserts the concrete pipeline output:

```python
assert report.contract_coverage is not None
assert report.contract_coverage.percentage is None
assert report.contract_coverage.reason == "no_effects_detected"
assert report.contract_coverage.total_contractual == 0
```

Note: `contract_coverage` is a `ContractCoverageResult` dataclass — numeric
comparisons against `0.0` are not valid. The correct assertions are against
the `.percentage`, `.reason`, and `.total_contractual` fields.

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
