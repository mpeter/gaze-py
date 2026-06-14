---
agent: gazepy-reporter
description: Run gazepy analysis and report CRAP scores for the current project.
---
<!-- scaffolded by gazepy 0.3.0 -->

# /gazepy

Delegate to the `gazepy-reporter` subagent to run gaze-py analysis and emit
a structured CRAP report.

## Usage

```
/gazepy [mode] [path]
```

**mode** (optional):
- *(omitted)* or `full` — run both `analyze` and `crap`; emit full report
- `crap` — run `crap` only; emit CRAP scores and CRAPload
- `analyze` — run `analyze` only; emit side-effect detection

**path** (optional): directory or file to analyze. Defaults to `src/`.

## Examples

```
/gazepy
/gazepy crap
/gazepy analyze src/mypackage/
/gazepy full src/
/gazepy crap src/mypackage/utils.py
```
