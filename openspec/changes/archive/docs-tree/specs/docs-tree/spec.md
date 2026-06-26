## ADDED Requirements

### Requirement: docs/index.md — navigation root
The docs tree SHALL have an `index.md` at the root that introduces gaze-py, lists the commands, and provides navigation links to all sections (concepts, getting-started, reference).

#### Scenario: User opens docs index
- **WHEN** a user opens `docs/index.md`
- **THEN** they see a one-paragraph description of gaze-py, a list of all CLI commands with one-line descriptions, and links to concepts, getting-started, and reference sections

### Requirement: docs/concepts/side-effects.md — taxonomy reference
The docs tree SHALL have `docs/concepts/side-effects.md` that describes all 38 `SideEffectType` values grouped by tier (P0–P4), their detection status as of the current release (Implemented (AST) or Not implemented), and why side effects matter for test quality.

#### Scenario: Taxonomy table accuracy
- **WHEN** the taxonomy table is rendered
- **THEN** it contains exactly 38 effect types (P0=5, P1=8, P2=10, P3=9, P4=6) and marks each as "Implemented (AST)" or "Not implemented" consistent with the `SideEffectType` enum and `detector.py` coverage

#### Scenario: No Go-specific content
- **WHEN** the content is reviewed
- **THEN** there are no references to goroutines, `go` statements, SSA analysis, or Go standard library patterns — all examples use Python

### Requirement: docs/concepts/scoring.md — CRAP and GazeCRAP
The docs tree SHALL have `docs/concepts/scoring.md` that explains the CRAP formula (C² + C(1-C/B)²), the GazeCRAP extension, what CRAPload is, and how to read the output.

#### Scenario: Formula accuracy
- **WHEN** the CRAP formula is presented
- **THEN** the formula matches the implementation in `src/gaze_py/crap/` with no aspirational extensions not yet implemented

### Requirement: docs/getting-started/installation.md — install guide
The docs tree SHALL have `docs/getting-started/installation.md` covering installation via `uv tool install gaze-py`, `pip install gaze-py`, and from source with `uv sync`.

#### Scenario: Version verification step
- **WHEN** the installation steps are completed
- **THEN** the guide instructs the user to run `gazepy --version` to confirm the installation

### Requirement: docs/getting-started/quickstart.md — first run
The docs tree SHALL have `docs/getting-started/quickstart.md` showing a first run with `gazepy crap` on a sample file, annotated output, and pointers to next steps.

#### Scenario: Example uses text format
- **WHEN** the quickstart shows example output
- **THEN** it uses `--format=text` (the crap command default) and shows how to read each field

### Requirement: docs/reference/cli/<cmd>.md — one page per command
The docs tree SHALL have one reference page per CLI command (analyze, crap, docscan, init, quality, report, schema, self-check). Each page SHALL include: synopsis, description, options table, output format description, and a usage example.

#### Scenario: Options match --help
- **WHEN** the options table on any CLI reference page is compared to `gazepy <cmd> --help`
- **THEN** every option listed in `--help` appears in the table with the correct default value

#### Scenario: Stub commands noted
- **WHEN** a command has unimplemented options (e.g., `report --ai`, `crap --baseline`)
- **THEN** the reference page notes the option is present but the capability requires O1/O2 or is not yet implemented

### Requirement: docs/reference/configuration.md — .gaze.yaml reference
The docs tree SHALL have `docs/reference/configuration.md` documenting all supported `.gaze.yaml` keys, their types, defaults, and effect on tool behavior.

#### Scenario: All config keys documented
- **WHEN** the configuration reference is compared to `src/gaze_py/config/`
- **THEN** every key loaded by the config module appears in the reference

### Requirement: docs/reference/glossary.md — canonical terms
The docs tree SHALL have `docs/reference/glossary.md` defining: side effect, contractual effect, incidental effect, CRAP score, GazeCRAP score, CRAPload, contract coverage, tier (P0–P4), AST analysis.

#### Scenario: Terms consistent with codebase
- **WHEN** glossary terms are compared to usage in source and other docs
- **THEN** every term uses the same label used in `SideEffectType`, output JSON, and `--help` text
