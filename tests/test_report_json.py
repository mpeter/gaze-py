"""Tests for JSON report formatters — validates against ANALYSIS_SCHEMA and QUALITY_SCHEMA.

Maps to spec acceptance scenarios SC-022 through SC-026 from
``specs/001-gaze-py-engine/spec.md`` User Story 3.

Tests are written BEFORE the implementation exists (TDD) and MUST fail
with ``ImportError`` until ``src/gaze_py/report/`` is created.

Convention pack compliance:
- TC-001: pytest only, no unittest.TestCase
- TC-002: direct assert statements
- TC-003: descriptive test names matching SC-NNN identifiers
- TC-007: acceptance tests named after spec success criteria
- TC-008: assert specific values, not just truthiness
- TC-009: each test is independently runnable
- TC-012: error paths and edge cases covered
"""

from __future__ import annotations

import io
import json

import jsonschema
import pytest

from gaze_py.report import build_metadata
from gaze_py.report.json import write_analysis_json, write_quality_json
from gaze_py.report.schema import ANALYSIS_SCHEMA, QUALITY_SCHEMA
from gaze_py.taxonomy import (
    AnalysisResult,
    ContractCoverage,
    FunctionTarget,
    OverSpecificationScore,
    PackageSummary,
    QualityReport,
    SideEffect,
    SideEffectType,
    Tier,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_target() -> FunctionTarget:
    """A minimal FunctionTarget for use in test fixtures.

    Returns:
        A ``FunctionTarget`` with package, function, signature, and location set.
    """
    return FunctionTarget(
        package="mypackage",
        function="my_func",
        signature="my_func() -> int",
        location="mypackage/module.py:10",
    )


@pytest.fixture()
def simple_side_effect(simple_target: FunctionTarget) -> SideEffect:
    """A minimal SideEffect for use in test fixtures.

    Args:
        simple_target: The function target for the side effect.

    Returns:
        A ``SideEffect`` with type ``ReturnValue`` and tier ``P0``.
    """
    return SideEffect(
        id="se-abc12345",
        type=SideEffectType.ReturnValue,
        tier=Tier.P0,
        location="mypackage/module.py:12",
        description="Returns an integer value",
        target=simple_target,
    )


@pytest.fixture()
def simple_analysis_result(simple_target: FunctionTarget, simple_side_effect: SideEffect) -> AnalysisResult:
    """A minimal AnalysisResult for use in test fixtures.

    Args:
        simple_target: The function target.
        simple_side_effect: One side effect to include.

    Returns:
        An ``AnalysisResult`` with one side effect and no metadata.
    """
    return AnalysisResult(
        target=simple_target,
        side_effects=[simple_side_effect],
    )


@pytest.fixture()
def simple_quality_report(simple_target: FunctionTarget, simple_side_effect: SideEffect) -> QualityReport:
    """A minimal QualityReport for use in test fixtures.

    Args:
        simple_target: The function under test.
        simple_side_effect: One side effect for coverage computation.

    Returns:
        A ``QualityReport`` with 100% contract coverage and no over-specification.
    """
    coverage = ContractCoverage(
        percentage=100.0,
        covered_count=1,
        total_contractual=1,
        gaps=[],
        gap_hints=[],
    )
    over_spec = OverSpecificationScore(
        count=0,
        ratio=0.0,
        incidental_assertions=[],
        suggestions=[],
    )
    return QualityReport(
        test_function="test_my_func",
        test_location="tests/test_module.py:5",
        target_function=simple_target,
        contract_coverage=coverage,
        over_specification=over_spec,
        ambiguous_effects=[],
        unmapped_assertions=[],
        assertion_count=1,
        assertion_detection_confidence=80,
    )


@pytest.fixture()
def simple_package_summary(simple_quality_report: QualityReport) -> PackageSummary:
    """A minimal PackageSummary for use in test fixtures.

    Args:
        simple_quality_report: One quality report to include in worst_coverage_tests.

    Returns:
        A ``PackageSummary`` with one test and 100% average coverage.
    """
    return PackageSummary(
        total_tests=1,
        average_contract_coverage=100.0,
        total_over_specifications=0,
        assertion_detection_confidence=80,
        worst_coverage_tests=[],
    )


# ---------------------------------------------------------------------------
# SC-022: Analysis JSON validates against ANALYSIS_SCHEMA
# ---------------------------------------------------------------------------


def test_sc022_analysis_json_validates_schema(simple_analysis_result: AnalysisResult) -> None:
    """SC-022: JSON output for analysis results validates against ANALYSIS_SCHEMA.

    Given a list of AnalysisResult objects,
    When write_analysis_json is called,
    Then the output parses as valid JSON and validates against ANALYSIS_SCHEMA.
    """
    out = io.StringIO()
    write_analysis_json([simple_analysis_result], "0.1.0", out)
    data = json.loads(out.getvalue())
    # Must not raise — schema validation is the assertion
    jsonschema.validate(data, ANALYSIS_SCHEMA)


# ---------------------------------------------------------------------------
# SC-023: Top-level keys are "version" and "results"
# ---------------------------------------------------------------------------


def test_sc023_analysis_json_top_level_keys(simple_analysis_result: AnalysisResult) -> None:
    """SC-023: Analysis JSON top-level keys are exactly 'version' and 'results'.

    Given a list of AnalysisResult objects,
    When write_analysis_json is called,
    Then the output has 'version' and 'results' as top-level keys.
    """
    out = io.StringIO()
    write_analysis_json([simple_analysis_result], "0.1.0", out)
    data = json.loads(out.getvalue())
    assert "version" in data
    assert "results" in data
    assert data["version"] == "0.1.0"
    assert isinstance(data["results"], list)


# ---------------------------------------------------------------------------
# SC-024: Metadata fields present, go_version absent
# ---------------------------------------------------------------------------


def test_sc024_metadata_fields_present(simple_analysis_result: AnalysisResult) -> None:
    """SC-024: Each result's metadata contains required Python-specific fields.

    Given a list of AnalysisResult objects,
    When write_analysis_json is called,
    Then each result's metadata contains 'gaze_py_version', 'python_version',
    and 'duration_ms', and does NOT contain 'go_version'.
    """
    out = io.StringIO()
    write_analysis_json([simple_analysis_result], "0.1.0", out)
    data = json.loads(out.getvalue())
    assert len(data["results"]) == 1
    meta = data["results"][0]["metadata"]
    assert "gaze_py_version" in meta
    assert "python_version" in meta
    assert "duration_ms" in meta
    assert "go_version" not in meta


# ---------------------------------------------------------------------------
# SC-026: Quality JSON validates against QUALITY_SCHEMA
# ---------------------------------------------------------------------------


def test_sc026_quality_json_validates_schema(
    simple_quality_report: QualityReport,
    simple_package_summary: PackageSummary,
) -> None:
    """SC-026: JSON output for quality reports validates against QUALITY_SCHEMA.

    Given a list of QualityReport objects and a PackageSummary,
    When write_quality_json is called,
    Then the output parses as valid JSON and validates against QUALITY_SCHEMA.
    """
    out = io.StringIO()
    write_quality_json([simple_quality_report], simple_package_summary, "0.1.0", out)
    data = json.loads(out.getvalue())
    jsonschema.validate(data, QUALITY_SCHEMA)


# ---------------------------------------------------------------------------
# Edge case: empty results list
# ---------------------------------------------------------------------------


def test_analysis_json_empty_results() -> None:
    """Edge case: write_analysis_json with an empty list produces valid JSON.

    Given an empty results list,
    When write_analysis_json is called,
    Then the output is valid JSON with 'results' as an empty list.
    """
    out = io.StringIO()
    write_analysis_json([], "0.1.0", out)
    data = json.loads(out.getvalue())
    assert data["results"] == []
    assert data["version"] == "0.1.0"
    # Must also validate against schema
    jsonschema.validate(data, ANALYSIS_SCHEMA)


# ---------------------------------------------------------------------------
# SC-024 (specific): go_version is absent from metadata
# ---------------------------------------------------------------------------


def test_metadata_gaze_py_version_absent_go_version(simple_analysis_result: AnalysisResult) -> None:
    """SC-024 (specific): 'go_version' is absent from result metadata.

    Given a list of AnalysisResult objects,
    When write_analysis_json is called,
    Then 'go_version' is NOT present in any result's metadata dict.
    """
    out = io.StringIO()
    write_analysis_json([simple_analysis_result], "0.1.0", out)
    data = json.loads(out.getvalue())
    for result in data["results"]:
        assert "go_version" not in result["metadata"]


# ---------------------------------------------------------------------------
# Structural: jq-compatible key access
# ---------------------------------------------------------------------------


def test_analysis_json_jq_compatible_structure(simple_analysis_result: AnalysisResult) -> None:
    """Verify jq-compatible dict key access: output['results'][0]['side_effects'].

    Given a list of AnalysisResult objects,
    When write_analysis_json is called,
    Then the output supports nested key access matching the schema structure.
    """
    out = io.StringIO()
    write_analysis_json([simple_analysis_result], "0.1.0", out)
    data = json.loads(out.getvalue())
    # jq-compatible: data["results"][0]["side_effects"] must be a list
    side_effects = data["results"][0]["side_effects"]
    assert isinstance(side_effects, list)
    assert len(side_effects) == 1
    assert side_effects[0]["type"] == "ReturnValue"
    assert side_effects[0]["tier"] == "P0"


# ---------------------------------------------------------------------------
# build_metadata: unit test for the metadata builder
# ---------------------------------------------------------------------------


def test_build_metadata_fields() -> None:
    """build_metadata returns a dict with all required metadata fields.

    Given a start_ns timestamp,
    When build_metadata is called,
    Then the returned dict contains gaze_py_version, python_version,
    duration_ms (non-negative int), timestamp, and warnings.
    """
    import time

    start_ns = time.perf_counter_ns()
    meta = build_metadata(start_ns)
    assert "gaze_py_version" in meta
    assert "python_version" in meta
    assert "duration_ms" in meta
    assert isinstance(meta["duration_ms"], int)
    assert meta["duration_ms"] >= 0
    assert "timestamp" in meta
    assert "warnings" in meta
    assert isinstance(meta["warnings"], list)
    assert "go_version" not in meta
