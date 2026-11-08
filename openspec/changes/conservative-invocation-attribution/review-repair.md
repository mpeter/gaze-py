# Independent-review repair

## Boundary and status

Follow-up to local commit `d95352f3dab0b8caf2b5e6f01694ae974315228a`, addressing
only four HIGH defects from Python review session `ses_e46dc44a1ffee7EXS66jUxjix9`.
Independent re-review is pending; implementation is not acceptance or adoption.
Origin, v0.9.3 base and isolated worktree are unchanged from verification.md.

No agents, publication, push, PR, merge, application changes, dependency adoption,
installation, threshold/baseline changes or gate weakening occurred.

## Red evidence before production edits

Eight parametrized regressions failed on d95352f production source:

- `yield` and `yield from`: constructing a generator incorrectly covered spawn.
- Record passed positionally, by keyword, through `*args` or `**kwargs`: a
  production overwrite of the escaped record incorrectly covered spawn.
- Walrus in the fake's argument annotation: rebinding monkeypatch to decoy still
  incorrectly covered spawn.
- Recorder name rebound to the selected target return: valid ReturnValue
  evidence was overwritten with None.

Command: **8 failed, 35 deselected**, with failures exactly as above:

```sh
PY=/home/mpeter/work/fieldkit-cli.worktrees/sync-pr234-20261107/.venv/bin/python
PYTHONPATH="$PWD/src" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m pytest -o addopts='' tests/test_quality_invocation.py -q -k review
```

All fixture strings are parsed as AST, never imported or executed.

## Bounded repairs

1. Exclude Yield/YieldFrom in the existing unsupported production-body grammar.
2. Reject any reference to the recorder in exercise argument/keyword syntax.
   Existing straight-line grammar already rejects intervening alias assignments;
   no alias tracking or interprocedural mutation inference was introduced.
3. Validate fake annotations against a small inert grammar: literal forward
   references/None, unshadowed built-in type names and built-in generic forms,
   and canonical subprocess.CompletedProcess types. Dynamic attributes,
   subscriptions, unions/operators and walruses outside that grammar fail closed.
   Existing module-header checks also reject assignment expressions.
4. Give existing ordered assertion evidence priority, including explicit blocked
   evidence. Invocation evidence fills only positions with no existing entry.
   This is not fallback to legacy semantic matching.

Added controls cover argument, kwargs and return annotations, dynamic annotation
attributes/subscripts/operators, a shadowed built-in annotation, and the original
standard typed fake shape. The previous target-overwrites-record negative now
requires ReturnValue rather than None: its old expectation encoded blocker 4.
It still forbids spawn attribution, and the new valid compatibility test asserts
the actual returned payload. Other invalid-record controls retain None.

## Green and mutation evidence

Focused verification: **198 passed, 1 existing collection warning**; **50 tests**
in the invocation module, including 15 added in this repair.

```sh
PYTHONPATH="$PWD/src" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m pytest -o addopts='' tests/test_quality_invocation.py tests/test_quality_mapper.py -q
ruff check .
ruff format --check .
mypy src/
git diff --check
```

Lint passed; 67 files formatted; strict types passed for 45 source files.

Four separate in-memory analyzer mutations were killed:

- Remove generator rejection: **2 failures**.
- Remove exercise-record escape rejection: **4 failures**.
- Accept all fake annotations: **7 failures**.
- Restore recorder-name override of existing evidence: **1 failure**.

Each mutation ran the corresponding review test selection with pytest
`-o addopts='' tests/test_quality_invocation.py -q -k <selection>` and required
exit 1. No source file was mutated. A setup indentation mismatch and an initial
patch to the definition rather than capture's imported factory alias were
corrected before these valid mutation results; neither was counted as a kill.
All mutation guard counters were **0 process, 0 socket, 0 network attempts**.

The three unchanged original typed reproduction fixtures were reassessed too:
confidence remains **69/74/79**, denominators **2/2/3**, success-test coverage
**50%/50%/66.66666666666666%**. All guard counters were zero. The native matrix
also continues to test max-per-test reduction with separate success/error tests.

## Full stable-source gate

**1303 passed, 17 existing warnings, 95.30% coverage, required 85%, exit 0**
in 107.24 seconds. All three safety guard counters were **0**. Source/test
hashes below matched before and after the full run. The launcher is the same guarded Python 3.11.17 launcher
recorded in verification.md, with an explicit local source-path assertion,
`PYTHONPATH="$PWD/src"`, plugin autoload disabled, pytest-cov explicitly loaded,
and `pytest.main(['-p', 'pytest_cov', '--cov=gaze_py', '--cov-fail-under=85'])`.
No tests or coverage floor are excluded from the full run.

Source/test SHA-256 identities checked during verification:

```text
7829a55ebc6167f4628a3486ce873334bfa0976af5a3c76e79e180792a0cf05d  src/gaze_py/quality/capture.py
843dad1dcf94e5d654b25d64d28a679c3731c58f000c679d4680eb33bf5e1921  src/gaze_py/quality/invocation.py
240fc00bdbda59661b730a969dd99d10af972d3a693a745c37048071a2739384  tests/test_quality_invocation.py
```

## Remaining limits

The matcher remains intentionally narrow; unsupported annotation types, unions,
record aliases/transformations, helper-mediated calls, fixture-defined fakes and
conditional execution receive no new invocation credit. No general provenance
solver was added. Scoring, classification, taxonomy, thresholds and max-per-test
implementation are unchanged. Full Python 3.12/3.13 CI, review acceptance and the
real application gate remain unverified. The inherited OpenSpec main-spec archive
structure warning remains outside this repair.

One older fixture-control limitation was noticed but not repaired outside the
four-defect scope: `_map_invocation` selects the first detected function, while
the existing `shadowed-error-constructor` control inserts a RuntimeError function
before run_worker. That control may therefore exercise the wrong selected target.
If broader test hardening is authorized, select run_worker explicitly there.
The new review regressions each have only the intended production function.
