# gaze-py

gaze-py is a Python static analysis tool that detects observable side effects in Python functions using AST-only analysis, classifies them as contractual or incidental, and computes CRAP and GazeCRAP scores to surface functions most likely to have test coverage gaps.

## Commands

| Command | Description |
|---|---|
| `gazepy analyze` | Detect side effects for a file or directory, optionally with classification |
| `gazepy crap` | Detect side effects and compute CRAP scores |
| `gazepy docscan` | Scan project documentation files |
| `gazepy init` | Scaffold `.opencode` agent and command assets into the current project |
| `gazepy quality` | Assess contract coverage and GazeCRAP scores |
| `gazepy report` | Generate an analysis report |
| `gazepy schema` | Emit the JSON schema for `analyze` and `crap` output |
| `gazepy self-check` | Run CRAP analysis on gaze-py's own source (dogfooding) |

## Documentation

### Concepts

- [Side Effects](concepts/side-effects.md) — the 38-type taxonomy, P0–P4 tiers, and why side effects matter for test quality
- [Scoring](concepts/scoring.md) — CRAP, GazeCRAP, and CRAPload explained

### Getting Started

- [Installation](getting-started/installation.md)
- [Quickstart](getting-started/quickstart.md)

### Reference

- [CLI: analyze](reference/cli/analyze.md)
- [CLI: crap](reference/cli/crap.md)
- [CLI: docscan](reference/cli/docscan.md)
- [CLI: init](reference/cli/init.md)
- [CLI: quality](reference/cli/quality.md)
- [CLI: report](reference/cli/report.md)
- [CLI: schema](reference/cli/schema.md)
- [CLI: self-check](reference/cli/self-check.md)
- [Configuration (.gaze.yaml)](reference/configuration.md)
- [Glossary](reference/glossary.md)
