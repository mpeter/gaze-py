## Context

gazepy's CLI currently has two commands that combine responsibilities Go gaze
separates. This change restructures the CLI to match Go gaze's eight-command
surface. The primary complexity is: (1) the `analyze` → `crap` split requires
moving CRAP logic without breaking the underlying pipeline, (2) `crap` needs to
run pytest as a subprocess for coverage collection, and (3) `init` needs a
scaffold engine with embedded assets.

Constraints from convention packs and AGENTS.md:
- No `rich` dependency — `click.echo()` only (CS-009 / CR-006)
- `--strict` mypy throughout
- All new public functions fully typed and documented
- Zero-waste: no orphaned helpers after the refactor
- 85% coverage floor must be maintained

## Goals / Non-Goals

**Goals**
- Exact flag-level parity with Go gaze for every command (cross-referenced
  against `../gaze/cmd/gaze/main.go`)
- `crap` runs pytest internally when no `--coverprofile` provided
- `init` deploys embedded agent + command assets idempotently
- Stubs present the correct `--help` surface and exit 1 with clear messages
- All new code passes ruff, mypy --strict, pytest --cov-fail-under=85

**Non-Goals**
- O1 implementation (quality) — tracked in 002/A
- O2 implementation (AI reports) — tracked in 002
- O3 implementation (docscan) — tracked in future change
- `--interactive` TUI mode — no Python equivalent in scope; flag absent by design
- PyPI publication — tracked in 002/C.1
- UF repo update (adding gazepy to initSubTools) — separate PR after this ships

## Cross-Spec Notes

**002-O5 conflict**: `002-deferred-capabilities/design.md` (O5 section) targets
threshold flags (`--max-crapload`, `--max-gaze-crapload`) on the `analyze`
command. This change removes CRAP scoring from `analyze` entirely — 002-O5's
design is invalidated. Task 9.4 requires filing an explicit update against
002-O5. Future 002/O5 implementation must target `crap`, not `analyze`.

**Porting contracts**: The porting requirements (requirements.md) define
capabilities R1–R5, O1–O7 — they do not specify CLI command names or flag
names. Command-level parity with Go gaze is a deliberate UX/integration choice
beyond what the contracts require, justified by UF integration, shared CI
templates, and agent doc reuse. This choice does not contradict any porting
contract. Constitution Principle V (Porting Contract Supremacy) is satisfied.

## Design

### Module structure after this change

```
src/gaze_py/cli/
├── __init__.py
├── main.py          # all Click commands (expanded from 2 to 8)
├── scaffold.py      # new — scaffold engine for `init`
└── assets/          # new — embedded package data
    ├── __init__.py  # empty, makes assets a package for importlib.resources
    ├── agents/
    │   └── gazepy-reporter.md
    └── commands/
        └── gazepy.md
```

### `analyze` refactor

Remove all CRAP-related logic from the `analyze` Click command. After this
change `analyze` calls `_run_detect_classify()` (renamed from `_run_pipeline`)
which returns `list[FunctionTarget]` without Score objects attached. The JSON
output from `analyze` wraps the list in an `AnalysisResult` envelope, but each
`FunctionTarget.score` is `None` (not emitted in JSON per OC-003 null-not-zero).
The `Summary` block is present but all CRAP-derived fields are `null`: `crapload`,
`avg_line_coverage`, `recommended_actions`, `gaze_crapload`.

**Schema impact**: The analyze JSON output continues to use the same
`AnalysisResult` envelope for schema compatibility, but CRAP fields are null.
This is a breaking change per OC-002 (callers expecting non-null CRAP fields
from `analyze` must migrate to `crap`). See version bump in tasks.md 9.4.

**`_score_target` and `_build_summary` disposition**: These helpers currently
live in `main.py` with `_run_pipeline` as their only caller. After the rename
to `_run_detect_classify`, they MUST be migrated into `_run_crap()` (task 2.1)
or deleted if superseded by a different decomposition. They must NOT be left in
place as dead code — this violates the Zero-Waste Mandate. Task 1.1 explicitly
requires their disposition.

New flags added to `analyze` (matching Go gaze `newAnalyzeCmd` exactly):
- `--classify` / `-c` — run classification engine on detected effects
- `--verbose` / `-v` — full signal breakdown (implies --classify)
- `--config` — path to .gaze.yaml (default: walk-up search)
- `--contractual-threshold INT` — override contractual confidence threshold
- `--incidental-threshold INT` — override incidental confidence threshold
- `--function STRING` / `-f` — analyze a specific function by name
- `--include-unexported` — include underscore-prefixed functions

**Format default**: Keep `--format json` as the Python default (intentional
divergence from Go gaze which defaults to `text`). This is documented as a
deliberate deviation: gazepy is primarily agent-consumed, making JSON the
more useful default. Add a note in `analyze` help text: "(default differs from
Go gaze which defaults to text)".

Removed from `analyze`: `--coverage-json` (moves to `crap` as `--coverprofile`)

### `crap` command

**Flag surface** (matching Go gaze `newCrapCmd` exactly, with Python adaptations):
- `PATH` positional (directory or file; Go gaze uses `[packages...]` import paths)
- `--format text|json` (default text, matching Go gaze)
- `--coverprofile PATH` (Go gaze: `--coverprofile`, renamed from `--coverage-json`)
- `--crap-threshold FLOAT` (default 15.0)
- `--gaze-crap-threshold FLOAT` (default 15.0, silently accepted and ignored
  until O1 ships — no warning emitted; contrast with `--max-gaze-crapload`
  which warns because it is a CI gate users expect to be enforced)
- `--max-crapload INT` (default 0 = no limit)
- `--max-gaze-crapload INT` (default 0 = no limit; accepted, skips enforcement
  with stderr warning until O1 ships)
- `--ai-mapper STRING` (accepted, ignored until O1; no help text for values)
- `--ai-mapper-model STRING` (accepted, ignored until O1)
- `--baseline PATH` (stub: exit 1 + "not yet implemented")
- Note: `--config` is NOT present on Go gaze's `crap` command — do not add it

**`--max-gaze-crapload` graceful degradation**: When `--max-gaze-crapload` is
provided with a non-zero value, emit a warning to stderr:
```
Warning: --max-gaze-crapload is not enforced until O1 (quality assessment)
is implemented. Threshold check skipped.
```
Then exit 0 as if the check passed.

**`_run_crap` signature** (CS-016 — keyword-only for 4+ parameters):
```python
def _run_crap(
    path: Path,
    coverage_data: dict[str, float] | None,
    *,
    config: GazeConfig,
    output_format: str = "text",
    max_crapload: int = 0,
    max_gaze_crapload: int = 0,
) -> AnalysisResult: ...
```

**Coverage acquisition — two paths:**

Path A: `--coverprofile <path>` provided
```python
try:
    coverage_data = _load_coverage_json(coverprofile)
except GazeConfigError as e:
    click.echo(f"Error: {e}", err=True)
    raise SystemExit(2)
```
Reuses the existing `_load_coverage_json` helper. `GazeConfigError` is raised
for missing files and malformed JSON — emit to stderr and exit 2 (user input error).

Path B: no `--coverprofile` (auto-run pytest)
```python
import sys
import subprocess
import tempfile
from pathlib import Path

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    tmp = f.name
try:
    subprocess.run(
        [sys.executable, "-m", "pytest",    # sys.executable = current interpreter
         f"--cov={path}",
         "--cov-report", f"json:{tmp}",
         "-q", "--tb=no"],
        check=True,
        capture_output=True,
    )
    coverage_data = _load_coverage_json(tmp)
except (subprocess.CalledProcessError, OSError):
    # pytest not installed, not found, or exited non-zero
    click.echo(
        "Warning: pytest failed or is not installed — "
        "continuing without coverage data. "
        "Use --coverprofile to provide a pre-generated report.",
        err=True,
    )
    coverage_data = None
except Exception:
    # _load_coverage_json parse error — treat same as coverage failure
    click.echo(
        "Warning: coverage JSON could not be parsed — "
        "continuing without coverage data.",
        err=True,
    )
    coverage_data = None
finally:
    Path(tmp).unlink(missing_ok=True)   # missing_ok avoids masking original exc
```

Note: `sys.executable` guarantees the same interpreter (and virtual environment)
that is running `gazepy`, not whatever `python` resolves to in PATH (which may
be the system Python on Debian/Ubuntu/Alpine or in containers).

**PATH input validation** (before subprocess and analysis):
Resolve and validate the `path` argument before invoking subprocess or analysis:
```python
src = Path(path).resolve()
if not src.exists():
    click.echo(f"Error: path does not exist: {path}", err=True)
    raise SystemExit(2)
```

**CI threshold enforcement:**
After scoring, compare `summary.crapload` against `--max-crapload`. If exceeded,
print a one-line CI summary to stderr and `raise SystemExit(1)`. `--max-gaze-crapload`
is accepted but enforcement is skipped with the warning above.

### Stub commands: `quality`, `docscan`, `report`

Each stub:
1. Accepts the full Go gaze flag surface (so `gazepy quality --help` is
   informative and matches `gaze quality --help`)
2. Emits to stderr:
   ```
   Error: <command> is not yet implemented in gazepy.
          Requires <capability> — tracked in change 002.
          Use Go gaze for full capability: gaze <command> <args>
   ```
3. `raise SystemExit(1)`

`report` stub error message includes migration guidance:
```
Error: report is not yet implemented in gazepy (requires O1+O2).
       Use 'gazepy crap [path]' for CRAP scoring previously available
       via 'gazepy report'.
       Use Go gaze for full AI reports: gaze report [packages] --ai=claude
```

`report` stub signature change: drop `(src, tests)` positional; adopt
`([path])` optional with `--ai`, `--model`, `--format`, `--coverprofile`,
`--max-crapload`, `--max-gaze-crapload`, `--min-contract-coverage`,
`--ai-timeout` flags.

`quality` flag surface (matching Go gaze `newQualityCmd`):
PATH, `--format`, `--target`, `--verbose`, `--include-unexported`, `--config`,
`--contractual-threshold`, `--incidental-threshold`, `--min-contract-coverage`,
`--max-over-specification`, `--ai-mapper`, `--ai-mapper-model`

`docscan` flag surface (matching Go gaze `newDocscanCmd`):
`[PATH]` optional positional, `--config`

### `schema` command

Extract the JSON schema string from `report/json_formatter.py` as a
module-level constant `SCHEMA: str`. The `schema` command simply:
```python
click.echo(SCHEMA)
```
No arguments. No flags. Mirrors `gaze schema` exactly.

### `self-check` command

**`_find_project_root()` algorithm:**
Walk up from `Path.cwd()` checking for `pyproject.toml`. Termination: stop
when `p.parent == p` (filesystem root reached). If not found, emit warning to
stderr and return `Path.cwd()`:
```python
def _find_project_root() -> Path:
    p = Path.cwd()
    while True:
        if (p / "pyproject.toml").exists():
            return p
        parent = p.parent
        if parent == p:  # filesystem root — terminate
            click.echo(
                "Warning: no pyproject.toml found in current directory or "
                "any parent. gazepy self-check works best in a Python "
                "project root.",
                err=True,
            )
            return Path.cwd()
        p = parent
```

Run `_run_crap()` on `<root>/src/gaze_py/` relative to that root. If that
path does not exist, emit:
```
Error: self-check only works within the gaze-py repository (src/gaze_py/ not found).
```
and `raise SystemExit(2)`.

Note: `self-check` is a dogfooding command that targets gaze-py's own source.
A user running it outside the gaze-py repo will see the above error — this is
intentional and documented in the help text.

Flags: `--format`, `--max-crapload`, `--max-gaze-crapload` (matching Go gaze
`newSelfCheckCmd`).

### `init` command + scaffold engine (`scaffold.py`)

**Asset embedding** via `importlib.resources`:
```python
from importlib.resources import files
# Anchor directly at the declared package for clarity
_ASSETS = files("gaze_py.cli.assets")
```

Assets ship as package data. Since `assets/` is inside `src/gaze_py/`, hatchling
includes it automatically via the existing `packages = ["src/gaze_py"]` directive.
No additional `pyproject.toml` changes needed.

**Version marker insertion** (mirrors Go gaze `insertMarkerAfterFrontmatter`):

Two code paths:
1. File has YAML frontmatter (`starts with "---\n"` and contains closing `"\n---\n"`):
   insert `<!-- scaffolded by gazepy <version> -->` on the line immediately
   following the closing `---`.
2. File has no frontmatter: append marker at end of file.

```python
def _insert_marker(content: bytes, marker: str) -> bytes:
    s = content.decode("utf-8")
    if marker in s:                    # idempotency guard — already present
        return content
    if not s.startswith("---\n"):
        return content + marker.encode("utf-8")
    close_idx = s[4:].find("\n---\n")
    if close_idx < 0:
        return content + marker.encode("utf-8")
    insert_at = close_idx + 4 + len("\n---\n")
    return (s[:insert_at] + marker + s[insert_at:]).encode("utf-8")
```

**Symlink guard**: Before writing any file, resolve the output path and assert
it remains under `.opencode/` within cwd. Use `Path.is_relative_to()` (Python 3.11+)
for correct structural containment — NOT `str.startswith()` which admits path-prefix
siblings (e.g., `.opencode_extra/` would bypass a startswith check):
```python
resolved = out_path.resolve()
guard = (Path.cwd() / ".opencode").resolve()
if not resolved.is_relative_to(guard):    # correct: structural containment
    click.echo(
        f"Error: destination {resolved} escapes .opencode/ — refusing to write.",
        err=True,
    )
    raise SystemExit(1)
```

**Ownership and write semantics:**
- All assets in v1 are user-owned (skip-if-present unless `--force`)
- `--force` overwrites all files regardless

**Sentinel and warning:**
Check for `pyproject.toml` in cwd. If absent, emit:
```
Warning: no pyproject.toml found in current directory.
gazepy works best in a Python project root.
```
Then proceed (warning only, not error — mirrors Go gaze go.mod behavior).

**`gazepy-reporter.md` key content decisions:**
- Binary resolution order: `uv run gazepy` (if `uv.lock` present in cwd) →
  `which gazepy` → install instructions
- Commands it runs: `gazepy analyze --format=json <path>` and
  `gazepy crap --format=json <path>` (post this change)
- Explicitly notes null O1 fields (GazeCRAP, quadrant, contract_coverage)
  and instructs the agent to handle them gracefully
- Emoji formatting contract: matches Go gaze reporter (mandatory per UF
  formatting contract defined in `../unbound-force/.opencode/agents/gaze-reporter.md`
  frontmatter — `mode: subagent`, mandatory emoji section markers, severity
  indicators `🟢🟡🔴⚪`, warning prefix `⚠️`)
- `mode: subagent`, `tools: {read: true, bash: true, write: false, edit: false}`

**`gazepy.md` key content decisions:**
- `agent: gazepy-reporter` delegation
- Usage: `/gazepy [mode] [path]` — modes: (none)=full, `crap`, `analyze`
- Default path: `src/` (Python convention; Go gaze defaults to `./...`)

## Coverage Strategy for New Code

| Module / Code Path | Coverage Approach | Test Cases |
|---|---|---|
| `scaffold.py` — frontmatter present path | Direct test with frontmatter asset | `test_init_version_marker_after_frontmatter` |
| `scaffold.py` — no frontmatter path | Direct test with no-frontmatter fixture | `test_init_version_marker_appended` |
| `scaffold.py` — skip-if-present | Run init twice; assert skip on second | `test_init_idempotent` |
| `scaffold.py` — `--force` overwrite | Modify file; run with `--force`; assert original content restored | `test_init_force_overwrites` |
| `scaffold.py` — pyproject.toml missing | tmpdir without pyproject.toml | `test_init_warns_no_pyproject` |
| `scaffold.py` — symlink escape | Symlink `.opencode/` to `/tmp/`; assert exit 1 | `test_init_rejects_symlink_escape` |
| `crap` — subprocess success | monkeypatch subprocess.run + fake JSON | `test_crap_subprocess_success` |
| `crap` — CalledProcessError | monkeypatch subprocess.run to raise | `test_crap_subprocess_calledprocesserror` |
| `crap` — FileNotFoundError | monkeypatch subprocess.run to raise OSError | `test_crap_subprocess_oserror` |
| `crap` — malformed JSON | subprocess writes bad JSON to tmp | `test_crap_subprocess_malformed_json` |
| `crap` — `--max-gaze-crapload` warning | invoke with non-zero value; assert warning | `test_crap_gaze_crapload_warns` |
| `self-check` — at cwd | pyproject.toml in cwd | `test_selfcheck_root_at_cwd` |
| `self-check` — N levels up | pyproject.toml 2 levels up | `test_selfcheck_root_at_depth_2` |
| `self-check` — not found | no pyproject.toml anywhere | `test_selfcheck_root_not_found` |
| `self-check` — src/gaze_py/ missing | root found, path doesn't exist | `test_selfcheck_gaze_py_missing` |
| Stubs — bare invocation | invoke each stub with no args | `test_quality_stub`, etc. |
| Stubs — flag surface correctness | invoke with distinctive flags | `test_quality_accepts_flags`, etc. |

Expected `scaffold.py` branch coverage: ~14 branches, all covered by the above.
85% floor is achievable.

## Migration notes

Callers of `gazepy analyze` that expect CRAP fields in JSON output must switch
to `gazepy crap`. The `analyze` JSON output shape changes — CRAP fields on
`score` are null, and `summary.crapload` is null. Existing `--coverage-json`
flag users must rename to `--coverprofile` on the `crap` command.

The `gazepy report src/ tests/` calling convention is replaced by
`gazepy report [path]` (stub). The old positional signature produces a Click
UsageError (exit 2) with "Got unexpected extra argument". Users should migrate
to `gazepy crap` for CRAP scoring.
