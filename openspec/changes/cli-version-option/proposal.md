## Why

The `gazepy` CLI has no way to report its own version. The Click group exposes
only `--help`, and while `__version__` is already imported in `cli/main.py`
(used for `init` scaffolding, and emitted as `gaze_version` in JSON metadata),
nothing surfaces it on the command line.

That gap has silently broken the release pipeline. `.github/workflows/release.yml`
smoke-tests each published artifact with:

```bash
uvx --from "gaze-py==${VER}" gazepy --version 2>/dev/null | grep -q "${VER}"
```

The option does not exist, so the command exits non-zero every time. The step
retries ten times over 300s and fails with *"Smoke test timed out after 300s —
verify manually"*, which reads as PyPI propagation lag.

It is not propagation lag. Verified on the 0.9.0 release (run 30705649358) and
again on 0.9.1: build, PyPI publish, git tag and GitHub release all succeeded,
and each package was live on PyPI immediately. The same failure occurred on
0.8.2's release (run 30542402019). **Three consecutive releases reported a red
publish job for a reason unrelated to publishing.**

The `2>/dev/null` is what made this undiagnosable: it discarded the actual
message, `Error: No such option '--version'`.

## What Changes

- Add `@click.version_option(_version, "-V", "--version", prog_name="gazepy")`
  to the CLI group. Output is `gazepy, version X.Y.Z`.
- Stop discarding stderr in the release smoke test. Capture it, report the last
  error when the retry loop gives up, and fail fast with the output when the
  published artifact *runs* but reports the wrong version — instead of
  retrying as though the package were missing.
- Add `--refresh` to the smoke test's `uvx` invocation so a cached build of a
  previous version cannot satisfy the check.

With `--version` present, the smoke test becomes meaningful for the first
time: it verifies the published artifact reports the version that was tagged,
rather than only proving something installable exists.

## Capabilities

### New Capabilities

- `cli-version`: `gazepy --version` / `-V` reports the installed package
  version and exits 0.

### Modified Capabilities

(none — no existing command's behavior changes)

### Removed Capabilities

(none)

## Impact

- `src/gaze_py/cli/main.py` — one decorator on the group
- `.github/workflows/release.yml` — smoke test error handling
- `tests/test_cli.py` — 3 new tests (both flags, plus a guard on the output
  *shape* the smoke test greps for)
- No analysis behavior changes; no baseline regeneration; PATCH release
