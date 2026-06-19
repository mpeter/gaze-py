# gazepy self-check

Run CRAP analysis on gaze-py's own source (dogfooding).

## Synopsis

```
gazepy self-check [OPTIONS]
```

## Description

Walks up from the current working directory to find the project root (`pyproject.toml`), then runs `gazepy crap` on `src/gaze_py/` within that root.

This command only works inside the gaze-py repository. It exits with code 2 if `src/gaze_py/` is not found relative to the project root.

Use `self-check` to verify that gaze-py's own codebase meets its quality gates — a form of dogfooding.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `text` | Output format |
| `--max-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when CRAPload exceeds this value |
| `--max-gaze-crapload INTEGER` | `0` (no limit) | CI gate: exit 1 when GazeCRAPload exceeds this value |

## When to Use

- Verifying gaze-py's own quality after a change
- As a smoke test after installing from source
- In gaze-py's own CI (not typical for consuming projects)

## Examples

```bash
# Run self-check from inside the gaze-py repo
gazepy self-check

# With CI gate
gazepy self-check --max-crapload 10
```
