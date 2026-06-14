## Why

`gazepy crap --coverprofile` silently returns null CRAP scores for every
function. The path resolver computes coverage lookup keys relative to the
analysis root (e.g. `analysis/complexity.py`), but coverage.py writes
them relative to the project root (e.g. `src/gaze_py/analysis/complexity.py`).
The keys never match, so all coverage lookups return None and CRAP scores
are never computed. The `--coverprofile` flag is completely non-functional
as shipped in v0.2.0.

## What Changes

- `_resolve_line_coverage` in `src/gaze_py/cli/main.py` gains a third
  lookup attempt: the path relative to `Path.cwd()`, tried between the
  existing root-relative attempt and the filename-only fallback.

## Capabilities

### New Capabilities
*(none)*

### Modified Capabilities
- `coverprofile-lookup`: the path resolution strategy for matching
  coverage.py JSON keys to source files gains a cwd-relative fallback.

## Impact

- `src/gaze_py/cli/main.py` — one-line change in `_resolve_line_coverage`
- `tests/test_cli.py` — one regression test added
- No schema changes, no breaking changes
