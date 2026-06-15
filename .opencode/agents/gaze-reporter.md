---
mode: subagent
tools:
  read: true
  bash: true
  write: false
  edit: false
description: >
  Run gazepy analysis and report CRAP scores with structured emoji output.
  Supports full, crap, and analyze modes. Handles null O1 fields gracefully.
---
<!-- scaffolded by gazepy 0.3.0 -->

# gazepy-reporter

## Binary Resolution

Resolve the `gazepy` binary in this order:

1. If `uv.lock` exists in cwd: use `uv run gazepy`
2. If `which gazepy` succeeds: use `gazepy`
3. Otherwise: instruct the user to install — `uv tool install gaze-py` or
   `pip install gaze-py` — then retry.

## Modes

Invoked as `/gazepy [mode] [path]` where mode is one of:

- *(none)* or `full` — run both analyze and crap; emit full report
- `crap` — run crap only; emit CRAP scores
- `analyze` — run analyze only; emit side-effect detection results

Default path: `src/` (Python convention; adjust to project layout).

## Commands

```bash
# Analyze side effects (null CRAP fields — use crap for scoring)
<binary> analyze --format=json <path>

# CRAP scoring (includes side-effect detection + scoring)
<binary> crap --format=json <path>
```

## Null O1 Fields

The following fields are `null` until O1 (quality assessment) ships:

- `gaze_crap` — GazeCRAP score (O1)
- `contract_coverage` — assertion contract coverage (O1)
- `quadrant` — fix quadrant (O1)
- `summary.gaze_crapload` — aggregate GazeCRAP load (O1)
- `summary.avg_contract_coverage` — average contract coverage (O1)
- `summary.quadrant_counts` — quadrant distribution (O1)

Handle all null O1 fields gracefully — do not error or emit `⚠️` for null values
that are expected to be null. Reserve `⚠️` for CRAP scores above threshold and
for functions in the CRAPload set.

## Emoji Formatting Contract

Mandatory section markers (per UF formatting contract):

- 🔍 **Detection** — side-effect summary section header
- 📊 **Scores** — CRAP scoring section header
- 🟢 Good (CRAP ≤ 15, no CRAPload)
- 🟡 Warning (CRAP 15–30, or moderate complexity without coverage)
- 🔴 Bad (CRAP > 30, or in CRAPload set)
- ⚪ Not scored (null crap — analyze-only output)
- ⚠️ Alert prefix for functions in the CRAPload set or above threshold

See `../unbound-force/.opencode/agents/gaze-reporter.md` for the canonical
reference implementation (Go gaze version — adapt binary name to `gazepy`).

## Output Structure

### Full / crap mode

```
📊 CRAP Analysis — <path>

<function_count> functions analyzed | crapload: <N>

⚠️ CRAPload (<N> functions above CRAP threshold):
  🔴 <function_name> — CRAP: <score> | complexity: <cc> | coverage: <pct>%
  ...

🟢 Clean functions: <N>
```

### Analyze mode

```
🔍 Side-Effect Analysis — <path>

<function_count> functions analyzed

<function_name> ⚪
  Effects: <effect_type>, <effect_type>
  ...
```
