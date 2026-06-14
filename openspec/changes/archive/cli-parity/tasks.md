## 0. Pre-flight: Version Bump and Cross-Spec Update

- [x] 0.1 Bump `version` in `pyproject.toml` and `src/gaze_py/__init__.py`
      to `0.2.0` (MAJOR-equivalent for pre-1.0 per convention; two breaking
      changes: `analyze` JSON schema change and `report` CLI signature change)
- [x] 0.2 Add `CHANGELOG.md` entry documenting breaking changes: `analyze` no
      longer emits CRAP fields; `report` signature changes from `(src, tests)`
      to `[path]`; `--coverage-json` flag replaced by `--coverprofile` on `crap`
- [x] 0.3 File a note in `openspec/changes/002-deferred-capabilities/design.md`
      that 002-O5 (CI threshold enforcement) must target `crap`, not `analyze`
      (002-O5 design is superseded by this change)

## 1. Refactor `analyze` — strip CRAP, align flags with Go gaze

- [x] 1.1 Rename `_run_pipeline` to `_run_detect_classify`; remove all CRAP
      scoring logic from it; return `list[FunctionTarget]` without Score objects.
      **Disposition of orphaned helpers**: migrate `_score_target` and
      `_build_summary` into `_run_crap()` (task 2.1) — do NOT leave them in
      place as dead code. Verify no remaining callers with grep before commit.
- [x] 1.2 Add `--classify` / `-c`, `--verbose` / `-v`, `--config`,
      `--contractual-threshold`, `--incidental-threshold`, `--function` / `-f`
      (analyze a specific function by name), `--include-unexported` flags to
      `analyze` (exact parity with Go gaze `newAnalyzeCmd`)
- [x] 1.3 Remove `--coverage-json` from `analyze`
- [x] 1.4 Update `analyze` docstring and help text: note that CRAP scoring
      has moved to `gazepy crap`; note format default differs from Go gaze
- [x] 1.5 `analyze` JSON output: wrap result in `AnalysisResult` envelope
      as before; all CRAP-derived fields on `FunctionTarget.score` are `None`
      (not emitted per OC-003 null-not-zero); `Summary.crapload` = `None`,
      `Summary.avg_line_coverage` = `None`, `Summary.recommended_actions` = `None`
- [x] 1.6 Update existing `analyze` tests: remove CRAP field assertions;
      add tests for `--classify`, `--verbose`, `--function`, `--include-unexported`;
      add test verifying CRAP fields are null/absent in analyze JSON output

## 2. Add `crap` command (real implementation)

- [x] 2.1 Implement `_run_crap(path, coverage_data, config, ...)` helper that
      runs detect → classify → score pipeline and returns `AnalysisResult`.
      Migrate `_score_target` and `_build_summary` from their current location
      into this helper (or inline them). Delete the originals after migration.
- [x] 2.2 Implement auto-coverage path: use `sys.executable` (NOT the literal
      string `"python"`) as the interpreter. Wrap in:
      ```
      try:
          subprocess.run([sys.executable, "-m", "pytest", ...], check=True, ...)
          coverage_data = _load_coverage_json(tmp)
      except (subprocess.CalledProcessError, OSError):
          warn + set coverage_data = None
      except Exception:
          warn + set coverage_data = None  # _load_coverage_json parse error
      finally:
          Path(tmp).unlink(missing_ok=True)
      ```
      Emit distinct warnings for subprocess failure vs JSON parse failure.
- [x] 2.3 Implement `--coverprofile` path: reuse `_load_coverage_json` helper;
      rename the flag from `--coverage-json` to `--coverprofile`
- [x] 2.4 Implement CI threshold enforcement: compare `summary.crapload` vs
      `--max-crapload`; print CI summary line to stderr; exit 1 if exceeded.
      For `--max-gaze-crapload`: if non-zero, emit warning to stderr
      ("not enforced until O1") and skip enforcement; exit 0.
- [x] 2.5 Wire `crap` Click command with full flag surface matching Go gaze
      `newCrapCmd`: `PATH`, `--format` (default text), `--coverprofile`,
      `--crap-threshold` (default 15.0), `--gaze-crap-threshold` (default 15.0),
      `--max-crapload` (default 0), `--max-gaze-crapload` (default 0),
      `--ai-mapper` (accepted, ignored), `--ai-mapper-model` (accepted, ignored),
      `--baseline` (stub: exit 1 + "not yet implemented").
      Note: `--config` is NOT on Go gaze's `crap` — do not add it.
- [x] 2.6 Tests (all must be named and independent):
      - `test_crap_coverprofile_path` — unit test with pre-generated JSON
      - `test_crap_subprocess_success` — monkeypatch subprocess.run + write
        valid JSON to tmpfile; assert exit 0 and CRAP fields in output
      - `test_crap_subprocess_calledprocesserror` — monkeypatch raises
        `subprocess.CalledProcessError`; assert exit 0, stderr warns, CRAP computed
        without coverage
      - `test_crap_subprocess_oserror` — monkeypatch raises `OSError`/
        `FileNotFoundError`; assert exit 0, stderr warns, CRAP computed without coverage
      - `test_crap_subprocess_malformed_json` — subprocess writes `{bad json}`
        to tmpfile; assert exit 0, stderr warns, CRAP computed without coverage
      - `test_crap_max_crapload_threshold_exceeded` — exit 1 when exceeded
      - `test_crap_max_crapload_threshold_passed` — exit 0 when not exceeded
      - `test_crap_max_gaze_crapload_warns_and_passes` — non-zero
        `--max-gaze-crapload` emits warning to stderr; exit 0
      - `test_crap_gaze_crap_threshold_accepted_silently` — invoke with
        `--gaze-crap-threshold 5.0`; assert exit 0 and no stderr output
      - `test_crap_coverprofile_missing_file` — invoke with `--coverprofile /nonexistent`;
        assert exit 2 with error message
      - `test_crap_coverprofile_malformed` — invoke with `--coverprofile` pointing
        to `{bad json}`; assert exit 2 with error message
      - `test_crap_baseline_stub` — invoke `crap <path> --baseline /tmp/x`;
        assert exit 1 with "not yet implemented" in stderr (not exit 2)
      - `test_crap_format_json` and `test_crap_format_text`
      - `test_crap_path_does_not_exist` — exit 2 with error message

## 3. Add `quality` stub

- [x] 3.1 Add `quality` Click command with full Go gaze flag surface:
      `PATH`, `--format`, `--target`, `--verbose`, `--include-unexported`,
      `--config`, `--contractual-threshold`, `--incidental-threshold`,
      `--min-contract-coverage`, `--max-over-specification`,
      `--ai-mapper`, `--ai-mapper-model`
- [x] 3.2 Body: emit "not yet implemented" error to stderr mentioning "O1"
      and "change 002/A"; `raise SystemExit(1)`
- [x] 3.3 Tests:
      - `test_quality_stub_bare_invocation` — exit 1, `"not yet implemented"` in stderr
      - `test_quality_stub_flag_surface` — invoke with `--format json
        --min-contract-coverage 80 /tmp`; assert exit 1 (not 2 = Click parse error)
        and `"O1"` in stderr and `"002/A"` in stderr
      - `test_quality_stub_mentions_o1_not_o3` — assert `"O1" in stderr` and
        `"O3" not in stderr` (guard: quality stub must not copy docscan's O3 message)

## 4. Add `docscan` stub

- [x] 4.1 Add `docscan` Click command with `[PATH]` optional positional and
      `--config` flag matching Go gaze `newDocscanCmd`
- [x] 4.2 Body: emit "not yet implemented" error to stderr mentioning "O3";
      `raise SystemExit(1)`
- [x] 4.3 Tests:
      - `test_docscan_stub_bare_invocation` — exit 1, `"not yet implemented"` in stderr
      - `test_docscan_stub_mentions_o3` — `"O3"` in stderr, `"O1"` NOT in stderr
      - `test_docscan_stub_accepts_config_flag` — invoke with `--config /tmp/x.yaml`;
        assert exit 1 (not 2)

## 5. Refactor `report` to stub with Go gaze signature

- [x] 5.1 Change positional args from `(src, tests)` to optional `[path]`
- [x] 5.2 Add flags matching Go gaze `newReportCmd`: `--ai`, `--model`,
      `--format`, `--coverprofile`, `--max-crapload`, `--max-gaze-crapload`,
      `--min-contract-coverage`, `--ai-timeout`
- [x] 5.3 Body: emit migration-guidance error to stderr (mentions O1+O2 and
      suggests `gazepy crap` for CRAP scoring); `raise SystemExit(1)`
- [x] 5.4 Tests:
      - `test_report_stub_bare_invocation` — exit 1, `"not yet implemented"` in stderr
      - `test_report_stub_mentions_crap_migration` — `"gazepy crap"` in stderr
      - `test_report_stub_accepts_ai_flag` — invoke with `--ai claude /tmp`;
        assert exit 1 (not 2)
      - `test_report_stub_old_two_positional_signature` — invoke with
        `report /some/src /some/tests`; assert exit code 2 (Click parse error —
        `[path]` accepts only one positional arg; second arg produces "Got unexpected
        extra argument" error)

## 6. Add `schema` command

- [x] 6.1 Extract JSON schema string as module-level constant `SCHEMA: str`
      in `src/gaze_py/report/json_formatter.py` if not already a constant
- [x] 6.2 Add `schema` Click command (no args, no flags); body: `click.echo(SCHEMA)`
- [x] 6.3 Tests:
      - `test_schema_exit_0` — exit 0
      - `test_schema_valid_json` — `json.loads(output)` does not raise
      - `test_schema_matches_constant` — `json.loads(output) == json.loads(SCHEMA)`,
        verifying task 6.1 was executed correctly

## 7. Add `self-check` command

- [x] 7.1 Implement `_find_project_root() -> Path` — walk up from `Path.cwd()`;
      check for `pyproject.toml` at each level; terminate when `p.parent == p`
      (filesystem root); emit warning and return `Path.cwd()` if not found.
      If `<root>/src/gaze_py/` does not exist, emit error and exit 2.
- [x] 7.2 Add `self-check` Click command with `--format`, `--max-crapload`,
      `--max-gaze-crapload` flags (matching Go gaze `newSelfCheckCmd`);
      body: call `_find_project_root()`, run `_run_crap()` on
      `<root>/src/gaze_py/`
- [x] 7.3 Tests:
      - `test_selfcheck_root_at_cwd` — pyproject.toml in cwd; assert correct path
      - `test_selfcheck_root_at_depth_1` — pyproject.toml one level up
      - `test_selfcheck_root_at_depth_2` — pyproject.toml two levels up
        (parametrize depths 0, 1, 2)
      - `test_selfcheck_root_not_found` — no pyproject.toml anywhere in chain;
        assert warning emitted to stderr
      - `test_selfcheck_gaze_py_missing` — root found but `src/gaze_py/` absent;
        assert exit 2 with error message
      - `test_selfcheck_max_crapload_flag` — monkeypatch `_run_crap`; verify flag
        passed through

## 8. Add `init` command and scaffold engine

- [x] 8.1 Create `src/gaze_py/cli/assets/` directory with `__init__.py`,
      `agents/gazepy-reporter.md`, and `commands/gazepy.md`
- [x] 8.2 Write `gazepy-reporter.md`: binary resolution (uv run → which →
      install), commands (`gazepy analyze --format=json`, `gazepy crap
      --format=json`), null O1 field handling, emoji formatting contract
      (mode: subagent; mandatory 🔍/📊/🟢🟡🔴⚪/⚠️ markers per UF contract;
      cite `../unbound-force/.opencode/agents/gaze-reporter.md` for reference),
      mode support (full / crap / analyze)
- [x] 8.3 Write `gazepy.md`: `agent: gazepy-reporter` delegation, usage
      `/gazepy [mode] [path]`, examples
- [x] 8.4 Implement `src/gaze_py/cli/scaffold.py`:
      - Asset embedding via `importlib.resources.files("gaze_py.cli.assets")`
      - Two-path version marker insertion (frontmatter present / absent)
        per `_insert_marker()` in design.md
      - Symlink guard: resolve output path; assert under `<cwd>/.opencode/`
      - Skip-if-present logic (user-owned files)
      - `--force` overwrite
      - pyproject.toml sentinel warning (check cwd only)
      - `Result` dataclass: `created: list[str]`, `skipped: list[str]`,
        `overwritten: list[str]`
      - `run(target_dir, force, version, stdout) -> Result`
- [x] 8.5 Add `init` Click command with `--force` flag; delegate to `scaffold.run()`
- [x] 8.6 Verify no `pyproject.toml` changes needed (hatchling includes
      `cli/assets/` automatically via `packages = ["src/gaze_py"]`)
- [x] 8.7 Tests (all in temp directory):
      - `test_init_creates_files` — first run; assert `created` contains both assets
      - `test_init_idempotent_skip` — second run without `--force`; assert
        `skipped` contains both; file content unchanged
      - `test_init_force_overwrites` — modify one file, run with `--force`;
        assert file content reverts to original asset content
      - `test_init_force_does_not_duplicate_version_marker` — `--force` twice;
        assert marker appears exactly once per file
      - `test_init_version_marker_after_frontmatter` — asset with frontmatter;
        assert marker on line immediately following closing `---`, not before it
      - `test_init_version_marker_appended_no_frontmatter` — asset without
        frontmatter; assert marker at end of file
      - `test_init_warns_no_pyproject` — tmpdir without `pyproject.toml`;
        assert warning in stderr; assert exit 0 (warning only)
      - `test_init_rejects_symlink_escape` — symlink `.opencode/` to `/tmp/outside`;
        assert exit 1 with "escapes .opencode/" message
      - `test_init_rejects_opencode_prefix_sibling` — attempt to write to a
        directory named `.opencode_extra/` (path-prefix sibling of `.opencode/`);
        assert `is_relative_to` guard rejects it with exit 1

## 9. CI gate pass

- [x] 9.1 `uv run ruff check . && uv run ruff format --check .`
- [x] 9.2 `uv run mypy src/`
- [x] 9.3 `uv run pytest --cov=gaze_py --cov-fail-under=85`
- [x] 9.4 Confirm version bump from 0.1 above is reflected in all output
      (e.g., `gazepy --version`, JSON output `version` field if present)

<!-- spec-review: passed -->

<!-- code-review: passed -->
