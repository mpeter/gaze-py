---
tag: quality-pairing-astroid
author: matt-peter
category: context
created_at: 2026-06-15T15:41:24Z
identity: quality-pairing-astroid-20260615T154124-matt-peter
tier: draft
---

When writing spec review council iterations for gaze-py openspec changes, the most productive council findings were: (1) porting contract violations that contradict the Go reference — always verify against internal/crap/contract.go before finalizing null/non-null decisions; (2) test fixture pairing assumptions — the undertested.py fixture calls compute_total as a bare ast.Name call, so Strategy 2 pairs it (it appears in result.reports, not result.untested); genuinely-untested functions need a fixture with NO corresponding test file at all; (3) API shape changes that break existing callers — assess() return type from list to dataclass broke 11 integration tests and required explicit migration; (4) [P] task markers that create impossible parallel deps — tasks that depend on other tasks in earlier sections must not be marked [P] even if they touch different files.
