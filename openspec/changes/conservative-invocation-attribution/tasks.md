## 1. Regression
- [x] 1.1 Add upstream-native positive mapping regression and observe red before source edits.
- [x] 1.2 Add negative controls for missing and ambiguous provenance.

## 2. Implementation
- [x] 2.1 Extend existing ordered evidence scan with a narrow recorded-invocation matcher.
- [x] 2.2 Preserve classification and scoring policy.

## 3. Verification
- [x] 3.1 Run focused tests, lint, format, strict source typing and full coverage gate.
- [x] 3.2 Prepare exact base, changed paths and evidence for independent review (verification.md).

## 4. Independent review repair
- [x] 4.1 Reproduce all four HIGH review blockers as red regressions on d95352f.
- [x] 4.2 Reject generator bodies, escaped records and state-changing fake headers; preserve independent return evidence.
- [x] 4.3 Run focused regressions, mutation checks, lint, types and stable-source full suite; prepare a follow-up commit for re-review.
