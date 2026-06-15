---
description: >
  Generate tests and documentation fixes for functions identified by
  gazepy quality analysis, or auto-detect and run the active implementation
  workflow (Speckit/OpenSpec). With arguments: batch remediation.
  Without arguments: detects active workflow and runs /speckit.implement
  or /opsx-apply.
---
<!-- scaffolded by gazepy 0.4.0 -->
<!-- code-review: passed -->

# Command: /gazepy fix

## Description

Dual-mode command. Without arguments, detects the active implementation
workflow (Speckit or OpenSpec) and runs it. With arguments, performs
batch remediation — reads gazepy analysis data, identifies functions
needing tests or documentation, and generates runnable fixes via the
`gazepy-test-generator` agent.

## Usage

```
/gazepy fix                          # auto-detect workflow and implement
/gazepy fix [path]                   # batch test generation
/gazepy fix --strategy=add_tests [path]
/gazepy fix --top=5 [path]
/gazepy fix --dry-run [path]
```

## Options

| Option | Description |
|--------|-------------|
| `[path]` | Python source path (default: `src/`) |
| `--strategy=X` | Filter: `add_tests`, `add_assertions`, `add_docs`, `decompose_and_test` |
| `--top=N` | Process only the top N functions by CRAP score |
| `--dry-run` | Show what would be generated without writing files |

## Instructions

### When no arguments are provided

Detect the active workflow and delegate to the corresponding
implementation command:

1. **Check for a Speckit feature branch**: Run
   `.specify/scripts/bash/check-prerequisites.sh --json --paths-only`
   from the repo root. If it succeeds and returns a `FEATURE_DIR`
   with a `tasks.md`, this is a Speckit strategic workflow.
   Read the full contents of `.opencode/command/speckit.implement.md`
   and execute its instructions directly — follow the implementation
   workflow it describes.

2. **Check for an OpenSpec active change**: Look for directories
   under `openspec/changes/` (excluding `archive/`) that contain a
   `tasks.md` file. If one exists, this is an OpenSpec tactical
   workflow.
   **Validate branch**: Run `git rev-parse --abbrev-ref HEAD`.
   The current branch must be `opsx/<change-name>` where
   `<change-name>` matches the detected change directory name.
   If not on the correct branch, **STOP** with error:
   > "OpenSpec change `<name>` detected but you are on branch
   > `<current-branch>`. Run: `git checkout opsx/<name>`"

   If on the correct branch, read the full contents of
   `.opencode/command/opsx-apply.md` and execute its instructions
   directly.

3. **If neither is detected**: Ask the user using the question tool:

   > No active implementation context detected. Would you like to:
   >
   > - `/speckit.implement` — Strategic spec implementation
   >   (requires a feature branch with `specs/NNN-*/tasks.md`)
   > - `/opsx-apply` — Tactical change implementation
   >   (requires an active change in `openspec/changes/`)
   > - `/gazepy fix src/` — Batch test generation on full source tree

   If the user selects a workflow command, read and execute the
   corresponding command file. If they select batch test generation,
   fall through to the "When arguments are provided" section below
   with `src/` as the path.

### When arguments are provided

#### Step 1: Run gazepy analysis

Resolve the `gazepy` binary: check `uv.lock` first and use
`uv run gazepy`; if not available try `which gazepy`. If neither
resolves, **STOP** with error:
> "`gazepy` binary not found. Install with: `uv tool install gaze-py`"

Run both commands:

```bash
uv run gazepy crap --format=json [path] > /tmp/gazepy-fix-crap.json
uv run gazepy quality --format=json [path] > /tmp/gazepy-fix-quality.json
```

Parse the CRAP JSON for `scores` array — each score has `function`,
`file`, `line`, `fix_strategy`, `crap`, `gaze_crap`, `quadrant`,
`contract_coverage`, `contract_coverage_reason`,
`effect_confidence_range`.

#### Step 2: Build target list

Filter scores to actionable fix strategies:
1. `add_tests` — functions with 0% line coverage
2. `add_assertions` — functions with line coverage but Q3 quadrant
3. `decompose_and_test` — complex functions with 0% coverage
4. Skip `decompose` — not fixable with tests alone

Additionally, check for `add_docs` candidates: functions where
`contract_coverage_reason` is `all_effects_ambiguous` AND
`effect_confidence_range[0]` >= 58 (close enough to push above 70
with improved docstrings).

Apply `--strategy` filter if specified.
Sort by priority: `add_tests` first (by CRAP desc), then
`add_assertions`, then `add_docs`, then `decompose_and_test`.
Apply `--top=N` limit if specified.

If the filtered list is empty, report:
> "No functions need remediation in [path]"
and stop.

#### Step 3: Process each target

For each function in the target list:

1. **Read the function source**: Use the `file` and `line` from the
   CRAP score to read the function implementation.
2. **Read existing tests**: Look for `tests/test_<module>.py` where
   `<module>` is the stem of the source file (e.g., `analysis.py`
   → `tests/test_analysis.py`). Read it if it exists.
3. **Get quality data**: Find the matching entry in the quality JSON
   (match by function name). Extract `Gaps`, `GapHints`,
   `DiscardedReturns`, `DiscardedReturnHints`, `AmbiguousEffects`,
   `UnmappedAssertions`.
4. **Determine action**: Based on fix strategy + quality data:
   - `add_tests` → generate full test function
   - `add_assertions` → add assertions to existing test
   - `add_docs` → add/improve docstring comments
   - `decompose_and_test` → generate test skeleton
   - `decompose` → skip with explanation
5. **Generate code**: Following the quality criteria and convention
   detection rules in the `gazepy-test-generator` agent prompt.
6. **Write code**: Append to the `tests/test_<module>.py` file (or
   modify the source file for `add_docs`). In `--dry-run` mode,
   show the code but don't write.

#### Step 4: Verify

After all generation:

```bash
uv run pytest --tb=short -k "TestName1 or TestName2..."
```

Report any test failures with context. Keep failing tests — a failing
test documents expected behavior and is more valuable than no test.

#### Step 5: Report

```
## /gazepy fix Results

Processed: N functions
- add_tests: X generated
- add_assertions: Y strengthened
- add_docs: Z documented
- decompose_and_test: W skeletons
- decompose: V skipped

Tests: K/X pass

Files modified:
- tests/test_foo.py (2 tests added)
- src/gaze_py/bar.py (docstring improved)
```

## Error Handling

- If `gazepy` binary not found: error with install instructions
  (`uv tool install gaze-py`)
- If analysis produces no actionable targets: report "No functions
  need remediation in [path]"
- If a generated test fails to compile (syntax error): report the
  error, skip that function, continue with others
- If a generated test fails: report the failure, keep the test
  (failing tests are still valuable as documentation of expected
  behavior)
