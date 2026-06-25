"""Tests for gaze_py.crap.compare — pure baseline comparison functions.

All tests use synthetic dicts — no file I/O except load_baseline() tests
which use tmp_path. No CLI invocation.

Spec: specs/002-gaze-parity/ Story 2, tasks T219–T226.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaze_py.crap.compare import (
    CompareOptions,
    FunctionStatus,
    classify_delta,
    compare,
    load_baseline,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(pkg: str, fn: str, crap: float | None = 5.0, gaze_crap: float | None = None) -> dict:
    """Build a minimal result dict for testing."""
    return {
        "target": {"package": pkg, "function": fn},
        "crap": crap,
        "gaze_crap": gaze_crap,
    }


def _baseline_json(entries: list[dict]) -> str:
    """Wrap entries in the new schema envelope."""
    return json.dumps({"results": entries})


# ---------------------------------------------------------------------------
# T219/T220: classify_delta — all parametrized cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "crap_delta,gaze_delta,has_gaze,epsilon,expected",
    [
        # (a) CRAP regression only → REGRESSION
        (2.0, None, False, 0.0, FunctionStatus.REGRESSION),
        # (b) GazeCRAP regression only → REGRESSION
        (0.0, 3.0, True, 0.0, FunctionStatus.REGRESSION),
        # (c) CRAP regression + GazeCRAP improvement → REGRESSION (wins)
        (2.0, -3.0, True, 0.0, FunctionStatus.REGRESSION),
        # (d) CRAP improvement + GazeCRAP regression → REGRESSION (wins)
        (-2.0, 3.0, True, 0.0, FunctionStatus.REGRESSION),
        # (e) Both improve → IMPROVEMENT
        (-2.0, -3.0, True, 0.0, FunctionStatus.IMPROVEMENT),
        # (f) CRAP within epsilon → UNCHANGED
        (0.3, None, False, 0.5, FunctionStatus.UNCHANGED),
        # (g1) has_gaze_delta=False + CRAP regresses → REGRESSION (GazeCRAP skipped)
        (2.0, None, False, 0.0, FunctionStatus.REGRESSION),
        # (g2) has_gaze_delta=False + CRAP within epsilon → UNCHANGED
        (0.1, None, False, 0.5, FunctionStatus.UNCHANGED),
        # CRAP improvement only (no GazeCRAP) → IMPROVEMENT
        (-2.0, None, False, 0.0, FunctionStatus.IMPROVEMENT),
        # Both within epsilon → UNCHANGED
        (0.1, 0.1, True, 0.5, FunctionStatus.UNCHANGED),
    ],
)
def test_classify_delta(
    crap_delta: float,
    gaze_delta: float | None,
    has_gaze: bool,
    epsilon: float,
    expected: FunctionStatus,
) -> None:
    """T220: classify_delta covers all parametrized cases."""
    result = classify_delta(crap_delta, gaze_delta, has_gaze, epsilon)
    assert result == expected, (
        f"classify_delta({crap_delta}, {gaze_delta}, {has_gaze}, {epsilon}) "
        f"= {result!r}, expected {expected!r}"
    )


# ---------------------------------------------------------------------------
# T221: compare() — structure and warning assertions
# ---------------------------------------------------------------------------


def test_compare_new_function_below_threshold() -> None:
    """T221a: new function below threshold → status NEW."""
    baseline = [_entry("src/foo.py", "old_fn", crap=5.0)]
    current = [_entry("src/foo.py", "new_fn", crap=8.0)]
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)

    result = compare(baseline, current, opts)

    assert len(result.new_functions) == 1
    assert result.new_functions[0]["target"]["function"] == "new_fn"
    assert result.summary.new_functions == 1
    assert result.summary.new_violations == 0


def test_compare_new_function_above_threshold() -> None:
    """T221b: new function above threshold → status NEW_VIOLATION."""
    baseline = [_entry("src/foo.py", "old_fn", crap=5.0)]
    current = [_entry("src/foo.py", "new_fn", crap=20.0)]
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)

    result = compare(baseline, current, opts)

    assert result.summary.new_violations == 1
    assert result.summary.new_functions == 0
    assert not result.summary.passed


def test_compare_removed_function() -> None:
    """T221c: removed function appears in removed_functions."""
    baseline = [_entry("src/foo.py", "gone_fn", crap=5.0)]
    current: list[dict] = []
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)

    result = compare(baseline, current, opts)

    assert len(result.removed_functions) == 1
    assert result.removed_functions[0]["target"]["function"] == "gone_fn"
    assert result.summary.removed_functions == 1


def test_compare_matched_regression() -> None:
    """T221d: matched regression appears in deltas with REGRESSION status."""
    baseline = [_entry("src/foo.py", "compute", crap=5.0)]
    current = [_entry("src/foo.py", "compute", crap=10.0)]
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)

    result = compare(baseline, current, opts)

    assert len(result.deltas) == 1
    assert result.deltas[0].status == FunctionStatus.REGRESSION
    assert result.deltas[0].crap_delta == pytest.approx(5.0)
    assert result.summary.regressions == 1
    assert not result.summary.passed


def test_compare_no_regression_passes() -> None:
    """T221e: no regression → summary.passed == True."""
    baseline = [_entry("src/foo.py", "compute", crap=10.0)]
    current = [_entry("src/foo.py", "compute", crap=8.0)]  # improvement
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)

    result = compare(baseline, current, opts)

    assert result.summary.passed
    assert result.summary.improvements == 1


def test_compare_large_unmatched_emits_warning() -> None:
    """T221f: > 50% baseline unmatched → warnings list is non-empty with 'unmatched'."""
    # 3 baseline entries, none matched in current → 3/3 = 100% unmatched
    baseline = [
        _entry("src/a.py", "fn1"),
        _entry("src/a.py", "fn2"),
        _entry("src/a.py", "fn3"),
    ]
    current: list[dict] = []
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)

    result = compare(baseline, current, opts)

    assert len(result.warnings) > 0
    assert "unmatched" in result.warnings[0]


# ---------------------------------------------------------------------------
# T222: load_baseline() error paths
# ---------------------------------------------------------------------------


def test_load_baseline_missing_file(tmp_path: Path) -> None:
    """T222a: missing file → ValueError with 're-generate' in message."""
    p = tmp_path / "nonexistent.json"
    with pytest.raises(ValueError, match="re-generate"):
        load_baseline(p)


def test_load_baseline_empty_file(tmp_path: Path) -> None:
    """T222b: empty file (zero bytes) → ValueError with 'empty' in message."""
    p = tmp_path / "baseline.json"
    p.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        load_baseline(p)


def test_load_baseline_malformed_json(tmp_path: Path) -> None:
    """T222c: malformed JSON → ValueError with actionable message (not raw JSONDecodeError)."""
    p = tmp_path / "baseline.json"
    p.write_text("{ not valid json }", encoding="utf-8")
    with pytest.raises(ValueError, match="parsing baseline"):
        load_baseline(p)


def test_load_baseline_old_schema(tmp_path: Path) -> None:
    """T222d: old 'functions' key → ValueError with 'incompatible schema'."""
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps({"functions": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="incompatible schema"):
        load_baseline(p)


def test_load_baseline_results_null(tmp_path: Path) -> None:
    """T222e: results=null → ValueError."""
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps({"results": None}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_baseline(p)


def test_load_baseline_empty_results(tmp_path: Path) -> None:
    """T222f: empty results list is valid — returns empty list."""
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps({"results": []}), encoding="utf-8")
    result = load_baseline(p)
    assert result == []


def test_load_baseline_non_dict_target(tmp_path: Path) -> None:
    """T222g: entry with target as string → ValueError with 'target must be an object'."""
    p = tmp_path / "baseline.json"
    entries = [{"target": "src/foo.py:compute"}]
    p.write_text(json.dumps({"results": entries}), encoding="utf-8")
    with pytest.raises(ValueError, match="target.*object"):
        load_baseline(p)


def test_load_baseline_missing_target_function(tmp_path: Path) -> None:
    """T222h: entry missing target.function → ValueError with entry index."""
    p = tmp_path / "baseline.json"
    entries = [{"target": {"package": "src/foo.py"}}]  # missing "function"
    p.write_text(json.dumps({"results": entries}), encoding="utf-8")
    with pytest.raises(ValueError, match="0"):
        load_baseline(p)


def test_load_baseline_valid(tmp_path: Path) -> None:
    """load_baseline returns list of dicts for valid input."""
    p = tmp_path / "baseline.json"
    entries = [_entry("src/foo.py", "compute", crap=5.0)]
    p.write_text(_baseline_json(entries), encoding="utf-8")
    result = load_baseline(p)
    assert len(result) == 1
    assert result[0]["target"]["function"] == "compute"


# ---------------------------------------------------------------------------
# T224: baseline.epsilon config path
# ---------------------------------------------------------------------------


def test_compare_epsilon_unchanged(tmp_path: Path) -> None:
    """T224: delta ≤ epsilon → UNCHANGED; delta > epsilon → REGRESSION."""
    baseline = [_entry("src/foo.py", "fn", crap=10.0)]
    current_within = [_entry("src/foo.py", "fn", crap=10.3)]
    current_outside = [_entry("src/foo.py", "fn", crap=10.6)]
    opts = CompareOptions(epsilon=0.5, new_function_threshold=15.0)

    r_within = compare(baseline, current_within, opts)
    assert r_within.deltas[0].status == FunctionStatus.UNCHANGED

    r_outside = compare(baseline, current_outside, opts)
    assert r_outside.deltas[0].status == FunctionStatus.REGRESSION


# ---------------------------------------------------------------------------
# T225: new_function_threshold config path (None → crap_threshold fallback)
# ---------------------------------------------------------------------------


def test_compare_new_function_threshold_explicit() -> None:
    """T225a/b: explicit threshold used correctly."""
    baseline: list[dict] = []
    # CRAP = 18.0, threshold = 20.0 → NEW (not NEW_VIOLATION)
    current_below = [_entry("src/foo.py", "new_fn", crap=18.0)]
    opts = CompareOptions(epsilon=0.0, new_function_threshold=20.0)
    result = compare(baseline, current_below, opts)
    assert result.summary.new_functions == 1
    assert result.summary.new_violations == 0

    # CRAP = 25.0, threshold = 20.0 → NEW_VIOLATION
    current_above = [_entry("src/foo.py", "new_fn2", crap=25.0)]
    result2 = compare(baseline, current_above, opts)
    assert result2.summary.new_violations == 1


def test_compare_new_function_threshold_none_falls_back_to_crap_threshold() -> None:
    """T225c: None threshold → resolved to crap_threshold (15.0) by caller.

    This test simulates the CLI wiring: new_function_threshold is None in
    BaselineConfig, resolved to config.crap_threshold (15.0) before passing to
    CompareOptions, so CompareOptions receives 15.0 (not None).
    """
    # Simulate T218 resolution: None → 15.0 (crap_threshold default)
    crap_threshold = 15.0
    opts = CompareOptions(epsilon=0.0, new_function_threshold=crap_threshold)

    baseline: list[dict] = []
    current = [_entry("src/foo.py", "new_fn", crap=18.0)]

    result = compare(baseline, current, opts)
    # 18.0 > 15.0 → NEW_VIOLATION
    assert result.summary.new_violations == 1


# ---------------------------------------------------------------------------
# T226: comparison_to_text output
# ---------------------------------------------------------------------------


def test_comparison_to_text_pass() -> None:
    """T226: PASS verdict when passed=True."""
    from gaze_py.report.json_formatter import comparison_to_text

    baseline = [_entry("src/foo.py", "fn", crap=5.0)]
    current = [_entry("src/foo.py", "fn", crap=4.0)]  # improvement
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)
    cmp = compare(baseline, current, opts)

    text = comparison_to_text("CRAP output\n", cmp)
    assert "PASS" in text
    assert "FAIL" not in text


def test_comparison_to_text_fail() -> None:
    """T226: FAIL verdict when passed=False."""
    from gaze_py.report.json_formatter import comparison_to_text

    baseline = [_entry("src/foo.py", "fn", crap=5.0)]
    current = [_entry("src/foo.py", "fn", crap=15.0)]  # regression
    opts = CompareOptions(epsilon=0.0, new_function_threshold=20.0)
    cmp = compare(baseline, current, opts)

    text = comparison_to_text("CRAP output\n", cmp)
    assert "FAIL" in text
    assert "Regressions:" in text


def test_comparison_to_text_omits_empty_sections() -> None:
    """T226: empty section headers (Improvements:, New violations:) are omitted."""
    from gaze_py.report.json_formatter import comparison_to_text

    baseline = [_entry("src/foo.py", "fn", crap=5.0)]
    current = [_entry("src/foo.py", "fn", crap=5.0)]  # unchanged
    opts = CompareOptions(epsilon=0.0, new_function_threshold=15.0)
    cmp = compare(baseline, current, opts)

    text = comparison_to_text("CRAP output\n", cmp)
    # Section headers appear on their own line — distinguish from counts-line words
    assert "\nImprovements:" not in text, "empty Improvements section should be omitted"
    assert "\nNew violations" not in text, "empty New violations section should be omitted"
