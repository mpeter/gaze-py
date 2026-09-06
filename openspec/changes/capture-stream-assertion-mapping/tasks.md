## 1. Regression contract

- [ ] 1.1 Add parametrized public mapper regression tests for supported capture patterns and observe the original failure.
- [ ] 1.2 Add rejection tests for ordering, drain, reassignment, unrelated capture/producer, nested bodies and wrong streams.

## 2. Implementation

- [ ] 2.1 Implement bounded AST-only capture provenance and integrate it before semantic fallback without altering existing return/exception precedence.
- [ ] 2.2 Pass test context through the normal quality pipeline and verify measured coverage with synthetic source fixtures.
- [ ] 2.3 Document supported patterns, conservative limitations and release notes.

## 3. Verification and delivery

- [ ] 3.1 Run Ruff check/format, strict mypy and full pytest with unchanged 85% coverage floor; validate this OpenSpec change.
- [ ] 3.2 Obtain all discovered review-council approvals and resolve findings before PR submission.
- [ ] 3.3 Submit PR, wait for green CI and required approval, merge, verify merged behavior and reconcile OpenSpec.
- [ ] 3.4 Verify a built/released artifact or full-commit dependency pin before downstream adoption; retain evidence on issue #82.
