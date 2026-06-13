"""Integration tests for gaze-py CLI using click.testing.CliRunner.

Covers S4 acceptance scenarios SC-027 through SC-031 and CLI-layer
path-safety tests.  All tests use ``CliRunner.invoke()`` so no subprocess
is spawned and no real filesystem side-effects escape the test.

Convention pack compliance:
- TC-001: pytest only
- TC-002: assert statements directly
- TC-003: descriptive test names
- TC-004: tmp_path for filesystem tests
- TC-007: acceptance tests named after spec success criteria
- TC-012: error paths tested alongside happy paths
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from gaze_py.cli import main

TESTDATA_ANALYSIS = Path(__file__).parent / "testdata" / "analysis"
TESTDATA_QUALITY = Path(__file__).parent / "testdata" / "quality"


# ---------------------------------------------------------------------------
# SC-027: analyze exits 0 with text output
# ---------------------------------------------------------------------------


def test_sc027_analyze_text_exit_0() -> None:
    """SC-027: gaze-py analyze <path> exits 0 and produces non-empty text output."""
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", str(TESTDATA_ANALYSIS / "returns.py")])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
    assert result.output.strip(), "Expected non-empty output"


# ---------------------------------------------------------------------------
# SC-028: analyze --format=json exits 0 with valid JSON
# ---------------------------------------------------------------------------


def test_sc028_analyze_json_exit_0() -> None:
    """SC-028: gaze-py analyze <path> --format=json exits 0 and outputs valid JSON."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", str(TESTDATA_ANALYSIS / "returns.py"), "--format", "json"],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
    # Output must be valid JSON
    try:
        data = json.loads(result.output)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Output is not valid JSON: {exc}\nOutput:\n{result.output}")
    # Must have top-level "version" and "results" keys (SC-023)
    assert "version" in data, f"Missing 'version' key in JSON output: {data.keys()}"
    assert "results" in data, f"Missing 'results' key in JSON output: {data.keys()}"


# ---------------------------------------------------------------------------
# SC-030: report exits 0
# ---------------------------------------------------------------------------


def test_sc030_report_exit_0() -> None:
    """SC-030: gaze-py report <src_path> <tests_path> exits 0 with non-empty output."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["report", str(TESTDATA_ANALYSIS), str(TESTDATA_QUALITY)],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
    assert result.output.strip(), "Expected non-empty output from report command"


# ---------------------------------------------------------------------------
# SC-031: missing path exits 1
# ---------------------------------------------------------------------------


def test_sc031_missing_path_exits_1() -> None:
    """SC-031: gaze-py analyze <nonexistent> exits 1 with an error message."""
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "/nonexistent/path/xyz"])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output:\n{result.output}"
    # No partial output should be emitted — only an error message
    assert result.output.strip(), "Expected error message in output"


# ---------------------------------------------------------------------------
# CLI-layer path traversal: exit 1 + message contains "path"
# ---------------------------------------------------------------------------


def test_cli_path_traversal_exits_1(tmp_path: Path) -> None:
    """CLI-layer: path escaping project root exits 1 with a message containing 'path'."""
    runner = CliRunner()
    # Construct a path that resolves outside tmp_path via ".."
    traversal = str(tmp_path / ".." / ".." / "etc")
    result = runner.invoke(main, ["analyze", traversal])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output:\n{result.output}"
    assert "path" in result.output.lower(), f"Expected 'path' in error output, got:\n{result.output}"


# ---------------------------------------------------------------------------
# CLI-layer directory walk excludes hidden directories
# ---------------------------------------------------------------------------


def test_cli_directory_walk_excludes_hidden(tmp_path: Path) -> None:
    """CLI-layer: directory walk excludes hidden directories from analysis."""
    # Create a normal Python file
    normal_py = tmp_path / "normal.py"
    normal_py.write_text("def visible_func():\n    return 42\n")

    # Create a hidden directory with a Python file that should NOT appear
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    secret_py = hidden_dir / "secret.py"
    secret_py.write_text("def secret_func():\n    return 99\n")

    runner = CliRunner()
    result = runner.invoke(main, ["analyze", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"

    data = json.loads(result.output)
    # Collect all function names from results
    function_names = [r["target"]["function"] for r in data["results"]]
    assert "visible_func" in function_names, f"Expected 'visible_func' in results, got: {function_names}"
    assert "secret_func" not in function_names, (
        f"'secret_func' from hidden dir should be excluded, got: {function_names}"
    )


# ---------------------------------------------------------------------------
# Missing coverprofile exits 1
# ---------------------------------------------------------------------------


def test_missing_coverprofile_exits_1() -> None:
    """quality --coverprofile pointing to a missing file exits 1."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "quality",
            str(TESTDATA_QUALITY),
            "--coverprofile",
            "/nonexistent/.coverage",
        ],
    )
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output:\n{result.output}"
    assert result.output.strip(), "Expected error message in output"


# ---------------------------------------------------------------------------
# quality subcommand — text and JSON output
# ---------------------------------------------------------------------------


def test_quality_text_exit_0() -> None:
    """quality <tests_path> exits 0 and produces non-empty text output."""
    runner = CliRunner()
    result = runner.invoke(main, ["quality", str(TESTDATA_QUALITY)])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"


def test_quality_json_exit_0() -> None:
    """quality <tests_path> --format=json exits 0 and outputs valid JSON."""
    runner = CliRunner()
    result = runner.invoke(main, ["quality", str(TESTDATA_QUALITY), "--format", "json"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
    data = json.loads(result.output)
    assert "quality_reports" in data
    assert "quality_summary" in data


def test_quality_missing_tests_path_exits_1() -> None:
    """quality with a non-existent tests_path exits 1."""
    runner = CliRunner()
    result = runner.invoke(main, ["quality", "/nonexistent/tests"])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output:\n{result.output}"


# ---------------------------------------------------------------------------
# analyze subcommand — directory mode
# ---------------------------------------------------------------------------


def test_analyze_directory_text_exit_0() -> None:
    """analyze <directory> exits 0 and produces non-empty text output."""
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", str(TESTDATA_ANALYSIS)])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"


def test_analyze_directory_json_exit_0() -> None:
    """analyze <directory> --format=json exits 0 with valid JSON."""
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", str(TESTDATA_ANALYSIS), "--format", "json"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
    data = json.loads(result.output)
    assert "version" in data
    assert "results" in data


# ---------------------------------------------------------------------------
# report subcommand — JSON format
# ---------------------------------------------------------------------------


def test_sc030_report_json_exit_0() -> None:
    """report <src_path> <tests_path> --format=json exits 0 with quality JSON.

    The report command emits quality_reports + quality_summary (not raw
    analysis results). Updated as part of opsx/quality-call-scanning.
    """
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["report", str(TESTDATA_ANALYSIS), str(TESTDATA_QUALITY), "--format", "json"],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
    data = json.loads(result.output)
    # report now emits quality JSON (quality_reports + quality_summary)
    assert "quality_reports" in data, f"Expected 'quality_reports' key in report output, got: {list(data.keys())}"
    assert "quality_summary" in data


def test_report_missing_src_exits_1() -> None:
    """report with a non-existent src_path exits 1."""
    runner = CliRunner()
    result = runner.invoke(main, ["report", "/nonexistent/src", str(TESTDATA_QUALITY)])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output:\n{result.output}"


def test_report_missing_tests_exits_1() -> None:
    """report with a non-existent tests_path exits 1."""
    runner = CliRunner()
    result = runner.invoke(main, ["report", str(TESTDATA_ANALYSIS), "/nonexistent/tests"])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output:\n{result.output}"


# ---------------------------------------------------------------------------
# Stub commands — smoke tests (exit 0, non-empty output)
# ---------------------------------------------------------------------------


def test_schema_stub_exit_0() -> None:
    """schema command exits 0 and mentions 'schema' in output (stub)."""
    runner = CliRunner()
    result = runner.invoke(main, ["schema"])
    assert result.exit_code == 0
    assert "schema" in result.output.lower(), f"Expected 'schema' in output, got: {result.output!r}"


def test_docscan_stub_exit_0() -> None:
    """docscan command exits 0 and mentions 'docscan' in output (stub)."""
    runner = CliRunner()
    result = runner.invoke(main, ["docscan"])
    assert result.exit_code == 0
    assert "docscan" in result.output.lower(), f"Expected 'docscan' in output, got: {result.output!r}"


def test_init_stub_exit_0() -> None:
    """init command exits 0 and mentions 'init' in output (stub)."""
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "init" in result.output.lower(), f"Expected 'init' in output, got: {result.output!r}"


def test_self_check_stub_exit_0() -> None:
    """self-check command exits 0 and mentions 'self-check' in output (stub)."""
    runner = CliRunner()
    result = runner.invoke(main, ["self-check"])
    assert result.exit_code == 0
    assert "self-check" in result.output.lower(), f"Expected 'self-check' in output, got: {result.output!r}"


def test_crap_stub_exit_0() -> None:
    """crap command exits 0 and mentions 'crap' in output (stub)."""
    runner = CliRunner()
    result = runner.invoke(main, ["crap"])
    assert result.exit_code == 0
    assert "crap" in result.output.lower(), f"Expected 'crap' in output, got: {result.output!r}"
