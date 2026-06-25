# Changelog

All notable changes to gaze-py are documented here.

## [0.7.0] — 2026-06-25

### Added

- **JSON schema parity with Go gaze** — `gazepy analyze` and `gazepy crap` now
  emit `{"results": [...], "summary": {...}}` with each entry wrapped as
  `{"target": <FunctionTarget>, "side_effects": [...], "metadata": {...}, ...}`.
  `gazepy quality` emits `{"quality_reports": [...], "quality_summary": {...}}`.
- **`--baseline` comparison** — `gazepy crap --baseline <file>` compares current
  CRAP scores against a previous run. Auto-discovered from `.gaze/baseline.json`.
  Exits 1 on regressions or new violations. Configure via `.gaze.yaml`
  `baseline:` section (`file`, `epsilon`, `new_function_threshold`).
- **`gazepy report`** — AI-powered narrative reports via direct HTTP REST calls to
  Ollama (`/api/generate`) or Vertex AI (`rawPredict`, Anthropic Messages format).
  Configure in `.gaze.yaml` `ai:` section or via `GAZEPY_AI_*` env vars.
  Without a configured provider, emits the raw JSON payload to stdout.
- **`gazepy report --model`** — per-invocation model override (takes precedence
  over config file and env vars).
- **`gazepy report --tests`** — optional quality enrichment for GazeCRAP,
  quadrant, and gap hint data in the report payload.
- **`.gaze.yaml` `ai:` section** — `provider`, `model`, `endpoint`, `project`,
  `region`, `timeout` fields for AI report configuration.
- **`GAZEPY_AI_*` env vars** — `GAZEPY_AI_PROVIDER`, `GAZEPY_AI_MODEL`,
  `GAZEPY_AI_ENDPOINT`, `GAZEPY_AI_PROJECT`, `GAZEPY_AI_REGION`,
  `GAZEPY_AI_TIMEOUT`.
- **`gap_hints`** field on `ContractCoverageResult`: `effect_hint` (which effect
  type to add assertions for) and `test_hint` (suggested test name pattern).
- **`FunctionTarget` new fields** — `package`, `receiver`, `signature` populated
  at analysis time. `receiver` is the enclosing class name for methods, `None`
  for module-level functions. `signature` is reconstructed from the AST.
- **`Metadata` per result** — `gaze_version`, `duration_ms`, `timestamp`,
  `warnings` injected at serialization time (OC-003 compliant).
- **`QualitySummary`** — `total_tests`, `average_contract_coverage`,
  `total_over_specifications`, `worst_coverage_tests`, `assertion_detection_confidence`.
- **`OverSpecification`** — `count`, `ratio`, `incidental_assertions`, `suggestions`
  per quality report.
- **`covered_count` and `total_contractual`** on `ContractCoverageResult`.
- **Strategy 3 pairing** via Astroid transitive call graph inference
  (`inference_method: "call_graph_transitive"`, confidence 0.75).
- **`"no_test_coverage"` reason code** on contract coverage for functions with
  effects but no paired test (GazeCRAP remains null — no test = no coverage data).
- **`--tests` option on `gazepy crap`** command.
- **`AssessResult`** return type from `assess()` with `.reports` (test-keyed)
  and `.untested` (production-function-keyed) fields.
- **`build_contract_coverage_map()`** in `quality/pipeline.py`.
- **Python-native detection patterns** — `subprocess.*` as `GoroutineSpawn` (P2);
  `async with param:` as `MutexOp`/`DatabaseTransaction` via `_is_db_context`;
  `atexit.register()` as `GlobalMutation` (P1); `warnings.warn()` as
  `LogWrite` (P2) + `GlobalMutation` (P1); `@lru_cache`/`@cache` decorated
  functions as `GlobalMutation` (P1).
- **`RecoverBehavior` (P3) detection** — `try/except` blocks that suppress or
  recover from exceptions. Handles Python 3.11+ `except*` blocks.
- **`WaitGroupOp` (P3) detection** — `asyncio.gather`, `asyncio.wait`,
  `async with asyncio.TaskGroup()`, `futures.wait(...)`, `threading.Barrier.wait`.
- **`UnsafeMutation` (P4) detection** — ctypes pointer subscript writes and
  `.contents` attribute writes.
- **Docs reference tree** — `docs/reference/cli/` now covers all commands
  (`analyze`, `crap`, `quality`, `docscan`, `report`, `schema`, `self-check`,
  `init`).

### Changed

- **`AnalysisResult.functions` renamed to `AnalysisResult.results`** — all
  internal callers updated. Direct Python callers must update:
  `result.functions` → `result.results`.
- **`FunctionTarget.name` renamed to `FunctionTarget.function`** — serializes
  as `"function"` in JSON per FR-002.
- **`gazepy quality` and `assess()` include private functions by default** —
  underscore-prefixed functions are now included. Use `--no-include-unexported`
  to restore the old behaviour. `gazepy analyze` retains `--include-unexported`
  defaulting to off.
- **`assess()` return type** changed from `list[QualityReport]` to `AssessResult`.
  Update callers: `reports = assess(...)` → `result = assess(...); reports = result.reports`.
- **`with param:` sync connection detection** now uses the shared `_is_db_context`
  helper, aligning sync and async heuristics. `session` is excluded — `with session:`
  now produces `MutexOp` (previously `DatabaseTransaction`).
- **`_matches_cache_decorator` refactored** — extracted as a shared helper,
  eliminating duplicated decorator-matching logic across visitor methods.
- **`--max-gaze-crapload` now enforced** in `crap`, `self-check`, and `report`
  commands. Previously emitted a stale "deferred until O1" warning.

### Removed

- **`gazepy report --ai` flag** — provider is now config-driven (`.gaze.yaml`
  `ai:` section or `GAZEPY_AI_*` env vars). **Migration**: replace
  `--ai ollama --model llama3.2:3b` with `.gaze.yaml`:
  `ai: {provider: ollama, model: llama3.2:3b}`
- **`gazepy report --ai-timeout` flag** — replaced by `ai.timeout` in `.gaze.yaml`
  or `GAZEPY_AI_TIMEOUT` env var.

### Breaking Changes

- **`functions` → `results` top-level key** in `gazepy analyze` / `gazepy crap`
  JSON output. Before: `{"functions": [...]}`. After: `{"results": [...]}`.
- **`target` wrapper** — each result entry now wraps function identity in a
  `"target"` object. Before: `{"name": "foo", "package": "...", ...}`.
  After: `{"target": {"function": "foo", "package": "...", "receiver": null,
  "signature": "def foo()", "location": "..."}, "side_effects": [...], ...}`.
- **`metadata` injection** — each result entry now includes a `"metadata"` object
  (`gaze_version`, `duration_ms`, `timestamp`, `warnings`). Consumers that
  enumerate result keys must handle this new field.
- **`quality_reports` / `quality_summary` envelope** in `gazepy quality` JSON
  output. Before: bare array `[...]`. After:
  `{"quality_reports": [...], "quality_summary": {...}}`.

- Spec: `openspec/changes/archive/quality-pairing-astroid/`

## [0.4.1] — 2026-06-15

### Bug Fixes

- **`gazepy init` scaffold asset names corrected** — `init` now deploys
  `gaze-reporter.md` and `gaze.md` instead of `gazepy-reporter.md` and
  `gazepy.md`, coordinated with the `uf init` sentinel change.

### Improvements

- **`docscan` repo-root detection** — Uses the shared `SENTINELS` frozenset
  from `gaze_py.config.loader` instead of hard-coded filename checks, keeping
  repo-root detection consistent across the codebase.

- Spec: `specs/001-gazepy-init-deploys/`

## [0.4.0] — 2026-06-14

### New Features

- **O3 Document Scanning** — `gazepy docscan` is now a real command. Walks
  the repository for `.md` files, applies glob filtering, assigns proximity
  priority (1=same-dir, 2=repo-root, 3=other), and emits a JSON array of
  `{path, content, priority}` objects or a text summary.
- **Signal 5 augmentation** — `gazepy analyze` and `gazepy crap` now
  automatically scan project docs before analysis. The documentation signal
  (CC-005, Signal 5) incorporates project-level behavioral declarations from
  `.md` files alongside per-function docstrings. Scan failures degrade
  gracefully (warning to stderr, analysis continues).
- **`.gaze.yaml` `doc_scan` config** — new `classification.doc_scan` block
  supports `exclude`, `include`, and `timeout` settings.

### Usage

```bash
# Scan project docs and list discovered files
gazepy docscan

# JSON output (default)
gazepy docscan . --format=json

# Override exclude patterns
gazepy docscan . --exclude "docs/internal/**" --exclude "vendor/**"

# Analyze with doc augmentation (happens automatically)
gazepy analyze src/mypackage/
```

- Spec: `openspec/changes/archive/o3-docscan/`

## [0.3.1] — 2026-06-14

### Bug Fixes / Improvements

- **`effect_confidence_range` now populated** — `Score.effect_confidence_range`
  is no longer always `null`. When all detected effects on a function are
  classified as ambiguous (`reason == "all_effects_ambiguous"`), the field
  is set to `[min_confidence, max_confidence]` (two ints in [0,100]).
  Matches Go gaze reference semantics. In all other cases it remains `null`.
- **Complexity algorithm formally specified** — `analysis/complexity.py`
  algorithm is now locked by 7 new round-trip tests with exact expected
  values. The previous `test_high_complexity_function_greater_than_1`
  (asserted `> 1`) is replaced by `test_high_complexity_function_exact_value`
  (asserts `== 9`).

- Spec: `openspec/changes/archive/effect-confidence-range/`

## [0.3.0] — 2026-06-14

### New Features

- **O1 quality assessment pipeline** — `gazepy quality` is now a real command.
  Pairs test functions to their production targets, detects assertion sites,
  maps assertions to detected side effects, and computes contract coverage.
- **GazeCRAP scores** — `Score.gaze_crap` is now populated when running
  `gazepy quality`. Uses contract coverage (not line coverage) as input to
  the GazeCRAP formula (SC-002).
- **Quadrant classification** — `Score.quadrant` (Q1–Q4) now populated.
- **Contract coverage** — `Score.contract_coverage` (0–100%) now populated.
- **Summary fields** — `gaze_crapload`, `avg_contract_coverage`,
  `quadrant_counts`, `fix_strategy_counts` all now populated.
- **Shared analysis utilities** — `analysis/files.py` and `analysis/runner.py`
  extracted as reusable pipeline primitives.

### Usage

```bash
# Assess test quality and compute GazeCRAP
gazepy quality src/mypackage/ --tests tests/ --format=json

# Auto-discover tests directory
gazepy quality src/mypackage/

# CI gate: fail if average contract coverage below threshold
gazepy quality src/mypackage/ --min-contract-coverage 80
```

- Spec: `openspec/changes/archive/o1-quality-pipeline/`

## [0.2.0] — 2026-06-14

### Breaking Changes

- **`analyze` JSON schema change**: `analyze` no longer emits CRAP scoring
  fields. All CRAP-derived fields in `FunctionTarget` (`line_coverage`, `crap`,
  `gaze_crap`, `fix_strategy`, `quadrant`, `contract_coverage`) are now `null`
  in `analyze` output. `Summary.crapload` is also `null`. Callers that relied
  on non-null CRAP fields from `gazepy analyze` must migrate to `gazepy crap`.

- **`report` CLI signature change**: The `report` command signature changes from
  `gazepy report <src> <tests>` (two positional arguments) to `gazepy report
  [path]` (one optional positional argument). The old two-argument invocation
  produces a Click `UsageError` (exit 2). Use `gazepy crap [path]` for CRAP
  scoring previously available via `gazepy report`.

- **`--coverage-json` flag removed from `analyze`**: The `--coverage-json` flag
  has been removed from `gazepy analyze`. It has moved to `gazepy crap` as
  `--coverprofile`. Update any scripts or agent configs that pass `--coverage-json`
  to `analyze`.

### New Features

- **`gazepy crap` command**: Full CRAP scoring pipeline. Accepts `PATH`
  (directory or file), auto-runs pytest for coverage when no `--coverprofile`
  is provided, enforces `--max-crapload` CI gate (exit 1 on violation).
  Flag surface matches Go gaze `newCrapCmd` exactly.

- **New flags on `gazepy analyze`**: `--classify` / `-c`, `--verbose` / `-v`,
  `--config`, `--contractual-threshold`, `--incidental-threshold`,
  `--function` / `-f`, `--include-unexported`. Achieves flag-level parity
  with Go gaze `newAnalyzeCmd`.

### New Commands

- **`quality` (stub)**: Accepts full Go gaze flag surface. Exits 1 with
  guidance to use Go gaze until O1 (change 002/A) is implemented.
- **`docscan` (stub)**: Accepts `[PATH]` and `--config`. Exits 1 with
  guidance to use Go gaze until O3 is implemented.
- **`schema`**: Emits the JSON schema for the `AnalysisResult` envelope used
  by `analyze` and `crap` output.
- **`self-check`**: Runs CRAP analysis on gaze-py's own source tree
  (`src/gaze_py/`). Walks up from cwd to find the project root via
  `pyproject.toml`. Supports `--format`, `--max-crapload`, and
  `--max-gaze-crapload`.
- **`init`**: Scaffolds `.opencode/agents/gazepy-reporter.md` and
  `.opencode/commands/gazepy.md` into the current project. Idempotent;
  use `--force` to overwrite existing user-owned files.

### Migration Guide

| Old invocation | New invocation |
|---|---|
| `gazepy analyze <path> --coverage-json=cov.json` | `gazepy crap <path> --coverprofile=cov.json` |
| `gazepy report <src> <tests>` | `gazepy crap <src>` |

- Spec: `openspec/changes/archive/cli-parity/`

## [0.1.0] — 2026-06-13

Initial release — Python-native port of the Go gaze GazeCRAP analysis engine.

### Features

- **Side-effect detection engine** — AST-only static analysis of Python source
  files. Detects 38 observable side-effect types across five tiers (P0–P4),
  matching the Go gaze taxonomy exactly (EC-001).
- **CRAP and GazeCRAP scoring** — Implements the CRAP formula
  (complexity² × (1 − coverage)³ + complexity) and the GazeCRAP variant using
  contract coverage instead of line coverage (SC-001, SC-002).
- **Five-signal confidence classification** — Classifies each detected effect
  as contractual or incidental using configurable confidence thresholds.
- **JSON output** — Schema-compatible with the Go gaze implementation.
  Null fields serialize as `null`, not `0.0` or `""` (OC-003).
- **CLI commands**: `analyze` (detect + classify), `report` (two-argument
  positional form: `gazepy report <src> <tests>`).
- **`.gaze.yaml` configuration** — `contractual_threshold` and
  `incidental_threshold` configurable per-project.
- **Python 3.11+** — Tested on CPython 3.11, 3.12, 3.13.

- Spec: _(initial release — predates spec workflow)_
