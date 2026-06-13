"""Report package — JSON and text formatters for gaze-py analysis results.

This package provides two formatters:

- ``report.json``: JSON output compatible with Go gaze's schema (ADR-002).
- ``report.text``: Human-readable text output using rich tables.

The ``build_metadata`` function is the single source of truth for metadata
assembly across all formatters.  It ensures consistent field names and
values regardless of which formatter is used.

ADR-002 adaptations vs. Go gaze:
- ``go_version`` is replaced by ``python_version``.
- ``gaze_py_version`` is added alongside ``gaze_version``.
- ``ssa_degraded`` and ``ssa_degraded_packages`` are omitted (not applicable).
- ``metadata`` is per-result (inside ``results[]``), not top-level.
"""

from __future__ import annotations

import sys
import time

from gaze_py import __version__


def build_metadata(start_ns: int, warnings: list[str] | None = None) -> dict[str, object]:
    """Build the metadata dict for JSON output.

    This is the single source of truth for metadata assembly.  All JSON
    formatters MUST call this function rather than constructing metadata
    dicts inline.

    ADR-002: ``go_version`` is absent; ``python_version`` and
    ``gaze_py_version`` are present instead.

    Args:
        start_ns: Start time from ``time.perf_counter_ns()``.  Used to
            compute ``duration_ms`` as the elapsed wall-clock time from
            the start of the analysis run to now.
        warnings: Optional list of warning strings to include in the
            ``warnings`` field.  Defaults to an empty list.

    Returns:
        A dict with the following keys:

        - ``gaze_version``: The gaze-py version string (schema compat).
        - ``gaze_py_version``: The gaze-py version string (Python-specific).
        - ``python_version``: The Python interpreter version (e.g. "3.12.0").
        - ``duration_ms``: Elapsed milliseconds since ``start_ns`` (int ≥ 0).
        - ``timestamp``: Empty string (reserved for future use).
        - ``warnings``: List of warning strings (may be empty).
    """
    elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
    vi = sys.version_info
    return {
        "gaze_version": __version__,
        "gaze_py_version": __version__,
        "python_version": f"{vi.major}.{vi.minor}.{vi.micro}",
        "duration_ms": int(elapsed_ms),
        "timestamp": "",
        "warnings": warnings or [],
    }
