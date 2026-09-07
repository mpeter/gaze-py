## 1. Regression contract

- [x] 1.1 Add parametrized public mapper regression tests for supported capture patterns and observe the original failure.
- [x] 1.2 Add rejection tests for ordering, drain, reassignment, unrelated capture/producer, nested bodies and wrong streams.

## 2. Implementation

- [x] 2.1 Implement bounded AST-only capture provenance and integrate it before semantic fallback without altering existing return/exception precedence.
- [x] 2.2 Pass test context through the normal quality pipeline and verify measured coverage with synthetic source fixtures.
- [x] 2.3 Document supported patterns, conservative limitations and release notes.
- [x] 2.4 Prepare matching 0.9.3 package version metadata and lockfile without upgrading unrelated dependencies.
- [x] 2.5 Carry bounded static import context into capture attribution and test exact qualified identity, module-name collisions and shadowed aliases without changing public schemas.

## 3. Verification and delivery

- [ ] 3.1 Run Ruff check/format, strict mypy and full pytest with unchanged 85% coverage floor; validate the repaired revision. The earlier pass at `add2733` does not verify the council repairs.
- [ ] 3.2 Obtain all discovered review-council approvals and resolve findings before PR submission.
- [ ] 3.3 Submit PR, wait for green CI and required approval, merge, verify merged behavior and reconcile OpenSpec.
- [ ] 3.4 Verify a built/released artifact or full-commit dependency pin before downstream adoption; retain evidence on issue #82.

## 4. Council round-one repairs (before repeating delivery gates)

Items 1 and 2 record the initial implementation, not council acceptance. Round one
returned eight REQUEST CHANGES and one APPROVE. These repairs remain outstanding.

- [x] 4.1 Review and commit the ordered-analysis design amendment before Python edits. Independent Astra design review approved the amended contract, including possible drains, nested JSON mutation and blocked-capture precedence; this is not council approval.
- [ ] 4.2 Demonstrate public mapper regressions for every acceptance-matrix row against `add2733`, including semantic-fallback traps.
- [ ] 4.3 Replace competing capture scans with one ordered assertion-time evidence owner; preserve no-context and non-capture compatibility.
- [ ] 4.4 Reuse canonical root identity with exact scoped direct/local/module imports and pipeline tests for package roots, namespace uncertainty and suffix collisions.
- [ ] 4.5 Implement blocked storage/transform provenance, alias mutation invalidation and independent producer taint.
- [ ] 4.6 Cover uncertain drains, headers, unreachable assertions and explicit patch-context capture isolation through public APIs.
- [ ] 4.7 Document the bounded JSON subset and quality-reference link; make internal machinery private or fully document it; link the canonical spec from release notes and verify release compatibility.
- [ ] 4.8 Rerun full gates and artifact smoke, then all nine council personas against the complete new diff. Preserve the existing council iteration count.
