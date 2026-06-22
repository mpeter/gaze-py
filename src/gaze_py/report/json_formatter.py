"""JSON output formatter for gaze-py analysis results.

Serializes AnalysisResult and QualityReport sequences to JSON strings using
a custom encoder that handles enum values and None → null.

Per OC-002: all field names are snake_case (no camelCase).
Per OC-003: None fields serialize as JSON null (default Python behavior).
Per FR-001/FR-002: top-level keys are "results" and "target"/"function" per
the Go gaze reference implementation's JSON field names.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import gaze_py
from gaze_py.taxonomy.models import (
    AnalysisResult,
    FunctionTarget,
    OverSpecification,
    QualityReport,
    QualitySummary,
)

# JSON schema for the AnalysisResult output format.
# Extracted as a module-level constant so the `schema` CLI command can emit it
# directly without re-serializing a live object (task 6.1).
# Updated to reflect "results"-keyed structure per FR-001 / OC-002.
SCHEMA: str = json.dumps(
    {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "AnalysisResult",
        "description": (
            "gaze-py analysis result envelope (analyze and crap commands). "
            "Quality-related fields (gaze_crap, contract_coverage, quadrant, "
            "gaze_crapload, avg_contract_coverage, quadrant_counts, "
            "fix_strategy_counts) are populated by the O1 quality pipeline "
            "when the 'quality' command is used."
        ),
        "type": "object",
        "required": ["results", "summary"],
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["target", "side_effects", "metadata"],
                    "properties": {
                        "target": {
                            "type": "object",
                            "required": [
                                "package",
                                "function",
                                "receiver",
                                "signature",
                                "location",
                            ],
                            "properties": {
                                "package": {"type": "string"},
                                "function": {"type": "string"},
                                "receiver": {"type": ["string", "null"]},
                                "signature": {"type": "string"},
                                "location": {"type": "string"},
                            },
                        },
                        "side_effects": {"type": "array"},
                        "metadata": {
                            "type": "object",
                            "required": ["gaze_version", "warnings", "duration_ms", "timestamp"],
                        },
                        "line_coverage": {"type": ["number", "null"]},
                        "crap": {"type": ["number", "null"]},
                        "gaze_crap": {"type": ["number", "null"]},
                        "contract_coverage": {"type": ["number", "null"]},
                        "contract_coverage_reason": {"type": ["string", "null"]},
                        "fix_strategy": {"type": ["string", "null"]},
                        "quadrant": {"type": ["string", "null"]},
                        "effect_confidence_range": {"type": ["array", "null"]},
                    },
                },
            },
            "summary": {
                "type": "object",
                "required": ["function_count", "crap_threshold", "gaze_crap_threshold"],
                "properties": {
                    "function_count": {"type": "integer"},
                    "crapload": {"type": ["integer", "null"]},
                    "gaze_crapload": {"type": ["integer", "null"]},
                    "avg_line_coverage": {"type": ["number", "null"]},
                    "avg_contract_coverage": {"type": ["number", "null"]},
                    "quadrant_counts": {"type": ["object", "null"]},
                    "fix_strategy_counts": {"type": ["object", "null"]},
                    "recommended_actions": {"type": ["array", "null"]},
                    "crap_threshold": {"type": "number"},
                    "gaze_crap_threshold": {"type": "number"},
                },
            },
        },
    },
    indent=2,
)


def _json_default(obj: Any) -> Any:  # noqa: ANN401  # Any is required — json.JSONEncoder.default() protocol uses Any.
    """Custom JSON encoder for types not handled by the default encoder.

    Handles:
    - enum.Enum subclasses: serialized as their .value (string for StrEnum)
    - tuple: converted to list (dataclasses.asdict converts tuples to lists
      for most cases, but nested tuples in frozen dataclasses may survive)
    - frozenset: converted to sorted list (AssertionSite.referenced_names is
      frozenset[str]; sorted for deterministic JSON output)

    Args:
        obj: Object that the default JSON encoder cannot handle.

    Returns:
        A JSON-serializable representation of obj.

    Raises:
        TypeError: When obj is not a recognized type.
    """
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (tuple, frozenset)):
        return sorted(obj) if isinstance(obj, frozenset) else list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _target_dict(ft: FunctionTarget) -> dict[str, object]:
    """Serialize a FunctionTarget's identity fields as a target dict.

    Produces the "target" sub-object in the analysis result JSON per FR-002.

    Args:
        ft: The FunctionTarget to serialize.

    Returns:
        Dict with package, function, receiver, signature, and location keys.
    """
    return {
        "package": ft.package,
        "function": ft.function,
        "receiver": ft.receiver,
        "signature": ft.signature,
        "location": f"{ft.file_path}:{ft.line}",
    }


def analysis_to_json(
    result: AnalysisResult,
    *,
    start_time: float | None = None,
    indent: int = 2,
) -> str:
    """Serialize an AnalysisResult to a JSON string.

    Produces the canonical "results"-keyed envelope per FR-001 / OC-002.
    Each result entry includes a "target" sub-object with package, function,
    receiver, signature, and location fields per FR-002.

    Metadata (gaze_version, warnings, duration_ms, timestamp) is injected at
    serialization time — not stored in the model pipeline (avoids circular
    imports and keeps models pure).

    Args:
        result: The AnalysisResult to serialize.
        start_time: time.monotonic() value captured before the analysis ran.
            Used to compute duration_ms. When None, duration_ms is 0.
        indent: JSON indentation level. Default: 2.

    Returns:
        Indented JSON string representation of the result.
    """
    gaze_version = gaze_py.__version__
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    duration_ms = int((time.monotonic() - start_time) * 1000) if start_time is not None else 0

    result_entries: list[dict[str, object]] = []
    for ft in result.results:
        score_dict: dict[str, object] = {}
        if ft.score is not None:
            score_dict = {
                "line_coverage": ft.score.line_coverage,
                "crap": ft.score.crap,
                "gaze_crap": ft.score.gaze_crap,
                "contract_coverage": ft.score.contract_coverage,
                "contract_coverage_reason": ft.score.contract_coverage_reason,
                "fix_strategy": ft.score.fix_strategy,
                "quadrant": ft.score.quadrant,
                "effect_confidence_range": (
                    list(ft.score.effect_confidence_range)
                    if ft.score.effect_confidence_range is not None
                    else None
                ),
            }
        else:
            score_dict = {
                "line_coverage": None,
                "crap": None,
                "gaze_crap": None,
                "contract_coverage": None,
                "contract_coverage_reason": None,
                "fix_strategy": None,
                "quadrant": None,
                "effect_confidence_range": None,
            }

        # Serialize effects using dataclasses.asdict for nested dataclasses.
        effects_list = [dataclasses.asdict(e) for e in ft.effects]

        entry: dict[str, object] = {
            "target": _target_dict(ft),
            "side_effects": effects_list,
            "metadata": {
                "gaze_version": gaze_version,
                "warnings": [],
                "duration_ms": duration_ms,
                "timestamp": timestamp,
            },
        }
        entry.update(score_dict)
        result_entries.append(entry)

    summary_dict = dataclasses.asdict(result.summary)

    payload: dict[str, object] = {
        "results": result_entries,
        "summary": summary_dict,
    }

    return json.dumps(payload, default=_json_default, indent=indent)


def to_json(result: AnalysisResult, *, indent: int = 2) -> str:
    """Serialize an AnalysisResult to a JSON string.

    Delegates to analysis_to_json() with no start_time (duration_ms = 0).
    Kept for backward compatibility with existing callers.

    Args:
        result: The AnalysisResult to serialize.
        indent: JSON indentation level. Default: 2.

    Returns:
        Indented JSON string representation of the result.
    """
    return analysis_to_json(result, indent=indent)


def _compute_quality_summary(reports: Sequence[QualityReport]) -> QualitySummary:
    """Compute aggregate quality metrics from a sequence of QualityReport objects.

    Args:
        reports: Quality assessment reports to aggregate.

    Returns:
        QualitySummary with computed aggregate metrics.
    """
    total_tests = len(reports)
    total_over_specs = 0
    coverages: list[float] = []
    confidences: list[int] = []

    for r in reports:
        total_over_specs += r.over_specification.count
        if r.contract_coverage is not None and r.contract_coverage.percentage is not None:
            coverages.append(r.contract_coverage.percentage)
        confidences.append(r.assertion_detection_confidence)

    avg_coverage: float | None = sum(coverages) / len(coverages) if coverages else None

    avg_confidence = round(sum(confidences) / len(confidences)) if confidences else 100

    # Worst coverage tests: bottom 5 by contract coverage percentage.
    paired = [
        (r.test_function, r.contract_coverage.percentage)
        for r in reports
        if r.contract_coverage is not None and r.contract_coverage.percentage is not None
    ]
    paired.sort(key=lambda x: x[1])
    worst = [name for name, _ in paired[:5]]

    return QualitySummary(
        total_tests=total_tests,
        average_contract_coverage=avg_coverage,
        total_over_specifications=total_over_specs,
        worst_coverage_tests=worst,
        assertion_detection_confidence=avg_confidence,
    )


def quality_to_json(reports: Sequence[QualityReport], *, indent: int = 2) -> str:
    """Serialize a sequence of QualityReport objects to JSON.

    Produces the canonical "quality_reports"-keyed envelope with a
    "quality_summary" aggregate per FR-003 / OC-002.

    Each report entry includes:
    - test_function, test_location, target_function (as target dict or null)
    - contract_coverage with covered_count, discarded_returns, discarded_return_hints
    - over_specification with count, ratio, incidental_assertions, suggestions
    - ambiguous_effects, unmapped_assertions (both empty — OC-003 compliant)
    - assertion_count, assertion_detection_confidence
    - assertions, warnings, complexity

    Args:
        reports: Quality assessment reports to serialize. Accepts any
            Sequence (list, tuple, etc.) of QualityReport instances.
        indent: JSON indentation level.

    Returns:
        JSON string with "quality_reports" and "quality_summary" keys.
    """
    report_entries: list[dict[str, object]] = []

    for qr in reports:
        # Serialize target_function as target dict or null.
        target_fn: dict[str, object] | None
        if isinstance(qr.target_function, FunctionTarget):
            target_fn = _target_dict(qr.target_function)
        else:
            target_fn = None

        # Serialize contract_coverage with new fields.
        cc_dict: dict[str, object] | None
        if qr.contract_coverage is not None:
            cc = qr.contract_coverage
            cc_dict = {
                "percentage": cc.percentage,
                "covered_count": cc.covered_count,
                "covered_effects": cc.covered_effects,
                "total_contractual": cc.total_contractual,
                "over_specification_count": cc.over_specification_count,
                "unmapped_assertions": cc.unmapped_assertions,
                "reason": cc.reason,
                "min_confidence": cc.min_confidence,
                "max_confidence": cc.max_confidence,
                "gaps": [dataclasses.asdict(g) for g in cc.gaps],
                "gap_hints": list(cc.gap_hints),
                "discarded_returns": [],
                "discarded_return_hints": [],
            }
        else:
            cc_dict = None

        # Serialize over_specification.
        os_obj: OverSpecification = qr.over_specification
        os_dict: dict[str, object] = {
            "count": os_obj.count,
            "ratio": os_obj.ratio,
            "incidental_assertions": list(os_obj.incidental_assertions),
            "suggestions": list(os_obj.suggestions),
        }

        # Serialize assertions using dataclasses.asdict.
        assertions_list = [dataclasses.asdict(a) for a in qr.assertions]

        entry: dict[str, object] = {
            "test_function": qr.test_function,
            "test_location": qr.test_location,
            "target_function": target_fn,
            "contract_coverage": cc_dict,
            "over_specification": os_dict,
            "ambiguous_effects": [],
            "unmapped_assertions": [],
            "assertion_count": qr.assertion_count,
            "assertion_detection_confidence": qr.assertion_detection_confidence,
            "assertions": assertions_list,
            "warnings": list(qr.warnings),
            "complexity": qr.complexity,
        }
        report_entries.append(entry)

    summary = _compute_quality_summary(reports)
    summary_dict: dict[str, object] = {
        "total_tests": summary.total_tests,
        "average_contract_coverage": summary.average_contract_coverage,
        "total_over_specifications": summary.total_over_specifications,
        "worst_coverage_tests": summary.worst_coverage_tests,
        "assertion_detection_confidence": summary.assertion_detection_confidence,
    }

    payload: dict[str, object] = {
        "quality_reports": report_entries,
        "quality_summary": summary_dict,
    }

    return json.dumps(payload, default=_json_default, indent=indent)
