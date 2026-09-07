## Context

The existing mapper follows return bindings, exception assertions and effect-target name overlap. Captured output is a separate observable channel, so output variable names do not identify the production function. Name tricks or dynamic production calls would conceal the measurement error rather than repair it.

This plan is for a contributor implementing issue #82. The intended action is to add conservative capture provenance and demonstrate its accuracy through the public quality pipeline.

## Goals / Non-Goals

Goals: recognize the documented tuple pattern, captured result attributes, directly assigned `.out`/`.err`, and inline captured stream assertions. Preserve existing return/exception behavior and output-length invariants.

Non-goals: general Python symbolic execution, execution/import of analyzed modules, whole-program output attribution, new effect types, schema changes, classification changes or quality gate adjustments.

## Decisions

1. Supply the test AST as optional keyword-only context to mapping. Preserve existing callers without context; the production quality pipeline supplies context. For context-aware mapping, one ordered analysis owns assertion-time return bindings and capture provenance, as specified below.
2. Track supported pytest capture fixture parameters and stream values through statement order. A capture read consumes pending output attribution; an earlier saved value remains valid until reassigned. Recognize direct target calls, including existing qualified-call forms. Ignore nested function/class/lambda bodies. Unsupported control flow or ambiguous intervening producers must not fabricate attribution.
3. Identify stream assertions structurally, not by names such as `out` or substrings in effect targets. Handle tuple capture, result attributes, direct/inline attributes and bounded value-preserving operations needed by real JSON assertions. Do not infer arbitrary helper-call semantics. Treat stdout and stderr independently; assertions mixing both streams remain conservative.
4. Preserve first-match behavior for valid, live return/error bindings. Context-aware mapping uses assertion-time evidence before applying precedence; stale bindings and unsupported capture expressions cannot enter the legacy passes. Attributable capture requires that the matching stream effect exists on the target.
5. No new runtime dependency. Tests parse synthetic source as AST; they never execute analyzed source. Existing public pipeline fixtures verify measured coverage and diagnostic output, not only helper internals.
6. Qualified capture-producing calls require exact target-module identity from statically parsed import context. Retain bounded import context on the internal test model and pass target identity to the capture helper; do not equate module basenames or arbitrary receiver method names. Shadowed aliases and unresolved identities remain unsupported. This is a capture-provenance check, not a replacement pairing engine, and does not change serialized schemas.

## Council Repair Contract

The implementation at `add2733` passed its local checks but failed council round
one. This amendment replaces the independent recursive scans that allowed false
credit. It is a design checkpoint, not evidence that the findings are fixed.

### One ordered owner of evidence

Use a private analysis component under `quality/` to produce an immutable record
per same-file, depth-zero assertion position: supported reachability, live return
roles, and capture disposition (`not_capture`, `stdout`, `stderr`, or
`blocked_capture`). Private typed state owns import bindings, fixture bindings,
saved values and the pending capture window. Expression evaluation updates state
once in Python evaluation order; inspecting provenance must not itself consume
output. Delete the superseded capture traversal when replacing it.

For assertions with context, consult that record before any mapping pass. A valid
live return role retains precedence over a supported stream in a mixed assertion.
`blocked_capture` overrides every legacy pass, including an otherwise live return
role in the same assertion; this deliberate false negative prevents unsupported
capture syntax from acquiring credit. A stale
role does not: `result = target(); result = capsys.readouterr(); assert result.out`
checks stdout. Unsupported or unreachable capture assertions map to `None` and
cannot regain credit from exception or semantic fallback. Keep one result per
input assertion. Helper assertions without corresponding local AST evidence do
not inherit local capture state. Preserve the no-context public mapper contract
and existing non-capture exception/helper behavior; this is not a replacement
test-target pairing engine.

### Execution and capture boundaries

Positive evidence comes from direct calls in supported straight-line statements,
ordinary assignments, assertions and synchronous `with` bodies. A target call is
proven only after its receiver and arguments have been evaluated through the
supported expression subset. Unknown calls taint pending output independently of
whether their arguments contain capture values. A target call does not clear that
taint. A definitely executed, recognized no-argument fixture read consumes the
window and starts a clean one; a saved immutable snapshot survives later drains.

Do not recursively promote calls from boolean short-circuit operands, conditional
expressions, comprehensions, generators or lambda bodies into execution evidence.
Unsupported expressions cannot establish a target call or a clean drain. They
taint pending output if they may run a producer or consume a capture. A structural,
non-executing scan may mark capture-derived names and assertion positions as
blocked and return possible-producer/drain uncertainty to the ordered owner; it
must never directly mutate the window. The owner invalidates attribution on a
possible drain without clearing ambiguity or establishing a clean window. A
deferred body that cannot execute at definition does not itself consume output;
it also cannot erase earlier producer ambiguity. In particular,
`target(); capsys.readouterr() if flag else None` cannot leave the next capture
attributable to the target.

For `if`, loops, `try`, `match` and asynchronous control flow, do not infer paths.
Block contained capture assertions, invalidate potentially rebound or mutated
values/imports, and conservatively taint the pending window even when no target
has run yet. A subsequent definite drain and supported target call may establish
a new window. Stop executing the current statement sequence after unconditional
`return` or `raise`; mark later capture assertions unreachable rather than falling
back. A return inside a supported `with` also terminates its enclosing sequence.

Each synchronous context enter/exit taints pending output. The supported isolation
is enter, explicit drain, target, saved capture, exit, then assertion on the saved
snapshot. If the body contains unsupported paths that can skip snapshot creation,
the snapshot cannot become definite outside the context. Never assume unknown
context managers are silent or non-suppressing.

Nested function/lambda bodies are not executed at definition. Their default
expressions, decorators and annotations can be producers: include positional-only,
ordinary, keyword-only, vararg, kwarg and return annotations. Conservatively taint
for potentially evaluated headers, even when postponed annotations could avoid
execution. Class creation is an unknown producer. Definition names also shadow
imports and target names.

### Exact names and storage

Capture attribution requires a canonical target file plus import root/module
identity, supplied through internal pipeline context. A source-relative
`FunctionTarget.package` or path suffix is not an import identity. For file
`/project/src/pkg/example.py` rooted at `/project/src`, the identity is
`pkg.example`; `example` and `src.pkg.example` must fail. Derive ordinary package
roots from package ancestry, including `__init__.py`; namespace packages require
an authoritative root, otherwise leave capture attribution unsupported. Verify
both a project-root analysis and a package-subdirectory analysis of Fieldkit's
`src/fieldkit` layout. Do not execute imports or inspect runtime `sys.path`.

Move the existing `pairing._import_root()` into one internal identity module and
delete its origin; do not reuse the marker-based project root as an import root.
Construct an immutable identity after `pipeline._resolve_target()`, using the
existing file/directory-aware `_target_path()` seam. Include the resolved target's
receiver: a module-level `module.method()` must not prove a class method merely
because its bare name matches. Receiver-method capture attribution remains
unsupported until exact receiver identity is proven. Retain bounded import
context at the existing test-discovery parse point, without changing serialized
taxonomy models or pairing strategy semantics.

Resolve exact direct function imports and module aliases at module scope and in
ordered local statements. Parameters of every kind, local assignments/deletions,
definitions, conditional imports, wildcard imports and unresolved relative imports
must not leave a trusted target binding. Precompute function-local names so a
later local assignment cannot expose a shadowed module binding earlier in the
function. Unknown bare names cannot establish capture identity. Keep legacy
bare-name return matching only where needed for non-capture compatibility; it
must not override known conflicting bindings or revive blocked capture credit.
Distinguish module imports from imported symbols in typed state: `from pkg import
thing` does not establish that `thing` is a module. Support exact symbol identity;
leave ambiguous imported-module usage uncredited unless source context proves it.

Rebinding a name differs from writing an attribute: `module.setting = value`
does not rebind `module`, but replacing `module.target` invalidates that callable.
Treat unknown attribute/subscript writes as possible output producers. Evaluate
assignment RHS before invalidating its destination. Track unsupported chained,
attribute, subscript and destructuring storage as blocked capture provenance,
including aliases, so later semantic overlap cannot revive it.

Support saved capture objects, their `.out`/`.err` strings, exact two-name tuple
unpacking, direct aliases, and `json.loads(stream)` under an unshadowed
`import json` binding with one positional argument and no keywords. Read-only
indexing of parsed JSON and equality/membership checks may preserve a single
stream. Arbitrary receiver methods (including zero-argument methods), custom
transformers, mixed streams and unsupported storage yield blocked provenance.
Give each parsed JSON result a provenance family containing its aliases and all
descendants obtained through supported indexing. Mutating or passing any family
member to an unknown call invalidates that entire family, including parent
containers, before later assertions. For example, clearing `payload['items']`
through a saved alias invalidates `payload` as well. Conservatively invalidating
all values derived from that parse avoids general heap analysis. Unknown helper calls also taint the
pending output window. No arbitrary method gets value-preserving status.

### Alternatives and delivery boundary

Reject patching each recursive scan separately: it keeps competing definitions
of execution order and binding lifetime. Reject general symbolic execution: it
adds path joins and Python runtime semantics beyond this bug's scope. The chosen
bounded analysis accepts false negatives for unsupported syntax and documents
them; it must not claim mathematical soundness for arbitrary Python operators,
descriptors or dynamic monkeypatching.

Keep machinery private or document its full public contract. Reuse canonical
root logic with one owner, moving it if necessary without re-export shims. Public
docs must list the JSON subset and link it from the quality command reference;
release notes must link the canonical quality-mapper specification. Existing
0.9.3 metadata is provisional: verify that compatibility corrections qualify as
the planned patch under the release policy before publishing.

### Acceptance matrix

Every row requires public mapper regressions, with public pipeline tests for
canonical identity, blocked fallback, and the downstream capture shape. Negative
tests must use tempting target/effect names so semantic fallback is exercised.

| Boundary | Required evidence |
| --- | --- |
| Execution | Reject target/assert after return or raise, false short-circuit, conditional/comprehension calls, and deferred lambda reads. |
| Recovery | A possible producer before target taints capture; a conditional read cannot clean it and invalidates already-pending target output; a definite drain followed by target can restore attribution. |
| Identity | Accept exact direct/local/module imports; reject wrong direct imports, parameters, local definitions, later local assignments, conditional imports and suffix collisions. |
| Mutation | Preserve module alias after unrelated attribute write; reject overwritten target attribute, chained/attribute capture storage, arbitrary methods and mutable alias changes. |
| Headers | Reject polluted windows from positional-only, vararg and kwarg annotations as well as defaults/decorators. |
| Lifetime | Reassigned return becomes stream evidence; live return precedes a supported stream, but blocked capture overrides live return; stale capture cannot regain semantic credit. |
| Context | Preserve explicit drain/call/snapshot isolation inside patch contexts and reject unsupported paths or uncertain drains. |
| JSON | Accept the documented loads/indexing form; reject shadowed json, hooks/keywords, methods, mutation through nested aliases and mixed-stream expressions. |
| Compatibility | Preserve no-context mapper behavior, non-capture exception/helper behavior, output cardinality, taxonomy, schemas, formulas and frozen gates. |

Commit this amendment before code changes. Demonstrate each council regression
against the checkpoint, implement against this matrix, then rerun full local
gates, artifact smoke and all nine council personas on the complete new diff.
This design review does not consume or replace the next formal council round.

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
