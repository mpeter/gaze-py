## Context

The existing mapper follows return bindings, exception assertions and effect-target name overlap. Captured output is a separate observable channel, so output variable names do not identify the production function. Name tricks or dynamic production calls would conceal the measurement error rather than repair it.

This plan is for a contributor implementing issue #82. The intended action is to add conservative capture provenance and demonstrate its accuracy through the public quality pipeline.

## Goals / Non-Goals

Goals: recognize the documented tuple pattern, captured result attributes, directly assigned `.out`/`.err`, and inline captured stream assertions. Preserve existing return/exception behavior and output-length invariants.

Non-goals: general Python symbolic execution, execution/import of analyzed modules, whole-program output attribution, new effect types, schema changes, classification changes or quality gate adjustments.

## Decisions

1. Supply the test AST as optional keyword-only context to mapping. Preserve existing callers without context; the production quality pipeline supplies context. A dedicated capture-provenance helper keeps ordered AST analysis separate from existing return bindings.
2. Track supported pytest capture fixture parameters and stream values through statement order. A capture read consumes pending output attribution; an earlier saved value remains valid until reassigned. Recognize direct target calls, including existing qualified-call forms. Ignore nested function/class/lambda bodies. Unsupported control flow or ambiguous intervening producers must not fabricate attribution.
3. Identify stream assertions structurally, not by names such as `out` or substrings in effect targets. Handle tuple capture, result attributes, direct/inline attributes and bounded value-preserving operations needed by real JSON assertions. Do not infer arbitrary helper-call semantics. Treat stdout and stderr independently; assertions mixing both streams remain conservative.
4. Preserve first-match behavior for return/error assertions. A capture-aware pass runs before semantic fallback for remaining assertions, and requires that the matching stream effect exists on the target. Captured stream assertions that cannot be safely attributed must not acquire stdout/stderr credit through the old name-overlap fallback.
5. No new runtime dependency. Tests parse synthetic source as AST; they never execute analyzed source. Existing public pipeline fixtures verify measured coverage and diagnostic output, not only helper internals.

## Porting Contract Alignment

Read the Go porting contracts, requirements and taxonomy reference before this plan. Requirement O1 permits any accurate assertion-mapping strategy. SC-002's formula and denominator semantics remain unchanged; EC-001's 48 types and tier assignments, EC-004 structures, OC-002 fields and OC-003 null semantics remain unchanged. The old constitution's historical 38-type prose is not used to alter the current canonical taxonomy. Principles I–VII are preserved: accuracy, AST-only assumptions, actionable output, isolated regression tests, porting authority, standalone operation and unchanged dependency graph.

## Risks / Trade-offs

- False credit is more damaging than an explicit unsupported pattern: negative tests cover captures before calls, drain boundaries, reassignment, unrelated producers/fixtures, nested bodies and wrong streams.
- General control-flow and helper attribution are deliberately unsupported where provenance cannot be established. Document the supported subset and leave uncertain effects uncovered.
- A real mapper correction can change measurements. Report downstream deltas and rerun existing gates; never alter baselines or thresholds to force success.

## Coverage Strategy

Use parametrized public mapper tests for all supported forms and rejection boundaries, first demonstrate the original bug with failing tests, then add a public pipeline fixture proving that separate return/output assertions increase contract coverage only for the intended function. Run lint, format, strict mypy, the full test suite at the unchanged 85% floor, and the required review council. Build and smoke-test the artifact before adoption.

## Migration Plan

Merge the reviewed upstream repair with green CI. Adopt a verified released version or reviewed full-commit pin downstream, rerun the unchanged fieldkit gates, and only then resume downstream PR/closure. Reverting the mapper repair restores prior mapping behavior; it does not change stored data or user source. Reconcile the OpenSpec delta after merge and verified acceptance.
