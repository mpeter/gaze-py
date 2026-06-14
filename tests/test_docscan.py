"""Tests for the O3 document scanner (DS-001 through DS-007).

Covers DocEntry model, scan_docs() discovery, priority assignment, exclude/
include filtering, timeout behaviour, and GazeConfig doc_scan field parsing.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from click.testing import CliRunner

from gaze_py.analysis.docscan import DocEntry, scan_docs
from gaze_py.cli.main import cli
from gaze_py.config.loader import GazeConfig, load_config_explicit
from gaze_py.taxonomy.exceptions import GazeConfigError

# ---------------------------------------------------------------------------
# DS-001 — DocEntry model
# ---------------------------------------------------------------------------


def test_docentry_is_frozen(tmp_path: Path) -> None:
    """DocEntry is a frozen dataclass — mutation raises FrozenInstanceError."""
    entry = DocEntry(path=tmp_path / "README.md", content="hello", priority=1)
    with pytest.raises(FrozenInstanceError):
        entry.priority = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DS-002 — scan_docs() discovery
# ---------------------------------------------------------------------------


def test_scan_finds_md_files(tmp_path: Path) -> None:
    """scan_docs() returns DocEntry for each .md file found (DS-002)."""
    (tmp_path / "README.md").write_text("hello")
    (tmp_path / "guide.md").write_text("world")
    # pyproject.toml makes tmp_path the repo root
    (tmp_path / "pyproject.toml").write_text("")

    config = GazeConfig(doc_scan_exclude=[])
    entries = scan_docs(tmp_path, config)

    paths = {e.path.name for e in entries}
    assert "README.md" in paths
    assert "guide.md" in paths
    assert len(entries) == 2


def test_empty_directory(tmp_path: Path) -> None:
    """scan_docs() returns [] when no .md files exist (DS-002)."""
    (tmp_path / "pyproject.toml").write_text("")
    config = GazeConfig(doc_scan_exclude=[])
    entries = scan_docs(tmp_path, config)
    assert entries == []


def test_scan_docs_returns_sorted(tmp_path: Path) -> None:
    """scan_docs() returns entries sorted by (priority, path) ascending (DS-002)."""
    (tmp_path / "pyproject.toml").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()

    # priority 2 (repo root) — tmp_path is both root and repo_root here,
    # so files directly in tmp_path get priority 1 (same dir as root).
    (tmp_path / "alpha.md").write_text("alpha")
    (tmp_path / "beta.md").write_text("beta")
    (sub / "gamma.md").write_text("gamma")

    config = GazeConfig(doc_scan_exclude=[])
    entries = scan_docs(tmp_path, config)

    # All entries in tmp_path get priority 1 (root == repo_root == tmp_path).
    # sub/gamma.md gets priority 3.
    priorities = [e.priority for e in entries]
    assert priorities == sorted(priorities), "Entries must be sorted by priority"

    # Within same priority, sorted by path string.
    p1_entries = [e for e in entries if e.priority == 1]
    p1_names = [e.path.name for e in p1_entries]
    assert p1_names == sorted(p1_names)


# ---------------------------------------------------------------------------
# DS-003 — Priority assignment
# ---------------------------------------------------------------------------


def test_priority_assignment(tmp_path: Path) -> None:
    """Priority: 1=same-dir-as-root, 2=repo-root, 3=other (DS-003)."""
    # Layout:
    #   tmp_path/          ← repo root (has pyproject.toml)
    #     pyproject.toml
    #     root_doc.md      ← priority 2 (repo root, but root arg is sub/)
    #     sub/
    #       sub_doc.md     ← priority 1 (same dir as root=sub/)
    #       deep/
    #         deep_doc.md  ← priority 3 (other)
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "root_doc.md").write_text("root")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "sub_doc.md").write_text("sub")
    deep = sub / "deep"
    deep.mkdir()
    (deep / "deep_doc.md").write_text("deep")

    config = GazeConfig(doc_scan_exclude=[])
    entries = scan_docs(sub, config)  # root = sub/

    by_name = {e.path.name: e.priority for e in entries}
    assert by_name["sub_doc.md"] == 1, "sub_doc.md should be priority 1 (same dir as root)"
    assert by_name["root_doc.md"] == 2, "root_doc.md should be priority 2 (repo root)"
    assert by_name["deep_doc.md"] == 3, "deep_doc.md should be priority 3 (other)"


# ---------------------------------------------------------------------------
# DS-002 — Exclude filter
# ---------------------------------------------------------------------------


def test_exclude_filter(tmp_path: Path) -> None:
    """CHANGELOG.md is excluded by default config; README.md is not (DS-002)."""
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "README.md").write_text("readme content")
    (tmp_path / "CHANGELOG.md").write_text("## v1.0.0\n- Initial release")

    config = GazeConfig()  # default excludes include CHANGELOG.md
    entries = scan_docs(tmp_path, config)

    names = {e.path.name for e in entries}
    assert "README.md" in names
    assert "CHANGELOG.md" not in names, "CHANGELOG.md must be excluded by default"


def test_exclude_filter_glob_pattern(tmp_path: Path) -> None:
    """Glob patterns in doc_scan_exclude filter matching files (DS-002)."""
    (tmp_path / "pyproject.toml").write_text("")
    sub = tmp_path / "vendor"
    sub.mkdir()
    (sub / "third_party.md").write_text("vendor doc")
    (tmp_path / "README.md").write_text("readme")

    config = GazeConfig(doc_scan_exclude=["vendor/**"])
    entries = scan_docs(tmp_path, config)

    names = {e.path.name for e in entries}
    assert "README.md" in names
    assert "third_party.md" not in names


# ---------------------------------------------------------------------------
# DS-002 — Include filter
# ---------------------------------------------------------------------------


def test_include_filter(tmp_path: Path) -> None:
    """When doc_scan_include is set, only matching files are returned (DS-002)."""
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "README.md").write_text("readme")
    (tmp_path / "guide.md").write_text("guide")

    config = GazeConfig(doc_scan_exclude=[], doc_scan_include=["README.md"])
    entries = scan_docs(tmp_path, config)

    names = {e.path.name for e in entries}
    assert "README.md" in names
    assert "guide.md" not in names, "guide.md must be excluded by include filter"


# ---------------------------------------------------------------------------
# DS-002 — Timeout
# ---------------------------------------------------------------------------


def test_timeout_returns_partial(tmp_path: Path) -> None:
    """scan_docs() returns partial results on timeout without raising (DS-002)."""
    (tmp_path / "pyproject.toml").write_text("")
    # Create enough files that a very short timeout may not process all.
    for i in range(20):
        (tmp_path / f"doc_{i:02d}.md").write_text(f"content {i}")

    # Use a very short timeout — scan should return whatever it found.
    config = GazeConfig(doc_scan_exclude=[], doc_scan_timeout=0.001)
    # Must not raise; result is a list (possibly partial).
    entries = scan_docs(tmp_path, config)
    assert isinstance(entries, list)


# ---------------------------------------------------------------------------
# DS-004 — GazeConfig doc_scan fields
# ---------------------------------------------------------------------------


def test_config_doc_scan_fields(tmp_path: Path) -> None:
    """doc_scan YAML block is parsed into GazeConfig fields (DS-004)."""
    config_file = tmp_path / ".gaze.yaml"
    config_file.write_text(
        "classification:\n"
        "  doc_scan:\n"
        "    exclude:\n"
        "      - vendor/**\n"
        "      - node_modules/**\n"
        "    include:\n"
        "      - README.md\n"
        "    timeout: 10.0\n"
    )

    config = load_config_explicit(config_file)

    assert config.doc_scan_exclude == ["vendor/**", "node_modules/**"]
    assert config.doc_scan_include == ["README.md"]
    assert config.doc_scan_timeout == pytest.approx(10.0)


def test_config_doc_scan_defaults() -> None:
    """GazeConfig() has correct default doc_scan values (DS-004)."""
    config = GazeConfig()
    assert "vendor/**" in config.doc_scan_exclude
    assert "CHANGELOG.md" in config.doc_scan_exclude
    assert config.doc_scan_include == []
    assert config.doc_scan_timeout == pytest.approx(30.0)


def test_doc_scan_timeout_validation(tmp_path: Path) -> None:
    """doc_scan_timeout <= 0 raises GazeConfigError during validation (DS-004)."""
    config_file = tmp_path / ".gaze.yaml"
    config_file.write_text("classification:\n  doc_scan:\n    timeout: 0\n")

    with pytest.raises(GazeConfigError, match="doc_scan_timeout"):
        load_config_explicit(config_file)


# ---------------------------------------------------------------------------
# DS-007 — gazepy docscan CLI command
# ---------------------------------------------------------------------------


def test_docscan_exits_zero_json(tmp_path: Path) -> None:
    """gazepy docscan exits 0 and produces valid JSON array (DS-007)."""
    (tmp_path / "README.md").write_text("readme content")
    (tmp_path / "pyproject.toml").write_text("")

    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--format=json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    for item in payload:
        assert "path" in item
        assert "content" in item
        assert "priority" in item


def test_docscan_json_keys(tmp_path: Path) -> None:
    """docscan JSON output has path (str), content (str), priority (int) (DS-007)."""
    (tmp_path / "README.md").write_text("hello world")
    (tmp_path / "pyproject.toml").write_text("")

    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--format=json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) >= 1
    item = payload[0]
    assert isinstance(item["path"], str)
    assert isinstance(item["content"], str)
    assert isinstance(item["priority"], int)


def test_docscan_text_format(tmp_path: Path) -> None:
    """docscan --format=text emits [P{priority}] lines (DS-007)."""
    (tmp_path / "README.md").write_text("hello world foo bar")
    (tmp_path / "pyproject.toml").write_text("")

    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--format=text"])

    assert result.exit_code == 0, result.output
    assert "[P" in result.output
    assert "words" in result.output


def test_docscan_exclude_option(tmp_path: Path) -> None:
    """--exclude replaces config excludes (DS-007)."""
    (tmp_path / "README.md").write_text("readme")
    (tmp_path / "CHANGELOG.md").write_text("changelog")
    (tmp_path / "pyproject.toml").write_text("")

    runner = CliRunner()
    # Exclude README.md explicitly; CHANGELOG.md should now appear.
    result = runner.invoke(
        cli,
        ["docscan", str(tmp_path), "--format=json", "--exclude=README.md"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    names = [Path(item["path"]).name for item in payload]
    assert "README.md" not in names
    assert "CHANGELOG.md" in names


def test_docscan_empty_directory(tmp_path: Path) -> None:
    """docscan on a directory with no .md files returns empty JSON array (DS-007)."""
    (tmp_path / "pyproject.toml").write_text("")

    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--format=json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == []
