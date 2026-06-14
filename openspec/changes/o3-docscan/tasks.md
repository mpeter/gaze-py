<!--
  [P] marks tasks eligible for parallel execution.
-->

## Phase 1 — Config

- [ ] 1.1 In `src/gaze_py/config/loader.py`, add three new fields to `GazeConfig`:
      ```python
      doc_scan_exclude: list[str] = field(default_factory=lambda: [
          "vendor/**", "node_modules/**", ".git/**",
          "testdata/**", "CHANGELOG.md", "CONTRIBUTING.md",
      ])
      doc_scan_include: list[str] = field(default_factory=list)
      doc_scan_timeout: float = 30.0
      ```
      Note: `GazeConfig` is a plain `@dataclass` (not frozen). Use
      `dataclasses.field(default_factory=...)` for the list fields.
      Import `field` from `dataclasses`.

      In `_build_config()`, parse `classification.doc_scan` YAML block:
      - `exclude` → list of strings (default list if missing)
      - `include` → list of strings (default empty if missing)
      - `timeout` → float seconds (default 30.0 if missing)

      In `_validate()`, add: `if cfg.doc_scan_timeout <= 0: raise GazeConfigError(...)`.

      Update the `GazeConfig` docstring to document the three new fields.

      Verify: `uv run mypy --strict src/` passes.

## Phase 2 — Scanner module

- [ ] 2.1 Create `src/gaze_py/analysis/docscan.py` with:

      ```python
      @dataclass(frozen=True)
      class DocEntry:
          path: Path
          content: str
          priority: int
      ```

      `_find_repo_root(start: Path) -> Path`:
      - Walk up from `start` (resolve first)
      - Stop at first ancestor containing `pyproject.toml` or `.git`
      - Return that ancestor; if never found, return `start`

      `_matches_any(rel: str, patterns: list[str]) -> bool`:
      - Return True if `fnmatch.fnmatch(rel, pattern)` is True for any pattern
      - Also match basename alone: `fnmatch.fnmatch(Path(rel).name, pattern)`

      `scan_docs(root: Path, config: GazeConfig) -> list[DocEntry]`:
      - `repo_root = _find_repo_root(root)`
      - Use `threading.Event` for timeout; start a `threading.Timer` that
        sets the event after `config.doc_scan_timeout` seconds
      - Walk `repo_root.rglob("*.md")`; on each file, check the stop event
      - For each `.md` file:
        - Compute `rel = str(p.relative_to(repo_root))`
        - Skip if `_matches_any(rel, config.doc_scan_exclude)` is True
        - Skip if `config.doc_scan_include` is non-empty and
          `not _matches_any(rel, config.doc_scan_include)`
        - Read content with `p.read_text(encoding="utf-8", errors="replace")`
        - Priority: 1 if `p.parent == root`, 2 if `p.parent == repo_root`, else 3
        - Append `DocEntry(path=p, content=content, priority=priority)`
      - Cancel the timer; sort entries by `(priority, str(path))`; return

      Handle `OSError` on individual file reads: skip the file with a
      `warnings.warn()`, do not abort the entire scan.

      Verify: `uv run mypy --strict src/gaze_py/analysis/docscan.py` passes.

## Phase 3 — Engine and runner wiring [P]

- [ ] 3.1 [P] In `src/gaze_py/classify/engine.py`, add `project_docs_text: str | None = None`
      to `ClassificationEngine.__init__()` (keyword-only after existing params).
      Store as `self._project_docs_text`.

      In `classify()`, find the `docstring_signal(...)` call and update it:
      ```python
      _combined_doc = (docstring or "") + (
          "\n" + self._project_docs_text if self._project_docs_text else ""
      )
      docstring_signal(_combined_doc if _combined_doc.strip() else None, effect.type)
      ```

      Update the `ClassificationEngine.__init__` docstring.

      Verify: `uv run mypy --strict src/` passes.

- [ ] 3.2 [P] In `src/gaze_py/analysis/runner.py`, add `docs_text: str | None = None`
      as a keyword-only parameter to `detect_and_classify()`.
      Pass it to `ClassificationEngine(project_docs_text=docs_text)`.
      Update the function docstring.

      Verify: `uv run mypy --strict src/` passes.

## Phase 4 — CLI changes

- [ ] 4.1 In `src/gaze_py/cli/main.py`, replace the `docscan` command stub
      (currently at the `# docscan command (not yet implemented — requires O3)`
      section) with a real implementation:

      - Import `scan_docs` from `gaze_py.analysis.docscan` (inline import at
        module level is fine; follow existing import ordering).
      - Add `DocEntry` to the import if needed for type annotations.
      - Command signature:
        ```
        gazepy docscan [PATH] [--format json|text] [--config PATH]
                       [--exclude GLOB]... [--include GLOB]... [--timeout FLOAT]
        ```
      - `PATH` defaults to `.`
      - `--exclude`/`--include` are `multiple=True` options; if provided, they
        REPLACE (not extend) the config's exclude/include lists.
      - `--timeout` overrides `config.doc_scan_timeout` if provided.
      - JSON output: a list of dicts with keys `path` (str, relative to cwd),
        `content` (str), `priority` (int). Use `json.dumps(..., indent=2)`.
      - Text output: one line per entry: `[P{priority}] {relative_path}`,
        followed by the word count: `  ({len(content.split())} words)`.
      - Exit 0 on success, 1 on error (wrap in try/except, `click.echo` error
        to stderr, `raise SystemExit(1)`).

- [ ] 4.2 In `src/gaze_py/cli/main.py`, wire doc scanning into `_run_analyze()`
      and `_run_crap()`:

      Before the `detect_and_classify()` call in each function, add:
      ```python
      import warnings
      _docs_text: str | None = None
      try:
          from gaze_py.analysis.docscan import scan_docs as _scan_docs
          _doc_entries = _scan_docs(src_path, config)
          _joined = "\n".join(e.content for e in _doc_entries)
          _docs_text = _joined if _joined.strip() else None
      except Exception as _exc:  # noqa: BLE001
          warnings.warn(
              f"docscan failed, continuing without doc augmentation: {_exc}",
              stacklevel=2,
          )
      ```
      Then pass `docs_text=_docs_text` to `detect_and_classify()`.

      Note: the inline import inside the try block is required per CR-004
      to prevent a hard import failure from aborting the command. The BLE001
      suppression is justified: scan failure must never abort analysis.

      Verify: `uv run mypy --strict src/` passes.

## Phase 5 — Tests and testdata [P]

- [ ] 5.1 [P] Create testdata fixtures under `tests/testdata/docscan/`:
      - `README.md` — content with behavioral keywords: "This function returns
        the total count. It writes to the database. It raises ValueError when
        input is invalid."
      - `CHANGELOG.md` — content: "## v1.0.0\n- Initial release"
        (should be excluded by default config)
      - `sub/guide.md` — content: "Architecture guide. The service modifies
        state on each call." (priority 3)

- [ ] 5.2 [P] Create `tests/test_docscan.py` with:
      - `test_scan_finds_md_files(tmp_path)` — create 2 .md files in tmp_path,
        call `scan_docs(tmp_path, GazeConfig())`, assert 2 entries returned
      - `test_priority_assignment(tmp_path)` — create files at root, same-dir,
        and subdirectory levels; assert correct priority values
      - `test_exclude_filter(tmp_path)` — create `CHANGELOG.md` and
        `README.md`; assert CHANGELOG.md is excluded with default config
      - `test_include_filter(tmp_path)` — create `README.md` and `guide.md`;
        use include=["README.md"]; assert only README.md returned
      - `test_empty_directory(tmp_path)` — no .md files; assert returns []
      - `test_scan_docs_returns_sorted(tmp_path)` — assert entries sorted by
        (priority, path)
      - `test_config_doc_scan_fields()` — parse YAML with doc_scan block;
        assert fields populated correctly on GazeConfig
      - `test_doc_scan_timeout_validation()` — GazeConfig(doc_scan_timeout=0)
        passed to load: assert GazeConfigError raised (via _validate)

- [ ] 5.3 [P] Update `tests/test_cli.py` — add a test that `gazepy docscan`
      exits 0 and produces valid JSON output (use `CliRunner` and the existing
      test pattern in the file). Assert the JSON is a list and each element
      has `path`, `content`, `priority` keys.

## Phase 6 — CI gate

- [ ] 6.1 Run full CI gate:
      ```bash
      uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85
      ```
      All commands must exit 0.
