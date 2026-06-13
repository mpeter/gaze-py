"""JSON output formatters for gaze-py analysis and quality reports.

Both formatters produce output that validates against the corresponding
JSON Schema (``ANALYSIS_SCHEMA`` and ``QUALITY_SCHEMA`` in
``gaze_py.report.schema``).

ADR-002 compliance:
- Top-level keys for analysis: ``version``, ``results``.
- Top-level keys for quality: ``quality_reports``, ``quality_summary``.
- Metadata is per-result (inside ``results[]``), not top-level.
- ``go_version`` is absent; ``gaze_py_version`` and ``python_version``
  are present.

Design note: ``build_metadata`` is called once per formatter invocation
and reused across all result dicts.  This ensures consistent
``duration_ms`` values (measured from the start of the write call)
and avoids repeated calls to ``time.perf_counter_ns()``.
"""

from __future__ import annotations

import json
import time
from typing import IO, TYPE_CHECKING

from gaze_py.report import build_metadata

if TYPE_CHECKING:
    from gaze_py.taxonomy import AnalysisResult, PackageSummary, QualityReport


def write_analysis_json(
    results: list[AnalysisResult],
    version: str,
    out: IO[str],
) -> None:
    """Write analysis results as formatted JSON to *out*.

    The output validates against ``ANALYSIS_SCHEMA`` (Draft 2020-12).
    Top-level keys are ``version`` and ``results`` (SC-023).  Each
    result dict includes a ``metadata`` field with ``gaze_py_version``,
    ``python_version``, and ``duration_ms`` (SC-024).

    Args:
        results: List of ``AnalysisResult`` objects to serialise.
        version: The gaze-py version string to embed in the output.
        out: Writable text stream to write JSON to.
    """
    # Capture start time once; all result metadata shares the same
    # duration_ms so the report reflects total formatter time.
    start_ns = time.perf_counter_ns()
    meta = build_metadata(start_ns)

    result_dicts = []
    for r in results:
        d = r.to_dict()
        # Inject metadata into each result dict (ADR-002: per-result, not top-level).
        d["metadata"] = meta
        result_dicts.append(d)

    payload: dict[str, object] = {"version": version, "results": result_dicts}
    json.dump(payload, out, indent=2)
    out.write("\n")


def write_quality_json(
    reports: list[QualityReport],
    summary: PackageSummary,
    version: str,
    out: IO[str],
) -> None:
    """Write quality reports as formatted JSON to *out*.

    The output validates against ``QUALITY_SCHEMA`` (Draft 2020-12).
    Top-level keys are ``quality_reports`` and ``quality_summary``.
    Each report dict includes a ``metadata`` field.

    Args:
        reports: List of ``QualityReport`` objects to serialise.
        summary: ``PackageSummary`` with aggregate metrics.
        version: The gaze-py version string (reserved for future use
            in the quality schema; not currently embedded in output).
        out: Writable text stream to write JSON to.
    """
    # Capture start time once; all report metadata shares the same duration_ms.
    start_ns = time.perf_counter_ns()
    meta = build_metadata(start_ns)

    report_dicts = []
    for r in reports:
        d = r.to_dict()
        d["metadata"] = meta
        report_dicts.append(d)

    payload: dict[str, object] = {
        "quality_reports": report_dicts,
        "quality_summary": summary.to_dict(),
    }
    json.dump(payload, out, indent=2)
    out.write("\n")
