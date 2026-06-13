"""Tests for the CLI — analyze and report subcommands.

Uses click.testing.CliRunner for isolation. No real file system writes
are performed except reading existing testdata fixtures.

Note: CliRunner in click 8.x mixes stderr into stdout by default. The
_parse_json() helper strips warning lines (starting with 'Warning:') before
parsing JSON so tests are robust to parse warnings from testdata fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gaze_py.cli.main import cli

# Path to the testdata directory (relative to this test file)
_TESTDATA = Path(__file__).parent / "testdata" / "analysis"
_COVERAGE_SAMPLE = Path(__file__).parent / "testdata" / "coverage_sample.json"


def _parse_json(output: str) -> dict[str, object]:
    """Parse JSON from CLI output, stripping warning lines.

    CliRunner mixes stderr into stdout, so warning lines may appear before
    the JSON payload. This helper finds the first '{' line and parses from
    there.

    Args:
        output: Raw CLI output string.

    Returns:
        Parsed JSON dict.
    """
    lines = output.splitlines()
    # Find the first line that starts the JSON object
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("{"):
            return dict(json.loads("\n".join(lines[i:])))
    # Fallback: try parsing the whole output
    return dict(json.loads(output))


# ---------------------------------------------------------------------------
# gazepy analyze — basic invocation
# ---------------------------------------------------------------------------


def test_analyze_json_exits_zero() -> None:
    """gazepy analyze <path> --format=json exits 0 and produces valid JSON."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=json"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert "functions" in data
    assert "summary" in data


def test_analyze_text_exits_zero() -> None:
    """gazepy analyze <path> --format=text exits 0 and contains 'complexity='."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=text"])
    assert result.exit_code == 0, result.output
    assert "complexity=" in result.output


def test_analyze_default_format_is_json() -> None:
    """gazepy analyze <path> (no --format) defaults to JSON output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA)])
    assert result.exit_code == 0, result.output
    # Should be valid JSON
    data = _parse_json(result.output)
    assert "functions" in data


# ---------------------------------------------------------------------------
# gazepy analyze — coverage-json flag
# ---------------------------------------------------------------------------


def test_analyze_with_coverage_json_exits_zero() -> None:
    """gazepy analyze <path> --coverage-json <file> exits 0, JSON has non-null line_coverage."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["analyze", str(_TESTDATA), "--format=json", f"--coverage-json={_COVERAGE_SAMPLE}"],
    )
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    # At least one function should have non-null line_coverage
    functions = data["functions"]
    assert len(functions) > 0
    # The coverage file maps one file — check that at least one fn has non-null coverage
    # (other functions will still have null coverage since they're not in the coverage file)
    line_coverages = [fn["line_coverage"] for fn in functions]
    # At least one should be non-null (the file in the coverage sample)
    assert any(lc is not None for lc in line_coverages)


def test_analyze_with_malformed_coverage_json_exits_nonzero() -> None:
    """gazepy analyze <path> --coverage-json <malformed> exits non-zero with error."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Write a malformed JSON file
        malformed = Path("malformed.json")
        malformed.write_text("{ not valid json }")

        result = runner.invoke(
            cli,
            ["analyze", str(_TESTDATA), f"--coverage-json={malformed.resolve()}"],
        )
    assert result.exit_code != 0


def test_analyze_with_nonexistent_coverage_json_exits_nonzero() -> None:
    """gazepy analyze <path> --coverage-json /nonexistent exits non-zero."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["analyze", str(_TESTDATA), "--coverage-json=/nonexistent/coverage.json"],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# gazepy analyze — error handling
# ---------------------------------------------------------------------------


def test_analyze_nonexistent_path_exits_nonzero() -> None:
    """gazepy analyze /nonexistent exits non-zero with error."""
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(cli, ["analyze", "/nonexistent/path"])
    assert result.exit_code != 0


def test_analyze_single_file_exits_zero() -> None:
    """gazepy analyze <single_file.py> exits 0."""
    runner = CliRunner()
    single_file = _TESTDATA / "return_value.py"
    result = runner.invoke(cli, ["analyze", str(single_file), "--format=json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "functions" in data


# ---------------------------------------------------------------------------
# gazepy report
# ---------------------------------------------------------------------------


def test_report_json_exits_zero() -> None:
    """gazepy report <src> <tests> --format=json exits 0 and produces valid JSON."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(_TESTDATA), str(_TESTDATA), "--format=json"],
    )
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert "functions" in data
    assert "summary" in data


def test_report_text_exits_zero() -> None:
    """gazepy report <src> <tests> --format=text exits 0."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(_TESTDATA), str(_TESTDATA), "--format=text"],
    )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# gazepy --help
# ---------------------------------------------------------------------------


def test_help_exits_zero_and_shows_analyze() -> None:
    """gazepy --help exits 0 and stdout contains 'analyze'."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.output


def test_analyze_help_exits_zero() -> None:
    """gazepy analyze --help exits 0."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--help"])
    assert result.exit_code == 0


def test_report_help_exits_zero() -> None:
    """gazepy report --help exits 0."""
    runner = CliRunner()
    result = runner.invoke(cli, ["report", "--help"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# JSON output structure from CLI
# ---------------------------------------------------------------------------


def test_cli_json_output_has_summary_thresholds() -> None:
    """CLI JSON output includes crap_threshold and gaze_crap_threshold in summary."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=json"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    summary = data["summary"]
    assert "crap_threshold" in summary
    assert "gaze_crap_threshold" in summary


def test_cli_json_functions_have_required_fields() -> None:
    """CLI JSON functions include all OC-002 required fields."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=json"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)

    for fn in data["functions"]:
        assert "side_effects" in fn, f"Missing side_effects in {fn.get('name')}"
        assert "line_coverage" in fn, f"Missing line_coverage in {fn.get('name')}"
        assert "crap" in fn, f"Missing crap in {fn.get('name')}"
        assert "fix_strategy" in fn, f"Missing fix_strategy in {fn.get('name')}"
        fn_name = fn.get("name")
        assert "effect_confidence_range" in fn, f"Missing effect_confidence_range in {fn_name}"
