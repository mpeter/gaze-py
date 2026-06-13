"""JSON Schema constants for gaze-py analysis and quality report output.

Both schemas use JSON Schema Draft 2020-12 and are designed to be
schema-compatible with Go gaze (ADR-002).  Field names are identical
where semantics match; Python-specific adaptations are documented below.

ADR-002 adaptations:
- ``go_version`` is absent from metadata; ``python_version`` is present.
- ``gaze_py_version`` is added alongside ``gaze_version``.
- ``ssa_degraded`` and ``ssa_degraded_packages`` are omitted.
- ``metadata`` is per-result (inside ``results[]``), not top-level.

Design note: ``additionalProperties: false`` is applied only at the
top-level object to prevent unknown top-level keys while keeping nested
objects flexible for schema evolution.  This follows the principle of
minimal assumptions (constitution principle 2).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Shared sub-schemas (referenced inline to avoid $defs complexity)
# ---------------------------------------------------------------------------

_METADATA_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["gaze_version", "gaze_py_version", "python_version", "duration_ms", "timestamp", "warnings"],
    "properties": {
        "gaze_version": {"type": "string"},
        "gaze_py_version": {"type": "string"},
        "python_version": {"type": "string"},
        "duration_ms": {"type": "integer", "minimum": 0},
        "timestamp": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}

_FUNCTION_TARGET_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["package", "function"],
    "properties": {
        "package": {"type": "string"},
        "function": {"type": "string"},
        "receiver": {"type": ["string", "null"]},
        "signature": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
    },
}

_SIDE_EFFECT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["id", "type", "tier", "location", "description"],
    "properties": {
        "id": {"type": "string"},
        "type": {"type": "string"},
        "tier": {"type": "string", "enum": ["P0", "P1", "P2", "P3", "P4"]},
        "location": {"type": "string"},
        "description": {"type": "string"},
        "target": {"oneOf": [_FUNCTION_TARGET_SCHEMA, {"type": "null"}]},
        "classification": {"type": ["object", "null"]},
    },
}

_ANALYSIS_RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["target", "side_effects", "metadata"],
    "properties": {
        "target": _FUNCTION_TARGET_SCHEMA,
        "side_effects": {
            "type": "array",
            "items": _SIDE_EFFECT_SCHEMA,
        },
        "metadata": _METADATA_SCHEMA,
    },
}

_CONTRACT_COVERAGE_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["percentage", "covered_count", "total_contractual", "gaps", "gap_hints"],
    "properties": {
        "percentage": {"type": "number", "minimum": 0.0, "maximum": 100.0},
        "covered_count": {"type": "integer", "minimum": 0},
        "total_contractual": {"type": "integer", "minimum": 0},
        "gaps": {"type": "array", "items": _SIDE_EFFECT_SCHEMA},
        "gap_hints": {"type": "array", "items": {"type": "string"}},
    },
}

_OVER_SPECIFICATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["count", "ratio", "incidental_assertions", "suggestions"],
    "properties": {
        "count": {"type": "integer", "minimum": 0},
        "ratio": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "incidental_assertions": {"type": "array"},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
}

_QUALITY_REPORT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": [
        "test_function",
        "test_location",
        "target_function",
        "contract_coverage",
        "over_specification",
        "ambiguous_effects",
        "unmapped_assertions",
        "assertion_count",
        "assertion_detection_confidence",
        "metadata",
    ],
    "properties": {
        "test_function": {"type": "string"},
        "test_location": {"type": "string"},
        "target_function": _FUNCTION_TARGET_SCHEMA,
        "contract_coverage": _CONTRACT_COVERAGE_SCHEMA,
        "over_specification": _OVER_SPECIFICATION_SCHEMA,
        "ambiguous_effects": {"type": "array"},
        "unmapped_assertions": {"type": "array"},
        "assertion_count": {"type": "integer", "minimum": 0},
        "assertion_detection_confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "metadata": _METADATA_SCHEMA,
    },
}

_QUALITY_SUMMARY_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": [
        "total_tests",
        "average_contract_coverage",
        "total_over_specifications",
        "assertion_detection_confidence",
        "worst_coverage_tests",
    ],
    "properties": {
        "total_tests": {"type": "integer", "minimum": 0},
        "average_contract_coverage": {"type": "number", "minimum": 0.0, "maximum": 100.0},
        "total_over_specifications": {"type": "integer", "minimum": 0},
        "assertion_detection_confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "worst_coverage_tests": {"type": "array"},
    },
}

# ---------------------------------------------------------------------------
# Public schema constants
# ---------------------------------------------------------------------------

ANALYSIS_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "gaze-py Analysis Report",
    "description": "Schema for gaze-py analysis output (ADR-002 compatible with Go gaze).",
    "type": "object",
    "required": ["version", "results"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string"},
        "results": {
            "type": "array",
            "items": _ANALYSIS_RESULT_SCHEMA,
        },
    },
}
"""Draft 2020-12 JSON Schema for gaze-py analysis report output.

Top-level structure::

    {
        "version": "0.1.0",
        "results": [
            {
                "target": {...},
                "side_effects": [...],
                "metadata": {
                    "gaze_version": "...",
                    "gaze_py_version": "...",
                    "python_version": "...",
                    "duration_ms": 42,
                    "timestamp": "",
                    "warnings": []
                }
            }
        ]
    }

ADR-002: ``go_version`` is absent; ``gaze_py_version`` and
``python_version`` are present.  ``ssa_degraded`` is omitted.
"""

QUALITY_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "gaze-py Quality Report",
    "description": "Schema for gaze-py quality report output.",
    "type": "object",
    "required": ["quality_reports", "quality_summary"],
    "additionalProperties": False,
    "properties": {
        "quality_reports": {
            "type": "array",
            "items": _QUALITY_REPORT_SCHEMA,
        },
        "quality_summary": _QUALITY_SUMMARY_SCHEMA,
    },
}
"""Draft 2020-12 JSON Schema for gaze-py quality report output.

Top-level structure::

    {
        "quality_reports": [
            {
                "test_function": "...",
                "test_location": "...",
                "target_function": {...},
                "contract_coverage": {...},
                "over_specification": {...},
                "ambiguous_effects": [],
                "unmapped_assertions": [],
                "assertion_count": 1,
                "assertion_detection_confidence": 80,
                "metadata": {...}
            }
        ],
        "quality_summary": {
            "total_tests": 1,
            "average_contract_coverage": 100.0,
            "total_over_specifications": 0,
            "assertion_detection_confidence": 80,
            "worst_coverage_tests": []
        }
    }
"""
