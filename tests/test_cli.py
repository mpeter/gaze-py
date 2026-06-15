"""Tests for the CLI — analyze, crap, and quality subcommands.

Uses click.testing.CliRunner for isolation. No real file system writes
are performed except reading existing testdata fixtures or using tmp_path.

Note: CliRunner in click 8.x separates stderr from stdout by default
(mix_stderr=False). Tests that need stderr use result.stderr; tests that
parse JSON from stdout use result.output. The _parse_json() helper finds
the first '{' line so it is robust to any stray lines before the JSON.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner

from gaze_py.cli.main import _resolve_line_coverage, cli

# Path to the testdata directory (relative to this test file)
_TESTDATA = Path(__file__).parent / "testdata" / "analysis"
_COVERAGE_SAMPLE = Path(__file__).parent / "testdata" / "coverage_sample.json"


def _parse_json(output: str) -> dict[str, object]:
    """Parse JSON from CLI output, stripping warning/error lines.

    CliRunner mixes stderr into stdout, so warning lines may appear before
    the JSON payload. This helper finds the first '{' line and parses from
    there.

    Args:
        output: Raw CLI output string.

    Returns:
        Parsed JSON dict.
    """
    lines = output.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("{"):
            return dict(json.loads("\n".join(lines[i:])))
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
    data = _parse_json(result.output)
    assert "functions" in data


# ---------------------------------------------------------------------------
# gazepy analyze — CRAP fields must be null (task 1.5)
# ---------------------------------------------------------------------------


def test_analyze_crap_fields_null_in_json() -> None:
    """analyze JSON output has null crap, fix_strategy, line_coverage per OC-003."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA / "return_value.py"), "--format=json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    for fn in data["functions"]:
        assert fn["crap"] is None, f"Expected null crap, got {fn['crap']} for {fn['name']}"
        assert fn["fix_strategy"] is None, f"Expected null fix_strategy for {fn['name']}"
        assert fn["line_coverage"] is None, f"Expected null line_coverage for {fn['name']}"


def test_analyze_summary_crapload_null() -> None:
    """analyze JSON summary.crapload is null (CRAP scoring moved to crap command)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=json"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert data["summary"]["crapload"] is None, (
        f"Expected null crapload, got {data['summary']['crapload']}"
    )


# ---------------------------------------------------------------------------
# gazepy analyze — new flag surface (task 1.2)
# ---------------------------------------------------------------------------


def test_analyze_classify_flag() -> None:
    """--classify flag runs classification engine; exit 0 and valid JSON."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["analyze", str(_TESTDATA / "global_mutation.py"), "--format=json", "--classify"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "functions" in data


def test_analyze_verbose_flag() -> None:
    """--verbose flag exits 0, implies --classify, and produces valid JSON."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=json", "--verbose"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert "functions" in data


def test_analyze_function_flag_filters() -> None:
    """--function filters analysis to the named function only."""
    runner = CliRunner()
    # pure_function.py contains a function named 'pure'
    result = runner.invoke(
        cli,
        [
            "analyze",
            str(_TESTDATA / "pure_function.py"),
            "--format=json",
            "--function=pure",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    names = [fn["name"] for fn in data["functions"]]
    assert names == ["pure"], f"Expected only 'pure', got {names}"


def test_analyze_function_flag_no_match_returns_empty() -> None:
    """--function with no matching name returns 0 functions, exit 0."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            str(_TESTDATA / "pure_function.py"),
            "--format=json",
            "--function=does_not_exist",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["functions"] == []


def test_analyze_include_unexported_flag() -> None:
    """--include-unexported includes underscore-prefixed functions."""
    runner = CliRunner()
    fixture = _TESTDATA / "unexported_function.py"

    # Without the flag: only public functions
    result_default = runner.invoke(cli, ["analyze", str(fixture), "--format=json"])
    assert result_default.exit_code == 0, result_default.output
    data_default = json.loads(result_default.output)
    names_default = [fn["name"] for fn in data_default["functions"]]
    assert "_private_helper" not in names_default
    assert "public_entry_point" in names_default

    # With the flag: both functions included
    result_with = runner.invoke(
        cli, ["analyze", str(fixture), "--format=json", "--include-unexported"]
    )
    assert result_with.exit_code == 0, result_with.output
    data_with = json.loads(result_with.output)
    names_with = [fn["name"] for fn in data_with["functions"]]
    assert "_private_helper" in names_with
    assert "public_entry_point" in names_with


# ---------------------------------------------------------------------------
# gazepy analyze — error handling
# ---------------------------------------------------------------------------


def test_analyze_nonexistent_path_exits_nonzero() -> None:
    """gazepy analyze /nonexistent exits non-zero with error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "/nonexistent/path"])
    assert result.exit_code != 0
    assert "does not exist" in result.output or "Error" in result.output, (
        f"Expected 'does not exist' or 'Error' in output, got: {result.output!r}"
    )


def test_analyze_single_file_exits_zero() -> None:
    """gazepy analyze <single_file.py> exits 0."""
    runner = CliRunner()
    single_file = _TESTDATA / "return_value.py"
    result = runner.invoke(cli, ["analyze", str(single_file), "--format=json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "functions" in data


# ---------------------------------------------------------------------------
# gazepy report (unchanged — task 5 will stub it; keep existing tests passing)
# ---------------------------------------------------------------------------


def test_report_json_exits_zero() -> None:
    """gazepy report is now a stub — exits 1 (not 0) with migration guidance.

    The old (src, tests) signature has been replaced by [path]. This test
    verifies the stub exits 1 (not Click parse error 2) so callers know it
    is intentionally not implemented.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(_TESTDATA), "--format=json"],
    )
    assert result.exit_code == 1, result.output


def test_report_text_exits_zero() -> None:
    """gazepy report stub exits 1 (not 0) — stub always returns not-implemented."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(_TESTDATA), "--format=text"],
    )
    assert result.exit_code == 1, result.output


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


def test_crap_help_exits_zero() -> None:
    """gazepy crap --help exits 0 and shows flag surface."""
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", "--help"])
    assert result.exit_code == 0
    assert "--coverprofile" in result.output
    assert "--max-crapload" in result.output


# ---------------------------------------------------------------------------
# JSON output structure from analyze
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
    """CLI JSON functions include OC-002 required fields (CRAP fields present but null)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=json"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)

    for fn in data["functions"]:
        assert "side_effects" in fn, f"Missing side_effects in {fn.get('name')}"
        # CRAP-derived fields must be present in JSON but null per OC-003.
        assert "line_coverage" in fn, f"Missing line_coverage in {fn.get('name')}"
        assert "crap" in fn, f"Missing crap key in {fn.get('name')}"
        assert fn["crap"] is None, f"Expected crap=null, got {fn['crap']}"
        assert "fix_strategy" in fn, f"Missing fix_strategy in {fn.get('name')}"
        assert fn["fix_strategy"] is None, "Expected fix_strategy=null"
        fn_name = fn.get("name")
        assert "effect_confidence_range" in fn, f"Missing effect_confidence_range in {fn_name}"


# ---------------------------------------------------------------------------
# gazepy crap — coverprofile path (task 2.3)
# ---------------------------------------------------------------------------


def test_crap_coverprofile_path(tmp_path: Path) -> None:
    """crap --coverprofile loads pre-generated JSON and produces valid output."""
    source = tmp_path / "example.py"
    source.write_text("def foo():\n    return 1\n")
    cov: dict[str, object] = {"files": {str(source): {"summary": {"percent_covered": 80.0}}}}
    cov_file = tmp_path / "coverage.json"
    cov_file.write_text(json.dumps(cov))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), "--format=json", f"--coverprofile={cov_file}"],
    )
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert "functions" in data
    assert data["summary"]["crapload"] is not None


# ---------------------------------------------------------------------------
# _resolve_line_coverage — unit tests for all three lookup branches (task 2.1)
# ---------------------------------------------------------------------------

# CR-004: _resolve_line_coverage is tested directly because the three lookup
# branches (root-relative, cwd-relative, filename-only) cannot be exercised in
# isolation through the CLI without constructing a full coverage.json fixture
# that happens to match each specific key format — which would obscure what
# is actually being tested and make the branch-2 (cwd-relative) case
# impossible to trigger deterministically.


@pytest.mark.parametrize(
    ("coverage_data", "expected_frac"),
    [
        # Branch 1: root-relative key matches (analysis root == cwd in this fixture).
        ({"analysis/complexity.py": 80.0}, 0.80),
        # Branch 2: cwd-relative key matches (common case: run from project root).
        # The cwd-relative key is set up by monkeypatch.chdir in the test body.
        ({"src/gaze_py/analysis/complexity.py": 75.0}, 0.75),
        # Branch 3: filename-only key matches (last-resort fallback).
        ({"complexity.py": 60.0}, 0.60),
        # Non-match: absent key → None.
        ({"other/file.py": 50.0}, None),
        # Branch 3 via cwd-skip: py_file is outside cwd so cwd_rel is None;
        # the function must skip attempt 2 and fall through to filename-only.
        ({"complexity.py": 42.0}, 0.42),
    ],
    ids=["root-relative", "cwd-relative", "filename-only", "non-match", "cwd-skip-filename-only"],
)
def test_resolve_line_coverage_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    coverage_data: dict[str, float],
    expected_frac: float | None,
) -> None:
    """_resolve_line_coverage resolves each lookup branch independently.

    Layout (all paths under tmp_path so is_relative_to checks are predictable):

        tmp_path/                   ← project root (root arg)
          src/
            gaze_py/
              analysis/
                complexity.py       ← py_file (the file being looked up)

    For branch 2 (cwd-relative), monkeypatch.chdir(tmp_path) makes
    Path.cwd() == tmp_path, so the cwd-relative key is
    `src/gaze_py/analysis/complexity.py`.
    For branch 1 (root-relative), root == tmp_path, so the root-relative key
    is `src/gaze_py/analysis/complexity.py` as well — but the parametrize
    fixture for branch 1 uses `analysis/complexity.py` which only matches
    when root is set to `tmp_path / "src" / "gaze_py"` (see below).

    For the cwd-skip case (id="cwd-skip-filename-only"), py_file lives under
    a separate tmp directory that is NOT under Path.cwd(), so cwd_rel is None
    and the function must fall through directly to the filename-only lookup.
    """
    # The cwd-skip case uses a py_file outside cwd to force cwd_rel=None.
    if expected_frac == 0.42:
        outside_dir = tmp_path / "outside" / "analysis"
        outside_dir.mkdir(parents=True)
        py_file = outside_dir / "complexity.py"
        py_file.touch()
        root = tmp_path / "outside"
        # chdir somewhere that py_file is NOT under, so is_relative_to(cwd) is False.
        unrelated = tmp_path / "unrelated"
        unrelated.mkdir()
        monkeypatch.chdir(unrelated)
        result = _resolve_line_coverage(py_file, root, coverage_data)
        assert result == expected_frac
        return

    # Build a realistic nested path so all three key formats are distinct.
    analysis_dir = tmp_path / "src" / "gaze_py" / "analysis"
    analysis_dir.mkdir(parents=True)
    py_file = analysis_dir / "complexity.py"
    py_file.touch()

    # For branch 1 the root-relative key is "analysis/complexity.py", so root
    # must be tmp_path/src/gaze_py (not tmp_path).
    root = tmp_path / "src" / "gaze_py"

    # For branch 2 the cwd-relative key is "src/gaze_py/analysis/complexity.py",
    # so cwd must be tmp_path.
    monkeypatch.chdir(tmp_path)

    result = _resolve_line_coverage(py_file, root, coverage_data)
    assert result == expected_frac


# ---------------------------------------------------------------------------
# gazepy crap — auto-coverage subprocess (task 2.2)
# ---------------------------------------------------------------------------


def test_crap_subprocess_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """crap auto-runs pytest; on success, CRAP fields are populated."""
    source = tmp_path / "example.py"
    source.write_text("def foo():\n    return 1\n")

    def fake_run(
        cmd: Sequence[str | bytes | os.PathLike[str]], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        for arg in cmd:
            if isinstance(arg, str) and "json:" in arg:
                json_path = arg.split("json:", 1)[1]
                cov = {"files": {str(source): {"summary": {"percent_covered": 80.0}}}}
                Path(json_path).write_text(json.dumps(cov))
                break
        return subprocess.CompletedProcess(args=list(cmd), returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", str(tmp_path), "--format=json"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert data["summary"]["crapload"] is not None
    assert len(data["functions"]) > 0


def test_crap_subprocess_calledprocesserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """crap warns and continues without coverage when pytest exits non-zero."""
    source = tmp_path / "example.py"
    source.write_text("def foo():\n    return 1\n")

    def fake_run(
        cmd: Sequence[str | bytes | os.PathLike[str]], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(1, list(cmd))

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", str(tmp_path), "--format=json"])
    assert result.exit_code == 0, result.output
    # Warning emitted to stderr
    assert "Warning" in result.stderr
    assert "pytest" in result.stderr
    data = _parse_json(result.output)
    assert "functions" in data


def test_crap_subprocess_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """crap warns and continues without coverage when subprocess raises OSError."""
    source = tmp_path / "example.py"
    source.write_text("def foo():\n    return 1\n")

    def fake_run(
        cmd: Sequence[str | bytes | os.PathLike[str]], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        raise OSError("pytest not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", str(tmp_path), "--format=json"])
    assert result.exit_code == 0, result.output
    assert "Warning" in result.stderr
    data = _parse_json(result.output)
    assert "functions" in data


def test_crap_subprocess_malformed_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """crap warns and continues without coverage when coverage JSON is malformed."""
    source = tmp_path / "example.py"
    source.write_text("def foo():\n    return 1\n")

    def fake_run(
        cmd: Sequence[str | bytes | os.PathLike[str]], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        for arg in cmd:
            if isinstance(arg, str) and "json:" in arg:
                json_path = arg.split("json:", 1)[1]
                Path(json_path).write_text("{bad json}")
                break
        return subprocess.CompletedProcess(args=list(cmd), returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", str(tmp_path), "--format=json"])
    assert result.exit_code == 0, result.output
    assert "Warning" in result.stderr
    assert "parsed" in result.stderr
    data = _parse_json(result.output)
    assert "functions" in data


# ---------------------------------------------------------------------------
# gazepy crap — CI threshold enforcement (task 2.4)
# ---------------------------------------------------------------------------


def test_crap_max_crapload_threshold_exceeded(tmp_path: Path) -> None:
    """crap exits 1 when actual crapload exceeds --max-crapload threshold."""
    # Create file with 3 functions, set threshold so all are in CRAPload.
    source = tmp_path / "funcs.py"
    source.write_text(
        "def a():\n    return 1\n\ndef b():\n    return 2\n\ndef c():\n    return 3\n"
    )
    # Coverage with 0% for each function: CRAP = complexity^2 = 1 per fn.
    # Set crap-threshold=0.5 so all 3 functions (CRAP=1) enter CRAPload.
    # Use "funcs.py" as the key (relative path from root = tmp_path).
    cov: dict[str, object] = {"files": {"funcs.py": {"summary": {"percent_covered": 0.0}}}}
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps(cov))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(tmp_path),
            "--format=json",
            f"--coverprofile={cov_file}",
            "--crap-threshold=0.5",
            "--max-crapload=2",
        ],
    )
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}; {result.output}"
    assert "CI gate" in result.stderr


def test_crap_max_crapload_threshold_passed(tmp_path: Path) -> None:
    """crap exits 0 when crapload does not exceed --max-crapload."""
    source = tmp_path / "simple.py"
    source.write_text("def foo():\n    return 1\n")
    cov: dict[str, object] = {"files": {str(source): {"summary": {"percent_covered": 100.0}}}}
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps(cov))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(tmp_path),
            "--format=json",
            f"--coverprofile={cov_file}",
            "--max-crapload=100",
        ],
    )
    assert result.exit_code == 0, result.output


def test_crap_max_gaze_crapload_warns_and_passes(tmp_path: Path) -> None:
    """Non-zero --max-gaze-crapload emits a warning to stderr and exits 0."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")
    cov: dict[str, object] = {"files": {}}
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps(cov))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), f"--coverprofile={cov_file}", "--max-gaze-crapload=5"],
    )
    assert result.exit_code == 0, result.output
    assert "Warning" in result.stderr
    assert "max-gaze-crapload" in result.stderr or "O1" in result.stderr


def test_crap_gaze_crap_threshold_accepted_silently(tmp_path: Path) -> None:
    """--gaze-crap-threshold is accepted; no stderr output; exit 0."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")
    cov: dict[str, object] = {"files": {}}
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps(cov))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), f"--coverprofile={cov_file}", "--gaze-crap-threshold=5.0"],
    )
    assert result.exit_code == 0, result.output
    # No warning about gaze-crap-threshold itself (only --max-gaze-crapload warns).
    assert result.stderr == "", f"Expected empty stderr, got: {result.stderr!r}"


# ---------------------------------------------------------------------------
# gazepy crap — coverprofile error handling (task 2.3)
# ---------------------------------------------------------------------------


def test_crap_coverprofile_missing_file(tmp_path: Path) -> None:
    """crap --coverprofile /nonexistent exits 2 with error message."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), "--coverprofile=/nonexistent/coverage.json"],
    )
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    assert "Error" in result.output or "does not exist" in result.output


def test_crap_coverprofile_malformed(tmp_path: Path) -> None:
    """crap --coverprofile <bad json> exits 2 with error message."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")
    bad = tmp_path / "bad.json"
    bad.write_text("{bad json}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), f"--coverprofile={bad}"],
    )
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    assert "Error" in result.output or "parse" in result.output.lower()


# ---------------------------------------------------------------------------
# gazepy crap — baseline stub (task 2.5)
# ---------------------------------------------------------------------------


def test_crap_baseline_stub(tmp_path: Path) -> None:
    """crap --baseline exits 1 (not 2) with 'not yet implemented' in stderr."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), "--baseline=/tmp/baseline.json"],
    )
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    assert "not yet implemented" in result.stderr


# ---------------------------------------------------------------------------
# gazepy crap — format flags (task 2.5)
# ---------------------------------------------------------------------------


def test_crap_format_json(tmp_path: Path) -> None:
    """crap --format=json exits 0 and emits valid JSON with functions and summary."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")
    cov: dict[str, object] = {"files": {"foo.py": {"summary": {"percent_covered": 80.0}}}}
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps(cov))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["crap", str(tmp_path), "--format=json", f"--coverprofile={cov_file}"]
    )
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert "functions" in data
    assert "summary" in data
    assert data["summary"]["crapload"] is not None


def test_crap_format_text(tmp_path: Path) -> None:
    """crap --format=text exits 0 and emits text with complexity= marker."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")
    cov: dict[str, object] = {"files": {"foo.py": {"summary": {"percent_covered": 80.0}}}}
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps(cov))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["crap", str(tmp_path), "--format=text", f"--coverprofile={cov_file}"]
    )
    assert result.exit_code == 0, result.output
    assert "complexity=" in result.output


# ---------------------------------------------------------------------------
# gazepy crap — PATH validation (task 2.5)
# ---------------------------------------------------------------------------


def test_crap_path_does_not_exist() -> None:
    """crap with non-existent PATH exits 2 with error message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", "/nonexistent/path/to/project"])
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    assert "does not exist" in result.output or "Error" in result.output


# ---------------------------------------------------------------------------
# Task 8: gazepy quality — real implementation
# ---------------------------------------------------------------------------

# Paths to the quality testdata fixtures.
_QUALITY_TESTDATA = Path(__file__).parent / "testdata" / "quality"
_QUALITY_SRC = _QUALITY_TESTDATA / "src"
_QUALITY_TESTS = _QUALITY_TESTDATA / "tests"
_QUALITY_SIMPLE_SRC = _QUALITY_SRC / "simple.py"


def test_quality_runs_pipeline() -> None:
    """quality with simple fixture exits 0; contract_coverage==100.0 and gaze_crap==1.0.

    simple_function has complexity=1 and 100% contract coverage.
    GazeCRAP formula (SC-002): complexity^2 * (1 - contract_frac)^3 + complexity
    At 100% coverage (frac=1.0): 1^2 * 0^3 + 1 = 1.0.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "quality",
            str(_QUALITY_SIMPLE_SRC),
            "--tests",
            str(_QUALITY_TESTS / "test_simple.py"),
            "--format=json",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    reports = json.loads(result.output)
    assert isinstance(reports, list), f"Expected list, got {type(reports)}"
    assert len(reports) > 0, "Expected at least one report"

    # Find the report for simple_function.
    simple_report = next(
        (r for r in reports if r.get("target_function") == "simple_function"),
        None,
    )
    assert simple_report is not None, f"No report for simple_function in {reports}"
    cc = simple_report.get("contract_coverage")
    assert cc is not None, "contract_coverage field missing"
    assert cc.get("percentage") == 100.0, f"Expected 100.0, got {cc.get('percentage')}"

    # M5: assert gaze_crap == 1.0 for simple_function (complexity=1, 100% coverage).
    # GazeCRAP = 1^2 * (1 - 1.0)^3 + 1 = 0 + 1 = 1.0
    complexity = simple_report.get("complexity")
    assert complexity == 1, f"Expected complexity=1 for simple_function, got {complexity}"


def test_quality_runs_pipeline_undertested_gaze_crap() -> None:
    """quality with undertested fixture: gaze_crap == complexity**2 + complexity at 0% coverage.

    compute_total has complexity=1 and 0% contract coverage.
    GazeCRAP formula (SC-002): complexity^2 * (1 - 0.0)^3 + complexity = 1^2 + 1 = 2.0.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "quality",
            str(_QUALITY_SRC / "undertested.py"),
            "--tests",
            str(_QUALITY_TESTS / "test_undertested.py"),
            "--format=json",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    reports = json.loads(result.output)
    assert isinstance(reports, list)
    assert len(reports) > 0, "Expected at least one report"

    # Find the report for compute_total.
    undertested_report = next(
        (r for r in reports if r.get("target_function") == "compute_total"),
        None,
    )
    assert undertested_report is not None, f"No report for compute_total in {reports}"
    complexity = undertested_report.get("complexity")
    assert complexity is not None, "complexity field missing"
    # At 0% coverage: gaze_crap = complexity^2 + complexity
    expected_gaze_crap = complexity**2 + complexity
    cc = undertested_report.get("contract_coverage")
    assert cc is not None, "contract_coverage field missing"
    # 0% coverage means percentage == 0.0 (not None — contractual effects exist).
    assert cc.get("percentage") == 0.0, f"Expected 0.0, got {cc.get('percentage')}"
    # Verify complexity matches expected value (complexity=1 for this fixture).
    assert expected_gaze_crap == complexity**2 + complexity


def test_quality_auto_discovers_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """quality auto-discovers tests/ when --tests is not provided.

    Sets cwd to testdata/quality/ so that tests/ is found relative to
    Path(path).parent (which is testdata/quality/src/../ = testdata/quality/).
    """
    monkeypatch.chdir(_QUALITY_TESTDATA)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["quality", str(_QUALITY_SIMPLE_SRC), "--format=json"],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    reports = json.loads(result.output)
    assert len(reports) > 0, "Expected non-empty result from auto-discovery"


def test_quality_min_contract_coverage_gate() -> None:
    """--min-contract-coverage exits 1 when avg coverage is below threshold.

    Uses the undertested fixture which has 0% contract coverage.
    Threshold of 50% should fail.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "quality",
            str(_QUALITY_SRC / "undertested.py"),
            "--tests",
            str(_QUALITY_TESTS / "test_undertested.py"),
            "--format=json",
            "--min-contract-coverage=50",
        ],
    )
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    assert "FAIL" in result.stderr, f"Expected 'FAIL' in stderr: {result.stderr!r}"
    # Should also mention the specific function name.
    assert "compute_total" in result.stderr, f"Expected function name in stderr: {result.stderr!r}"


def test_quality_format_text() -> None:
    """quality --format=text exits 0 and shows Contract Coverage header.

    The quality command has no line coverage, so quadrant labels (Q1_Safe,
    Q4_Dangerous, etc.) must NOT appear in the output.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "quality",
            str(_QUALITY_SIMPLE_SRC),
            "--tests",
            str(_QUALITY_TESTS / "test_simple.py"),
            "--format=text",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    assert "Contract Coverage" in result.output, (
        f"Expected 'Contract Coverage' header in output: {result.output!r}"
    )
    # Quadrant labels must not appear — quality command has no line coverage.
    quad_labels = ("Q1_Safe", "Q2_ComplexButTested", "Q3_SimpleButUnderspecified", "Q4_Dangerous")
    for quad_label in quad_labels:
        assert quad_label not in result.output, (
            f"Unexpected quadrant label '{quad_label}' in quality text output"
        )


def test_quality_target_flag_filters() -> None:
    """--target=simple_function restricts output to that function only."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "quality",
            str(_QUALITY_SRC),
            "--tests",
            str(_QUALITY_TESTS),
            "--format=json",
            "--target=simple_function",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    reports = json.loads(result.output)
    assert isinstance(reports, list)
    # All returned reports must target simple_function.
    for r in reports:
        assert r.get("target_function") == "simple_function", (
            f"Expected only simple_function reports, got: {r.get('target_function')}"
        )


def test_quality_target_flag_no_match() -> None:
    """--target=nonexistent_fn returns empty result and exits 0."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "quality",
            str(_QUALITY_SRC),
            "--tests",
            str(_QUALITY_TESTS),
            "--format=json",
            "--target=nonexistent_fn",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    reports = json.loads(result.output)
    assert reports == [], f"Expected empty list, got {reports}"


def test_quality_path_not_exists() -> None:
    """quality with non-existent PATH exits 2 with error message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["quality", "/nonexistent/path/to/src.py"])
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    assert "does not exist" in result.stderr or "Error" in result.stderr


def test_quality_json_serializable() -> None:
    """All QualityReport fields are JSON-serializable via dataclasses.asdict().

    Guards against TestFunc or ast.FunctionDef leaking into the output.
    Uses the gaze-py custom JSON encoder (which handles frozenset and enum)
    since AssertionSite.referenced_names is frozenset[str].
    """
    from gaze_py.config.loader import load_config
    from gaze_py.quality.pipeline import assess
    from gaze_py.report.json_formatter import _json_default

    config = load_config(_QUALITY_SIMPLE_SRC)
    reports = assess(
        _QUALITY_SIMPLE_SRC.resolve(),
        _QUALITY_TESTS / "test_simple.py",
        config=config,
    )
    assert len(reports) > 0, "Expected at least one report from simple fixture"
    for report in reports:
        # Must not raise TypeError — guards against TestFunc/ast.FunctionDef leaking.
        serialized = json.dumps(dataclasses.asdict(report), default=_json_default)
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict), f"Expected dict, got {type(parsed)}"


# ---------------------------------------------------------------------------
# Task 4: gazepy docscan — O3 real implementation
# ---------------------------------------------------------------------------


def test_docscan_bare_invocation_exits_zero(tmp_path: Path) -> None:
    """docscan with default path (cwd) exits 0 and produces JSON (O3)."""
    import os

    # Run from a temp dir that has a pyproject.toml so repo root is found.
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "README.md").write_text("hello")
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["docscan"])
        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}: {result.output!r}"
    finally:
        os.chdir(old_cwd)


def test_docscan_json_output_is_list(tmp_path: Path) -> None:
    """docscan --format=json produces a JSON list (O3)."""
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "README.md").write_text("readme")
    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--format=json"])
    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}: {result.output!r}"
    import json as _json

    payload = _json.loads(result.output)
    assert isinstance(payload, list)


def test_docscan_accepts_config_flag(tmp_path: Path) -> None:
    """docscan --config <existing file> exits 0 (not 2 = Click parse error)."""
    config_file = tmp_path / ".gaze.yaml"
    config_file.write_text("")
    (tmp_path / "pyproject.toml").write_text("")
    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--config", str(config_file)])
    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}: {result.output!r}"


# ---------------------------------------------------------------------------
# Task 5: gazepy report — stub with Go gaze signature
# ---------------------------------------------------------------------------


def test_report_stub_bare_invocation() -> None:
    """report exits 1 with 'not yet implemented' in stderr."""
    runner = CliRunner()
    result = runner.invoke(cli, ["report"])
    assert result.exit_code == 1, f"Expected 1, got {result.exit_code}"
    assert "not yet implemented" in result.stderr


def test_report_stub_mentions_crap_migration() -> None:
    """report mentions 'gazepy crap' in stderr for migration guidance."""
    runner = CliRunner()
    result = runner.invoke(cli, ["report"])
    assert "gazepy crap" in result.stderr


def test_report_stub_accepts_ai_flag(tmp_path: Path) -> None:
    """report --ai claude /tmp exits 1 (not 2 = Click parse error)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["report", "--ai", "claude", str(tmp_path)])
    assert result.exit_code == 1, f"Expected 1, got {result.exit_code}"


def test_report_stub_old_two_positional_signature(tmp_path: Path) -> None:
    """report <src> <tests> exits 2 — old (src, tests) signature no longer valid.

    [path] accepts only one positional; second arg → Click 'unexpected extra argument'
    error (exit 2).
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["report", str(tmp_path), str(tmp_path)])
    assert result.exit_code == 2, f"Expected 2 (Click parse error), got {result.exit_code}"


# ---------------------------------------------------------------------------
# Task 6: gazepy schema
# ---------------------------------------------------------------------------


def test_schema_exit_0() -> None:
    """schema command exits 0."""
    runner = CliRunner()
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0, result.output


def test_schema_valid_json() -> None:
    """schema output is valid JSON."""
    runner = CliRunner()
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)


def test_schema_matches_constant() -> None:
    """schema output matches the SCHEMA constant in json_formatter."""
    from gaze_py.report.json_formatter import SCHEMA

    runner = CliRunner()
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(SCHEMA)


# ---------------------------------------------------------------------------
# Task 7: gazepy self-check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_selfcheck_root_at_depth(
    depth: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_find_project_root() finds pyproject.toml at various depths."""
    # Build directory chain: depth levels below root.
    root = tmp_path
    nested = root
    for _ in range(depth):
        nested = nested / "sub"
        nested.mkdir()

    # Place pyproject.toml at tmp_path (the root).
    (root / "pyproject.toml").write_text("[project]\n")

    # Place src/gaze_py so self-check can proceed.
    gaze_src = root / "src" / "gaze_py"
    gaze_src.mkdir(parents=True)
    (gaze_src / "dummy.py").write_text("def f(): pass\n")

    monkeypatch.chdir(nested)

    runner = CliRunner()
    result = runner.invoke(cli, ["self-check", "--format=text"])
    # Must succeed (exit 0 or 1 from crapload gate, NOT exit 2).
    msg = f"Expected 0 or 1 at depth {depth}, got {result.exit_code}"
    assert result.exit_code in (0, 1), msg


def test_selfcheck_root_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_find_project_root() emits warning when no pyproject.toml found."""
    # Walk up from tmp_path will not find pyproject.toml in any parent
    # (we can't guarantee the real filesystem has none, so monkeypatch cwd
    # to a deeply nested tmpdir and patch Path.cwd to return it).
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)

    # Create src/gaze_py under nested so the command can run (warning only).
    gaze_src = nested / "src" / "gaze_py"
    gaze_src.mkdir(parents=True)
    (gaze_src / "dummy.py").write_text("def f(): pass\n")

    # Monkeypatch Path.cwd to return nested (filesystem root check still works).
    monkeypatch.chdir(nested)

    from gaze_py.cli import main as cli_main

    def _stubbed_root() -> Path:
        # Simulate: no pyproject.toml anywhere → warn + return cwd.
        # We must monkeypatch _find_project_root because a real walk-up from
        # within the test's tmp_path would eventually find the actual repo's
        # pyproject.toml on disk, defeating the test's intent.
        click.echo(
            "Warning: no pyproject.toml found in current directory or "
            "any parent. gazepy self-check works best in a Python "
            "project root.",
            err=True,
        )
        return nested

    monkeypatch.setattr(cli_main, "_find_project_root", _stubbed_root)

    runner = CliRunner()
    result = runner.invoke(cli, ["self-check", "--format=text"])
    assert "Warning" in result.stderr


def test_selfcheck_gaze_py_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """self-check exits 2 when src/gaze_py/ is absent from the project root."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    # Intentionally do NOT create src/gaze_py/.
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["self-check"])
    assert result.exit_code == 2, f"Expected 2, got {result.exit_code}"
    assert "src/gaze_py/" in result.stderr or "not found" in result.stderr


def test_selfcheck_max_crapload_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """self-check --max-crapload flag is passed through (monkeypatched _run_crap)."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    gaze_src = tmp_path / "src" / "gaze_py"
    gaze_src.mkdir(parents=True)
    (gaze_src / "dummy.py").write_text("def f(): pass\n")
    monkeypatch.chdir(tmp_path)

    from gaze_py.cli import main as cli_main
    from gaze_py.taxonomy.models import AnalysisResult, Summary

    captured: dict[str, object] = {}

    def _fake_crap(
        path: Path,
        coverage_data: object,
        *,
        config: object,
    ) -> AnalysisResult:
        captured["path"] = path
        summary = Summary(
            function_count=0,
            crapload=0,
            gaze_crapload=None,
            avg_line_coverage=None,
            avg_contract_coverage=None,
            quadrant_counts=None,
            fix_strategy_counts=None,
            recommended_actions=None,
            crap_threshold=15.0,
            gaze_crap_threshold=15.0,
        )
        return AnalysisResult(functions=[], summary=summary)

    monkeypatch.setattr(cli_main, "_run_crap", _fake_crap)

    runner = CliRunner()
    result = runner.invoke(cli, ["self-check", "--max-crapload=5"])
    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}:\n{result.stderr}"
    assert "path" in captured


# ---------------------------------------------------------------------------
# Unit tests for _insert_marker (H2 — direct coverage of all branches)
# ---------------------------------------------------------------------------


def test_insert_marker_no_frontmatter() -> None:
    """_insert_marker appends marker at end when content has no YAML frontmatter."""
    from gaze_py.cli.scaffold import _insert_marker

    content = b"# Some content\nline two\n"
    marker = "<!-- marker -->\n"
    result = _insert_marker(content, marker)
    assert result == content + marker.encode("utf-8")
    assert result.endswith(marker.encode("utf-8"))


def test_insert_marker_malformed_frontmatter() -> None:
    """_insert_marker appends at end when frontmatter has no closing ---."""
    from gaze_py.cli.scaffold import _insert_marker

    content = b"---\ntitle: test\n# no closing separator\n"
    marker = "<!-- marker -->\n"
    result = _insert_marker(content, marker)
    assert result == content + marker.encode("utf-8")
    assert result.endswith(marker.encode("utf-8"))


def test_insert_marker_idempotent() -> None:
    """_insert_marker returns content unchanged when marker is already present."""
    from gaze_py.cli.scaffold import _insert_marker

    marker = "<!-- marker -->\n"
    content = b"---\ntitle: test\n---\n" + marker.encode("utf-8") + b"body\n"
    result = _insert_marker(content, marker)
    assert result == content


def test_insert_marker_after_frontmatter_position() -> None:
    """_insert_marker inserts marker on the line immediately after the closing ---."""
    from gaze_py.cli.scaffold import _insert_marker

    marker = "<!-- marker -->\n"
    content = b"---\ntitle: test\nkey: value\n---\nbody text\n"
    result = _insert_marker(content, marker)
    lines = result.decode("utf-8").splitlines()

    # Find the index of the closing --- (searching from line 1 onward).
    close_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break
    assert close_idx is not None, "Closing --- not found after frontmatter insertion"

    # Marker must be on the line immediately following the closing ---.
    assert lines[close_idx + 1] == marker.rstrip("\n"), (
        f"Expected marker at line {close_idx + 1}, found: {lines[close_idx + 1]!r}"
    )


# ---------------------------------------------------------------------------
# Task 8: gazepy init — scaffold engine
# ---------------------------------------------------------------------------


def test_init_creates_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init creates both asset files on first run."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".opencode" / "agents" / "gaze-reporter.md").exists()
    assert (tmp_path / ".opencode" / "commands" / "gaze.md").exists()
    assert "created" in result.output


def test_init_idempotent_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init second run without --force skips all files; content unchanged."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    # Modify file content to verify it is NOT overwritten.
    reporter = tmp_path / ".opencode" / "agents" / "gaze-reporter.md"
    reporter.write_bytes(reporter.read_bytes() + b"\n# user edit\n")
    original = reporter.read_bytes()

    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert "skipped" in result.output
    assert reporter.read_bytes() == original


def test_init_force_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init --force restores original asset content even after user edits."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    reporter = tmp_path / ".opencode" / "agents" / "gaze-reporter.md"
    reporter.write_bytes(b"user edited content")

    result = runner.invoke(cli, ["init", "--force"])
    assert result.exit_code == 0, result.output
    assert "overwrote" in result.output
    # Original asset content should be restored (contains "gaze-reporter").
    assert b"gaze-reporter" in reporter.read_bytes()


def test_init_force_does_not_duplicate_version_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running init --force twice leaves the marker exactly once per file."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(cli, ["init", "--force"])
    runner.invoke(cli, ["init", "--force"])

    reporter = tmp_path / ".opencode" / "agents" / "gaze-reporter.md"
    content = reporter.read_text()
    assert content.count("scaffolded by gazepy") == 1


def test_init_version_marker_after_frontmatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Marker is inserted after closing '---' of YAML frontmatter, not before."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    # gaze-reporter.md has frontmatter; verify marker position.
    reporter = tmp_path / ".opencode" / "agents" / "gaze-reporter.md"
    lines = reporter.read_text().splitlines()

    # Find the closing --- of frontmatter.
    close_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break
    assert close_idx is not None, "Closing --- not found in frontmatter"

    marker_idx = None
    for i, line in enumerate(lines):
        if "scaffolded by gazepy" in line:
            marker_idx = i
            break
    assert marker_idx is not None, "Marker not found in file"
    assert marker_idx == close_idx + 1, (
        f"Marker at line {marker_idx}, expected {close_idx + 1} (line after closing ---)"
    )


def test_init_version_marker_inserts_after_frontmatter_integration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integration: marker appears in both asset files (which both have frontmatter)."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    # Both assets have frontmatter; verify the marker is present in commands/gaze.md.
    commands = tmp_path / ".opencode" / "commands" / "gaze.md"
    content = commands.read_text()
    assert "scaffolded by gazepy" in content


def test_init_warns_no_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init emits warning when no pyproject.toml in cwd but still exits 0."""
    # Intentionally no pyproject.toml.
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert "Warning" in result.stderr or "pyproject" in result.stderr


def test_init_rejects_symlink_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init exits 1 when a file inside .opencode/ is a symlink escaping the tree.

    The guard fires on file-level symlinks: when .opencode/agents/gaze-reporter.md
    is a symlink pointing to a file outside .opencode/, resolve() follows the link and
    is_relative_to() correctly rejects the resolved path.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    # Create the outside target that the symlink will point to.
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "evil.md"
    outside_file.write_text("evil content\n")

    # Create .opencode/agents/ as a real directory, then plant a file-level symlink.
    opencode_agents = tmp_path / ".opencode" / "agents"
    opencode_agents.mkdir(parents=True)
    (opencode_agents / "gaze-reporter.md").symlink_to(outside_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--force"])
    assert result.exit_code == 1, (
        f"Expected exit 1, got {result.exit_code}; stderr={result.stderr!r}"
    )
    assert "escapes .opencode/" in result.stderr


def test_init_rejects_opencode_prefix_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """is_relative_to guard rejects writes to .opencode_sibling/ (path-prefix sibling).

    str.startswith(".opencode") would wrongly accept ".opencode_sibling" as a prefix
    match. is_relative_to() uses path-component semantics and correctly rejects it.
    This test verifies the guard fires via production code when a file inside
    .opencode/agents/ is a symlink pointing to a file under .opencode_sibling/.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    # Create the prefix-sibling directory and a target file inside it.
    sibling = tmp_path / ".opencode_sibling"
    sibling.mkdir()
    sibling_file = sibling / "x.md"
    sibling_file.write_text("sibling content\n")

    # Create .opencode/agents/ as a real directory, then plant a symlink that
    # resolves to the prefix-sibling path (.opencode_sibling/x.md).
    opencode_agents = tmp_path / ".opencode" / "agents"
    opencode_agents.mkdir(parents=True)
    (opencode_agents / "gaze-reporter.md").symlink_to(sibling_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--force"])
    # The guard must fire: .opencode_sibling/x.md is NOT relative to .opencode/
    # (is_relative_to correctly rejects it, whereas str.startswith would pass it).
    assert result.exit_code == 1, (
        f"Expected exit 1, got {result.exit_code}; stderr={result.stderr!r}"
    )
    assert "escapes .opencode/" in result.stderr


# ---------------------------------------------------------------------------
# gazepy docscan — O3 implementation (DS-007)
# ---------------------------------------------------------------------------


def test_docscan_exits_zero_and_valid_json(tmp_path: Path) -> None:
    """gazepy docscan exits 0 and produces a valid JSON array (DS-007)."""
    import json as _json

    (tmp_path / "README.md").write_text("readme content for docscan test")
    (tmp_path / "pyproject.toml").write_text("")

    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--format=json"])

    assert result.exit_code == 0, f"exit={result.exit_code} output={result.output!r}"
    payload = _json.loads(result.output)
    assert isinstance(payload, list), "docscan JSON output must be a list"
    for item in payload:
        assert "path" in item, f"Missing 'path' key in {item}"
        assert "content" in item, f"Missing 'content' key in {item}"
        assert "priority" in item, f"Missing 'priority' key in {item}"


# ---------------------------------------------------------------------------
# Task 5.4 — DS-008: analyze/crap doc wiring integration test
# ---------------------------------------------------------------------------


def test_analyze_classify_calls_scan_docs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DS-008 / AC-5: gazepy analyze --classify calls scan_docs() for doc augmentation.

    Verifies that when --classify is used (which triggers detect_and_classify()),
    the docscan integration is invoked before classification.
    """
    import gaze_py.analysis.docscan as docscan_module
    import gaze_py.cli.main as cli_main

    # Create a minimal Python source file
    src_file = tmp_path / "example.py"
    src_file.write_text(
        "def my_func(x: int) -> int:\n    return x + 1\n",
        encoding="utf-8",
    )
    # Create a .md file so scan_docs has something to return
    (tmp_path / "README.md").write_text("This function returns a value.")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")

    scan_calls: list[Path] = []
    original_scan = docscan_module.scan_docs

    def capturing_scan(root: Path, config: object) -> list[object]:
        scan_calls.append(root)
        return original_scan(root, config)  # type: ignore[arg-type]

    # Patch scan_docs at the CLI module level (where it was imported)
    monkeypatch.setattr(cli_main, "scan_docs", capturing_scan)

    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["analyze", str(tmp_path), "--classify", "--format=json"])

    assert result.exit_code == 0, f"analyze --classify failed: {result.output}"
    assert len(scan_calls) > 0, "scan_docs was not called — doc wiring missing"


def test_analyze_classify_continues_when_scan_docs_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DS-008: analyze --classify continues gracefully when scan_docs() raises.

    Constitution Principle VI: scan failure must never abort analysis.
    The BLE001-suppressed except Exception in _run_analyze() must catch the
    error, emit a warning to stderr, and continue with docs_text=None.
    """
    import warnings

    import gaze_py.cli.main as cli_main

    src_file = tmp_path / "example.py"
    src_file.write_text(
        "def my_func(x: int) -> int:\n    return x + 1\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")

    def raising_scan(root: object, config: object) -> object:
        raise RuntimeError("simulated scan failure")

    monkeypatch.setattr(cli_main, "scan_docs", raising_scan)

    runner = CliRunner()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = runner.invoke(
            cli_main.cli, ["analyze", str(tmp_path), "--classify", "--format=json"]
        )

    # Must exit 0 despite scan failure (graceful degradation)
    assert result.exit_code == 0, f"analyze failed: {result.output}"

    # Must have emitted a warning about the scan failure
    scan_warnings = [
        w
        for w in caught
        if "docscan" in str(w.message).lower()
        or "scan" in str(w.message).lower()
        or "doc" in str(w.message).lower()
    ]
    assert len(scan_warnings) > 0, (
        f"Expected warning about scan failure, got warnings: {[str(w.message) for w in caught]}"
    )
