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

- [x] 3.1 Run Ruff check/format, strict mypy and full pytest with unchanged 85% coverage floor; validate the repaired revision. The final revision passes 1,253 tests at 95.30% coverage on Python 3.11, 3.12 and 3.13.
- [x] 3.2 Obtain all discovered review-council approvals and resolve findings before PR submission. All nine personas approved the final repair recheck.
- [x] 3.3 Submit PR, wait for green CI and required approval, merge, verify merged behavior and reconcile OpenSpec. PR #83 merged as `d5039a7` after all three CI matrix jobs passed; this archive applies the delta to the canonical specification.
- [x] 3.4 Verify a built/released artifact or full-commit dependency pin before downstream adoption; retain evidence on issue #82. Thirty installed-wheel checks passed for the merged source commit's 0.9.3 wheel, SHA-256 `be9a83a076f568289c349a3c8132ca841a49894c5f555d7562e599c76d495e1b`.

## 4. Council round-one repairs (before repeating delivery gates)

Items 1 and 2 record the initial implementation, not council acceptance. Round one
returned eight REQUEST CHANGES and one APPROVE. These repairs remain outstanding.

- [x] 4.1 Review and commit the ordered-analysis design amendment before Python edits. Independent Astra design review approved the amended contract, including possible drains, nested JSON mutation and blocked-capture precedence; this is not council approval.
- [x] 4.2 Demonstrate public mapper regressions for every acceptance-matrix row against `add2733`, including semantic-fallback traps. The initial valid red run had 22 failures; Python review added regressions for five further defect classes before its approving recheck.
- [x] 4.3 Replace competing capture scans with one ordered assertion-time evidence owner; preserve no-context and non-capture compatibility. Round two's missing tuple and attribute return roles are restored.
- [x] 4.4 Reuse canonical root identity with exact scoped direct/local/module imports and pipeline tests for package roots, namespace uncertainty and suffix collisions. Member replacement and conditional imports now invalidate canonical identity.
- [x] 4.5 Implement blocked storage/transform provenance, alias mutation invalidation and independent producer taint, including descendant storage, context escape and assertion-expression cases.
- [x] 4.6 Cover uncertain drains, headers, unreachable assertions and explicit patch-context capture isolation through public APIs.
- [x] 4.7 Document the bounded JSON subset and quality-reference link; keep internal machinery private; link the active contract from pending release notes and move that link to the canonical spec during post-merge reconciliation.
- [x] 4.8 Rerun full gates and artifact smoke, then all nine council personas against the complete new diff. Preserve the existing council iteration count.

## 5. Council round-two repairs

Round two returned six REQUEST CHANGES and three APPROVE. The approved design
remains the contract; passing tests on the prior revision did not establish these
behaviors. Shared documentation findings are verified with their behavior roots.

- [x] 5.1 Cover direct and possible JSON descendant writes, augmented writes and deletes; revoke escaped families in context expressions.
- [x] 5.2 Apply consistent scoped name/member invalidation to target imports, capture fixtures and the JSON transformer; preserve unrelated member writes.
- [x] 5.3 Restore live non-capture tuple return/error roles and ordinary return-derived assertions; preserve blocked-capture precedence.
- [x] 5.4 Reject uncertain capture expressions and unsupported stream attributes; handle assignment expressions in evaluation order.
- [x] 5.5 Keep new state types private and document the public mapper's full capture-context prerequisites.
- [x] 5.6 Verify public mapper and pipeline regressions, full gates and the exact built artifact; obtain all nine round-three verdicts before PR submission.

## 6. Council round-three repair verification

Round three identified three behavior roots plus one dead pipeline computation and
stale work-order evidence. The canonical quality-spec link was checked and exists;
the reported broken-link finding required no source change.

- [x] 6.1 Reject skipped return operands in Boolean and conditional expressions while preserving blocked-capture precedence.
- [x] 6.2 Reject arbitrary attributes on JSON-derived stream values.
- [x] 6.3 Propagate canonical member replacement across aliases and later imports of the same module.
- [x] 6.4 Remove the unused pipeline call-binding computation and refresh completed task evidence.
- [x] 6.5 Rerun the exact CI matrix, built-wheel smoke and quality report on the repaired revision, then obtain nine approving repair-verification verdicts. The Python 3.11-3.13 matrix passes 1,253 tests at 95.30%; 30 installed-wheel checks pass for SHA-256 `be9a83a076f568289c349a3c8132ca841a49894c5f555d7562e599c76d495e1b`; the isolated quality report approves with CRAPload 12 and GazeCRAPload 11.

## 7. Council round-three repair recheck

- [x] 7.1 Reject evaluated-but-non-enforcing return operands while preserving the documented supported-stream conjunction.
- [x] 7.2 Point pending release notes at the active delta contract until OpenSpec archival updates the canonical specification.
- [x] 7.3 Refresh final gates, wheel evidence, quality reporting and all nine verdicts on this revision.
