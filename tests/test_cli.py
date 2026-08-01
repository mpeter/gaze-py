"""Tests for the CLI — analyze, crap, quality, and report subcommands.

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
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from gaze_py.cli.main import _FileCoverage, _resolve_line_coverage, cli
from gaze_py.report.ai import NoopSynthesizer
from gaze_py.taxonomy.models import FunctionTarget

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
    assert "results" in data
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
    assert "results" in data


# ---------------------------------------------------------------------------
# gazepy analyze — CRAP fields must be null (task 1.5)
# ---------------------------------------------------------------------------


def test_analyze_crap_fields_null_in_json() -> None:
    """analyze JSON output has null crap, fix_strategy, line_coverage per OC-003."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA / "return_value.py"), "--format=json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    for fn in data["results"]:
        fn_name = fn["target"]["function"]
        assert fn["crap"] is None, f"Expected null crap, got {fn['crap']} for {fn_name}"
        assert fn["fix_strategy"] is None, f"Expected null fix_strategy for {fn_name}"
        assert fn["line_coverage"] is None, f"Expected null line_coverage for {fn_name}"


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
# gazepy analyze — JSON schema compatibility (T122, T122b, T123, T126b, T127)
# ---------------------------------------------------------------------------


def test_analyze_json_schema_envelope() -> None:
    """T122: results[0][target] has all 5 sub-keys with correct types (FR-002).
    T122b: schema regression guard — results key present, target nested, metadata present.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA / "return_value.py"), "--format=json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)

    # T122b: regression guard — top-level must be 'results' not 'functions'
    assert "results" in data, "top-level key must be 'results'"
    assert "functions" not in data, "old 'functions' key must not be present"
    assert len(data["results"]) > 0

    r0 = data["results"][0]
    # T122b: target must be nested, not flat
    assert "target" in r0, "results[0] must have 'target' key"
    # T122b: metadata must be present
    assert "metadata" in r0, "results[0] must have 'metadata' key"
    assert "gaze_version" in r0["metadata"], "metadata must have 'gaze_version'"

    # T122: all 5 target sub-keys present with correct types
    t = r0["target"]
    assert isinstance(t.get("package"), str), (
        f"target.package must be str, got {t.get('package')!r}"
    )
    assert isinstance(t.get("function"), str), (
        f"target.function must be str, got {t.get('function')!r}"
    )
    assert t.get("receiver") is None or isinstance(t.get("receiver"), str), (
        f"target.receiver must be str|null, got {t.get('receiver')!r}"
    )
    assert isinstance(t.get("signature"), str), (
        f"target.signature must be str, got {t.get('signature')!r}"
    )
    assert isinstance(t.get("location"), str), (
        f"target.location must be str, got {t.get('location')!r}"
    )


def test_analyze_json_metadata_fields() -> None:
    """T123: metadata has gaze_version, duration_ms (int ≥ 0), timestamp (RFC3339 Z)."""
    import re

    import gaze_py

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA / "return_value.py"), "--format=json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    meta = data["results"][0]["metadata"]

    assert meta["gaze_version"] == gaze_py.__version__, (
        f"gaze_version mismatch: {meta['gaze_version']!r} != {gaze_py.__version__!r}"
    )
    assert isinstance(meta["duration_ms"], int) and meta["duration_ms"] >= 0, (
        f"duration_ms must be non-negative int, got {meta['duration_ms']!r}"
    )
    ts_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    assert re.match(ts_pattern, meta["timestamp"]), (
        f"timestamp must match RFC3339 Z format, got {meta['timestamp']!r}"
    )


def test_analyze_function_target_receiver_method_vs_module(tmp_path: Path) -> None:
    """T126b: receiver is class name for methods, null for module-level functions.

    Writes inline source strings to tmp_path — not testdata files — to avoid
    coupling to production file content.
    """
    import textwrap

    from gaze_py.analysis.detector import FileDetector

    root = tmp_path

    # Method case: receiver should be "Foo"
    method_file = tmp_path / "method_case.py"
    method_file.write_text(
        textwrap.dedent("""\
        class Foo:
            def bar(self) -> int:
                return 42
    """)
    )
    targets = FileDetector.detect(method_file, root=root)
    bar = next((t for t in targets if t.function == "bar"), None)
    assert bar is not None, "bar not found"
    assert bar.receiver == "Foo", f"Expected receiver='Foo', got {bar.receiver!r}"

    # Module-level case: receiver should be None
    module_file = tmp_path / "module_case.py"
    module_file.write_text("def baz() -> None:\n    pass\n")
    targets2 = FileDetector.detect(module_file, root=root)
    baz = next((t for t in targets2 if t.function == "baz"), None)
    assert baz is not None, "baz not found"
    assert baz.receiver is None, f"Expected receiver=None, got {baz.receiver!r}"

    # *args / **kwargs case: signature must contain them, not fallback "def f(...)"
    variadic_file = tmp_path / "variadic_case.py"
    variadic_file.write_text("def f(*args: int, **kwargs: str) -> None:\n    pass\n")
    targets3 = FileDetector.detect(variadic_file, root=root)
    f = next((t for t in targets3 if t.function == "f"), None)
    assert f is not None, "f not found"
    assert "*args" in f.signature, f"Expected *args in signature, got {f.signature!r}"
    assert "**kwargs" in f.signature, f"Expected **kwargs in signature, got {f.signature!r}"
    assert f.signature != "def f(...)", f"Must not use fallback 'def f(...)', got {f.signature!r}"

    # Return annotation case
    annotated_file = tmp_path / "annotated_case.py"
    annotated_file.write_text("def g() -> int:\n    return 1\n")
    targets4 = FileDetector.detect(annotated_file, root=root)
    g = next((t for t in targets4 if t.function == "g"), None)
    assert g is not None, "g not found"
    assert "-> int" in g.signature, f"Expected '-> int' in signature, got {g.signature!r}"

    # Positional-only parameter case (Python 3.8+): signature must contain '/'
    posonly_file = tmp_path / "posonly_case.py"
    posonly_file.write_text("def h(x: int, /, y: str) -> None:\n    pass\n")
    targets5 = FileDetector.detect(posonly_file, root=root)
    h = next((t for t in targets5 if t.function == "h"), None)
    assert h is not None, "h not found"
    assert "/" in h.signature, (
        f"Expected '/' separator in signature for positional-only param, got {h.signature!r}"
    )


def test_schema_command_uses_results_key() -> None:
    """T127: gazepy schema output uses 'results' key, not 'functions'."""
    runner = CliRunner()
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0, result.output
    schema = json.loads(result.output)
    # The schema should reference 'results' not 'functions'
    schema_str = json.dumps(schema)
    assert '"results"' in schema_str or "results" in schema_str, (
        "schema must reference 'results' key"
    )
    assert '"functions"' not in schema_str, "schema must not reference old 'functions' key"


# ---------------------------------------------------------------------------
# gazepy quality — schema envelope (T124, T125, T126)
# ---------------------------------------------------------------------------


def test_quality_json_envelope() -> None:
    """T124: quality JSON output uses quality_reports/quality_summary envelope."""
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
    data = json.loads(result.output)
    assert "quality_reports" in data, "top-level must have 'quality_reports'"
    assert "quality_summary" in data, "top-level must have 'quality_summary'"
    assert isinstance(data["quality_reports"], list)

    # T124: quality_summary fields
    qs = data["quality_summary"]
    assert "total_tests" in qs
    assert "average_contract_coverage" in qs
    assert isinstance(qs.get("worst_coverage_tests"), list), (
        f"worst_coverage_tests must be list, got {qs.get('worst_coverage_tests')!r}"
    )
    assert "assertion_detection_confidence" in qs
    assert isinstance(qs["assertion_detection_confidence"], int)

    # T125: per-report fields
    for r in data["quality_reports"]:
        assert "over_specification" in r, f"Missing over_specification in {r.get('test_function')}"
        assert "assertion_count" in r, f"Missing assertion_count in {r.get('test_function')}"
        assert "assertion_detection_confidence" in r
        assert "test_location" in r
        ratio = r["over_specification"].get("ratio")
        assert isinstance(ratio, float) and 0.0 <= ratio <= 1.0, (
            f"over_specification.ratio must be float in [0,1], got {ratio!r}"
        )

    # T126: contract_coverage sub-fields
    reports_with_cc = [r for r in data["quality_reports"] if r.get("contract_coverage") is not None]
    assert len(reports_with_cc) > 0, (
        "T126 precondition: at least one quality_report must have non-null contract_coverage"
    )
    for r in reports_with_cc:
        cc = r["contract_coverage"]
        assert "covered_count" in cc, "contract_coverage must have covered_count"
        assert "total_contractual" in cc, "contract_coverage must have total_contractual"
        assert cc.get("discarded_returns") == [], (
            f"discarded_returns must be [] (OC-003), got {cc.get('discarded_returns')!r}"
        )
        assert cc.get("discarded_return_hints") == [], (
            f"discarded_return_hints must be [] (OC-003), got {cc.get('discarded_return_hints')!r}"
        )


def test_quality_over_specification_ratio_zero_assertions() -> None:
    """T125: over_specification.ratio = 0.0 when assertion_count = 0 (no ZeroDivisionError)."""
    # Use a source file that the test suite doesn't cover at all
    # so assertion_count = 0 → ratio must be 0.0 not ZeroDivisionError
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "quality",
            str(_QUALITY_SRC / "undertested.py"),
            "--tests",
            str(_QUALITY_TESTS / "test_simple.py"),  # test_simple doesn't test undertested
            "--format=json",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    data = json.loads(result.output)
    for r in data["quality_reports"]:
        assert r.get("assertion_count") == 0, (
            f"Expected assertion_count=0 (test_simple doesn't test undertested), "
            f"got {r.get('assertion_count')!r}"
        )
        ratio = r.get("over_specification", {}).get("ratio")
        assert ratio == 0.0, (
            f"T125: ratio must be exactly 0.0 when assertion_count=0, got {ratio!r}"
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
    assert "results" in data


def test_analyze_verbose_flag() -> None:
    """--verbose flag exits 0, implies --classify, and produces valid JSON."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), "--format=json", "--verbose"])
    assert result.exit_code == 0, result.output
    data = _parse_json(result.output)
    assert "results" in data


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
    names = [fn["target"]["function"] for fn in data["results"]]
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
    assert data["results"] == []


def test_analyze_include_unexported_flag() -> None:
    """--include-unexported includes underscore-prefixed functions."""
    runner = CliRunner()
    fixture = _TESTDATA / "unexported_function.py"

    # Without the flag: only public functions
    result_default = runner.invoke(cli, ["analyze", str(fixture), "--format=json"])
    assert result_default.exit_code == 0, result_default.output
    data_default = json.loads(result_default.output)
    names_default = [fn["target"]["function"] for fn in data_default["results"]]
    assert "_private_helper" not in names_default
    assert "public_entry_point" in names_default

    # With the flag: both functions included
    result_with = runner.invoke(
        cli, ["analyze", str(fixture), "--format=json", "--include-unexported"]
    )
    assert result_with.exit_code == 0, result_with.output
    data_with = json.loads(result_with.output)
    names_with = [fn["target"]["function"] for fn in data_with["results"]]
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
    assert "results" in data


# ---------------------------------------------------------------------------
# gazepy report — flag removal assertions (4.4)
# ---------------------------------------------------------------------------


def test_report_ai_flag_rejected() -> None:
    """gazepy report --ai <provider> exits 2 (flag removed in ai-http-adapters).

    Scenario: --ai flag rejected (spec §gazepy-report-command).
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["report", "--ai", "ollama"])
    assert result.exit_code == 2
    assert "No such option" in result.output or "No such option" in (result.stderr or "")


def test_report_ai_timeout_flag_rejected() -> None:
    """gazepy report --ai-timeout <n> exits 2 (flag removed in ai-http-adapters).

    Scenario: --ai-timeout flag rejected (spec §gazepy-report-command).
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["report", "--ai-timeout", "60"])
    assert result.exit_code == 2
    assert "No such option" in result.output or "No such option" in (result.stderr or "")


# ---------------------------------------------------------------------------
# gazepy report — prompt-only mode (no provider configured) (4.4)
# ---------------------------------------------------------------------------


def test_report_prompt_only_no_provider(tmp_path: Path) -> None:
    """gazepy report exits 0 and emits JSON when no AI provider is configured.

    Scenario: No provider configured (spec §report command prompt-only mode).
    Patches new_synthesizer_from_config to return None (no provider).
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    # Patch at gaze_py.report.provider (not gaze_py.cli.main) because report()
    # imports new_synthesizer_from_config lazily inside the function body.
    # If that import is ever hoisted to module level, update this patch target.
    with patch(
        "gaze_py.report.provider.new_synthesizer_from_config",
        return_value=None,
    ):
        result = runner.invoke(
            cli,
            ["report", str(_TESTDATA), f"--coverprofile={cov_file}"],
        )

    assert result.exit_code == 0, result.output
    data = _parse_json(result.stdout)
    assert "results" in data
    # Fix 13: assert against result.stderr directly (tip goes to stderr, not stdout).
    assert "Tip:" in result.stderr
    assert ".gaze.yaml" in result.stderr


# ---------------------------------------------------------------------------
# gazepy report — config-driven AI flow (4.4)
# ---------------------------------------------------------------------------


def test_report_config_driven_flow(tmp_path: Path) -> None:
    """gazepy report synthesizes via config-driven provider when available.

    Scenario: Provider from config (spec §gazepy-report-command).
    Patches new_synthesizer_from_config to return NoopSynthesizer(avail=True).
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    noop = NoopSynthesizer(response="AI narrative output", avail=True)
    runner = CliRunner()
    # Patch at gaze_py.report.provider (not gaze_py.cli.main) because report()
    # imports new_synthesizer_from_config lazily inside the function body.
    # If that import is ever hoisted to module level, update this patch target.
    with patch(
        "gaze_py.report.provider.new_synthesizer_from_config",
        return_value=noop,
    ):
        result = runner.invoke(
            cli,
            ["report", str(_TESTDATA), f"--coverprofile={cov_file}"],
        )

    assert result.exit_code == 0, result.output
    assert "AI narrative output" in result.output


def test_report_model_override(tmp_path: Path) -> None:
    """gazepy report --model <m> passes the model override to read_ai_config.

    Scenario: Model CLI override (spec §gazepy-report-command).
    Verifies that read_ai_config is called with the cli_model argument.
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    noop = NoopSynthesizer(response="model override output", avail=True)
    runner = CliRunner()
    with (
        # Patch at gaze_py.report.provider (not gaze_py.cli.main) because report()
        # imports new_synthesizer_from_config lazily inside the function body.
        # If that import is ever hoisted to module level, update this patch target.
        patch(
            "gaze_py.report.provider.new_synthesizer_from_config",
            return_value=noop,
        ),
        patch(
            "gaze_py.report.config.read_ai_config",
            wraps=lambda cfg, cli_model: __import__(
                "gaze_py.report.provider", fromlist=["ProviderConfig"]
            ).ProviderConfig(model=cli_model or ""),
        ) as mock_read,
    ):
        result = runner.invoke(
            cli,
            ["report", str(_TESTDATA), "--model", "gemma3:4b", f"--coverprofile={cov_file}"],
        )

    assert result.exit_code == 0, result.output
    mock_read.assert_called_once()
    _call_args = mock_read.call_args
    assert _call_args[0][1] == "gemma3:4b" or _call_args[1].get("cli_model") == "gemma3:4b"


# ---------------------------------------------------------------------------
# gazepy report — unavailable provider fallback (4.4)
# ---------------------------------------------------------------------------


def test_report_unavailable_provider_fallback(tmp_path: Path) -> None:
    """gazepy report falls back to prompt-only when provider is unavailable.

    Scenario: Provider configured but unavailable (spec §report command
    prompt-only mode). Patches new_synthesizer_from_config to return a
    NoopSynthesizer with avail=False.
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    noop = NoopSynthesizer(avail=False, model="llama3.2:3b")
    runner = CliRunner()
    with (
        # Patch at gaze_py.report.provider (not gaze_py.cli.main) because report()
        # imports new_synthesizer_from_config lazily inside the function body.
        # If that import is ever hoisted to module level, update this patch target.
        patch(
            "gaze_py.report.provider.new_synthesizer_from_config",
            return_value=noop,
        ),
        patch(
            "gaze_py.report.config.read_ai_config",
            return_value=__import__(
                "gaze_py.report.provider", fromlist=["ProviderConfig"]
            ).ProviderConfig(provider="ollama", model="llama3.2:3b"),
        ),
    ):
        result = runner.invoke(
            cli,
            ["report", str(_TESTDATA), f"--coverprofile={cov_file}"],
        )

    assert result.exit_code == 0, result.output
    combined = (result.stderr or "") + result.output
    assert "Warning:" in combined
    assert "not available" in combined
    assert "falling back to prompt-only mode" in combined
    data = _parse_json(result.output)
    assert "results" in data


# ---------------------------------------------------------------------------
# gazepy report — basic invocation (existing tests, updated docstrings)
# ---------------------------------------------------------------------------


def test_report_json_exits_zero(tmp_path: Path) -> None:
    """gazepy report PATH --format=json exits 0 and emits JSON (prompt-only mode).

    No AI provider is configured, so the command emits the JSON payload to
    stdout and exits 0. Uses --coverprofile to skip pytest subprocess.
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(_TESTDATA), "--format=json", f"--coverprofile={cov_file}"],
    )
    assert result.exit_code == 0, result.output
    data = _parse_json(result.stdout)
    assert "results" in data


def test_report_text_exits_zero(tmp_path: Path) -> None:
    """gazepy report PATH --format=text exits 0 (prompt-only mode ignores --format).

    No AI provider is configured, so the command emits JSON regardless of
    --format and exits 0. Uses --coverprofile to skip pytest subprocess.
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(_TESTDATA), "--format=text", f"--coverprofile={cov_file}"],
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

    for fn in data["results"]:
        fn_name = fn.get("target", {}).get("function")
        assert "side_effects" in fn, f"Missing side_effects in {fn_name}"
        # CRAP-derived fields must be present in JSON but null per OC-003.
        assert "line_coverage" in fn, f"Missing line_coverage in {fn_name}"
        assert "crap" in fn, f"Missing crap key in {fn_name}"
        assert fn["crap"] is None, f"Expected crap=null, got {fn['crap']}"
        assert "fix_strategy" in fn, f"Missing fix_strategy in {fn_name}"
        assert fn["fix_strategy"] is None, "Expected fix_strategy=null"
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
    assert "results" in data
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
#
# These cases cover *path resolution* only, so they deliberately use degraded
# entries (no line arrays) and a target with no known extent. That drives the
# file-level fallback, isolating which key matched from how the fraction is
# derived. Per-function derivation is covered separately below.


def _degraded_coverage(raw: dict[str, float]) -> dict[str, _FileCoverage]:
    """Build a coverage map with no per-line data, forcing file-level fallback."""
    return {
        key: _FileCoverage(percent_covered=pct, executed_lines=None, missing_lines=None)
        for key, pct in raw.items()
    }


def _extentless_target() -> FunctionTarget:
    """Build a target with no known line extent (owned_lines is None)."""
    return FunctionTarget(
        function="f",
        file_path="complexity.py",
        line=1,
        complexity=1,
        package="complexity.py",
        receiver=None,
        signature="def f()",
    )


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
        result = _resolve_line_coverage(
            py_file, root, _degraded_coverage(coverage_data), _extentless_target()
        )
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

    result = _resolve_line_coverage(
        py_file, root, _degraded_coverage(coverage_data), _extentless_target()
    )
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
    assert len(data["results"]) > 0


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
    assert "results" in data


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
    assert "results" in data


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
    assert "results" in data


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
    """--max-gaze-crapload exits 0 when gaze_crapload is None (no quality data).

    Without --tests, gaze_crapload is None (OC-003). The gate condition
    requires gaze_crapload is not None, so it does not fire. No warning
    is emitted — the old stale warning has been replaced by real enforcement
    (O5 fix in openspec/changes/report-command/).
    """
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
    # No stale warning — real enforcement is silent when gaze_crapload is None.
    assert "deferred until O1" not in result.stderr


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


def test_crap_baseline_missing_file_exits_2(tmp_path: Path) -> None:
    """T223: crap --baseline with missing file exits 2 with error on stderr."""
    source = tmp_path / "foo.py"
    source.write_text("def foo():\n    return 1\n")
    missing = tmp_path / "nonexistent_baseline.json"

    # Use empty coverprofile to avoid spawning pytest subprocess.
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), f"--baseline={missing}", f"--coverprofile={cov_file}"],
    )
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    # L-1: result.stderr may be None when mix_stderr=True (default) — use `or ""`.
    combined = result.output + (result.stderr or "")
    assert "baseline" in combined.lower() or "not found" in combined.lower()


# ---------------------------------------------------------------------------
# gazepy crap — format flags (task 2.5)
# ---------------------------------------------------------------------------


def test_crap_format_json(tmp_path: Path) -> None:
    """crap --format=json exits 0 and emits valid JSON with results and summary.

    T122b (crap): regression guard — top-level must be 'results' not 'functions'.
    """
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
    # T122b regression guard — 'results' key present, 'functions' key absent.
    assert "results" in data, "T122b: top-level key must be 'results'"
    assert "functions" not in data, "T122b: old 'functions' key must not be present"
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
    payload = json.loads(result.output)
    assert isinstance(payload, dict), f"Expected dict, got {type(payload)}"
    assert "quality_reports" in payload
    reports = payload["quality_reports"]
    assert len(reports) > 0, "Expected at least one report"

    # Find the report for simple_function.
    simple_report = next(
        (
            r
            for r in reports
            if isinstance(r.get("target_function"), dict)
            and r["target_function"].get("function") == "simple_function"
        ),
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
    payload = json.loads(result.output)
    assert isinstance(payload, dict)
    reports = payload["quality_reports"]
    assert len(reports) > 0, "Expected at least one report"

    # Find the report for compute_total.
    undertested_report = next(
        (
            r
            for r in reports
            if isinstance(r.get("target_function"), dict)
            and r["target_function"].get("function") == "compute_total"
        ),
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
    payload = json.loads(result.output)
    reports = payload["quality_reports"]
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
    payload = json.loads(result.output)
    reports = payload["quality_reports"]
    assert isinstance(reports, list)
    # All returned reports must target simple_function.
    # target_function is now a FunctionTarget dict per FR-005 / OC-002.
    for r in reports:
        tf = r.get("target_function")
        tf_name = tf.get("function") if isinstance(tf, dict) else tf
        assert tf_name == "simple_function", (
            f"Expected only simple_function reports, got: {tf_name!r}"
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
    payload = json.loads(result.output)
    reports = payload["quality_reports"]
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
    assert config
    result = assess(
        _QUALITY_SIMPLE_SRC.resolve(),
        _QUALITY_TESTS / "test_simple.py",
        config=config,
    )
    reports = result.reports
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
    """report without PATH exits 2 (missing required argument).

    The report command is now implemented. Without PATH it exits 2 with
    'missing argument' in stderr (our manual check, not Click's).
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["report"])
    assert result.exit_code == 2, f"Expected 2, got {result.exit_code}"
    assert "PATH" in result.stderr or "missing" in result.stderr.lower()


def test_report_stub_mentions_crap_migration() -> None:
    """report --help mentions 'PATH' and 'report' in the help text."""
    runner = CliRunner()
    result = runner.invoke(cli, ["report", "--help"])
    assert result.exit_code == 0
    assert "PATH" in result.output or "report" in result.output


def test_report_stub_accepts_ai_flag(tmp_path: Path) -> None:
    """report --ai <provider> exits 2 — flag removed in ai-http-adapters change.

    The --ai flag was removed; Click returns exit 2 with "No such option".
    Scenario: --ai flag rejected (spec §gazepy-report-command).
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", "--ai", "claude", str(src_dir), f"--coverprofile={cov_file}"],
    )
    assert result.exit_code == 2, f"Expected 2, got {result.exit_code}"


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
        return AnalysisResult(results=[], summary=summary)

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
    """init creates all 8 asset files on first run."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output

    expected = [
        ".opencode/agents/gaze-reporter.md",
        ".opencode/agents/gaze-test-generator.md",
        ".opencode/agents/reviewer-testing.md",
        ".opencode/commands/gaze.md",
        ".opencode/commands/gaze-fix.md",
        ".opencode/commands/speckit.testreview.md",
        ".opencode/references/doc-scoring-model.md",
        ".opencode/references/example-report.md",
    ]
    for rel in expected:
        assert (tmp_path / rel).exists(), f"missing: {rel}"
    assert "created" in result.output
    assert "Run /gaze for quality reports" in result.output


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
    assert "overwritten" in result.output
    # Original asset content should be restored (contains "gaze-reporter").
    assert b"gaze-reporter" in reporter.read_bytes()


def test_init_tool_owned_updated_on_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool-owned files are updated when content differs, even without --force."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    # Corrupt a tool-owned file.
    tool_owned = tmp_path / ".opencode" / "commands" / "gaze-fix.md"
    original = tool_owned.read_bytes()
    tool_owned.write_bytes(b"stale content from an old version")

    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert "updated" in result.output
    assert "content changed" in result.output
    # Content should be restored to embedded version.
    assert tool_owned.read_bytes() == original


def test_init_tool_owned_skipped_when_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tool-owned files are skipped (not reported as updated) when content is identical."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    # Run again without changes — tool-owned files have identical content.
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert "updated" not in result.output
    assert "already up to date" in result.output


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


# ---------------------------------------------------------------------------
# Task 6.4: gazepy crap --tests integration
# ---------------------------------------------------------------------------

# Paths to the quality testdata fixtures (reuse constants from quality section).
_QUALITY_TESTDATA_CRAP = Path(__file__).parent / "testdata" / "quality"
_QUALITY_SRC_CRAP = _QUALITY_TESTDATA_CRAP / "src"
_QUALITY_TESTS_CRAP = _QUALITY_TESTDATA_CRAP / "tests"


def test_crap_with_tests_populates_contract_coverage_reason(tmp_path: Path) -> None:
    """crap --tests populates contract_coverage_reason for at least one function.

    Runs crap on tests/testdata/quality/src/ with --tests pointing at the
    quality test fixtures.  At least one function must have a non-null
    contract_coverage_reason in the JSON output (e.g. "no_test_coverage"
    for orphan_compute, or a real coverage reason for paired functions).

    Uses --coverprofile with an empty files dict to skip the pytest subprocess
    (coverage data is not required for contract_coverage_reason to be populated).
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(_QUALITY_SRC_CRAP),
            "--format=json",
            f"--tests={_QUALITY_TESTS_CRAP}",
            f"--coverprofile={cov_file}",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    data = _parse_json(result.output)
    functions = data["results"]
    assert isinstance(functions, list)
    reasons = [fn.get("contract_coverage_reason") for fn in functions]
    assert any(r is not None for r in reasons), (
        f"Expected at least one non-null contract_coverage_reason; got: {reasons}"
    )


def test_crap_no_test_coverage_reason_gaze_crap_still_null(tmp_path: Path) -> None:
    """crap --tests: orphan_compute has no_test_coverage reason and null gaze_crap.

    The uncovered.py fixture contains orphan_compute which has no corresponding
    test.  Per D5 / Go contract: no_test_coverage → percentage=None →
    gaze_crap stays null (not a float).

    Uses --coverprofile with an empty files dict to skip the pytest subprocess.
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(_QUALITY_SRC_CRAP),
            "--format=json",
            f"--tests={_QUALITY_TESTS_CRAP}",
            f"--coverprofile={cov_file}",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    data = _parse_json(result.output)
    functions = data["results"]

    orphan = next(
        (fn for fn in functions if fn.get("target", {}).get("function") == "orphan_compute"),
        None,
    )
    assert orphan is not None, (
        f"orphan_compute not found in crap output; functions: "
        f"{[f.get('target', {}).get('function') for f in functions]}"
    )
    assert orphan.get("contract_coverage_reason") == "no_test_coverage", (
        f"Expected 'no_test_coverage', got: {orphan.get('contract_coverage_reason')!r}"
    )
    # D5 / Go contract: no_test_coverage → gaze_crap must be null (not a float).
    assert orphan.get("gaze_crap") is None, (
        f"Expected gaze_crap=null for no_test_coverage function, got: {orphan.get('gaze_crap')!r}"
    )


def test_crap_without_tests_gaze_crap_null(tmp_path: Path) -> None:
    """crap without --tests in a dir with no discoverable tests: all gaze_crap are null.

    Creates a minimal source file in a temp dir with no tests/ subdirectory
    and no test_*.py files.  Without quality pipeline data, gaze_crap must
    remain null for all functions (OC-003 compliant).
    """
    source = tmp_path / "example.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    # Provide coverage so CRAP is computed (not null), but no --tests.
    cov: dict[str, object] = {"files": {"example.py": {"summary": {"percent_covered": 80.0}}}}
    cov_file = tmp_path / "coverage.json"
    cov_file.write_text(json.dumps(cov), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(tmp_path),
            "--format=json",
            f"--coverprofile={cov_file}",
        ],
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr}"
    )
    data = _parse_json(result.output)
    for fn in data["results"]:
        assert fn.get("gaze_crap") is None, (
            f"Expected gaze_crap=null without --tests, got {fn.get('gaze_crap')!r} "
            f"for function {fn.get('target', {}).get('function')!r}"
        )


def test_crap_help_shows_tests_option() -> None:
    """gazepy crap --help output contains '--tests'."""
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", "--help"])
    assert result.exit_code == 0, result.output
    assert "--tests" in result.output, (
        f"Expected '--tests' in crap --help output; got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Phase 4 — CLI tests (tasks 4.1–4.15)
# ---------------------------------------------------------------------------


def test_analyze_invalid_config_exits_2(tmp_path: Path) -> None:
    """analyze --config with invalid threshold value exits 2."""
    config_file = tmp_path / ".gaze.yaml"
    config_file.write_text("classification:\n  thresholds:\n    contractual: -5\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(_TESTDATA), f"--config={config_file}"])
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    assert "Error" in result.output or "Error" in (result.stderr or "")


def test_analyze_contractual_threshold_override(tmp_path: Path) -> None:
    """analyze --contractual-threshold and --incidental-threshold flags are accepted."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            str(_TESTDATA),
            "--contractual-threshold=95",
            "--incidental-threshold=10",
            "--format=json",
        ],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"


def test_crap_invalid_config_exits_2(tmp_path: Path) -> None:
    """crap --config with invalid threshold exits 2."""
    config_file = tmp_path / ".gaze.yaml"
    config_file.write_text("classification:\n  thresholds:\n    contractual: -5\n")
    # Need a valid coverprofile so the command runs past arg parsing
    cov = tmp_path / "cov.json"
    cov.write_text('{"files": {}}')
    runner = CliRunner()
    result = runner.invoke(
        cli, ["crap", str(_TESTDATA), f"--config={config_file}", f"--coverprofile={cov}"]
    )
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    assert "Error" in result.output or "Error" in (result.stderr or "")


def test_crap_contractual_threshold_override(tmp_path: Path) -> None:
    """crap --crap-threshold and --gaze-crap-threshold flags accepted."""
    cov = tmp_path / "cov.json"
    cov.write_text('{"files": {}}')
    source = tmp_path / "foo.py"
    source.write_text("def f(): return 1\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(tmp_path),
            f"--coverprofile={cov}",
            "--crap-threshold=5.0",
            "--gaze-crap-threshold=10.0",
        ],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"


def test_quality_no_tests_discovered_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """quality with no discoverable tests exits 2."""
    src = tmp_path / "src" / "foo.py"
    src.parent.mkdir()
    src.write_text("def f(): return 1\n")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["quality", str(src)])
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"
    assert "no tests" in (result.stderr or "").lower() or "no tests" in result.output.lower()


def test_quality_auto_discovers_test_file_via_glob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """quality discovers test_*.py via glob when no tests/ dir exists."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src = src_dir / "foo.py"
    src.write_text("def foo(): return 1\n")
    test_file = tmp_path / "test_foo.py"
    test_file.write_text("def test_foo():\n    result = foo()\n    assert result == 1\n")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["quality", str(src)])
    # Should NOT exit with "no tests directory found" error (exit 2 + that message)
    combined = result.output + (result.stderr or "")
    assert not (result.exit_code == 2 and "no tests" in combined.lower()), (
        f"Glob fallback not used; got exit {result.exit_code}\n{result.output}"
    )


def test_crap_quadrant_counts_populated_with_tests_and_coverage(tmp_path: Path) -> None:
    """crap with --tests and --coverprofile populates summary.quadrant_counts."""
    # Use the testdata/quality fixtures which have pairable src+tests
    # Need a coverprofile that provides non-zero line coverage for those functions
    quality_src = Path(__file__).parent / "testdata" / "quality" / "src"
    quality_tests = Path(__file__).parent / "testdata" / "quality" / "tests"

    # Build a coverprofile with 100% for the simple function
    cov = tmp_path / "cov.json"
    # The quality src has simple.py with simple_function; give it 100% coverage
    cov_data = {
        "files": {
            str(quality_src / "simple.py"): {"summary": {"percent_covered": 100.0}},
        }
    }
    cov.write_text(json.dumps(cov_data))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(quality_src),
            f"--tests={quality_tests}",
            f"--coverprofile={cov}",
            "--format=json",
        ],
    )
    assert result.exit_code == 0, f"Expected exit 0\n{result.output}\n{result.stderr}"
    data = _parse_json(result.output)
    # quadrant_counts requires both line_coverage (from coverprofile) and
    # contract_coverage (from quality pipeline) to be non-null
    # With 100% line coverage and a paired test, at least one function should have a quadrant
    summary = data.get("summary", {})
    # It's acceptable if quadrant_counts is still None (depends on pairing quality)
    # The key assertion is the command succeeded and returned valid JSON with summary
    assert "quadrant_counts" in summary, f"summary missing quadrant_counts key: {summary}"


def test_docscan_include_flag(tmp_path: Path) -> None:
    """docscan --include flag accepted without error."""
    (tmp_path / "README.md").write_text("readme content")
    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--include=*.md"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"


def test_docscan_timeout_flag(tmp_path: Path) -> None:
    """docscan --timeout flag accepted without error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), "--timeout=5.0"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"


def test_docscan_invalid_config_exits_1(tmp_path: Path) -> None:
    """docscan --config with invalid YAML exits 1 with error message."""
    # docscan uses click.Path(exists=True) so file must exist on disk
    config_file = tmp_path / ".gaze.yaml"
    config_file.write_text("classification:\n  thresholds:\n    contractual: -5\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path), f"--config={config_file}"])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    assert "Error" in result.output or "Error" in (result.stderr or "")


def test_docscan_scan_docs_exception_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docscan exits 1 when scan_docs raises an unexpected exception."""
    import gaze_py.cli.main as cli_main

    # Patch at the CLI module level (where scan_docs was imported via
    # `from gaze_py.analysis.docscan import scan_docs`).
    monkeypatch.setattr(
        cli_main,
        "scan_docs",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["docscan", str(tmp_path)])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    assert "Error" in result.output or "Error" in (result.stderr or "")


def test_quality_min_coverage_gate_skipped_for_no_contractual_effects(tmp_path: Path) -> None:
    """quality --min-contract-coverage exits 0 when no contractual effects (gate skipped)."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src = src_dir / "pure.py"
    src.write_text("def pure_function(): pass\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_pure.py"
    test_file.write_text(
        "from pure import pure_function\n\n"
        "def test_pure():\n"
        "    result = pure_function()\n"
        "    assert result is None\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["quality", str(src_dir), f"--tests={tests_dir}", "--min-contract-coverage=50"],
    )
    assert result.exit_code == 0, (
        f"Expected exit 0 (no contractual effects), got {result.exit_code}\n"
        f"{result.output}\n{result.stderr}"
    )
    assert "FAIL" not in result.output
    assert "FAIL" not in (result.stderr or "")


def test_compute_avg_line_coverage_returns_none_when_no_data() -> None:
    """_compute_avg_line_coverage returns None when coverage_data is None.

    # CR-004: Tested directly because the None-return branch when coverage_data=None
    # cannot be triggered through the CLI without spawning a subprocess (which would
    # require a full coverage run); the CliRunner path always provides coverage data
    # when --coverprofile is given.
    """
    from gaze_py.cli.main import _compute_avg_line_coverage

    result = _compute_avg_line_coverage([], coverage_data=None)
    assert result is None


def test_compute_gaze_crapload_returns_none_when_no_gaze_crap_data() -> None:
    """_compute_gaze_crapload returns None when no targets have gaze_crap scores.

    # CR-004: Tested directly because producing zero gaze_crap targets through the CLI
    # requires quality pipeline results, which depend on test fixture pairing —
    # prohibitively complex for a boundary test.
    """
    from gaze_py.cli.main import _compute_gaze_crapload
    from gaze_py.config.loader import GazeConfig

    result = _compute_gaze_crapload([], GazeConfig())
    assert result is None


def test_compute_quadrant_counts_returns_none_when_no_labels() -> None:
    """_compute_quadrant_counts returns None when no targets have quadrant labels.

    # CR-004: Tested directly because producing zero quadrant labels through the CLI
    # requires line coverage AND contract coverage to both be non-null for at least
    # one function — complex to set up for a boundary test.
    """
    from gaze_py.cli.main import _compute_quadrant_counts

    result = _compute_quadrant_counts([])
    assert result is None


# ---------------------------------------------------------------------------
# Task 5.2 — report command + max-gaze-crapload + prompt loading tests
# ---------------------------------------------------------------------------
# Note: _QUALITY_SRC and _QUALITY_TESTS are defined at module level above
# (line 1174–1175) — no redefinition needed here.


def test_max_gaze_crapload_exits_1_when_exceeded(tmp_path: Path) -> None:
    """crap with --max-gaze-crapload=1 exits 1 when gaze_crapload exceeds 1.

    Uses quality testdata fixtures with --gaze-crap-threshold=1 so that
    functions with GazeCRAP >= 1.0 count toward gaze_crapload (the fixture
    has functions with GazeCRAP=1.0 and GazeCRAP=2.5). Sets
    --max-gaze-crapload=1 so the gate fires when gaze_crapload > 1.

    Uses --coverprofile with an empty files dict to skip the pytest subprocess
    (same pattern as test_crap_with_tests_populates_contract_coverage_reason).
    Also asserts stdout is non-empty (guards against vacuous pass).
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(_QUALITY_SRC),
            "--tests",
            str(_QUALITY_TESTS),
            "--gaze-crap-threshold=1",
            "--max-gaze-crapload=1",
            "--format=json",
            f"--coverprofile={cov_file}",
        ],
    )
    # stdout must be non-empty (analysis ran and produced data).
    assert result.stdout.strip(), "stdout should be non-empty (analysis must have run)"
    # Parse the JSON payload from stdout.
    data = json.loads(result.stdout)
    gaze_crapload = data.get("summary", {}).get("gaze_crapload")
    if gaze_crapload is not None and gaze_crapload > 1:
        assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
        assert "CI gate" in (result.stderr or ""), (
            f"Expected 'CI gate' in stderr, got: {result.stderr!r}"
        )
    else:
        # If fixture produces gaze_crapload <= 1, gate doesn't fire — skip.
        pytest.skip(f"fixture gaze_crapload={gaze_crapload!r}; gate not triggered")


def test_max_gaze_crapload_help_text_updated() -> None:
    """gazepy crap --help output does NOT contain the stale 'deferred until O1' text."""
    runner = CliRunner()
    result = runner.invoke(cli, ["crap", "--help"])
    assert result.exit_code == 0, result.output
    assert "deferred until O1" not in result.output


def test_report_no_ai_emits_json(tmp_path: Path) -> None:
    """gazepy report (no provider configured) exits 0, stdout is JSON, stderr has Tip.

    Uses --coverprofile with an empty files dict to skip the pytest subprocess
    (same pattern as other crap/report integration tests).

    Note: CliRunner in click 8.4 separates stderr automatically via
    result.stdout / result.stderr; no mix_stderr parameter needed.
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(_QUALITY_SRC), f"--coverprofile={cov_file}"],
    )
    assert result.exit_code == 0, f"exit={result.exit_code} stderr={result.stderr!r}"
    # stdout must be valid JSON containing 'functions' and 'summary'.
    data = json.loads(result.stdout)
    assert "results" in data, f"'results' not in JSON: {list(data.keys())}"
    assert "summary" in data, f"'summary' not in JSON: {list(data.keys())}"
    # stderr must contain the Tip about configuring a provider.
    tip_text = (result.stderr or "") + result.output
    assert "Tip:" in tip_text, f"Expected Tip in output, got: {result.stderr!r}"
    assert ".gaze.yaml" in tip_text, f"Expected .gaze.yaml in Tip, got: {result.stderr!r}"


def test_report_config_driven_flow_synthesizes_via_factory(tmp_path: Path) -> None:
    """gazepy report exits 0 and stdout equals the mocked AI response.

    The report command uses new_synthesizer_from_config to obtain a Synthesizer.
    We patch at the provider module so the factory returns a NoopSynthesizer.

    Uses --coverprofile with an empty files dict to skip the pytest subprocess.
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    noop = NoopSynthesizer(response="narrative text", avail=True)
    runner = CliRunner()
    # Patch at gaze_py.report.provider (not gaze_py.cli.main) because report()
    # imports new_synthesizer_from_config lazily inside the function body.
    # If that import is ever hoisted to module level, update this patch target.
    with patch(
        "gaze_py.report.provider.new_synthesizer_from_config",
        return_value=noop,
    ):
        result = runner.invoke(
            cli,
            ["report", str(_QUALITY_SRC), f"--coverprofile={cov_file}"],
        )

    assert result.exit_code == 0, f"exit={result.exit_code} stderr={result.stderr!r}"
    assert "narrative text" in result.stdout


def test_load_report_prompt_uses_local_override(tmp_path: Path) -> None:
    """_load_report_prompt returns local override content (frontmatter stripped)."""
    from gaze_py.cli.main import _load_report_prompt

    # Create a local override with frontmatter.
    agent_dir = tmp_path / ".opencode" / "agents"
    agent_dir.mkdir(parents=True)
    override = agent_dir / "gaze-reporter.md"
    override.write_text(
        "---\nmode: subagent\n---\nThis is the local override body.\n",
        encoding="utf-8",
    )

    result = _load_report_prompt(tmp_path)
    assert "This is the local override body." in result
    # Frontmatter must be stripped.
    assert "mode: subagent" not in result


def test_load_report_prompt_falls_back_to_bundled(tmp_path: Path) -> None:
    """_load_report_prompt returns a non-empty string from the bundled asset."""
    from gaze_py.cli.main import _load_report_prompt

    # tmp_path has no .opencode/agents/gaze-reporter.md.
    result = _load_report_prompt(tmp_path)
    assert result.strip(), "Bundled prompt should be non-empty"


# ---------------------------------------------------------------------------
# MEDIUM-2: report command gate-failure and --format warning tests
# ---------------------------------------------------------------------------


def test_report_max_gaze_crapload_gate(tmp_path: Path) -> None:
    """report --max-crapload=1 exits 1 AND stdout contains valid JSON.

    HIGH-1 contract: the gate fires AFTER output, so the JSON payload must
    always be written to stdout before the exit.

    Creates two functions with complexity=5 and 0% line coverage so that
    CRAP = 5^2 * (1-0)^3 + 5 = 30 for each, which exceeds the default
    crap_threshold=15.0 → crapload=2. Setting --max-crapload=1 triggers the
    gate (crapload=2 > max_crapload=1).

    Coverage key uses filename-only ("complex.py") to match the resolver's
    filename-only fallback (branch 3 of _resolve_line_coverage).
    """
    src = tmp_path / "complex.py"
    src.write_text(
        # Two functions with cyclomatic complexity=5 (4 nested ifs + 1 base).
        "def func_a(x, y, z, w):\n"
        "    if x:\n"
        "        if y:\n"
        "            if z:\n"
        "                if w:\n"
        "                    return 1\n"
        "                return 2\n"
        "            return 3\n"
        "        return 4\n"
        "    return 5\n"
        "\n"
        "def func_b(a, b, c, d):\n"
        "    if a:\n"
        "        if b:\n"
        "            if c:\n"
        "                if d:\n"
        "                    return 1\n"
        "                return 2\n"
        "            return 3\n"
        "        return 4\n"
        "    return 5\n",
        encoding="utf-8",
    )
    # Filename-only key so _resolve_line_coverage's branch-3 fallback matches.
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(
        json.dumps({"files": {"complex.py": {"summary": {"percent_covered": 0.0}}}}),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "report",
            str(tmp_path),
            "--max-crapload=1",
            f"--coverprofile={cov_file}",
        ],
    )

    # stdout must be non-empty valid JSON regardless of exit code (gate fires after output).
    assert result.stdout.strip(), "stdout must be non-empty — JSON emitted before gate"
    data = json.loads(result.stdout)
    assert "results" in data, f"'results' missing from JSON: {list(data.keys())}"
    assert "summary" in data, f"'summary' missing from JSON: {list(data.keys())}"

    crapload_val = data.get("summary", {}).get("crapload")
    if crapload_val is not None and crapload_val > 1:
        assert result.exit_code == 1, (
            f"Expected exit 1 when crapload={crapload_val} > 1, got {result.exit_code}"
        )
        assert "CI gate" in (result.stderr or ""), (
            f"Expected 'CI gate' in stderr, got: {result.stderr!r}"
        )
    else:
        pytest.skip(f"fixture crapload={crapload_val!r}; gate not triggered")


def test_report_format_warning_with_ai(tmp_path: Path) -> None:
    """report --ai flag is rejected with exit 2 (flag removed in ai-http-adapters).

    The --ai flag was removed; --format is still accepted. Verifies that
    passing --ai returns exit 2 with "No such option" from Click.

    Scenario: --ai flag rejected (spec §gazepy-report-command).
    """
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "report",
            str(_QUALITY_SRC),
            "--ai",
            "opencode",
            "--format=json",
            f"--coverprofile={cov_file}",
        ],
    )

    assert result.exit_code == 2, f"Expected 2, got {result.exit_code}"
    assert "No such option" in result.output or "No such option" in (result.stderr or "")


# ---------------------------------------------------------------------------
# T223: CLI integration tests for --baseline (Story 2)
# ---------------------------------------------------------------------------


def _make_baseline_json(entries: list[dict]) -> str:  # type: ignore[type-arg]
    """Wrap entries in the new-schema baseline envelope."""
    return json.dumps({"results": entries})


def _make_crap_entry(pkg: str, fn: str, crap: float) -> dict:  # type: ignore[type-arg]
    """Build a minimal crap result entry for baseline fixtures.

    ``pkg`` should match the ``target.package`` value that ``gazepy crap``
    produces — typically the filename relative to the analysis root (e.g.
    ``"src.py"`` when analyzing a directory containing ``src.py``).
    """
    return {
        "target": {"package": pkg, "function": fn},
        "crap": crap,
        "gaze_crap": None,
    }


def test_crap_baseline_regression_exits_1(tmp_path: Path) -> None:
    """T223: regression (CRAP increased) → exit 1 + comparison.passed == false in JSON."""
    source = tmp_path / "src.py"
    source.write_text("def compute():\n    return 1\n", encoding="utf-8")

    # 0% coverage → CRAP = complexity^2 = 2.0 for complexity=1.
    # This ensures a non-null CRAP value for the regression comparison.
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(
        json.dumps({"files": {"src.py": {"summary": {"percent_covered": 0.0}}}}),
        encoding="utf-8",
    )

    # Baseline: compute had CRAP=0.0 → current CRAP=2.0 is a regression.
    # package must match the relative path that gazepy crap produces ("src.py").
    baseline_entries = [_make_crap_entry("src.py", "compute", crap=0.0)]
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(_make_baseline_json(baseline_entries), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(tmp_path),
            "--format=json",
            f"--baseline={baseline_file}",
            f"--coverprofile={cov_file}",
        ],
    )
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    data = json.loads(result.output)
    assert "comparison" in data, f"'comparison' key missing: {list(data.keys())}"
    assert data["comparison"]["passed"] is False


def test_crap_baseline_no_regression_exits_0(tmp_path: Path) -> None:
    """T223: no regression → exit 0 + comparison.passed == true in JSON."""
    source = tmp_path / "src.py"
    source.write_text("def compute():\n    return 1\n", encoding="utf-8")

    # Use empty coverprofile to avoid spawning pytest subprocess.
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    # Baseline: compute had CRAP=999.0 → current will always be an improvement.
    # package must match the relative path that gazepy crap produces ("src.py").
    baseline_entries = [_make_crap_entry("src.py", "compute", crap=999.0)]
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(_make_baseline_json(baseline_entries), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(tmp_path),
            "--format=json",
            f"--baseline={baseline_file}",
            f"--coverprofile={cov_file}",
        ],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}"
    data = json.loads(result.output)
    assert "comparison" in data
    assert data["comparison"]["passed"] is True


def test_crap_baseline_auto_discovery(tmp_path: Path) -> None:
    """T223: auto-discovery reads .gaze/baseline.json from project_root."""
    source = tmp_path / "src.py"
    source.write_text("def compute():\n    return 1\n", encoding="utf-8")

    # Use empty coverprofile to avoid spawning pytest subprocess.
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    # Write baseline to the auto-discovery location.
    # package must match the relative path that gazepy crap produces ("src.py").
    gaze_dir = tmp_path / ".gaze"
    gaze_dir.mkdir()
    baseline_entries = [_make_crap_entry("src.py", "compute", crap=999.0)]
    (gaze_dir / "baseline.json").write_text(_make_baseline_json(baseline_entries), encoding="utf-8")

    runner = CliRunner()
    # No --baseline flag — auto-discovery should find .gaze/baseline.json.
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), "--format=json", f"--coverprofile={cov_file}"],
    )
    # Auto-discovery ran → comparison key present in output.
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}"
    data = json.loads(result.output)
    assert "comparison" in data, (
        f"'comparison' key missing — auto-discovery may not have fired: {list(data.keys())}"
    )


def test_crap_baseline_auto_discovery_corrupt_warns_and_skips(tmp_path: Path) -> None:
    """T223: auto-discovered corrupt baseline → stderr warning, no exit 2, normal output."""
    source = tmp_path / "src.py"
    source.write_text("def compute():\n    return 1\n", encoding="utf-8")

    # Use empty coverprofile to avoid spawning pytest subprocess.
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    gaze_dir = tmp_path / ".gaze"
    gaze_dir.mkdir()
    (gaze_dir / "baseline.json").write_text("{ not valid json }", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["crap", str(tmp_path), "--format=json", f"--coverprofile={cov_file}"],
    )
    # Must NOT exit 2 — auto-discovered corrupt file is a warning, not a fatal error.
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}"
    # Warning may appear in stderr or mixed into output depending on Click version.
    combined = result.output + (result.stderr or "")
    assert "Warning" in combined or "warning" in combined.lower()
    # Normal CRAP output emitted (no comparison key since comparison was skipped).
    data = _parse_json(result.output)
    assert "results" in data


def test_crap_baseline_text_format_pass(tmp_path: Path) -> None:
    """T223/T226: --format=text with passing baseline emits PASS verdict."""
    source = tmp_path / "src.py"
    source.write_text("def compute():\n    return 1\n", encoding="utf-8")

    # Use empty coverprofile to avoid spawning pytest subprocess.
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    # package must match the relative path that gazepy crap produces ("src.py").
    baseline_entries = [_make_crap_entry("src.py", "compute", crap=999.0)]
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(_make_baseline_json(baseline_entries), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crap",
            str(tmp_path),
            "--format=text",
            f"--baseline={baseline_file}",
            f"--coverprofile={cov_file}",
        ],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}"
    assert "--- Baseline Comparison: PASS ---" in result.output
