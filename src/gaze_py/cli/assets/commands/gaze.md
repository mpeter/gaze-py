---
agent: gaze-reporter
description: Run gaze-py analysis and report CRAP scores for the current project.
---

# /gaze

Delegate to the `gaze-reporter` subagent to run gaze-py analysis and emit
a structured CRAP report.

## Usage

```
/gaze [mode] [path]
```

**mode** (optional):
- *(omitted)* or `full` — run both `analyze` and `crap`; emit full report
- `crap` — run `crap` only; emit CRAP scores and CRAPload
- `analyze` — run `analyze` only; emit side-effect detection

**path** (optional): directory or file to analyze. Defaults to `src/`.

## Examples

```
/gaze
/gaze crap
/gaze analyze src/mypackage/
/gaze full src/
/gaze crap src/mypackage/utils.py
```
