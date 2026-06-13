"""Tests for JSON and text output formatters — OC-002 and OC-003.

All tests use synthetic AnalysisResult objects. No file I/O or AST analysis
is performed here.
"""

from __future__ import annotations

import json

import pytest

from gaze_py.report.json_formatter import to_json
from gaze_py.report.text_formatter import to_text
from gaze_py.taxonomy.effects import SideEffectType, Tier
from gaze_py.taxonomy.models import (
    AnalysisResult,
    ClassificationResult,
    FunctionTarget,
    Score,
    SideEffect,
    Signal,
    Summary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_effect(effect_type: SideEffectType = SideEffectType.ReturnValue) -> SideEffect:
    """Build a minimal SideEffect for testing."""
    return SideEffect(
        id="se-00000000",
        type=effect_type,
        tier=Tier.P0,
        location="test.py:1:0",
        description="test effect",
        target="my_func",
    )


def _make_classification() -> ClassificationResult:
    """Build a minimal ClassificationResult."""
    return ClassificationResult(
        label="contractual",
        score=85,
        signals=(Signal(source="naming", weight=10),),
    )


def _make_target(
    *,
    name: str = "my_func",
    file_path: str = "src/foo.py",
    complexity: int = 3,
    line_coverage: float | None = None,
    crap_score: float | None = None,
    fix_strategy: str | None = None,
    with_effects: bool = True,
    with_classification: bool = True,
) -> FunctionTarget:
    """Build a FunctionTarget with optional score fields."""
    target = FunctionTarget(
        name=name,
        file_path=file_path,
        line=1,
        complexity=complexity,
    )
    if with_effects:
        target.effects = [_make_effect()]
    if with_classification:
        target.classification = _make_classification()
    target.score = Score(
        line_coverage=line_coverage,
        crap=crap_score,
        fix_strategy=fix_strategy,
        effect_confidence_range=None,
    )
    return target


def _make_result(
    *,
    targets: list[FunctionTarget] | None = None,
    crap_threshold: float = 15.0,
    gaze_crap_threshold: float = 15.0,
) -> AnalysisResult:
    """Build a minimal AnalysisResult."""
    if targets is None:
        targets = [_make_target()]
    summary = Summary(
        function_count=len(targets),
        crapload=0,
        crap_threshold=crap_threshold,
        gaze_crap_threshold=gaze_crap_threshold,
    )
    return AnalysisResult(functions=targets, summary=summary)


# ---------------------------------------------------------------------------
# OC-002: Required JSON fields at function level
# ---------------------------------------------------------------------------


def test_oc002_json_function_has_required_fields() -> None:
    """OC-002: JSON output includes all required function-level fields."""
    result = _make_result()
    output = to_json(result)
    data = json.loads(output)

    assert "functions" in data
    assert len(data["functions"]) == 1
    fn = data["functions"][0]

    # Required fields per OC-002
    assert "side_effects" in fn
    assert "line_coverage" in fn
    assert "crap" in fn
    assert "gaze_crap" in fn
    assert "contract_coverage" in fn
    assert "fix_strategy" in fn
    assert "quadrant" in fn
    assert "recommended_actions" in fn


def test_oc002_json_summary_has_threshold_fields() -> None:
    """OC-002: JSON summary includes crap_threshold and gaze_crap_threshold."""
    result = _make_result(crap_threshold=20.0, gaze_crap_threshold=25.0)
    output = to_json(result)
    data = json.loads(output)

    assert "summary" in data
    summary = data["summary"]
    assert "crap_threshold" in summary
    assert "gaze_crap_threshold" in summary
    assert summary["crap_threshold"] == pytest.approx(20.0)
    assert summary["gaze_crap_threshold"] == pytest.approx(25.0)


def test_oc002_recommended_actions_entry_keys() -> None:
    """OC-002: recommended_actions entries have 'function', 'file', 'strategy', 'crap'."""
    target = _make_target(
        crap_score=30.0,
        fix_strategy="add_tests",
        line_coverage=0.5,
    )
    summary = Summary(
        function_count=1,
        crapload=1,
        recommended_actions=[
            {
                "function": "my_func",
                "file": "src/foo.py",
                "strategy": "add_tests",
                "crap": 30.0,
            }
        ],
        crap_threshold=15.0,
        gaze_crap_threshold=15.0,
    )
    result = AnalysisResult(functions=[target], summary=summary)
    output = to_json(result)
    data = json.loads(output)

    actions = data["summary"]["recommended_actions"]
    assert actions is not None
    assert len(actions) == 1
    action = actions[0]
    assert "function" in action
    assert "file" in action
    assert "strategy" in action
    assert "crap" in action


def test_oc002_no_camel_case_field_names() -> None:
    """OC-002: No camelCase field names in JSON output."""
    result = _make_result()
    output = to_json(result)

    # Check for common camelCase patterns
    camel_case_patterns = [
        "lineCoverage",
        "gazeCrap",
        "contractCoverage",
        "fixStrategy",
        "sideEffects",
        "functionCount",
        "crapLoad",
        "crapThreshold",
    ]
    for pattern in camel_case_patterns:
        assert pattern not in output, f"Found camelCase field: {pattern!r}"


# ---------------------------------------------------------------------------
# OC-003: Null-not-zero
# ---------------------------------------------------------------------------


def test_oc003_line_coverage_is_null_when_not_provided() -> None:
    """OC-003: line_coverage is null (not 0.0) when not provided."""
    target = _make_target(line_coverage=None)
    result = _make_result(targets=[target])
    output = to_json(result)
    data = json.loads(output)

    fn = data["functions"][0]
    assert "line_coverage" in fn
    assert fn["line_coverage"] is None  # JSON null, not 0.0


def test_oc003_effect_confidence_range_is_null_key_present() -> None:
    """OC-003: effect_confidence_range key MUST exist with value null."""
    target = _make_target()
    result = _make_result(targets=[target])
    output = to_json(result)
    data = json.loads(output)

    fn = data["functions"][0]
    # Key must exist AND value must be null
    assert "effect_confidence_range" in fn
    assert fn["effect_confidence_range"] is None


def test_oc003_contract_coverage_reason_for_pure_function() -> None:
    """OC-003: contract_coverage_reason = 'no_effects_detected' for pure functions."""
    # A pure function has no effects
    target = FunctionTarget(
        name="pure_func",
        file_path="test.py",
        line=1,
        complexity=1,
    )
    target.effects = []  # No effects
    target.score = Score(
        contract_coverage_reason="no_effects_detected",
        effect_confidence_range=None,
    )
    result = _make_result(targets=[target])
    output = to_json(result)
    data = json.loads(output)

    fn = data["functions"][0]
    assert fn.get("contract_coverage_reason") == "no_effects_detected"


# ---------------------------------------------------------------------------
# JSON output validity
# ---------------------------------------------------------------------------


def test_json_output_is_valid_json() -> None:
    """to_json() produces valid JSON."""
    result = _make_result()
    output = to_json(result)
    # Should not raise
    data = json.loads(output)
    assert isinstance(data, dict)


def test_json_output_has_indent() -> None:
    """to_json() produces indented JSON by default."""
    result = _make_result()
    output = to_json(result)
    # Indented JSON has newlines
    assert "\n" in output


def test_json_output_enum_values_are_strings() -> None:
    """to_json() serializes SideEffectType enum values as strings."""
    target = _make_target(with_effects=True)
    result = _make_result(targets=[target])
    output = to_json(result)
    data = json.loads(output)

    fn = data["functions"][0]
    effects = fn["side_effects"]
    assert len(effects) > 0
    # Effect type should be a string, not an object
    assert isinstance(effects[0]["type"], str)
    assert effects[0]["type"] == "ReturnValue"


def test_json_output_tier_enum_is_string() -> None:
    """to_json() serializes Tier enum values as strings."""
    target = _make_target(with_effects=True)
    result = _make_result(targets=[target])
    output = to_json(result)
    data = json.loads(output)

    fn = data["functions"][0]
    effects = fn["side_effects"]
    assert isinstance(effects[0]["tier"], str)


# ---------------------------------------------------------------------------
# Text formatter
# ---------------------------------------------------------------------------


def test_text_output_contains_complexity() -> None:
    """to_text() output contains 'complexity=' for each function."""
    result = _make_result()
    output = to_text(result)
    assert "complexity=" in output


def test_text_output_contains_function_name() -> None:
    """to_text() output contains the function name."""
    result = _make_result()
    output = to_text(result)
    assert "my_func" in output


def test_text_output_contains_crap_field() -> None:
    """to_text() output contains 'CRAP=' for each function."""
    result = _make_result()
    output = to_text(result)
    assert "CRAP=" in output


def test_text_output_contains_effects_count() -> None:
    """to_text() output contains 'effects=' for each function."""
    result = _make_result()
    output = to_text(result)
    assert "effects=" in output


def test_text_output_contains_strategy_field() -> None:
    """to_text() output contains 'strategy=' for each function."""
    result = _make_result()
    output = to_text(result)
    assert "strategy=" in output


def test_text_output_one_line_per_function() -> None:
    """to_text() produces one line per function."""
    targets = [
        _make_target(name="func_a", file_path="a.py"),
        _make_target(name="func_b", file_path="b.py"),
    ]
    result = _make_result(targets=targets)
    output = to_text(result)
    lines = [line for line in output.splitlines() if line.strip()]
    _expected_min_lines = 2
    assert len(lines) >= _expected_min_lines


def test_text_output_shows_null_for_missing_crap() -> None:
    """to_text() shows 'null' when CRAP score is not available."""
    target = _make_target(line_coverage=None, crap_score=None)
    result = _make_result(targets=[target])
    output = to_text(result)
    assert "null" in output


def test_text_output_is_plain_string() -> None:
    """to_text() returns a plain string (no rich markup)."""
    result = _make_result()
    output = to_text(result)
    assert isinstance(output, str)
    # No rich markup characters
    assert "[bold" not in output
    assert "[red" not in output
