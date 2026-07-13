"""Document scanner for gaze-py — O3 implementation.

Discovers Markdown files under the repository root, applies include/exclude
filters, assigns priority based on proximity to the analysis root, and
respects a configurable timeout.

Per DS-001 through DS-003 (openspec/changes/o3-docscan/specs.md).
"""

from __future__ import annotations

import fnmatch
import os
import threading
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from gaze_py.config.loader import SENTINELS, GazeConfig


@dataclass(frozen=True)
class DocEntry:
    """A discovered Markdown document with its content and priority.

    Attributes:
        path: Absolute path to the discovered document.
        content: Full text content of the file.
        priority: Proximity priority — 1 (same directory as analysis root),
            2 (repository root), 3 (all other locations).
    """

    path: Path
    content: str
    priority: int


def _find_repo_root(start: Path) -> Path:
    """Walk up from start to find the nearest pyproject.toml or .git sentinel.

    Resolves start to an absolute path before walking. Stops at the first
    ancestor directory that contains pyproject.toml or .git. Returns start
    itself when no sentinel is found (e.g., in a bare temp directory).

    Args:
        start: Path to begin the upward search from. May be a file or
            directory; if a file, the search begins from its parent.

    Returns:
        Absolute path to the repository root directory, or start (resolved)
        when no sentinel is found.
    """
    current = start.resolve()
    if current.is_file():
        current = current.parent

    while True:
        if any((current / s).exists() for s in SENTINELS):
            return current
        parent = current.parent
        if parent == current:  # filesystem root reached
            return start.resolve() if start.resolve().is_dir() else start.resolve().parent
        current = parent


def _matches_any(rel: str, patterns: list[str]) -> bool:
    """Return True if rel matches any of the given fnmatch patterns.

    Matches are attempted against both the full relative path and the
    basename alone, so patterns like "CHANGELOG.md" match regardless of
    directory depth.

    Args:
        rel: Relative path string to test (e.g., "docs/CHANGELOG.md").
        patterns: List of fnmatch glob patterns.

    Returns:
        True when rel (or its basename) matches at least one pattern.
    """
    name = Path(rel).name
    return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat) for pat in patterns)


def _iter_md_files(
    repo_root: Path,
    exclude: list[str],
    stop_event: threading.Event,
) -> Iterator[Path]:
    """Yield .md files under repo_root, pruning excluded directories in-walk.

    Mirrors the Go reference scanner (scanner.go filepath.SkipDir): hidden
    directories (dot-prefixed — .git, .venv, .tox) are never descended, and
    directories matched by an exclude pattern (vendor/**, node_modules/**)
    are pruned before descent rather than filtered file-by-file afterwards.
    The previous rglob approach enumerated everything and filtered late —
    on large repos it burned the entire doc_scan_timeout walking virtualenv
    trees and silently truncated the doc list.

    Directory pruning tests a synthetic child path ('<rel>/_') against the
    exclude patterns so that 'dir/**' patterns prune the directory while
    file patterns like 'CHANGELOG.md' do not. Directories and files are
    visited in sorted order for deterministic output.

    Args:
        repo_root: Repository root to walk.
        exclude: fnmatch exclude patterns (relative to repo_root).
        stop_event: Timeout event — the walk stops when set.

    Yields:
        Absolute Paths of .md files, in deterministic (sorted) walk order.
    """
    for dirpath, dirnames, filenames in os.walk(repo_root):
        if stop_event.is_set():
            return
        rel_dir = Path(dirpath).relative_to(repo_root).as_posix()

        kept: list[str] = []
        for d in sorted(dirnames):
            if d.startswith("."):
                continue
            rel_child = d if rel_dir == "." else f"{rel_dir}/{d}"
            if _matches_any(f"{rel_child}/_", exclude):
                continue
            kept.append(d)
        dirnames[:] = kept

        for fname in sorted(filenames):
            if fname.lower().endswith(".md"):
                yield Path(dirpath) / fname


def scan_docs(root: Path, config: GazeConfig) -> list[DocEntry]:
    """Discover .md files under the repository root and return DocEntry list.

    Walks the repository root (nearest ancestor containing pyproject.toml or
    .git) for all *.md files, pruning hidden and excluded directories during
    the walk (Go reference parity — scanner.go filepath.SkipDir). Applies
    exclude/include filters from config, assigns priority based on proximity
    to root, and respects the configured timeout. On timeout, returns
    whatever has been collected so far without raising, and emits a warning
    that the doc list was truncated.

    Individual file read errors (OSError) are logged as warnings and skipped;
    they do not abort the scan.

    Args:
        root: Analysis root path. Used to determine priority-1 files and to
            locate the repository root via upward sentinel search.
        config: GazeConfig providing doc_scan_exclude, doc_scan_include, and
            doc_scan_timeout values.

    Returns:
        List of DocEntry sorted by (priority, str(path)) ascending.
    """
    root = root.resolve()
    repo_root = _find_repo_root(root)

    # Threading.Event-based timeout — portable across platforms and threads.
    # SIGALRM is Linux-only and unsafe in multi-threaded contexts.
    stop_event = threading.Event()
    timer = threading.Timer(config.doc_scan_timeout, stop_event.set)
    timer.daemon = True
    timer.start()

    entries: list[DocEntry] = []
    try:
        for p in _iter_md_files(repo_root, config.doc_scan_exclude, stop_event):
            if stop_event.is_set():
                break

            rel = p.relative_to(repo_root).as_posix()

            # Apply exclude filter (file-level; directories are pruned in-walk).
            if _matches_any(rel, config.doc_scan_exclude):
                continue

            # Apply include filter (empty = no filter).
            if config.doc_scan_include and not _matches_any(rel, config.doc_scan_include):
                continue

            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                warnings.warn(f"docscan: skipping {p}: {exc}", stacklevel=2)
                continue

            # Priority: 1 = same dir as root, 2 = repo root, 3 = other.
            if p.parent == root:
                priority = 1
            elif p.parent == repo_root:
                priority = 2
            else:
                priority = 3

            entries.append(DocEntry(path=p, content=content, priority=priority))
    finally:
        timer.cancel()

    if stop_event.is_set():
        # Truncation must be visible — a silently shortened doc list changes
        # classification inputs run-to-run (determinism, not just speed).
        warnings.warn(
            f"docscan: timed out after {config.doc_scan_timeout}s —"
            f" doc list truncated at {len(entries)} entries",
            stacklevel=2,
        )

    entries.sort(key=lambda e: (e.priority, str(e.path)))
    return entries
