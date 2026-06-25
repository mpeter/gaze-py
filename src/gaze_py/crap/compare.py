"""Baseline CRAP comparison — port of Go gaze internal/crap/compare.go.

Pure functions only — no I/O except load_baseline() file read.
No global state. Safe to call from any context.

Per FR-007, FR-008, FR-009, FR-010 and spec 002-gaze-parity Story 2.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class FunctionStatus(enum.StrEnum):
    """Per-function change status in a baseline comparison.

    Values match the Go reference wire format (compare_report.go).
    """

    REGRESSION = "regression"
    IMPROVEMENT = "improvement"
    UNCHANGED = "unchanged"
    NEW = "new"
    NEW_VIOLATION = "new_violation"
    REMOVED = "removed"


# ---------------------------------------------------------------------------
# Options and result types
# ---------------------------------------------------------------------------


@dataclass
class CompareOptions:
    """Options for the baseline comparison algorithm.

    Attributes:
        epsilon: Minimum CRAP / GazeCRAP delta to trigger regression or
            improvement classification. Deltas within [-epsilon, +epsilon]
            are classified as UNCHANGED. Default: 0.0 (any delta counts).
        new_function_threshold: CRAP score above which a new function is
            classified as NEW_VIOLATION instead of informational NEW.
            None is resolved at CLI wiring time to config.crap_threshold.
            Default: None.
    """

    epsilon: float = 0.0
    new_function_threshold: float | None = None


@dataclass(frozen=True)
class FunctionDelta:
    """Comparison result for a single function matched in both baseline and current.

    Attributes:
        baseline: Raw baseline result dict for this function.
        current: Raw current result dict for this function.
        crap_delta: current.crap - baseline.crap. Positive = worse.
        gaze_crap_delta: GazeCRAP delta, or None when baseline had no
            GazeCRAP data (null or zero). None means the metric was skipped.
        status: Classification of this function's change.
    """

    baseline: dict  # type: ignore[type-arg]
    current: dict  # type: ignore[type-arg]
    crap_delta: float
    gaze_crap_delta: float | None
    status: FunctionStatus


@dataclass
class ComparisonSummary:
    """Aggregate counts and pass/fail gate from a baseline comparison.

    Attributes:
        regressions: Functions whose CRAP or GazeCRAP regressed.
        improvements: Functions whose CRAP or GazeCRAP improved.
        unchanged: Functions with no significant delta.
        new_functions: New functions within the threshold (informational).
        new_violations: New functions above new_function_threshold.
        removed_functions: Functions present in baseline but absent now.
        passed: True when regressions == 0 and new_violations == 0 (D7).
        epsilon: The epsilon value used for this comparison.
        new_function_threshold: The threshold used for new-function gate.
    """

    regressions: int = 0
    improvements: int = 0
    unchanged: int = 0
    new_functions: int = 0
    new_violations: int = 0
    removed_functions: int = 0
    passed: bool = True
    epsilon: float = 0.0
    new_function_threshold: float = 15.0


@dataclass
class ComparisonResult:
    """Full result of a baseline comparison run.

    Attributes:
        deltas: Per-function diffs for functions matched in both runs.
        new_functions: Result entries present in current but not baseline.
        removed_functions: Result entries present in baseline but not current.
        summary: Aggregate counts and pass/fail gate.
        warnings: Non-fatal warnings (e.g. large unmatched set suggesting
            file renames). Emitted to stderr — not serialized in JSON output.
    """

    deltas: list[FunctionDelta] = field(default_factory=list)
    new_functions: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    removed_functions: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    summary: ComparisonSummary = field(default_factory=ComparisonSummary)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_baseline(path: Path) -> list[dict]:  # type: ignore[type-arg]
    """Deserialize a prior ``gazepy crap --format=json`` output as a baseline.

    Args:
        path: Path to the baseline JSON file.

    Returns:
        List of result dicts from the ``results`` key.

    Raises:
        ValueError: When the file is missing, empty, malformed, or uses an
            incompatible schema. All errors include an actionable message
            suggesting how to regenerate the baseline.
    """
    _REGEN = "re-generate with: gazepy crap --format=json > baseline.json"

    # (a/b) Read file — wrap FileNotFoundError early for clearer message.
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ValueError(f"baseline not found: {path}; {_REGEN}") from None
    except OSError as exc:
        raise ValueError(f"cannot read baseline {path}: {exc}; {_REGEN}") from exc

    # (a) Empty-file guard — matches Go: len(data) == 0 → error.
    if len(raw) == 0:
        raise ValueError(f"baseline is empty: {path}; {_REGEN}")

    # (c) Parse JSON — wrap JSONDecodeError with actionable message.
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"error parsing baseline JSON {path}: {exc}; {_REGEN}") from exc

    # (d) Validate results key — detect old gaze-py schema.
    if not isinstance(data, dict) or "results" not in data:
        if isinstance(data, dict) and "functions" in data:
            raise ValueError(
                f"baseline uses incompatible schema (found 'functions' key, "
                f"expected 'results'); {_REGEN}"
            )
        raise ValueError(f"baseline uses incompatible schema (missing 'results' key); {_REGEN}")

    results = data["results"]
    if not isinstance(results, list):
        raise ValueError(
            f"baseline 'results' must be a list, got {type(results).__name__}; {_REGEN}"
        )

    # (e) Empty results is valid — matches Go behavior (return empty).
    if not results:
        return []

    # (f) Validate each entry structure.
    for i, entry in enumerate(results):
        _validate_baseline_entry(i, entry, _REGEN)

    return results


def _validate_baseline_entry(i: int, entry: object, regen_hint: str) -> None:
    """Validate a single baseline entry dict has the required target fields.

    Extracted from load_baseline() to keep branch count within PLR0912 limit.

    Args:
        i: Entry index (for error messages).
        entry: Raw entry value from the JSON array.
        regen_hint: Suffix to append to error messages.

    Raises:
        ValueError: When the entry structure is invalid.
    """
    if not isinstance(entry, dict):
        raise ValueError(
            f"baseline entry {i}: expected object, got {type(entry).__name__}; {regen_hint}"
        )
    target = entry.get("target")
    if not isinstance(target, dict):
        raise ValueError(
            f"baseline entry {i}: 'target' must be an object, got "
            f"{type(target).__name__ if target is not None else 'null'}; "
            f"{regen_hint}"
        )
    for key in ("package", "function"):
        if key not in target:
            raise ValueError(f"baseline entry {i}: missing target.{key}; {regen_hint}")


def score_key(entry: dict) -> str:  # type: ignore[type-arg]
    """Build the composite lookup key for matching functions.

    Uses ``target.package + ":" + target.function`` — equivalent to
    Go's ``file + ":" + function`` (D2).

    Args:
        entry: A result dict from a ``gazepy crap --format=json`` output.

    Returns:
        Composite key string.
    """
    t = entry["target"]
    return str(t["package"]) + ":" + str(t["function"])


def classify_delta(
    crap_delta: float,
    gaze_crap_delta: float | None,
    has_gaze_delta: bool,
    epsilon: float,
) -> FunctionStatus:
    """Classify a matched function's change status.

    When signals conflict (CRAP regresses + GazeCRAP improves, or vice
    versa), regression takes precedence — conservative approach per SC-003.

    Args:
        crap_delta: current.crap - baseline.crap. Positive = worse.
        gaze_crap_delta: GazeCRAP delta, or None when has_gaze_delta is False.
        has_gaze_delta: True when baseline had GazeCRAP data (not null/zero).
        epsilon: Delta magnitude below which a change is UNCHANGED.

    Returns:
        FunctionStatus classification.
    """
    crap_regression = crap_delta > epsilon
    crap_improvement = crap_delta < -epsilon

    gaze_regression = False
    gaze_improvement = False
    if has_gaze_delta and gaze_crap_delta is not None:
        gaze_regression = gaze_crap_delta > epsilon
        gaze_improvement = gaze_crap_delta < -epsilon

    # Any regression signal wins (conservative, matches Go SC-003).
    if crap_regression or gaze_regression:
        return FunctionStatus.REGRESSION

    # Improvement only when no regression and at least one metric improved.
    if crap_improvement or gaze_improvement:
        return FunctionStatus.IMPROVEMENT

    return FunctionStatus.UNCHANGED


def compare(
    baseline: list[dict],  # type: ignore[type-arg]
    current: list[dict],  # type: ignore[type-arg]
    opts: CompareOptions,
) -> ComparisonResult:
    """Compare baseline and current CRAP results per-function.

    Pure function — no I/O, no global state (D1).

    Args:
        baseline: Result dicts from ``load_baseline()``.
        current: Result dicts from the current ``gazepy crap`` run.
        opts: Comparison options. ``opts.new_function_threshold`` MUST be
            non-None at this call site (resolved by the CLI wiring layer
            before constructing CompareOptions).

    Returns:
        ComparisonResult with per-function deltas, new/removed functions,
        summary counts, and any warnings.
    """
    # Build lookup map from baseline entries.
    baseline_map: dict[str, dict] = {score_key(e): e for e in baseline}  # type: ignore[type-arg]

    result = ComparisonResult()
    matched: set[str] = set()

    for cur in current:
        key = score_key(cur)
        base = baseline_map.get(key)

        if base is None:
            # New function — classify in summary.
            result.new_functions.append(cur)
            continue

        matched.add(key)

        crap_cur = cur.get("crap") or 0.0
        crap_base = base.get("crap") or 0.0
        crap_delta = crap_cur - crap_base

        # GazeCRAP delta — skip when baseline had no data (null/zero).
        gaze_cur = cur.get("gaze_crap")
        gaze_base = base.get("gaze_crap")
        has_gaze_delta = gaze_base is not None and gaze_base > 0 and gaze_cur is not None
        gaze_delta: float | None = None
        if has_gaze_delta and gaze_cur is not None and gaze_base is not None:
            gaze_delta = gaze_cur - gaze_base

        status = classify_delta(crap_delta, gaze_delta, has_gaze_delta, opts.epsilon)

        result.deltas.append(
            FunctionDelta(
                baseline=base,
                current=cur,
                crap_delta=crap_delta,
                gaze_crap_delta=gaze_delta,
                status=status,
            )
        )

    # Unmatched baseline entries are removed functions.
    for base in baseline:
        key = score_key(base)
        if key not in matched:
            result.removed_functions.append(base)

    # Large unmatched set warning — likely caused by file renames.
    if baseline and len(result.removed_functions) > len(baseline) * 0.5:
        n = len(result.removed_functions)
        result.warnings.append(
            f"Warning: {n} baseline functions unmatched — "
            f"file renames cause false positives in baseline comparison."
        )

    result.summary = _build_comparison_summary(result, opts)
    return result


def _build_comparison_summary(result: ComparisonResult, opts: CompareOptions) -> ComparisonSummary:
    """Compute aggregate counts from comparison result.

    Args:
        result: Populated ComparisonResult (before summary is set).
        opts: Comparison options. ``opts.new_function_threshold`` must be
            non-None at this call site.

    Returns:
        ComparisonSummary with counts and pass/fail gate.
    """
    assert opts.new_function_threshold is not None, (
        "_build_comparison_summary called before new_function_threshold was resolved; "
        "resolve None → crap_threshold in the CLI wiring layer (T218)"
    )
    threshold = opts.new_function_threshold

    summary = ComparisonSummary(
        epsilon=opts.epsilon,
        new_function_threshold=threshold,
        removed_functions=len(result.removed_functions),
    )

    for delta in result.deltas:
        if delta.status == FunctionStatus.REGRESSION:
            summary.regressions += 1
        elif delta.status == FunctionStatus.IMPROVEMENT:
            summary.improvements += 1
        else:
            summary.unchanged += 1

    for entry in result.new_functions:
        crap = entry.get("crap") or 0.0
        if crap > threshold:
            summary.new_violations += 1
        else:
            summary.new_functions += 1

    # Gate: pass when zero regressions and zero new violations (D7).
    summary.passed = summary.regressions == 0 and summary.new_violations == 0

    return summary
