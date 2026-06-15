# Specs: o3-docscan

## DS-001 — DocEntry model

A `DocEntry` is a frozen dataclass with three fields:
- `path: Path` — absolute path to the discovered document
- `content: str` — full text content of the file
- `priority: int` — 1 (same-package), 2 (repo-root), 3 (other)

## DS-002 — scan_docs() discovery

`scan_docs(root: Path, config: GazeConfig) -> list[DocEntry]`

**Given** a root path and config
**When** `scan_docs()` runs
**Then**:
- Walks the repository root (nearest ancestor containing `pyproject.toml` or
  `.git`) for all `*.md` files
- Applies `config.doc_scan_exclude` glob patterns to filter out matching paths
  (uses `fnmatch` on path relative to repo root; Python's `fnmatch` treats
  `*` as matching any characters including `/`, so `vendor/**` correctly
  excludes nested paths)
- When `config.doc_scan_include` is non-empty, only paths matching at least one
  include pattern are returned
- Returns entries sorted by `(priority, path)` ascending
- Respects `config.doc_scan_timeout` seconds; if scanning exceeds the timeout,
  returns whatever has been collected so far (no exception raised)

## DS-003 — Priority assignment

**Given** a discovered `.md` file at absolute path `p`
**When** priority is assigned
**Then**:
- Priority 1: `p.parent == root` (same directory as `root`, i.e., co-located)
- Priority 2: `p.parent == repo_root` (at the project root level)
- Priority 3: all other paths

## DS-004 — GazeConfig doc_scan fields

`GazeConfig` has three new fields with defaults matching the Go reference:
- `doc_scan_exclude: list[str]` — default:
  `["vendor/**", "node_modules/**", ".git/**", "testdata/**", "CHANGELOG.md", "CONTRIBUTING.md"]`
- `doc_scan_include: list[str]` — default: `[]` (empty = no filter, all included)
- `doc_scan_timeout: float` — default: `30.0` (seconds)

YAML parsing: `classification.doc_scan.exclude`, `.include`, `.timeout`.
Validation: `doc_scan_timeout > 0`; if `<= 0`, raises `GazeConfigError` with
message `"doc_scan.timeout must be positive"` and exits 1.

## DS-005 — Classification engine augmentation

`ClassificationEngine.__init__` gains optional `project_docs_text: str | None = None`.

When `project_docs_text` is provided, Signal 5 (`docstring_signal`) is called
with a combined text string: `(docstring or "") + "\n" + project_docs_text`.
The signal function signature is unchanged — augmentation happens at the call site.

## DS-006 — `detect_and_classify()` wiring

`detect_and_classify()` in `analysis/runner.py` gains optional
`docs_text: str | None = None` parameter (keyword-only).
When provided, it is passed to `ClassificationEngine(project_docs_text=docs_text)`.
Existing callers without `docs_text` are unaffected (defaults to `None`).

## DS-007 — `gazepy docscan` command

**Given** user runs `gazepy docscan [PATH]`
**When** the command executes
**Then**:
- Discovers the repo root from `PATH` (or cwd if omitted)
- Calls `scan_docs(root, config)`
- With `--format=json` (default): emits a JSON array of objects with keys
  `path` (string, relative to cwd), `content` (string), `priority` (int).
  The CLI layer is responsible for converting `DocEntry.path` (absolute `Path`)
  to a cwd-relative string via `str(path.relative_to(cwd))`.
- With `--format=text`: emits two lines per document:
  `[P{priority}] {relative_path}` followed by `  ({word_count} words)`.
  This matches the actual implementation; "blank line separator" described
  in earlier drafts was superseded by the word-count line.
- Exits 0 on success, 1 on error
- Supports `--config`, `--exclude` (repeatable), `--include` (repeatable),
  `--timeout` (float seconds)
- When `--exclude` or `--include` flags are provided, they **replace** (not extend)
  the corresponding config lists. Timeout exits 0 with partial results + warning.

## DS-008 — `gazepy analyze` and `gazepy crap` doc scanning

**Given** user runs `gazepy analyze PATH` or `gazepy crap PATH`
**When** the command runs
**Then**:
- Before calling `detect_and_classify()`, calls `scan_docs(src_path, config)`
- Joins all `DocEntry.content` values into a single `docs_text` string
- Passes `docs_text` to `detect_and_classify()`
- If scanning fails (OSError, timeout), logs a warning to stderr and continues
  without doc augmentation (graceful degradation per Principle VI)
