"""Output formatting layer — JSON and text report formatters.

Provides to_json() and to_text() for serializing AnalysisResult to the two
supported output formats. JSON output uses dataclasses.asdict() + a custom
_json_default encoder (CR-005 deviation from AP-003). Text output uses plain
string formatting — no rich dependency (CR-006 exception to CS-009).
"""
