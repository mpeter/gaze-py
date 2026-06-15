"""Scaffold engine for the `gazepy init` command.

Deploys embedded .opencode agent and command assets into the current project
idempotently. Files are user-owned (skip-if-present) unless --force is given.

Per CR-006: no rich dependency — click.echo() only.
Per CS-016: run() uses keyword-only parameters for 4+ args.
"""

from __future__ import annotations

import dataclasses
from importlib.resources import files
from pathlib import Path

import click

# Anchor for embedded package data via importlib.resources.
# hatchling includes assets/ automatically via packages = ["src/gaze_py"].
_ASSETS = files("gaze_py.cli.assets")

# Relative paths within the assets package → target paths within .opencode/.
# Each tuple is (asset_subpath, target_relative_to_opencode).
_ASSET_MAP: tuple[tuple[str, str], ...] = (
    ("agents/gaze-reporter.md", "agents/gaze-reporter.md"),
    ("commands/gaze.md", "commands/gaze.md"),
)


@dataclasses.dataclass
class Result:
    """Outcome of a scaffold run.

    Attributes:
        created: Relative paths of files written for the first time.
        skipped: Relative paths of files that already existed (no --force).
        overwritten: Relative paths of files overwritten by --force.
    """

    created: list[str] = dataclasses.field(default_factory=list)
    skipped: list[str] = dataclasses.field(default_factory=list)
    overwritten: list[str] = dataclasses.field(default_factory=list)


def _insert_marker(content: bytes, marker: str) -> bytes:
    """Insert a version marker into asset content, with idempotency guard.

    Two insertion paths:
    1. File has YAML frontmatter (starts with '---\\n' and contains '\\n---\\n'):
       insert marker on the line immediately following the closing '---'.
    2. No frontmatter: append marker at end of file.

    If the marker is already present (idempotency guard), return content unchanged.

    Args:
        content: Raw asset bytes.
        marker: Marker string to insert (e.g. '<!-- scaffolded by gazepy 0.2.0 -->\\n').

    Returns:
        Modified content bytes with marker inserted exactly once.
    """
    s = content.decode("utf-8")
    if marker in s:  # idempotency guard — already present
        return content
    if not s.startswith("---\n"):
        # No frontmatter — append at end.
        return content + marker.encode("utf-8")
    close_idx = s[4:].find("\n---\n")
    if close_idx < 0:
        # Malformed frontmatter (no closing ---) — append at end.
        return content + marker.encode("utf-8")
    insert_at = close_idx + 4 + len("\n---\n")
    return (s[:insert_at] + marker + s[insert_at:]).encode("utf-8")


def run(
    target_dir: Path,
    force: bool,
    version: str,
    *,
    stdout: bool = True,
) -> Result:
    """Deploy embedded assets into target_dir idempotently.

    Checks for pyproject.toml in cwd and emits a warning when absent (proceeds
    regardless — mirrors Go gaze go.mod behavior). Each output path is resolved
    and validated to remain inside target_dir via is_relative_to() (structural
    containment, not str.startswith — guards against path-prefix siblings such
    as .opencode_extra/).

    Args:
        target_dir: Absolute path to the .opencode/ directory (or equivalent)
            where assets will be written.
        force: When True, overwrite existing files. When False, skip existing.
        version: gazepy version string embedded in the scaffold marker comment.
        stdout: When True, warnings are emitted via click.echo(err=True).
            Set False in tests to suppress output side-effects on coverage.

    Returns:
        Result dataclass listing created, skipped, and overwritten paths.
    """
    result = Result()

    # Sentinel check: warn when no pyproject.toml in cwd (warning only, not error).
    if not (Path.cwd() / "pyproject.toml").exists():
        if stdout:
            click.echo(
                "Warning: no pyproject.toml found in current directory.\n"
                "gazepy works best in a Python project root.",
                err=True,
            )

    marker = f"<!-- scaffolded by gazepy {version} -->\n"
    guard = target_dir.resolve()

    for asset_rel, target_rel in _ASSET_MAP:
        out_path = target_dir / target_rel

        # Symlink guard: resolve output path; assert it stays within target_dir.
        # Use is_relative_to() (Python 3.9+) — NOT str.startswith() which admits
        # path-prefix siblings (e.g. .opencode_extra/ would bypass startswith).
        resolved = out_path.resolve()
        if not resolved.is_relative_to(guard):
            if stdout:
                click.echo(
                    f"Error: destination {resolved} escapes .opencode/ — refusing to write.",
                    err=True,
                )
            raise SystemExit(1)

        already_exists = out_path.exists()

        # Skip-if-present (user-owned) unless --force.
        if already_exists and not force:
            result.skipped.append(target_rel)
            continue

        # Load asset content from embedded package data.
        asset_bytes = _ASSETS.joinpath(asset_rel).read_bytes()
        final_bytes = _insert_marker(asset_bytes, marker)

        # Ensure parent directory exists.
        out_path.parent.mkdir(parents=True, exist_ok=True)

        out_path.write_bytes(final_bytes)
        out_path.chmod(0o644)

        if already_exists:
            result.overwritten.append(target_rel)
        else:
            result.created.append(target_rel)

    return result
