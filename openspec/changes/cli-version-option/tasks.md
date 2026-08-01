<!-- All tasks are sequential; no [P] markers. -->

## 1. Diagnose

- [x] 1.1 Confirm the CLI group exposes only `--help` (`cli/main.py:72`) and has no version option
- [x] 1.2 Confirm `_version` is already imported and used (`init` scaffolding; `gaze_version` in JSON metadata)
- [x] 1.3 Reproduce: `uvx --from gaze-py==0.9.0 gazepy --version` → `Error: No such option '--version'`
- [x] 1.4 Confirm publishing itself is healthy — 0.9.0 run 30705649358 shows Build, Publish to PyPI, git tag and GitHub release all green; only the smoke test failed. Same on 0.9.1 and on 0.8.2 (run 30542402019)
- [x] 1.5 Confirm the artifacts were live on PyPI immediately, so "propagation lag" was never the cause

## 2. Implement

- [x] 2.1 Add `@click.version_option(_version, "-V", "--version", prog_name="gazepy")` to the group
- [x] 2.2 Capture stderr in the smoke test instead of `2>/dev/null`; report the last error on timeout
- [x] 2.3 Fail fast when the artifact runs but reports the wrong version
- [x] 2.4 Add `--refresh` so a cached earlier build cannot satisfy the check

## 3. Tests

- [x] 3.1 `--version` and `-V` both exit 0 and contain the version (parametrized)
- [x] 3.2 Output shape guard: the version appears as a standalone token, matching the workflow's `grep -q`

## 4. Gates

- [x] 4.1 `ruff check` / `ruff format --check` — clean, 63 files
- [x] 4.2 `mypy --strict src/` — success, 42 source files
- [x] 4.3 `pytest -m "not slow" --cov-fail-under=85` — **1120 passed, 95.50%**
- [x] 4.4 End-to-end: ran the workflow's exact smoke-test logic against the built 0.9.2 wheel → `gazepy, version 0.9.2`, grep matches
- [ ] 4.5 `/review-council`

## 5. Release 0.9.2

- [x] 5.1 CHANGELOG entry
- [x] 5.2 Version bump — separate commit
- [ ] 5.3 PR, green CI, merge, tag. **This release is the real test**: its smoke test is the first that can pass.
