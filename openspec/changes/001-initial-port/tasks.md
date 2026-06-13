<!--
  [P] marks tasks eligible for parallel execution.
  Add [P] when a task: (a) touches different files from
  other [P] tasks in the group, (b) has no dependency
  on prior tasks in the group, (c) can safely execute
  without ordering constraints.
  Do NOT add [P] when tasks modify the same file —
  parallel workers will cause merge conflicts.
  Tasks without [P] run sequentially first, then [P]
  tasks run in parallel.
-->

## 1. Package Scaffold

- [ ] 1.1 Write `pyproject.toml` — name="gaze-py", hatchling build backend, `requires-python = ">=3.11"`, binary="gazepy", ruff/mypy/pytest config including `norecursedirs = ["tests/testdata"]` and `pythonpath = ["src"]`; `[tool.mypy]` with `strict = true`
- [ ] 1.2 [P] Write `src/gaze/__init__.py` — `__version__ = "0.1.0"` only
- [ ] 1.3 [P] Write all `__init__.py` files with module docstrings: `src/gaze/taxonomy/`, `src/gaze/analysis/`, `src/gaze/classify/`, `src/gaze/classify/signals/`, `src/gaze/crap/`, `src/gaze/config/`, `src/gaze/report/`, `src/gaze/cli/`
- [ ] 1.4 Create `tests/testdata/analysis/` directory structure with `.gitkeep`. Do NOT create `tests/__init__.py` — pytest discovers tests without it in src-layout projects with `pythonpath = ["src"]`
- [ ] 1.5 Run `uv sync` — confirm environment installs cleanly

## 2. Taxonomy Layer

- [ ] 2.1 [P] Write `src/gaze/taxonomy/effects.py` — `SideEffectType` (38-value StrEnum per EC-001 with note about 37-vs-38 contract bug), `Tier` enum, `TIER_MAP: dict[SideEffectType, Tier]`
- [ ] 2.2 [P] Write `src/gaze/taxonomy/models.py` — `@dataclass(frozen=True)` for value objects: `Signal`, `ClassificationResult`, `SideEffect`, `Score`; mutable dataclasses: `FunctionTarget`, `AnalysisResult`; all nullable fields typed `X | None`; include `contract_coverage_reason: str | None = None` on `Score`
- [ ] 2.3 [P] Write `src/gaze/config/loader.py` — `GazeConfig` dataclass, `load_config(start_path: Path) -> GazeConfig` with walk-up discovery, validation raising `GazeConfigError` on out-of-range thresholds, `GazeParseError` exception class

## 3. Taxonomy Tests (EC-001)

- [ ] 3.1 Write `tests/test_taxonomy.py` — EC-001: assert 38 types (with comment referencing the 37-vs-38 contract bug), assert tier counts (P0=5 P1=8 P2=10 P3=9 P4=6), assert all named types present, assert TIER_MAP covers all 38 types; assert `Score` has `contract_coverage_reason` field
- [ ] 3.2 Run `uv run pytest tests/test_taxonomy.py` — MUST pass

## 4. AST Detector (R1)

- [ ] 4.1 Write testdata fixtures (all in `tests/testdata/analysis/`):
  - `pure_function.py` — body `pass`, no annotation
  - `return_value.py` — `return expr` (non-None)
  - `return_value_annotation.py` — `-> Item | None` with `return None` body
  - `error_return.py` — `raise ValueError(...)`
  - `sentinel_error.py` — module-level `class NotFoundError(Exception): pass`
  - `sentinel_error_transitive.py` — `class MyErr(ValueError): pass`
  - `receiver_mutation.py` — `self.x = val`
  - `pointer_arg_mutation.py` — `param[key] = val`
  - `slice_mutation.py` — `param.append(x)`
  - `map_mutation.py` — `param.update({...})`
  - `global_mutation.py` — `global X; X = val`
  - `writer_output.py` — `writer.write(data)` where `writer` is a parameter
  - `http_response_write.py` — `response.write(data)` where `response` is a parameter
  - `channel_send.py` — `import queue; q.put(x)` where `q` is a parameter
  - `channel_close.py` — `q.close()` on a queue parameter
  - `deferred_return_mutation.py` — `finally: result = modified_val; return result`
  - `filesystem_write.py` — `open(path, 'w')`
  - `filesystem_delete.py` — `os.remove(path)`
  - `filesystem_meta.py` — `os.chmod(path, mode)`
  - `db_write.py` — `cursor.execute(sql)`
  - `db_transaction.py` — `with connection: ...` or `connection.begin()`
  - `thread_spawn.py` — `threading.Thread(target=fn).start()` (Note: effect type is `GoroutineSpawn`)
  - `context_cancellation.py` — `task.cancel()`
  - `log_write.py` — `logging.info(...)`
  - `stdout_write.py` — `print(x)`
  - `callback_invoke.py` — `fn_param(arg)` where `fn_param` is a parameter
  - `mutex_op.py` — `with lock: ...` where `lock` is a `threading.Lock` parameter
  - `syntax_error.py` — deliberately invalid Python (for failure mode test)
- [ ] 4.2 Write `tests/test_detector.py` — tests FIRST (red):
  - EC-002: P0 zero tolerance on each fixture (one test per P0 type; NO disjunctive "or" assertions)
  - EC-002: ReturnValue annotation exception scenario
  - EC-002: Explicit `return None` without annotation → no ReturnValue
  - EC-002: Pure function → zero effects
  - EC-002: SentinelError — direct and transitive inheritance
  - EC-002: SentinelError NOT for nested exception class
  - EC-002: Failure mode — `syntax_error.py` raises `GazeParseError`
  - EC-003: Deterministic IDs (analyze twice, compare)
  - EC-003: Stable IDs (relative path used, not absolute)
  - EC-004: All required fields present on every detected effect
  - EC-004: `location` matches `r'.+:\d+:\d+'` (two colons, file:line:col)
  - EC-005: Python-specific effects (ChannelSend, MutexOp, FileSystemMeta, DatabaseTransaction)
  - EC-005: WriterOutput, DeferredReturnMutation detected
  - Panic/ProcessExit: `raise SystemExit` → Panic; `sys.exit()`/`os._exit()`/`os.abort()` → ProcessExit (no overlap)
  - PointerArgMutation vs SliceMutation: item assignment → P0; `.append()` → P1
  - No-op coverage for WaitGroupOp, AtomicOp, RecoverBehavior, UnsafeMutation, SyncPoolOp (assert empty)
- [ ] 4.3 Write `src/gaze/analysis/detector.py` — two-phase scanning:
  (1) module-level pass for SentinelError via top-level ClassDef with transitive base resolution;
  (2) per-function `FunctionVisitor(ast.NodeVisitor)` for all other types;
  `FileDetector.detect(path, *, root: Path, callers: dict[str, int] | None = None) -> list[FunctionTarget]`;
  `GazeParseError` raised on SyntaxError;
  implement all P0 + P1 + feasible P2/P3 types per design.md language mapping table;
  apply ReturnValue heuristic and Panic/ProcessExit disambiguation
- [ ] 4.4 Run `uv run pytest tests/test_detector.py` — MUST pass; `uv run mypy src/gaze/analysis/` — MUST pass

## 5. Classification Engine (R2)

- [ ] 5.1 Write `tests/test_classifier.py` — tests FIRST (red):
  - CC-001: P0 baseline score = 75; P1 = 60; P2-P4 = 50
  - CC-002: Raw score -5 → clamped to 0; raw score 120 → clamped to 100
  - CC-003: Use `@pytest.mark.parametrize` for all 3 label thresholds (contractual/ambiguous/incidental)
  - CC-004: Contradiction signal recorded with `source="contradiction"`, `weight=-20`
  - CC-004: No contradiction when only positive signals
  - CC-005: Interface signal (+30) from ABC subclass method
  - CC-005: Visibility signal (+20) for fully public function
  - CC-005: Caller dependency signal weights (0,+5,+10,+15) via `@pytest.mark.parametrize`
  - CC-005: Naming contractual prefix (+10) and incidental prefix (-10)
  - CC-005: Naming sentinel special case (+30)
  - CC-005: Docstring direct match (+15) using `source="godoc"`
  - CC-005: Docstring indirect match (+5) using `source="godoc_keyword_indirect"`
  - CC-005: Docstring incidental keyword (-15)
  - CC-006: Every signal has `source` (str) and `weight` (int) fields
  - Config failure: `GazeConfigError` raised for `contractual_threshold=150`
- [ ] 5.2 [P] Write `src/gaze/classify/signals/naming.py` — contractual/incidental prefix tables, sentinel special case (+30)
- [ ] 5.3 [P] Write `src/gaze/classify/signals/visibility.py` — exported function (+8), exported return type (+6), exported receiver type (+6), clamped to +20
- [ ] 5.4 [P] Write `src/gaze/classify/signals/docstring.py` — contractual/incidental keyword scan, direct (+15) vs indirect (+5) match; use source IDs `"godoc"` and `"godoc_keyword_indirect"` (NOT "docstring")
- [ ] 5.5 [P] Write `src/gaze/classify/signals/interface.py` — ABC/Protocol base class detection (+30)
- [ ] 5.6 [P] Write `src/gaze/classify/signals/caller.py` — caller count → weight table (0→0, 1→+5, 2-3→+10, 4+→+15)
- [ ] 5.7 Write `src/gaze/classify/engine.py` — `ClassificationEngine.classify(effect, context) -> ClassificationResult`; runs all 5 signals, applies tier boost + contradiction penalty, clamps score [0, 100], assigns label
- [ ] 5.8 Run `uv run pytest tests/test_classifier.py` — MUST pass; `uv run mypy src/gaze/classify/` — MUST pass

## 6. CRAP Scoring (R3 + R4)

- [ ] 6.1 Write `tests/test_scorer.py` — tests FIRST (red):
  - SC-001: Use `@pytest.mark.parametrize` for all 13 reference values from taxonomy-reference.md
  - SC-001: CRAP is null when `line_coverage` is null
  - SC-002: GazeCRAP reference values via `@pytest.mark.parametrize` (same formula, 3+ cases)
  - SC-002: GazeCRAP null when `contract_coverage` is null
  - SC-003: CRAPload counting ([5.0, 10.0, 15.0, 20.0, 30.0] threshold=15 → 3)
  - SC-003: GazeCRAPload null when O1 not run
  - SC-004: All 4 quadrant combinations via `@pytest.mark.parametrize` (Q1/Q2/Q3/Q4)
  - SC-005: Rule 1 wins over default (complexity≥threshold, coverage=0 → decompose_and_test)
  - SC-005: Rule 2 wins over rule 3 (complexity≥threshold, coverage>0, Q3 → decompose)
  - SC-006: Sort order: add_tests before add_assertions before decompose_and_test before decompose
  - SC-006: Cap at 20 entries (25 functions → 20 in output)
- [ ] 6.2 Write `src/gaze/crap/scorer.py` — `crap()`, `gaze_crap()`, `quadrant()`, `fix_strategy()`, `recommended_actions()`, `crapload()`; CRAP returns `None` when `line_coverage is None`; respect SC-005 evaluation order (check complexity rules first, then Q3, then default)
- [ ] 6.3 Run `uv run pytest tests/test_scorer.py` — MUST pass; `uv run mypy src/gaze/crap/` — MUST pass

## 7. Output Formatting (R5)

- [ ] 7.1 Write `tests/test_output.py` — tests FIRST (red):
  - OC-001: `--format=json` → valid JSON; `--format=text` → non-empty non-JSON string
  - OC-002: Required fields present: `side_effects`, `line_coverage`, `crap`, `gaze_crap`, `contract_coverage`, `fix_strategy`, `quadrant`, `recommended_actions`
  - OC-002: No camelCase field names in JSON output
  - OC-003: `line_coverage` is null (NOT 0.0) when coverage not provided
  - OC-003: `crap` is null when `line_coverage` is null
  - OC-003: `gaze_crap` is null, `contract_coverage` is null, `quadrant` is null (O1 not run)
  - OC-003: `contract_coverage_reason` is `"no_effects_detected"` for pure functions
  - OC-001 failure: CLI with invalid path → non-zero exit code and stderr message
- [ ] 7.2 [P] Write `src/gaze/report/json_formatter.py` — `to_json(result: AnalysisResult, *, indent: int = 2) -> str`; use `dataclasses.asdict()` + custom encoder for enums; all OC-002 field names; `None` → JSON `null`; include `contract_coverage_reason`
- [ ] 7.3 [P] Write `src/gaze/report/text_formatter.py` — human-readable summary: function list, CRAP scores, effect counts, fix strategies
- [ ] 7.4 Run `uv run pytest tests/test_output.py` — MUST pass; `uv run mypy src/gaze/report/` — MUST pass

## 8. CLI (R5 continued)

- [ ] 8.1 Write `tests/test_cli.py` — tests FIRST (red), use `click.testing.CliRunner`:
  - `gazepy analyze <testdata_path> --format=json` exits 0, output is valid JSON
  - `gazepy analyze <testdata_path> --format=text` exits 0, output is non-empty
  - `gazepy analyze <testdata_path> --coverage-json <coverage_file>` exits 0
  - `gazepy analyze /nonexistent` exits non-zero, stderr contains error message
  - `gazepy report <src> <tests> --format=json` exits 0
  - `gazepy --help` exits 0
- [ ] 8.2 Write `src/gaze/cli/main.py` — `@click.group() cli`, `analyze` subcommand (path, `--format`, `--coverage-json`), `report` subcommand (src, tests, `--format`); wire detector → classifier → scorer → formatter pipeline; catch `GazeParseError` and emit warning, continue; set `line_coverage=None` when `--coverage-json` not provided
- [ ] 8.3 Run `uv run pytest tests/test_cli.py` — MUST pass; `uv run mypy src/gaze/cli/` — MUST pass

## 9. Full CI Gate

- [ ] 9.1 Run full CI gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze --cov-fail-under=85`; fix any failures
- [ ] 9.2 `rm -rf dist/ && uv build` — confirm wheel named `gaze_py-0.1.0-py3-none-any.whl`
- [ ] 9.3 `uv tool install --force dist/gaze_py-0.1.0-py3-none-any.whl` — confirm `gazepy --help` works from PATH
- [ ] 9.4 Write minimal `README.md` — installation (local wheel only, NOT PyPI), basic usage (`gazepy analyze <path>`), `--coverage-json` flag explanation, Python 3.11+ requirement
- [ ] 9.5 Commit on feature branch `001-initial-port`, push, open PR against `main`
