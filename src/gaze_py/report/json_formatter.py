"""JSON output formatter for gaze-py analysis results.

Serializes AnalysisResult to a JSON string using dataclasses.asdict() with
a custom encoder that handles enum values and None → null.

Per OC-002: all field names are snake_case (no camelCase).
Per OC-003: None fields serialize as JSON null (default Python behavior).
Per CR-005: uses dataclasses.asdict() + custom encoder; no to_dict() methods.
"""

from __future__ import annotations

import dataclasses
import enum
import json
from typing import Any

from gaze_py.taxonomy.models import AnalysisResult

# JSON schema for the AnalysisResult output format.
# Extracted as a module-level constant so the `schema` CLI command can emit it
# directly without re-serializing a live object (task 6.1).
SCHEMA: str = json.dumps(
    {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "AnalysisResult",
        "description": "gaze-py analysis result envelope (analyze and crap commands).",
        "type": "object",
        "required": ["functions", "summary"],
        "properties": {
            "functions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "file_path", "line", "complexity", "side_effects"],
                    "properties": {
                        "name": {"type": "string"},
                        "file_path": {"type": "string"},
                        "line": {"type": "integer"},
                        "complexity": {"type": "integer"},
                        "side_effects": {"type": "array"},
                        "classification": {"type": ["object", "null"]},
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

    Args:
        obj: Object that the default JSON encoder cannot handle.

    Returns:
        A JSON-serializable representation of obj.

    Raises:
        TypeError: When obj is not a recognized type.
    """
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_json(result: AnalysisResult, *, indent: int = 2) -> str:
    """Serialize an AnalysisResult to a JSON string.

    Uses dataclasses.asdict() to convert the result to a plain dict, then
    json.dumps() with a custom encoder for enum values. None fields serialize
    as JSON null per OC-003.

    The output structure mirrors the AnalysisResult dataclass hierarchy:
    - "functions": list of function-level dicts
    - "summary": aggregate statistics dict

    Each function dict includes all Score fields (line_coverage, crap,
    gaze_crap, contract_coverage, fix_strategy, quadrant,
    effect_confidence_range) per OC-002 and OC-003.

    Args:
        result: The AnalysisResult to serialize.
        indent: JSON indentation level. Default: 2.

    Returns:
        Indented JSON string representation of the result.
    """
    # dataclasses.asdict() recursively converts all nested dataclasses to dicts.
    # It also converts tuples to lists, which is correct for JSON arrays.
    raw = dataclasses.asdict(result)

    # Reshape each function dict to match OC-002 field names.
    # The Score fields are nested under "score" in the dataclass but must be
    # flattened to the function level in the JSON output per OC-002.
    for fn_dict in raw.get("functions", []):
        score_dict: dict[str, object] = fn_dict.pop("score", None) or {}
        fn_dict["line_coverage"] = score_dict.get("line_coverage")
        fn_dict["crap"] = score_dict.get("crap")
        fn_dict["gaze_crap"] = score_dict.get("gaze_crap")
        fn_dict["contract_coverage"] = score_dict.get("contract_coverage")
        fn_dict["contract_coverage_reason"] = score_dict.get("contract_coverage_reason")
        fn_dict["fix_strategy"] = score_dict.get("fix_strategy")
        fn_dict["quadrant"] = score_dict.get("quadrant")
        fn_dict["effect_confidence_range"] = score_dict.get("effect_confidence_range")
        # Rename "effects" → "side_effects" per OC-002 field naming.
        if "effects" in fn_dict:
            fn_dict["side_effects"] = fn_dict.pop("effects")

    return json.dumps(raw, default=_json_default, indent=indent)
