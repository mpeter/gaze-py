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
from typing import TypeAlias

# ---------------------------------------------------------------------------
# Type aliases — avoids bare dict[] annotations throughout (CS-005 / H-3)
# ---------------------------------------------------------------------------

JsonEntry: TypeAlias = dict[str, object]

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


@dataclass(frozen=True)
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

    baseline: JsonEntry
    current: JsonEntry
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
    new_functions: list[JsonEntry] = field(default_factory=list)
    removed_functions: list[JsonEntry] = field(default_factory=list)
    summary: ComparisonSummary = field(default_factory=ComparisonSummary)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_baseline(path: Path) -> list[JsonEntry]:
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


def score_key(entry: JsonEntry) -> str:
    """Build the composite lookup key for matching functions.

    Uses ``package:receiver.function`` for methods and ``package:function``
    for module-level functions. The receiver qualifier matters: without it,
    every method sharing a name within one file collapses to a single key
    (four ``to_dict`` methods in one module are ordinary), and the comparator
    then scores one method against another's baseline.

    That aliasing was latent while coverage was attributed per file — every
    function in a file shared one coverage value, so same-named functions of
    equal complexity produced equal CRAP and the mismatch cancelled out. Once
    coverage became per function (0.9.0), an uncovered method compared against
    a covered namesake's baseline reports a phantom regression, and with the
    default epsilon of 0.0 that fails the gate.

    Go's key is ``file + ":" + function`` (D2), which does not need the
    qualifier: Go methods carry their receiver in the function name already.
    Qualifying here reproduces that uniqueness rather than departing from it.

    Args:
        entry: A result dict from a ``gazepy crap --format=json`` output.

    Returns:
        Composite key string.
    """
    t = entry["target"]
    if not isinstance(t, dict):
        raise TypeError(f"score_key: expected target dict, got {type(t).__name__}")
    receiver = t.get("receiver")
    qualifier = f"{receiver}." if isinstance(receiver, str) and receiver else ""
    return str(t["package"]) + ":" + qualifier + str(t["function"])


def legacy_score_key(entry: JsonEntry) -> str:
    """Build the pre-0.9.1 unqualified key (``package:function``).

    Baselines generated before receiver qualification key methods without it.
    Matching falls back to this key so an existing baseline keeps matching
    instead of reporting every method as simultaneously removed and new.

    Args:
        entry: A result dict from a ``gazepy crap --format=json`` output.

    Returns:
        Composite key string without the receiver qualifier.
    """
    t = entry["target"]
    if not isinstance(t, dict):
        raise TypeError(f"legacy_score_key: expected target dict, got {type(t).__name__}")
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
    baseline: list[JsonEntry],
    current: list[JsonEntry],
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
    # Group baseline entries by key rather than collapsing to one entry each.
    # A plain dict comprehension keeps only the LAST entry per key, so any
    # remaining duplicate (two module-level functions of the same name in one
    # file, or two same-named methods of the same class) would score every
    # occurrence against that one survivor. Grouping matches them one-to-one in
    # encounter order, which is the detector's stable AST walk order.
    baseline_groups: dict[str, list[JsonEntry]] = {}
    for e in baseline:
        baseline_groups.setdefault(score_key(e), []).append(e)

    # Fallback index for baselines written before receiver qualification, where
    # methods are keyed bare. Only consulted when the qualified lookup misses.
    legacy_groups: dict[str, list[JsonEntry]] = {}
    for e in baseline:
        legacy_groups.setdefault(legacy_score_key(e), []).append(e)

    result = ComparisonResult()
    matched: set[int] = set()
    consumed: dict[str, int] = {}

    for cur in current:
        key = score_key(cur)
        group = baseline_groups.get(key)
        lookup_key = key
        if not group:
            # Pre-0.9.1 baseline: retry unqualified.
            lookup_key = legacy_score_key(cur)
            group = legacy_groups.get(lookup_key)

        offset = consumed.get(lookup_key, 0)
        base = group[offset] if group is not None and offset < len(group) else None

        if base is None:
            # New function — classify in summary.
            result.new_functions.append(cur)
            continue

        consumed[lookup_key] = offset + 1
        matched.add(id(base))

        # OC-003: None means "not computed" — treat as 0.0 for delta math only.
        # Use explicit isinstance check, not `or 0.0`, to avoid treating crap=0.0 as missing.
        crap_cur_raw = cur.get("crap")
        crap_base_raw = base.get("crap")
        crap_cur: float = float(crap_cur_raw) if isinstance(crap_cur_raw, (int, float)) else 0.0
        crap_base: float = float(crap_base_raw) if isinstance(crap_base_raw, (int, float)) else 0.0
        crap_delta = crap_cur - crap_base

        # GazeCRAP delta — skip when baseline had no data (null/zero).
        gaze_cur = cur.get("gaze_crap")
        gaze_base = base.get("gaze_crap")
        has_gaze_delta = (
            isinstance(gaze_base, (int, float))
            and gaze_base > 0
            and isinstance(gaze_cur, (int, float))
        )
        gaze_delta: float | None = None
        if (
            has_gaze_delta
            and isinstance(gaze_cur, (int, float))
            and isinstance(gaze_base, (int, float))
        ):
            gaze_delta = float(gaze_cur) - float(gaze_base)

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

    # Unmatched baseline entries are removed functions. Identity-based so that
    # duplicates are reported individually — keying by name here would hide a
    # genuinely removed overload behind a surviving namesake.
    for base in baseline:
        if id(base) not in matched:
            result.removed_functions.append(base)

    # Large unmatched set warning — likely caused by file renames.
    if baseline and len(result.removed_functions) > len(baseline) * 0.5:
        n = len(result.removed_functions)
        result.warnings.append(
            f"Warning: {n} baseline functions unmatched — "
            f"file renames cause false positives in baseline comparison."
        )

    result.summary = build_comparison_summary(result, opts)
    return result


def build_comparison_summary(result: ComparisonResult, opts: CompareOptions) -> ComparisonSummary:
    """Compute aggregate counts from comparison result.

    Args:
        result: Populated ComparisonResult (before summary is set).
        opts: Comparison options. ``opts.new_function_threshold`` must be
            non-None at this call site.

    Returns:
        ComparisonSummary with counts and pass/fail gate.

    Raises:
        ValueError: When ``opts.new_function_threshold`` is None, indicating
            the CLI wiring layer failed to resolve None → crap_threshold (T218).
    """
    if opts.new_function_threshold is None:
        raise ValueError(
            "build_comparison_summary called before new_function_threshold was resolved; "
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
        # OC-003: explicit isinstance check — crap=0.0 is valid and must not be treated as missing.
        crap_raw = entry.get("crap")
        crap: float = float(crap_raw) if isinstance(crap_raw, (int, float)) else 0.0
        if crap > threshold:
            summary.new_violations += 1
        else:
            summary.new_functions += 1

    # Gate: pass when zero regressions and zero new violations (D7).
    summary.passed = summary.regressions == 0 and summary.new_violations == 0

    return summary
