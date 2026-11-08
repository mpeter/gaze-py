# Conservative invocation attribution — implementation evidence

Historical evidence for d95352f. Independent Python review subsequently returned
four HIGH blockers; the bounded follow-up is recorded in [review-repair.md](review-repair.md).

## Status and provenance

Implemented and locally verified; independent Python review remains pending with
the coordinating session. This is not adoption, release, merge, or PR readiness.

- Actual upstream origin: `https://github.com/mpeter/gaze-py.git`.
- Base: tag `v0.9.3`, commit `73c464ec81cd240e72d45d59157a0ac597ccfa28`.
- Installed distribution metadata says 0.9.3 but names the unavailable
  `https://github.com/unbound-force/gaze-py` URL. Existing owning repository's
  origin resolves v0.9.3; all 44 Python files in its tag were SHA-256 compared
  with the installed distribution and match exactly, including after this work.
- Isolated branch: `opsx/conservative-invocation-attribution`.
- Worktree: `/home/mpeter/prj/unbound-force/gaze-py.worktrees/conservative-invocation-attribution`.
- Primary checkout remained clean, on its existing revision. Other worktrees were
  inspected, not modified. Installed package and fieldkit source/configuration,
  dependencies, thresholds, baselines, job/runtime/provider settings were not edited.

## Changed behavior

`quality/invocation.py` recognizes one narrow AST grammar: a fresh local dict,
nested received-parameter recording fake, live module-object monkeypatch of the
selected function's direct subprocess.run boundary, one exact selected-target
exercise, then direct record equality against literal data. It reuses
`_TargetIdentity`, import bindings, and the execution order owned by `capture.py`.
The latter contributes only lifecycle hooks and explicit record evidence.

The original reproduction's `from fixture_N import client` owner form works.
Record/fake/argument names are not semantic signals. A renamed positive test
guards this. Unknown calls, storage, branches, record escapes, wrong or shadowed
patches, unused fakes and multiple producers fail closed. No analyzed source is
executed or imported.

No classification, confidence, taxonomy, scoring formula, max-per-test reducer,
threshold or baseline implementation changed. The new matrix tests exercise the
real assessor and reducer with separate success and error tests.

## Red, green and negative controls

Before source edits, the command below produced **1 failed, 11 passed**. The
failure was exactly `[ReturnValue, None]` versus required
`[ReturnValue, GoroutineSpawn]` for the real received-arguments assertion.

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /usr/bin/python3 -m pytest -o addopts='' tests/test_quality_invocation.py -q
```

The final new module has **35 passing tests**. Together with the existing mapper
tests, focused verification produced **183 passed, 1 collection warning**:

```sh
PY=/home/mpeter/work/fieldkit-cli.worktrees/sync-pr234-20261107/.venv/bin/python
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PY" -B -m pytest -o addopts='' tests/test_quality_invocation.py tests/test_quality_mapper.py -q
```

An in-memory mutation that forces record attribution while ignoring lifecycle
invalidation was killed by **20 negative-control failures** (3 controls still
passed; 12 unrelated tests deselected). No mutation was written to disk.

Direct assessments of all three unchanged original diagnostic fixtures also
passed under process/socket/network guards. Confidence, contractual denominator
and best success-test percentages were respectively:

- 0 callers: **69**, **2**, **50%**.
- 1 caller: **74**, **2**, **50%**.
- 2 callers: **79**, **3**, **66.66666666666666%** (previously 33.33333333333333%).

Each original success test now maps return to ReturnValue and received argv/kwargs
to GoroutineSpawn. No ErrorReturn coverage was added to success tests. Guards
recorded **0 process, 0 socket, 0 network attempts**; no fieldkit module was imported.

## Full project gates

Existing tools/environments were reused; no dependencies were installed. Ruff
0.15.13 and the existing strict mypy configuration were used. Python 3.11.17,
pytest 9.2.0 and pytest-cov 7.1.0 came from the read-only existing environment.
`uv run` was not used, avoiding environment synchronization or installation.

```sh
ruff check .                  # All checks passed
ruff format --check .         # 67 files already formatted
mypy src/                     # Success: 45 source files
git diff --check              # clean
openspec validate conservative-invocation-attribution --strict
# Change valid; inherited main-spec archive warning described below
```

Full gate ran in a task-owned tmux session against a stable source revision:
**1288 passed, 17 warnings, 95.30% coverage; required 85%; exit 0**.
Warnings concern existing TestFunc collection, deliberate malformed-source
fixtures and the docscan timeout test; no test was skipped or weakened.

Equivalent exact Python launcher and guard body used for the full gate:

```sh
PYTHONPATH="$PWD/src" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
GIT_CONFIG_GLOBAL=/dev/null GIT_EDITOR=true "$PY" -B - <<'PYEOF'
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
import gaze_py
print('Interpreter:', sys.version)
print('Source:', gaze_py.__file__)
assert Path(gaze_py.__file__).resolve() == Path('src/gaze_py/__init__.py').resolve()
with patch('subprocess.Popen', side_effect=AssertionError('real process forbidden')) as process_guard, patch('socket.socket', side_effect=AssertionError('real socket forbidden')) as socket_guard, patch('socket.create_connection', side_effect=AssertionError('real network forbidden')) as network_guard:
    code = pytest.main(['-p', 'pytest_cov', '--cov=gaze_py', '--cov-fail-under=85', '-v'])
    attempts = (process_guard.call_count, socket_guard.call_count, network_guard.call_count)
print('Safety guard attempts:', attempts)
assert attempts == (0, 0, 0), attempts
raise SystemExit(code)
PYEOF
```

All three full-suite guard counters were **0**. The task-owned tmux session was
closed afterward.

## Corrected verification setup errors

The first test harness referenced a nonexistent detector helper; it was corrected
to the established `FileDetector.detect` API before the valid red observation.
An initial integration-test assumption that the aggregate map excludes untested
caller functions was corrected to inspect the selected target's exact key.

One full-suite launcher imported gaze_py before pytest configured its source
path, inadvertently selecting the installed package. That run is excluded from
acceptance evidence (5 failures, 1282 passes; zero guard attempts). Its printed
source path exposed the error. The final launcher explicitly supplies PYTHONPATH
and asserts the exact local package path before collecting tests. No installed
source was patched to obtain green.

## Deliberate limits and next decision

This is a bounded syntax matcher, not a general provenance solver. It requires
the fresh record/fake/patch/exercise sequence, a direct unconditional production
boundary assignment, a simple completed-process stub and literal dictionary
equality. Module scopes containing arbitrary executable statements or constants,
decorated definitions, helper-mediated calls, record aliases/transformations,
string patch targets, conditional calls and fixture-defined fakes are not newly
supported. Existing legacy mapping outside recognized evidence remains unchanged.

Only Python 3.11 full gates and additional Python 3.14 focused checks ran here;
the full 3.12/3.13 CI matrix, council review and fieldkit gate remain unverified.
No claim is made that fieldkit's real gate now passes. Independent Python review
must assess conservatism and maintainability before proposing any adoption.

OpenSpec validates this delta after adding a missing scenario to its metric-policy
requirement. It also warns that the existing main quality-assessment spec has
requirements outside its main Requirements section and would prevent archive.
That pre-existing structural issue was not repaired; address it separately before
any future authorized archive.

No push, PR, issue, release, merge, dependency adoption or policy waiver occurred.
