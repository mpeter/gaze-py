"""Integration tests for quality/pipeline.py — assess() using testdata fixtures."""

from __future__ import annotations

from pathlib import Path

# TC-013: _score_target is imported directly because the public CLI surface
# (gazepy crap / gazepy quality) cannot exercise the effect_confidence_range
# wiring in isolation — the public path requires a fixture whose classification
# is guaranteed ambiguous by the real engine, which is non-deterministic.
# Testing _score_target directly verifies the wiring without coupling to
# classifier thresholds or fixture classification outcomes.
from gaze_py.cli.main import _score_target
from gaze_py.config.loader import GazeConfig
from gaze_py.quality.pipeline import AssessResult, assess
from gaze_py.taxonomy.models import ContractCoverageResult, FunctionTarget

# Paths to testdata fixtures.
_TESTDATA = Path(__file__).parent / "testdata" / "quality"
_SRC = _TESTDATA / "src"
_TESTS = _TESTDATA / "tests"

# Alias used by task 4.4 tests (matches tasks.md naming convention).
QUALITY_FIXTURES = Path(__file__).parent / "testdata" / "quality"


def _default_config() -> GazeConfig:
    """Return a GazeConfig with default thresholds."""
    return GazeConfig()


# ---------------------------------------------------------------------------
# simple fixture: 100% coverage expected
# ---------------------------------------------------------------------------


def test_simple_fixture_full_coverage() -> None:
    """simple_function: assert on return value → 100% contract coverage."""
    result = assess(
        _SRC / "simple.py",
        _TESTS / "test_simple.py",
        config=_default_config(),
    )
    reports = result.reports
    assert len(reports) >= 1
    # Find the report for simple_function.
    report = next(
        (r for r in reports if r.target_function == "simple_function"),
        None,
    )
    assert report is not None, f"No report for simple_function. Reports: {reports}"
    assert report.contract_coverage is not None
    assert report.contract_coverage.percentage == 100.0


# ---------------------------------------------------------------------------
# raises fixture: RaiseException effect covered
# ---------------------------------------------------------------------------


def test_raises_fixture_coverage() -> None:
    """raises_on_negative: pytest.raises → ErrorReturn covered, percentage > 0."""
    result = assess(
        _SRC / "raises_fn.py",
        _TESTS / "test_raises.py",
        config=_default_config(),
    )
    reports = result.reports
    assert len(reports) >= 1
    report = next(
        (r for r in reports if r.target_function == "raises_on_negative"),
        None,
    )
    assert report is not None, f"No report for raises_on_negative. Reports: {reports}"
    assert report.contract_coverage is not None
    # RaiseException should be covered.
    assert report.contract_coverage.percentage is not None
    assert report.contract_coverage.percentage > 0


# ---------------------------------------------------------------------------
# undertested fixture: 0% coverage (contractual effects exist but no assertions)
# ---------------------------------------------------------------------------


def test_undertested_fixture_zero_coverage() -> None:
    """compute_total: no assertions → 0% coverage (not None — contractual effects exist)."""
    result = assess(
        _SRC / "undertested.py",
        _TESTS / "test_undertested.py",
        config=_default_config(),
    )
    reports = result.reports
    assert len(reports) >= 1
    report = next(
        (r for r in reports if r.target_function == "compute_total"),
        None,
    )
    assert report is not None, f"No report for compute_total. Reports: {reports}"
    assert report.contract_coverage is not None
    # Must be 0.0 (not None) — contractual effects exist but no assertions cover them.
    assert report.contract_coverage.percentage is not None, (
        "Expected 0.0 coverage, got None — pipeline incorrectly returned null-not-zero"
    )
    assert report.contract_coverage.percentage == 0.0


# ---------------------------------------------------------------------------
# attribute_mutation fixture: attribute mutation classified as incidental
# ---------------------------------------------------------------------------


def test_attribute_mutation_fixture_coverage() -> None:
    """set_label: attribute mutation classified as incidental.

    Pipeline returns percentage=None, reason='no_effects_detected'.
    """
    result = assess(
        _SRC / "attribute_mutation.py",
        _TESTS / "test_attribute_mutation.py",
        config=_default_config(),
    )
    reports = result.reports
    assert len(reports) >= 1
    report = next(
        (r for r in reports if r.target_function == "set_label"),
        None,
    )
    assert report is not None, f"No report for set_label. Reports: {reports}"
    # The attribute_mutation fixture's set_label function mutates an attribute
    # but the detector classifies it as incidental (not contractual), so total_contractual=0.
    # The pipeline returns a ContractCoverageResult with percentage=None and
    # reason='no_effects_detected'. Assert the concrete pipeline output.
    assert report.contract_coverage is not None
    assert report.contract_coverage.percentage is None
    assert report.contract_coverage.reason == "no_effects_detected"
    assert report.contract_coverage.total_contractual == 0


# ---------------------------------------------------------------------------
# target_func filtering
# ---------------------------------------------------------------------------


def test_target_func_filtering() -> None:
    """target_func='simple_function' → only reports for that function returned."""
    result = assess(
        _SRC / "simple.py",
        _TESTS / "test_simple.py",
        config=_default_config(),
        target_func="simple_function",
    )
    reports = result.reports
    for report in reports:
        assert report.target_function == "simple_function"


def test_target_func_no_match() -> None:
    """target_func='nonexistent_fn' → empty result, no error."""
    result = assess(
        _SRC / "simple.py",
        _TESTS / "test_simple.py",
        config=_default_config(),
        target_func="nonexistent_fn",
    )
    reports = result.reports
    assert reports == ()


# ---------------------------------------------------------------------------
# empty tests_path
# ---------------------------------------------------------------------------


def test_empty_tests_path_returns_empty(tmp_path: Path) -> None:
    """No test functions found → assess() returns AssessResult with empty tuples."""
    # Create an empty directory.
    empty_tests = tmp_path / "tests"
    empty_tests.mkdir()
    result = assess(
        _SRC / "simple.py",
        empty_tests,
        config=_default_config(),
    )
    reports = result.reports
    assert reports == ()


def test_nonexistent_tests_file_returns_empty(tmp_path: Path) -> None:
    """Non-existent tests file → assess() returns AssessResult with empty tuples."""
    result = assess(
        _SRC / "simple.py",
        tmp_path / "test_missing.py",
        config=_default_config(),
    )
    reports = result.reports
    assert reports == ()


# ---------------------------------------------------------------------------
# effect_confidence_range — ECR-001 / ECR-002
# ---------------------------------------------------------------------------


def test_effect_confidence_range_populated_when_all_effects_ambiguous() -> None:
    """ECR-001: effect_confidence_range is (min, max) when reason=='all_effects_ambiguous'."""
    # Construct a ContractCoverageResult directly with the all_effects_ambiguous reason.
    # This tests the _score_target() CLI wiring independently of the classification
    # engine, which avoids needing a fixture whose classification is guaranteed ambiguous.
    quality_result = ContractCoverageResult(
        percentage=None,
        covered_effects=0,
        total_contractual=0,
        over_specification_count=0,
        unmapped_assertions=0,
        reason="all_effects_ambiguous",
        min_confidence=60,
        max_confidence=85,
    )
    target = FunctionTarget(name="f", file_path="test.py", line=1, complexity=1)
    cfg = GazeConfig()
    _score_target(target, line_coverage_frac=None, config=cfg, quality_result=quality_result)

    assert target.score is not None
    assert target.score.effect_confidence_range == (60, 85)
    assert target.score.effect_confidence_range[0] <= target.score.effect_confidence_range[1]
    assert 0 <= target.score.effect_confidence_range[0] <= 100
    assert 0 <= target.score.effect_confidence_range[1] <= 100


def test_effect_confidence_range_none_for_normal_coverage() -> None:
    """ECR-002: effect_confidence_range is None when reason is not 'all_effects_ambiguous'."""
    quality_result = ContractCoverageResult(
        percentage=100.0,
        covered_effects=1,
        total_contractual=1,
        over_specification_count=0,
        unmapped_assertions=0,
        reason=None,
    )
    target = FunctionTarget(name="f", file_path="test.py", line=1, complexity=1)
    cfg = GazeConfig()
    _score_target(target, line_coverage_frac=None, config=cfg, quality_result=quality_result)

    assert target.score is not None
    assert target.score.effect_confidence_range is None


def test_effect_confidence_range_none_for_no_effects() -> None:
    """ECR-002: effect_confidence_range is None when reason is 'no_effects_detected'."""
    quality_result = ContractCoverageResult(
        percentage=None,
        covered_effects=0,
        total_contractual=0,
        over_specification_count=0,
        unmapped_assertions=0,
        reason="no_effects_detected",
    )
    target = FunctionTarget(name="f", file_path="test.py", line=1, complexity=1)
    cfg = GazeConfig()
    _score_target(target, line_coverage_frac=None, config=cfg, quality_result=quality_result)

    assert target.score is not None
    assert target.score.effect_confidence_range is None


# ---------------------------------------------------------------------------
# Task 4.4 — AssessResult.untested population (D6 in design.md)
# ---------------------------------------------------------------------------


def test_assess_returns_assess_result() -> None:
    """assess() returns an AssessResult with .reports and .untested attributes."""
    result = assess(
        QUALITY_FIXTURES / "src" / "simple.py",
        QUALITY_FIXTURES / "tests" / "test_simple.py",
        config=_default_config(),
    )
    assert isinstance(result, AssessResult)
    assert hasattr(result, "reports")
    assert hasattr(result, "untested")


def test_assess_untested_has_no_test_coverage_reason() -> None:
    """uncovered.py: orphan_compute has no test → reason='no_test_coverage', percentage=None."""
    result = assess(
        src_path=QUALITY_FIXTURES / "src",
        tests_path=QUALITY_FIXTURES / "tests",
        config=_default_config(),
    )
    assert len(result.untested) > 0, (
        f"Expected non-empty untested, got empty. reports={result.reports}"
    )
    orphan = next(
        (r for r in result.untested if r.target_function == "orphan_compute"),
        None,
    )
    assert orphan is not None, f"No untested entry for orphan_compute. untested={result.untested}"
    assert orphan.contract_coverage is not None
    assert orphan.contract_coverage.reason == "no_test_coverage", (
        f"Expected reason='no_test_coverage', got {orphan.contract_coverage.reason!r}"
    )
    assert orphan.contract_coverage.percentage is None, (
        f"Expected percentage=None (OC-003), got {orphan.contract_coverage.percentage!r}"
    )


def test_assess_untested_test_function_is_empty_string() -> None:
    """All entries in result.untested have test_function='' (sentinel per D6)."""
    result = assess(
        src_path=QUALITY_FIXTURES / "src",
        tests_path=QUALITY_FIXTURES / "tests",
        config=_default_config(),
    )
    for report in result.untested:
        assert report.test_function == "", (
            f"Expected test_function='', got {report.test_function!r} "
            f"for target_function={report.target_function!r}"
        )


def test_assess_paired_functions_not_in_untested() -> None:
    """No function name appears in both result.reports and result.untested."""
    result = assess(
        src_path=QUALITY_FIXTURES / "src",
        tests_path=QUALITY_FIXTURES / "tests",
        config=_default_config(),
    )
    paired_names = {r.target_function for r in result.reports if r.target_function}
    untested_names = {r.target_function for r in result.untested}
    overlap = paired_names & untested_names
    assert not overlap, f"Functions appear in both reports and untested: {overlap}"


def test_assess_no_effects_function_not_in_untested() -> None:
    """simple.py: simple_function is fully covered → result.untested is empty."""
    result = assess(
        src_path=QUALITY_FIXTURES / "src" / "simple.py",
        tests_path=QUALITY_FIXTURES / "tests" / "test_simple.py",
        config=_default_config(),
    )
    assert len(result.untested) == 0, (
        f"Expected empty untested for fully-covered simple.py, got {result.untested}"
    )
