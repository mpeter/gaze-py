# Glossary

## AST analysis

Analysis using Python's `ast` module to parse source code into an abstract syntax tree and traverse it without executing the code or importing the module. gaze-py uses AST-only analysis — no runtime introspection.

## contract coverage

The fraction of a function's [contractual effects](#contractual-effect) that are actively asserted in tests. A test that calls a function but ignores its return value or output contributes to line coverage but not to contract coverage. Expressed as a fraction in [0.0, 1.0].

## contractual effect

A [side effect](#side-effect) classified as contractual — the caller depends on it. Contractual effects appear in the function's observable interface: return values, raised exceptions, mutations callers read back. A test that does not assert on a contractual effect misses part of the function's contract.

See also: [incidental effect](#incidental-effect).

## CRAP score

Change Risk Anti-Patterns score. Combines cyclomatic complexity and line coverage to predict how risky a function is to change:

```
CRAP = complexity² × (1 − line_coverage)³ + complexity
```

Higher is worse. A function at full coverage has CRAP = complexity. The default threshold for flagging a function is 15.0. See [Scoring](../concepts/scoring.md).

## CRAPload

The count of functions whose [CRAP score](#crap-score) exceeds the configured `crap_threshold`. A project-level metric representing test debt burden.

## GazeCRAP score

Extension of [CRAP](#crap-score) that replaces line coverage with [contract coverage](#contract-coverage):

```
GazeCRAP = complexity² × (1 − contract_coverage)³ + complexity
```

GazeCRAP is `null` when the quality pipeline has not run. See [Scoring](../concepts/scoring.md).

## incidental effect

A [side effect](#side-effect) classified as incidental — an implementation detail callers do not depend on. Tests need not assert on incidental effects. Examples: logging calls, internal cache updates, metric counters.

See also: [contractual effect](#contractual-effect).

## side effect

Any observable change a function produces beyond its return value. gaze-py detects 38 types of side effects organized into five priority [tiers](#tier-p0-p4). See [Side Effects](../concepts/side-effects.md).

## tier (P0–P4)

The priority tier assigned to each [side effect type](#side-effect). Lower numbers are higher priority:

| Tier | Priority | Example types |
|---|---|---|
| P0 | Must Detect | `ReturnValue`, `ErrorReturn`, `ReceiverMutation` |
| P1 | High Value | `GlobalMutation`, `WriterOutput`, `SliceMutation` |
| P2 | Important | `FileSystemWrite`, `GoroutineSpawn`, `LogWrite` |
| P3 | Nice to Have | `StdoutWrite`, `ProcessExit`, `TimeDependency` |
| P4 | Exotic | `ReflectionMutation`, `CgoCall`, `ClosureCaptureMutation` |
