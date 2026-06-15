---
tag: quality-pairing-astroid
author: matt-peter
category: pattern
created_at: 2026-06-15T15:41:13Z
identity: quality-pairing-astroid-20260615T154113-matt-peter
tier: draft
---

The gaze-py quality pipeline's assess() return type was changed from list[QualityReport] to AssessResult (a frozen dataclass with reports: tuple[QualityReport,...] and untested: tuple[QualityReport,...]) as part of the quality-pairing-astroid change (v0.5.0). The untested field contains QualityReports for production functions with detected effects but no paired test, each using test_function="" as a sentinel. The quality CLI command only shows result.reports; the crap --tests command uses both fields via build_contract_coverage_map(). Direct Python callers of assess() must migrate: reports = assess(...) becomes result = assess(...); reports = result.reports.
