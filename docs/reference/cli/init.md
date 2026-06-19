# gazepy init

Scaffold `.opencode` agent and command assets into the current project.

## Synopsis

```
gazepy init [OPTIONS]
```

## Description

Writes gaze-py integration assets into `.opencode/` in the current working directory. These assets include AI agent definitions and slash commands for use with OpenCode.

Warns when no `pyproject.toml` is found in the current directory (assets are still written).

## File Ownership Model

| File | Ownership | Behavior |
|---|---|---|
| `.opencode/agents/gaze-reporter.md` | User-owned | Skipped when it already exists (unless `--force`) |
| `.opencode/agents/reviewer-testing.md` | User-owned | Skipped when it already exists (unless `--force`) |
| `.opencode/commands/gaze.md` | User-owned | Skipped when it already exists (unless `--force`) |
| `.opencode/agents/gaze-test-generator.md` | Tool-owned | Updated when content changes |
| `.opencode/commands/gaze-fix.md` | Tool-owned | Updated when content changes |
| `.opencode/commands/speckit.testreview.md` | Tool-owned | Updated when content changes |
| `.opencode/references/doc-scoring-model.md` | Tool-owned | Updated when content changes |
| `.opencode/references/example-report.md` | Tool-owned | Updated when content changes |

User-owned files are configuration entry points you customize for your project. Tool-owned files are updated automatically by gaze-py when their content changes — local edits will be overwritten.

## Options

| Option | Default | Description |
|---|---|---|
| `--force` | off | Overwrite existing user-owned files |

## Examples

```bash
# Initialize in the current project
cd my-python-project
gazepy init

# Re-initialize, overwriting user-owned files
gazepy init --force
```
