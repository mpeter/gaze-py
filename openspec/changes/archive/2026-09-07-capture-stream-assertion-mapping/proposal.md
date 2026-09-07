## Why

Issue #82 reproduces a gap in the mapper: the recommended pytest `capsys` assertion never credits `StdoutWrite`. Real output assertions therefore leave contract coverage understated and can block downstream quality gates.

## What Changes

- Add capture provenance analysis for pytest stdout/stderr assertions using only AST data.
- Preserve stream identity, call/capture ordering and reassignment boundaries; ambiguous captures remain unmapped.
- Integrate the analysis into normal quality reporting and add regression fixtures.
- Document supported patterns and limitations without changing taxonomy, classification, formulas, schemas or thresholds.
- Prepare patch release 0.9.3 with matching package metadata and lockfile; publish only after reviewed merge and verified artifact tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `quality-mapper`: recognize captured stream assertions without crediting unrelated output or double-counting assertions.

## Impact

Quality mapping and its pipeline integration, mapper/pipeline tests and user-facing release notes. No new dependencies or analyzed-code execution. Downstream adoption is a separate reviewed fieldkit-cmd change; this tactical change fixes one upstream bug.
