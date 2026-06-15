---
tag: quality-pairing-astroid
author: matt-peter
category: gotcha
created_at: 2026-06-15T15:41:09Z
identity: quality-pairing-astroid-20260615T154109-matt-peter
tier: draft
---

OC-003 (nullable fields) in gaze-py's porting contracts means: when a function has detected side effects but no test targets it, the correct contract_coverage_reason is "no_test_coverage" with percentage=None and gaze_crap=null — NOT percentage=0.0 with computable GazeCRAP. The Go reference at contract.go:148 is explicit: "no test = no coverage data, not 0% coverage" (ok=false return from BuildContractCoverageFunc). The misinterpretation that untested-but-has-effects should produce computable GazeCRAP at 0% is a common OC-003 violation that the review council correctly identified as a blocking finding in iteration 1. The distinction matters because "measured as zero" and "not measured" are semantically different and must not be conflated in quality output.
