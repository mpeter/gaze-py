# Design: o3-docscan

## Module structure

```
src/gaze_py/analysis/docscan.py     # new — DocEntry, scan_docs(), _find_repo_root()
src/gaze_py/config/loader.py        # modified — 3 new GazeConfig fields
src/gaze_py/classify/engine.py      # modified — project_docs_text in __init__
src/gaze_py/analysis/runner.py      # modified — docs_text kwarg on detect_and_classify
src/gaze_py/cli/main.py             # modified — docscan command real; analyze/crap wired
tests/test_docscan.py               # new
tests/testdata/docscan/             # new — fixture .md files
```

## docscan.py

```python
@dataclass(frozen=True)
class DocEntry:
    path: Path
    content: str
    priority: int

def _find_repo_root(start: Path) -> Path:
    """Walk up from start to find pyproject.toml or .git sentinel."""

def _matches_any(rel: str, patterns: list[str]) -> bool:
    """Return True if rel matches any fnmatch pattern."""

def scan_docs(root: Path, config: GazeConfig) -> list[DocEntry]:
    """Discover .md files under repo root, apply filters, assign priority."""
```

Timeout: use `threading.Timer` to set a `stop_event`. The walk loop checks
`stop_event.is_set()` on each iteration. No SIGALRM (not portable on Windows
or in threads).

Priority rule: `p.parent == root` → 1, `p.parent == repo_root` → 2, else → 3.
When `root == repo_root`, all files in root get priority 1.

## Classification engine change

Minimal change to `ClassificationEngine.__init__`:

```python
def __init__(
    self,
    contractual_threshold: int = 80,
    incidental_threshold: int = 50,
    project_docs_text: str | None = None,
) -> None:
    ...
    self._project_docs_text = project_docs_text
```

In `classify()`, the existing Signal 5 call:
```python
# Before:
docstring_signal(docstring, effect.type)
# After:
combined = (docstring or "") + ("\n" + self._project_docs_text if self._project_docs_text else "")
docstring_signal(combined or None, effect.type)
```

Note: `docstring_signal` accepts `str | None`. If the combined string is
non-empty, pass it. If both docstring and project_docs_text are None/empty,
pass None (current behavior preserved).

## runner.py change

```python
def detect_and_classify(
    src_path: Path,
    *,
    config: GazeConfig,
    target_func: str | None = None,
    docs_text: str | None = None,       # new kwarg
) -> list[FunctionTarget]:
    engine = ClassificationEngine(
        config.contractual_threshold,
        config.incidental_threshold,
        project_docs_text=docs_text,    # new
    )
    ...
```

## cli/main.py — docscan command

Replace lines 732–753 (the stub) with:

```python
@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "text"]))
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
@click.option("--exclude", "extra_excludes", multiple=True)
@click.option("--include", "extra_includes", multiple=True)
@click.option("--timeout", "timeout", default=None, type=float)
def docscan(path, fmt, config_path, extra_excludes, extra_includes, timeout):
    ...
    entries = scan_docs(Path(path), config)
    if fmt == "json":
        click.echo(json.dumps([...], indent=2))
    else:
        for e in entries:
            click.echo(f"[P{e.priority}] {e.path}")
```

## cli/main.py — analyze and crap wiring

In `_run_analyze()` (~line 1152) and `_run_crap()` (~line 1060), before calling
`detect_and_classify()`, add:

```python
import warnings
try:
    from gaze_py.analysis.docscan import scan_docs
    doc_entries = scan_docs(src_path, config)
    docs_text = "\n".join(e.content for e in doc_entries) or None
except Exception as exc:  # noqa: BLE001
    warnings.warn(f"docscan failed, continuing without doc augmentation: {exc}", stacklevel=2)
    docs_text = None

targets = detect_and_classify(src_path, config=config, docs_text=docs_text, ...)
```

The `BLE001` suppression is justified: scan failure must never abort an analysis
run (Principle VI graceful degradation).

## Tests

`tests/testdata/docscan/`:
- `README.md` — contains behavioral keywords ("returns", "writes")
- `CHANGELOG.md` — excluded by default config
- `sub/guide.md` — lower priority

`tests/test_docscan.py`:
- `test_scan_finds_md_files()` — basic discovery
- `test_priority_assignment()` — same-dir=1, root=2, other=3
- `test_exclude_filter()` — CHANGELOG.md excluded
- `test_include_filter()` — only matching files returned
- `test_timeout_returns_partial()` — timeout yields what's found so far
- `test_empty_directory()` — no .md files → empty list
- `test_config_round_trip()` — doc_scan YAML fields parsed correctly
