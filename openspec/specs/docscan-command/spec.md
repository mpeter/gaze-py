# Spec: docscan-command

Capability: Document scanning (`gazepy docscan`) and Signal 5 augmentation.

Sources: DS-001 through DS-008 (`openspec/changes/archive/o3-docscan/specs.md`),
`src/gaze_py/analysis/docscan.py`, `src/gaze_py/cli/main.py`.

---

### Requirement: DocEntry model

A `DocEntry` SHALL be a frozen dataclass with three fields:
- `path: Path` — absolute path to the discovered document
- `content: str` — full text content of the file
- `priority: int` — proximity priority: 1 (same directory as analysis root),
  2 (repository root), 3 (all other locations)

#### Scenario: DocEntry is immutable
- **WHEN** a `DocEntry` is created
- **THEN** it is frozen (attempts to mutate fields raise `FrozenInstanceError`)

---

### Requirement: Repository root detection

`_find_repo_root(start: Path) -> Path` SHALL walk upward from `start` to find
the nearest ancestor directory containing `pyproject.toml` or `.git`. It SHALL
use the same `SENTINELS` frozenset as `gaze_py.config.loader` to keep
detection consistent across the codebase.

#### Scenario: Sentinel found in ancestor
- **WHEN** an ancestor directory contains `pyproject.toml` or `.git`
- **THEN** that ancestor is returned as the repository root

#### Scenario: No sentinel found
- **WHEN** no ancestor up to the filesystem root contains a sentinel
- **THEN** `start` (resolved to absolute) is returned as the fallback root

#### Scenario: Start path is a file
- **WHEN** `start` is a file path rather than a directory
- **THEN** the search begins from `start.parent`

---

### Requirement: scan_docs discovery

`scan_docs(root: Path, config: GazeConfig) -> list[DocEntry]` SHALL:

1. Resolve `root` to an absolute path
2. Locate the repository root via `_find_repo_root(root)`
3. Walk the repository root recursively for all `*.md` files
4. Apply `config.doc_scan_exclude` glob patterns to filter out matching files
5. When `config.doc_scan_include` is non-empty, return only files matching at
   least one include pattern
6. Return entries sorted by `(priority, str(path))` ascending
7. Respect `config.doc_scan_timeout`; on timeout, return whatever has been
   collected so far without raising an exception

Individual file read errors (OSError) SHALL be logged as warnings to stderr
and skipped; they MUST NOT abort the scan.

#### Scenario: Basic discovery
- **WHEN** `scan_docs` is called on a directory containing `.md` files
- **THEN** all non-excluded `.md` files under the repository root are returned
  as `DocEntry` objects

#### Scenario: Exclude filter applied
- **WHEN** `config.doc_scan_exclude` contains `"CHANGELOG.md"`
- **THEN** any file named `CHANGELOG.md` is excluded regardless of directory depth

#### Scenario: Include filter applied
- **WHEN** `config.doc_scan_include` is `["docs/**"]`
- **THEN** only files matching `docs/**` are returned; all others are excluded

#### Scenario: Timeout returns partial results
- **WHEN** scanning exceeds `config.doc_scan_timeout` seconds
- **THEN** the entries collected so far are returned; no exception is raised
  and exit code is 0

#### Scenario: Empty directory
- **WHEN** no `.md` files exist under the repository root
- **THEN** an empty list is returned

---

### Requirement: Priority assignment

Priority SHALL be assigned to each discovered `.md` file as follows:

- **Priority 1**: `p.parent == root` — file is in the same directory as the
  analysis root argument
- **Priority 2**: `p.parent == repo_root` — file is at the repository root
  level (and not priority 1)
- **Priority 3**: all other paths

When `root == repo_root`, all files directly in that directory receive
priority 1.

#### Scenario: Same-directory file
- **WHEN** a `.md` file resides in the same directory as the `root` argument
- **THEN** it receives priority 1

#### Scenario: Repo-root file
- **WHEN** a `.md` file resides directly in the repository root (but not in
  `root` when `root != repo_root`)
- **THEN** it receives priority 2

#### Scenario: Nested file
- **WHEN** a `.md` file resides in a subdirectory that is neither `root` nor
  `repo_root`
- **THEN** it receives priority 3

---

### Requirement: Glob pattern matching

Glob patterns in `doc_scan_exclude` and `doc_scan_include` SHALL be matched
using Python's `fnmatch` module against:

1. The path relative to the repository root (e.g. `"vendor/lib/README.md"`)
2. The basename alone (e.g. `"README.md"`)

A file is matched when either form matches at least one pattern. This means
`"CHANGELOG.md"` matches files named `CHANGELOG.md` at any depth, and
`"vendor/**"` correctly excludes nested paths because Python's `fnmatch`
treats `*` as matching any characters including `/`.

#### Scenario: Basename-only pattern
- **WHEN** the exclude pattern is `"CHANGELOG.md"` (no path separator)
- **THEN** `docs/CHANGELOG.md` is excluded (basename match)

#### Scenario: Glob with double-star
- **WHEN** the exclude pattern is `"vendor/**"`
- **THEN** `vendor/lib/README.md` is excluded (full-path fnmatch match)

---

### Requirement: Default exclude patterns

The default `doc_scan_exclude` list SHALL match the Go reference implementation:

```
vendor/**
node_modules/**
.git/**
testdata/**
CHANGELOG.md
CONTRIBUTING.md
```

These defaults are applied when no `.gaze.yaml` is present and when the
config file does not specify `classification.doc_scan.exclude`.

---

### Requirement: Timeout implementation

The scan timeout SHALL be implemented using `threading.Timer` and a
`threading.Event` stop flag. The walk loop SHALL check `stop_event.is_set()`
on each iteration.

SIGALRM MUST NOT be used. It is Linux-only and unsafe in multi-threaded
contexts.

#### Scenario: Timeout fires mid-scan
- **WHEN** `config.doc_scan_timeout` elapses before all files are visited
- **THEN** the scan loop exits at the next iteration check, collected entries
  are returned, and a warning is emitted to stderr

---

### Requirement: gazepy docscan command

`gazepy docscan [PATH]` SHALL:

1. Discover the repository root from `PATH` (defaults to `.` when omitted)
2. Load config from `.gaze.yaml` (walk-up search) or from `--config` if provided
3. Apply CLI flag overrides (see below)
4. Call `scan_docs(root, config)`
5. Emit results in the requested format
6. Exit 0 on success, 1 on error

**Flags:**
- `--format [json|text]` — output format (default: `json`)
- `--config PATH` — explicit config file path
- `--exclude PATTERN` — repeatable; when provided, **replaces** (not extends)
  `config.doc_scan_exclude`
- `--include PATTERN` — repeatable; when provided, **replaces** (not extends)
  `config.doc_scan_include`
- `--timeout FLOAT` — overrides `config.doc_scan_timeout`

#### Scenario: JSON output (default)
- **WHEN** `gazepy docscan` is run without `--format`
- **THEN** stdout is a JSON array of objects with keys `path` (string,
  cwd-relative when possible), `content` (string), `priority` (int)

#### Scenario: Text output
- **WHEN** `gazepy docscan --format=text` is run
- **THEN** each discovered file is emitted as two lines:
  `[P{priority}] {relative_path}` followed by `  ({word_count} words)`

#### Scenario: CLI exclude replaces config
- **WHEN** `--exclude "docs/internal/**"` is passed
- **THEN** `config.doc_scan_exclude` is set to `["docs/internal/**"]`,
  discarding the config-file value entirely

#### Scenario: Path output is cwd-relative
- **WHEN** a discovered file is under the current working directory
- **THEN** its `path` in JSON output is relative to cwd (not absolute)

---

### Requirement: Signal 5 augmentation via gazepy analyze and gazepy crap

Before calling `detect_and_classify()`, both `gazepy analyze` and
`gazepy crap` SHALL:

1. Call `scan_docs(src_path, config)` to discover project documentation
2. Join all `DocEntry.content` values into a single `docs_text` string
3. Pass `docs_text` to `detect_and_classify()` as the `docs_text` keyword argument

When `docs_text` is provided, `ClassificationEngine` SHALL combine it with
each function's docstring before passing to Signal 5 (`docstring_signal`):

```
combined = (docstring or "") + "\n" + project_docs_text
```

If both docstring and `project_docs_text` are empty/None, Signal 5 receives
`None` (current behavior preserved).

#### Scenario: Doc content augments Signal 5
- **WHEN** project `.md` files contain behavioral keywords (`returns`, `writes`,
  `modifies`, `updates`, `sets`, `persists`, `stores`, `deletes`, `removes`)
- **THEN** those keywords contribute to the Signal 5 score for all functions
  in the analysis run

#### Scenario: Scan failure degrades gracefully
- **WHEN** `scan_docs` raises any exception (OSError, timeout, etc.)
- **THEN** a warning is emitted to stderr and analysis continues without
  doc augmentation; the command does not exit non-zero due to scan failure

#### Scenario: No docs found
- **WHEN** no `.md` files are discovered (empty list returned)
- **THEN** `docs_text` is `None` and Signal 5 falls back to docstring-only
  behavior (unchanged from pre-O3)

---

### Requirement: detect_and_classify docs_text parameter

`detect_and_classify()` in `analysis/runner.py` SHALL accept an optional
keyword-only parameter `docs_text: str | None = None`. When provided, it
SHALL be passed to `ClassificationEngine(project_docs_text=docs_text)`.
Existing callers that do not pass `docs_text` SHALL be unaffected.

#### Scenario: Backward compatibility
- **WHEN** `detect_and_classify()` is called without `docs_text`
- **THEN** behavior is identical to pre-O3 (no doc augmentation)
