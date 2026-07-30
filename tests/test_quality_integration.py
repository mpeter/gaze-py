"""Integration tests for quality/pipeline.py — assess() using testdata fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

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
    assert result
    reports = result.reports
    assert len(reports) >= 1
    # Find the report for simple_function.
    report = next(
        (
            r
            for r in reports
            if isinstance(r.target_function, FunctionTarget)
            and r.target_function.function == "simple_function"
        ),
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
    assert result
    reports = result.reports
    assert len(reports) >= 1
    report = next(
        (
            r
            for r in reports
            if isinstance(r.target_function, FunctionTarget)
            and r.target_function.function == "raises_on_negative"
        ),
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
    assert result
    reports = result.reports
    assert len(reports) >= 1
    report = next(
        (
            r
            for r in reports
            if isinstance(r.target_function, FunctionTarget)
            and r.target_function.function == "compute_total"
        ),
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
    assert result
    reports = result.reports
    assert len(reports) >= 1
    report = next(
        (
            r
            for r in reports
            if isinstance(r.target_function, FunctionTarget)
            and r.target_function.function == "set_label"
        ),
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
    assert isinstance(result, AssessResult)
    reports = result.reports
    for report in reports:
        assert isinstance(report.target_function, FunctionTarget)
        assert report.target_function.function == "simple_function"


def test_target_func_no_match() -> None:
    """target_func='nonexistent_fn' → empty result, no error."""
    result = assess(
        _SRC / "simple.py",
        _TESTS / "test_simple.py",
        config=_default_config(),
        target_func="nonexistent_fn",
    )
    assert isinstance(result, AssessResult)
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
    assert isinstance(result, AssessResult)
    reports = result.reports
    assert reports == ()


def test_nonexistent_tests_file_returns_empty(tmp_path: Path) -> None:
    """Non-existent tests file → assess() returns AssessResult with empty tuples."""
    result = assess(
        _SRC / "simple.py",
        tmp_path / "test_missing.py",
        config=_default_config(),
    )
    assert isinstance(result, AssessResult)
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
    target = FunctionTarget(
        function="f",
        file_path="test.py",
        line=1,
        complexity=1,
        package="test.py",
        receiver=None,
        signature="def f()",
    )
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
    target = FunctionTarget(
        function="f",
        file_path="test.py",
        line=1,
        complexity=1,
        package="test.py",
        receiver=None,
        signature="def f()",
    )
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
    target = FunctionTarget(
        function="f",
        file_path="test.py",
        line=1,
        complexity=1,
        package="test.py",
        receiver=None,
        signature="def f()",
    )
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
        (
            r
            for r in result.untested
            if isinstance(r.target_function, FunctionTarget)
            and r.target_function.function == "orphan_compute"
        ),
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
    assert result
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
    assert result
    paired_names = {
        r.target_function.function
        for r in result.reports
        if isinstance(r.target_function, FunctionTarget)
    }
    untested_names = {
        r.target_function.function
        for r in result.untested
        if isinstance(r.target_function, FunctionTarget)
    }
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


def test_assess_untested_not_suppressed_by_unrelated_same_named_tested_function(
    tmp_path: Path,
) -> None:
    """A tested method must not suppress the untested entry for an unrelated
    top-level function sharing its bare name.

    Regression fixture for fieldkit-cmd's de-gating bug (572d87fd):
    GHIssueStore.add_note vs. an unrelated top-level add_note. Before the
    fix, _untested_reports()'s seen_names set was keyed on bare function
    name only — testing one same-named function made assess() silently
    drop the OTHER same-named function's untested entry entirely, rather
    than reporting it as untested. The bug is at the seen_names layer,
    independent of pair_to_targets() correctly resolving which function a
    test targets — even a fully-correct pairing decision is not enough if
    the untested-collection step re-collides on the bare name afterward.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "gh_store.py").write_text(
        "class GHIssueStore:\n"
        "    def add_note(self, issue_id: str, note: str) -> None:\n"
        "        print(note)\n",
        encoding="utf-8",
    )
    (src_dir / "docs_domain.py").write_text(
        "def add_note(pursuit_file: str, meeting_title: str, content: str) -> None:\n"
        "    print(content)\n",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_gh_store.py").write_text(
        "def test_add_note() -> None:\n"
        "    store = GHIssueStore()\n"
        "    store.add_note('1', 'text')\n",
        encoding="utf-8",
    )

    result = assess(src_path=src_dir, tests_path=tests_dir, config=_default_config())

    docs_domain_untested = [
        r
        for r in result.untested
        if isinstance(r.target_function, FunctionTarget)
        and r.target_function.function == "add_note"
        and r.target_function.file_path.endswith("docs_domain.py")
    ]
    assert docs_domain_untested, (
        "docs_domain.add_note must appear in result.untested — it has zero "
        f"tests. untested={result.untested}"
    )


# ---------------------------------------------------------------------------
# Phase 5 — Pipeline tests (tasks 5.1–5.4)
# ---------------------------------------------------------------------------


def test_assess_inferred_target_not_in_source_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """assess() produces null-coverage report when inferred target not in source map.

    # CR-004: Tested directly via monkeypatch because pipeline.py lines 167-175
    # (the "inferred target not in source map" guard) are a defensive check that
    # cannot be triggered through normal flow — all pairing strategies only return
    # names from source_targets, which are always present in target_map.
    # Monkeypatching pair_to_targets to return a name not in source_targets is the
    # only way to exercise this defensive path without modifying production code.

    Monkeypatches pair_to_targets to return "nonexistent_fn" as the target_name
    even though it is not in the source analysis. The pipeline's defensive guard
    at lines 167-175 then produces a QualityReport with contract_coverage=None
    and a warning containing "not found".
    """
    import gaze_py.quality.pipeline as pipeline_mod
    from gaze_py.taxonomy.models import TestTargetPair

    src = tmp_path / "other.py"
    src.write_text("def other_function(): return 1\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_things.py"
    test_file.write_text("def test_something():\n    pass\n")

    # Monkeypatch pair_to_targets at the pipeline module level (where it was imported).
    def fake_pair(test_func: object, source_functions: object, **kwargs: object) -> TestTargetPair:
        return TestTargetPair(
            test_name="test_something",
            target_name="nonexistent_fn",
            inference_method="call_graph",
            confidence=0.8,
        )

    monkeypatch.setattr(pipeline_mod, "pair_to_targets", fake_pair)

    result = assess(src, tests_dir, config=_default_config())
    assert result
    # Find report with no target (inferred target not in source map → target_function=None)
    paired = [
        r for r in result.reports if r.target_function is None and r.contract_coverage is None
    ]
    assert paired, (
        f"Expected report with target_function=None and contract_coverage=None, "
        f"got: {[(r.test_function, r.target_function) for r in result.reports]}"
    )
    assert paired[0].contract_coverage is None
    assert any("not found" in w.lower() for w in paired[0].warnings)


def test_build_contract_coverage_map_exception_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """build_contract_coverage_map returns {} when assess() raises."""
    import gaze_py.quality.pipeline as pipeline_mod
    from gaze_py.quality.pipeline import build_contract_coverage_map

    monkeypatch.setattr(
        pipeline_mod,
        "assess",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = build_contract_coverage_map(tmp_path, tmp_path, _default_config())
    assert result == {}
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower() or "pipeline" in captured.err.lower()


def test_build_contract_coverage_map_keeps_higher_percentage_for_duplicate_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_contract_coverage_map keeps highest percentage for same target."""
    import gaze_py.quality.pipeline as pipeline_mod
    from gaze_py.quality.pipeline import AssessResult, build_contract_coverage_map
    from gaze_py.taxonomy.models import ContractCoverageResult, QualityReport

    low_ccr = ContractCoverageResult(
        percentage=0.0,
        covered_effects=0,
        total_contractual=1,
        over_specification_count=0,
        unmapped_assertions=0,
        reason=None,
    )
    high_ccr = ContractCoverageResult(
        percentage=100.0,
        covered_effects=1,
        total_contractual=1,
        over_specification_count=0,
        unmapped_assertions=0,
        reason=None,
    )
    my_func_target = FunctionTarget(
        function="my_func",
        file_path="src.py",
        line=1,
        complexity=1,
        package="src.py",
        receiver=None,
        signature="def my_func()",
    )
    report_low = QualityReport(
        test_function="test_a",
        target_function=my_func_target,
        assertions=(),
        contract_coverage=low_ccr,
        warnings=(),
    )
    report_high = QualityReport(
        test_function="test_b",
        target_function=my_func_target,
        assertions=(),
        contract_coverage=high_ccr,
        warnings=(),
    )
    fake_result = AssessResult(reports=(report_low, report_high), untested=())
    monkeypatch.setattr(pipeline_mod, "assess", lambda *a, **kw: fake_result)

    result = build_contract_coverage_map(tmp_path, tmp_path, _default_config())
    assert result
    assert ("my_func", "src.py") in result
    assert result[("my_func", "src.py")].percentage == 100.0


def test_build_contract_coverage_map_none_does_not_displace_percentage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_contract_coverage_map: None percentage does not displace existing non-None."""
    import gaze_py.quality.pipeline as pipeline_mod
    from gaze_py.quality.pipeline import AssessResult, build_contract_coverage_map
    from gaze_py.taxonomy.models import ContractCoverageResult, QualityReport

    ccr_50 = ContractCoverageResult(
        percentage=50.0,
        covered_effects=1,
        total_contractual=2,
        over_specification_count=0,
        unmapped_assertions=0,
        reason=None,
    )
    ccr_none = ContractCoverageResult(
        percentage=None,
        covered_effects=0,
        total_contractual=1,
        over_specification_count=0,
        unmapped_assertions=0,
        reason="no_test_coverage",
    )
    fn_target = FunctionTarget(
        function="fn",
        file_path="src.py",
        line=1,
        complexity=1,
        package="src.py",
        receiver=None,
        signature="def fn()",
    )
    r50 = QualityReport(
        test_function="test_a",
        target_function=fn_target,
        assertions=(),
        contract_coverage=ccr_50,
        warnings=(),
    )
    r_none = QualityReport(
        test_function="test_b",
        target_function=fn_target,
        assertions=(),
        contract_coverage=ccr_none,
        warnings=(),
    )
    fake_result = AssessResult(reports=(r50, r_none), untested=())
    monkeypatch.setattr(pipeline_mod, "assess", lambda *a, **kw: fake_result)

    result = build_contract_coverage_map(tmp_path, tmp_path, _default_config())
    assert result
    assert result[("fn", "src.py")].percentage == 50.0


def test_build_contract_coverage_map_does_not_merge_same_named_functions_in_different_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fully-tested function must not overwrite an unrelated, untested same-named function.

    Regression fixture for fieldkit-cmd's de-gating bug (572d87fd), reproduced
    at the exact layer that produced the reported symptom: this is the map
    consumed by _run_crap()'s --tests path, and the original repro was
    confirmed via "the raw contract_coverage field (100% -> 50% on an
    unmodified function)". Before the (function, file_path) key, an untested
    top-level add_note would silently inherit GHIssueStore.add_note's 100%
    coverage because both entries collided on the bare key "add_note".
    """
    import gaze_py.quality.pipeline as pipeline_mod
    from gaze_py.quality.pipeline import AssessResult, build_contract_coverage_map
    from gaze_py.taxonomy.models import ContractCoverageResult, QualityReport

    tested_ccr = ContractCoverageResult(
        percentage=100.0,
        covered_effects=1,
        total_contractual=1,
        over_specification_count=0,
        unmapped_assertions=0,
        reason=None,
    )
    untested_ccr = ContractCoverageResult(
        percentage=None,
        covered_effects=0,
        total_contractual=1,
        over_specification_count=0,
        unmapped_assertions=0,
        reason="no_test_coverage",
    )
    method_target = FunctionTarget(
        function="add_note",
        file_path="commands/issue/gh_store.py",
        line=511,
        complexity=2,
        package="commands/issue/gh_store.py",
        receiver="GHIssueStore",
        signature="def add_note(self, issue_id: str, note: str)",
    )
    function_target = FunctionTarget(
        function="add_note",
        file_path="meeting/docs_domain.py",
        line=315,
        complexity=3,
        package="meeting/docs_domain.py",
        receiver=None,
        signature="def add_note(pursuit_file, meeting_title, content)",
    )
    tested_report = QualityReport(
        test_function="test_add_note",
        target_function=method_target,
        assertions=(),
        contract_coverage=tested_ccr,
        warnings=(),
    )
    untested_report = QualityReport(
        test_function="",
        target_function=function_target,
        assertions=(),
        contract_coverage=untested_ccr,
        warnings=("No test targets this function.",),
    )
    fake_result = AssessResult(reports=(tested_report,), untested=(untested_report,))
    monkeypatch.setattr(pipeline_mod, "assess", lambda *a, **kw: fake_result)

    result = build_contract_coverage_map(tmp_path, tmp_path, _default_config())

    assert result[("add_note", "commands/issue/gh_store.py")].percentage == 100.0
    assert result[("add_note", "meeting/docs_domain.py")].percentage is None
    assert result[("add_note", "meeting/docs_domain.py")].reason == "no_test_coverage"


# ---------------------------------------------------------------------------
# gap-hints change — integration test
# ---------------------------------------------------------------------------


def test_quality_report_includes_gap_hints() -> None:
    """assess() on undertested fixture → gap_hints non-empty, ReturnValue hint fires.

    compute_total has a ReturnValue effect with zero assertions → 0% coverage.
    The gap_hints tuple must be non-empty and the first hint must contain
    'result' or 'assert' (the ReturnValue tailored hint).
    """
    result = assess(
        _SRC / "undertested.py",
        _TESTS / "test_undertested.py",
        config=_default_config(),
    )
    assert result
    report = next(
        (
            r
            for r in result.reports
            if isinstance(r.target_function, FunctionTarget)
            and r.target_function.function == "compute_total"
        ),
        None,
    )
    assert report is not None, f"No report for compute_total. Reports: {result.reports}"
    assert report.contract_coverage is not None
    assert report.contract_coverage.gap_hints, (
        "Expected non-empty gap_hints for undertested compute_total, got empty"
    )
    first_hint = report.contract_coverage.gap_hints[0]
    assert "result" in first_hint or "assert" in first_hint, (
        f"Expected ReturnValue hint containing 'result' or 'assert', got: {first_hint!r}"
    )


# ---------------------------------------------------------------------------
# O3 docs augmentation: assess() classifies with project docs text
# ---------------------------------------------------------------------------


def test_assess_uses_project_docs_for_classification(tmp_path: Path) -> None:
    """assess() threads project docs text into classification (O3 parity).

    Regression: the analyze/crap CLI passed docs_text into the engine but
    assess() classified without it, so the same effect got a different label
    per command. A private helper's ReturnValue (P0) with no docstring scores
    75 — ambiguous; a project doc containing "returns" adds the direct godoc
    signal (+15) → 90 — contractual, so the paired test gets a real coverage
    percentage instead of reason="all_effects_ambiguous".
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "mod.py").write_text(
        "def _helper(x):\n    return x + 1\n",
        encoding="utf-8",
    )
    (src_dir / "README.md").write_text(
        "This module returns computed values.\n",
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mod.py").write_text(
        "def test_helper_gives_value() -> None:\n    assert _helper(1) == 2\n",
        encoding="utf-8",
    )

    result = assess(src_dir, tests_dir / "test_mod.py", config=_default_config())
    report = next(
        (
            r
            for r in result.reports
            if isinstance(r.target_function, FunctionTarget)
            and r.target_function.function == "_helper"
        ),
        None,
    )
    assert report is not None, f"No report paired to _helper. Reports: {result.reports}"
    assert report.contract_coverage is not None
    assert report.contract_coverage.reason != "all_effects_ambiguous", (
        "Docs text did not reach the classifier — ReturnValue stayed ambiguous"
    )
    assert report.contract_coverage.percentage is not None
