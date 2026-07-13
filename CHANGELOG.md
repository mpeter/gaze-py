# Changelog

All notable changes to gaze-py are documented here.

## [Unreleased]

### Added

- **Frontier detectors for four "Defined" taxonomy types** (EC-001 / audit
  G1c) — first detection anywhere; these types are specified in
  taxonomy-reference.md but undetected by the reference Go implementation:
  - **GeneratorYield** (P1): `yield` / `yield from` in sync generators
  - **AsyncGeneratorYield** (P2): `yield` in async generators
  - **ImportSideEffect** (P2): deferred imports inside function bodies —
    module top-level code executes at call time
  - **ResourceManagement** (P2): generic context-manager acquisition
    (`with open(...)`, `async with client.session()`); param-based
    with-items keep their specific MutexOp / DatabaseTransaction /
    WaitGroupOp effects
  - **MonkeyPatch** (P2): attribute replacement on from-imported names
    (`Cls.method = fake`) and dotted chains rooted at imported modules
    (`mod.Cls.method = fake`). Single-level module attributes
    (`os.getcwd = fake`) stay GlobalMutation for Go parity.

### Fixed

- **Quality pipeline classified without project docs text** (O3 parity):
  `gazepy analyze`/`crap` augment Signal 5 with scanned project docs, but
  `assess()` (the `quality` command) classified the same effects without
  them — so the same effect could be contractual under `analyze` and
  ambiguous under `quality`. Go's quality path consumes classifications
  attached by the docs-aware analysis pipeline; `assess()` now scans docs
  via the shared `project_docs_text()` helper and threads them into
  `detect_and_classify`.
- **Strategy 3 pairing never fired for class-based or packaged tests**:
  `_pair_astroid` reconstructed the test's FQN from its file path, which
  dropped the enclosing `Test*` class and any package prefix (a `tests/`
  directory with `__init__.py`) — astroid graph keys look like
  `tests.test_mod.TestCase.test_x`, so the lookup missed and the transitive
  call-graph strategy silently paired nothing. Start keys are now located by
  matching graph keys directly (last component == test name, file stem among
  the key's components), with BFS seeded from all matches in sorted order.
- **Astroid graph had no cross-file edges when gaze-py runs as a console
  script**: astroid resolves a test file's `from pkg.mod import fn` via
  `sys.path`; the analyzed project's root is only on `sys.path` by accident
  (e.g. `python` from the repo root). Run as an installed CLI from any other
  directory, every cross-file inference failed and Strategy 3 produced zero
  test→source pairings. `_build_astroid_graph` now temporarily prepends each
  analyzed file's project root (pyproject.toml / setup.py markers) to
  `sys.path` during the build and restores it afterwards. Combined with the
  FQN fix above, test-target pairing on fieldkit-cmd went from 48.3% to
  86.7% (1060 → 1902 of 2194 tests).
- **Per-effect classification restored in JSON output** (OC-002 / audit G2):
  the runner previously classified every effect but kept only the last
  result in a single per-function slot, and JSON emitted no classification
  at all. Each `SideEffect` now carries its own `classification` —
  serialized as `{label, confidence, signals}` and omitted when
  classification has not run, matching Go's schema exactly. The legacy
  per-function slot is no longer populated.
- **Classification context threaded through the runner** (audit G3): the
  analyze/crap path now passes the function docstring, class bases, return
  type hint, and receiver into the classification engine — Signals 1
  (interface), 2 (visibility), and 5 (docstring) previously ran blind in
  this path despite being implemented and tested. The quality pipeline
  (contract coverage) now reuses the attached classification instead of
  re-classifying without context or project docs text.
- **DatabaseWrite on locally-constructed connections** — `con =
  sqlite3.connect(...)` followed by `con.execute()`/`con.commit()` (and
  cursors derived via `.cursor()`) emitted no effect; detection previously
  fired only when the connection was a function parameter. Tracked DBAPI
  modules: sqlite3, psycopg/psycopg2, pymysql, MySQLdb, cx_Oracle, duckdb,
  mariadb.
- **GlobalMutation via imported-module attribute assignment** —
  monkeypatch-style `os.getcwd = fake` emitted no effect; module objects are
  process-global state. Parameter names shadowing module names are excluded.

### Performance

- **Astroid call-graph state survives across quality runs** (audit P3):
  `_build_astroid_graph` called `MANAGER.clear_cache()` on every invocation,
  evicting astroid's builtins/stdlib bootstrap modules and forcing a
  multi-second rebuild of inference state per `assess()` call. Eviction is
  now targeted at the analyzed files only — matched by resolved path AND
  module name, so a same-named fixture at a different path can never serve
  stale content (pinned by new staleness tests). The graph build is also
  lazy: it runs only when name/call-site pairing (Strategies 1–2) leaves a
  test unpaired. gaze-py's own suite drops from 2:24 to 0:36 (4×).
- **Classification engine no longer re-scans project docs per side effect** —
  `ClassificationEngine` previously concatenated the entire O3 doc-scan text
  onto the per-function docstring and lowercased + keyword-scanned the blob
  for every classified effect (O(effects × docs_bytes)). Docs keywords are
  now precomputed once at engine construction and unioned with per-docstring
  hits. On a 212-file / 5.9 MB-docs repo, `gazepy crap` drops from 4:35 to
  0:22 (12.4×) with byte-identical output.
- **docscan prunes excluded directories during the walk** (audit P2): the
  scanner previously enumerated every `.md` under the repo root via rglob
  and filtered afterwards — descending `.venv/`, `node_modules/`, `.git/`
  in full, burning the 30s `doc_scan_timeout` on large repos and then
  **silently truncating** the doc list (a run-to-run determinism problem,
  not just speed). The walk now prunes hidden (dot-prefixed) directories
  and `dir/**` exclude patterns before descent, matching the Go reference
  scanner (`filepath.SkipDir`). Behavior change: `.md` files inside hidden
  directories such as `.venv/` were previously **included** as priority-3
  docs (`.venv` was never in the default excludes) — they are now pruned.
  Timeout truncation, if it still occurs, emits a warning.

### Changed

- **Effect taxonomy completed to 48 types** (EC-001): `SideEffectType` now
  defines all 48 types from the porting contract tier table (P0=6 + P1=11 +
  P2=16 + P3=9 + P4=6), adding the 10 types marked "Defined" in
  taxonomy-reference.md: ErrorSignal (P0); GeneratorYield, ContainerMutation,
  StreamOutput (P1); AsyncGeneratorYield, MetaprogrammingMutation,
  DescriptorEffect, ResourceManagement, ImportSideEffect, MonkeyPatch (P2).
  Definitions only — these types are not yet detected by the reference Go
  implementation either; detection follows separately. AGENTS.md's prior
  "38 types / documentation bug" claim contradicted the contract and has been
  amended per its own contracts-first rule. JSON schema is unaffected (the
  `side_effects` array is not enum-restricted).

## [0.7.2] — 2026-07-07

### Fixed

- **Vertex token fetch** — `gcloud auth print-access-token` now returns a plain
  token string in current gcloud versions; the legacy `--format=json` flag and
  JSON parsing (`token`/`token_expiry` fields) have been removed. Token TTL is
  now derived from a 55-minute constant rather than the (absent) expiry field.

## [0.7.1] — 2026-07-07

### Fixed

- Re-release patch: `v0.7.0` git tag was pushed without triggering the PyPI
  publish workflow. No functional changes from `0.7.0`.

## [0.7.0] — 2026-06-25

### Breaking Changes

- **JSON output schema — `functions` → `results`** (OC-002 / FR-001): The
  top-level key in `gazepy analyze` and `gazepy crap` JSON output has been
  renamed from `"functions"` to `"results"`. Any consumer parsing `data["functions"]`
  must be updated to `data["results"]`.

- **`FunctionTarget` now nested under `"target"` wrapper** (OC-002 / FR-002):
  Each result entry no longer exposes `name`, `file_path`, `line`, etc. at the
  top level. They are now wrapped in a `"target"` sub-object with keys
  `package`, `function`, `receiver`, `signature`, `location`.

  Before:
  ```json
  {"name": "parse", "file_path": "src/parser.py", "line": 12, ...}
  ```
  After:
  ```json
  {"target": {"package": "src/parser.py", "function": "parse", "receiver": null,
              "signature": "def parse(text: str) -> int", "location": "src/parser.py:12"},
   "side_effects": [...], "metadata": {...}, ...}
  ```

- **`"metadata"` object injected per result entry** (OC-002 / FR-003): Each
  result entry now includes a `"metadata"` sub-object with `gaze_version`,
  `warnings`, `duration_ms`, and `timestamp` (RFC3339 Z format). Consumers
  that iterate result entries by key index must account for the new key.

- **Quality JSON output uses `quality_reports`/`quality_summary` envelope**
  (OC-002 / FR-004): `gazepy quality` JSON output top-level keys changed from
  a bare array to `{"quality_reports": [...], "quality_summary": {...}}`.

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
