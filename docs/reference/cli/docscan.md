# gazepy docscan

Scan project documentation files under a path.

## Synopsis

```
gazepy docscan [OPTIONS] [PATH]
```

## Description

Discovers `.md` files under the repository root, applies exclude/include filters from `.gaze.yaml` or CLI flags, and emits a list of documents with their priority.

**Priority levels:**
- `1` — same directory as `PATH`
- `2` — repository root
- `3` — other locations

This command is used by the `gazepy report --ai` pipeline to supply relevant documentation context to the AI report generator.

## Options

| Option | Default | Description |
|---|---|---|
| `--format [json\|text]` | `json` | Output format |
| `--config PATH` | walk-up search | Path to `.gaze.yaml` configuration file |
| `--exclude TEXT` | from config | Glob pattern to exclude (repeatable; replaces config excludes when provided) |
| `--include TEXT` | from config | Glob pattern to include (repeatable; replaces config includes when provided) |
| `--timeout FLOAT` | from config (30.0s) | Maximum seconds to spend scanning |

## Output Format

**JSON** (default): Array of document objects with `path` and `priority` fields.

**Text**: One line per document: `<priority>\t<path>`.

## Examples

```bash
# Scan from current directory
gazepy docscan

# Scan from a specific path
gazepy docscan src/mymodule/

# Exclude test fixtures
gazepy docscan --exclude "tests/testdata/**"

# Include only architecture docs
gazepy docscan --include "docs/architecture/**"
```
