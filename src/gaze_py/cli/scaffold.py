"""Scaffold engine for the `gazepy init` command.

Deploys embedded .opencode agent, command, and reference assets into the
current project idempotently. Files are classified as user-owned (skip-if-
present unless --force) or tool-owned (overwrite-on-diff: replaced when
content differs from the embedded version, even without --force).

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
    ("agents/gaze-test-generator.md", "agents/gaze-test-generator.md"),
    ("agents/reviewer-testing.md", "agents/reviewer-testing.md"),
    ("commands/gaze.md", "commands/gaze.md"),
    ("commands/gaze-fix.md", "commands/gaze-fix.md"),
    ("commands/speckit.testreview.md", "commands/speckit.testreview.md"),
    ("references/doc-scoring-model.md", "references/doc-scoring-model.md"),
    ("references/example-report.md", "references/example-report.md"),
)

# Tool-owned paths (relative to .opencode/) use overwrite-on-diff semantics:
# they are replaced when their content differs from the embedded version, even
# without --force. User-owned files use skip-if-present semantics.
#
# Ownership mirrors gaze's isToolOwned() in internal/scaffold/scaffold.go:
# - All references/ files are tool-owned by directory convention.
# - Specific command/agent files are tool-owned by exact match.
_TOOL_OWNED: frozenset[str] = frozenset(
    {
        "agents/gaze-test-generator.md",
        "commands/gaze-fix.md",
        "commands/speckit.testreview.md",
        "references/doc-scoring-model.md",
        "references/example-report.md",
    }
)


@dataclasses.dataclass
class Result:
    """Outcome of a scaffold run.

    Attributes:
        created: Relative paths of files written for the first time.
        skipped: Relative paths of files that already existed (no --force).
        overwritten: Relative paths of files overwritten by --force.
        updated: Relative paths of tool-owned files updated due to content
            change (overwrite-on-diff, even without --force).
    """

    created: list[str] = dataclasses.field(default_factory=list)
    skipped: list[str] = dataclasses.field(default_factory=list)
    overwritten: list[str] = dataclasses.field(default_factory=list)
    updated: list[str] = dataclasses.field(default_factory=list)


def _insert_marker(content: bytes, marker: str) -> bytes:
    """Insert a version marker into asset content, with idempotency guard.

    Two insertion paths:
    1. File has YAML frontmatter (starts with '---\\n' and contains '\\n---\\n'):
       insert marker on the line immediately following the closing '---'.
    2. No frontmatter: append marker at end of file.

    If the marker is already present (idempotency guard), return content unchanged.

    Args:
        content: Raw asset bytes.
        marker: Marker string to insert (e.g. '<!-- scaffolded by gazepy 0.4.1 -->\\n').

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

    Tool-owned files (gaze-test-generator.md, gaze-fix.md,
    speckit.testreview.md, references/) use overwrite-on-diff: they are
    replaced when their content differs from the embedded version even without
    --force. User-owned files (gaze-reporter.md, reviewer-testing.md,
    gaze.md) retain skip-if-present behavior.

    Args:
        target_dir: Absolute path to the .opencode/ directory (or equivalent)
            where assets will be written.
        force: When True, overwrite all existing files. When False, skip
            user-owned files that already exist; still update tool-owned files
            when content differs.
        version: gazepy version string embedded in the scaffold marker comment.
        stdout: When True, warnings are emitted via click.echo(err=True).
            Set False in tests to suppress output side-effects on coverage.

    Returns:
        Result dataclass listing created, skipped, overwritten, and updated paths.
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

        # Load asset content and insert version marker.
        asset_bytes = _ASSETS.joinpath(asset_rel).read_bytes()
        final_bytes = _insert_marker(asset_bytes, marker)

        if already_exists and not force:
            tool_owned = target_rel in _TOOL_OWNED
            if tool_owned:
                # Overwrite-on-diff: update tool-owned file only if content changed.
                existing = out_path.read_bytes()
                if existing == final_bytes:
                    result.skipped.append(target_rel)
                else:
                    out_path.write_bytes(final_bytes)
                    out_path.chmod(0o644)
                    result.updated.append(target_rel)
            else:
                # User-owned: skip without touching the file.
                result.skipped.append(target_rel)
            continue

        # Ensure parent directory exists.
        out_path.parent.mkdir(parents=True, exist_ok=True)

        out_path.write_bytes(final_bytes)
        out_path.chmod(0o644)

        if already_exists:
            result.overwritten.append(target_rel)
        else:
            result.created.append(target_rel)

    return result
