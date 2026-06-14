## Context

`_resolve_line_coverage` currently tries two keys when looking up coverage
for a file:

1. `rel` — path relative to the analysis root (`analysis/complexity.py`)
2. `py_file.name` — bare filename (`complexity.py`)

coverage.py JSON reports store keys relative to the working directory from
which pytest was run — typically the project root. So for a file at
`/project/src/gaze_py/analysis/complexity.py` with analysis root
`/project/src/gaze_py/`, the key in coverage.json is
`src/gaze_py/analysis/complexity.py` — matching neither attempt 1 nor 2.

## Fix

Add a third lookup: the file path relative to `Path.cwd()`.

```python
# before
pct = coverage_data.get(rel) or coverage_data.get(py_file.name)

# after
cwd_rel: str | None = None
if py_file.is_relative_to(Path.cwd()):
    cwd_rel = str(py_file.relative_to(Path.cwd()))

pct = (
    coverage_data.get(rel)
    or (coverage_data.get(cwd_rel) if cwd_rel else None)
    or coverage_data.get(py_file.name)
)
```

Resolution order (most specific → least specific):
1. Root-relative (`analysis/complexity.py`) — matches when analysis root = cwd
2. Cwd-relative (`src/gaze_py/analysis/complexity.py`) — matches the common
   case where users run `gazepy crap src/mypackage/` from the project root.
   When `py_file` is not under `Path.cwd()` (e.g. absolute path outside the
   project, or unusual layout), `cwd_rel` is `None` and this attempt is
   silently skipped — falling through to filename-only as before.
3. Filename-only (`complexity.py`) — last resort for any remaining edge cases
