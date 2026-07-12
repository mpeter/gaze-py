"""Classification engine — runs all 5 signals and computes the final score.

ClassificationEngine.classify() is the single entry point for classifying a
side effect. It runs all five signal analyzers, applies the tier boost and
contradiction penalty, clamps the score to [0, 100], and assigns a label.

Per CC-001 through CC-006 (contracts.md and specs.md).
"""

from __future__ import annotations

from gaze_py.classify.signals.caller import caller_signal
from gaze_py.classify.signals.docstring import keywords_in, signal_from_keywords
from gaze_py.classify.signals.interface import interface_signal
from gaze_py.classify.signals.naming import naming_signal
from gaze_py.classify.signals.visibility import visibility_signal
from gaze_py.taxonomy.effects import TIER_MAP, Tier
from gaze_py.taxonomy.models import ClassificationResult, FunctionTarget, SideEffect, Signal

# Base confidence score for all effects (CC-001).
_BASE_CONFIDENCE: int = 50

# Tier boost values per CC-001.
_TIER_BOOST: dict[Tier, int] = {
    Tier.P0: 25,
    Tier.P1: 10,
    Tier.P2: 0,
    Tier.P3: 0,
    Tier.P4: 0,
}

# Contradiction penalty applied when both positive and negative signals exist (CC-004).
_CONTRADICTION_PENALTY: int = -20

# Score range bounds (CC-002).
_SCORE_MIN: int = 0
_SCORE_MAX: int = 100


class ClassificationEngine:
    """Classifies side effects using five signal analyzers.

    Runs all five signal analyzers (interface, visibility, caller, naming,
    docstring), sums their weights, applies the tier boost and contradiction
    penalty, clamps the score to [0, 100], and assigns a label.

    Per CC-001 through CC-006.
    """

    def __init__(
        self,
        contractual_threshold: int = 80,
        incidental_threshold: int = 50,
        *,
        project_docs_text: str | None = None,
    ) -> None:
        """Initialize the engine with classification thresholds.

        Args:
            contractual_threshold: Minimum confidence score for the
                'contractual' label. Must be in [0, 100]. Default: 80.
            incidental_threshold: Maximum confidence score (exclusive) for
                the 'incidental' label. Must be in [0, 100]. Default: 50.
            project_docs_text: Combined text from project documentation files
                (O3 doc scanning). When provided, augments Signal 5
                (docstring_signal) by appending this text to the per-function
                docstring. Default: None (no augmentation).
        """
        self._contractual_threshold = contractual_threshold
        self._incidental_threshold = incidental_threshold
        self._project_docs_text = project_docs_text
        # Perf: project docs text is invariant across every classify() call,
        # so scan it for signal keywords exactly once here. Re-scanning the
        # multi-MB combined docs blob per side effect made large-repo runs
        # take minutes (O(effects × docs_bytes) in str.lower()).
        self._docs_keywords = keywords_in(project_docs_text)

    def classify(
        self,
        effect: SideEffect,
        target: FunctionTarget,
        *,
        class_bases: list[str] | None = None,
        docstring: str | None = None,
        return_type_hint: str | None = None,
        receiver_name: str | None = None,
    ) -> ClassificationResult:
        """Classify a side effect and return a ClassificationResult.

        Runs all five signal analyzers, applies tier boost and contradiction
        penalty, clamps the score to [0, 100], and assigns a label based on
        the configured thresholds.

        Args:
            effect: The SideEffect being classified.
            target: The FunctionTarget containing the effect. Provides
                caller_count and function name.
            class_bases: List of base class names for the containing class,
                or None for standalone functions. Used by the interface signal.
            docstring: The function's docstring text, or None when absent.
                Used by the docstring signal.
            return_type_hint: String representation of the return type
                annotation, or None when absent. Used by the visibility signal.
            receiver_name: Name of the containing class, or None for
                standalone functions. Used by the visibility signal.

        Returns:
            A frozen ClassificationResult with label, score, and signals.
        """
        signals: list[Signal] = []

        # Signal 1: Interface satisfaction.
        sig = interface_signal(class_bases)
        if sig is not None:
            signals.append(sig)

        # Signal 2: API visibility.
        sig = visibility_signal(
            target.function,
            return_type_hint=return_type_hint,
            receiver_name=receiver_name,
        )
        if sig is not None:
            signals.append(sig)

        # Signal 3: Caller dependency.
        sig = caller_signal(target.caller_count)
        if sig is not None:
            signals.append(sig)

        # Signal 4: Naming convention.
        sig = naming_signal(target.function, effect.type)
        if sig is not None:
            signals.append(sig)

        # Signal 5: Docstring keywords — augmented with project docs text (O3).
        # Per-function docstring keywords are unioned with the precomputed
        # project-docs keyword set (see __init__) so behavioral declarations
        # in README/architecture docs contribute even when functions lack
        # docstrings. Equivalent to scanning the concatenated text — keywords
        # are alphabetic, so none can straddle the old "\n" join boundary —
        # but without re-scanning megabytes of docs per side effect.
        found_keywords = keywords_in(docstring) | self._docs_keywords
        sig = signal_from_keywords(found_keywords, effect.type)
        if sig is not None:
            signals.append(sig)

        # CC-004: Contradiction detection — both positive AND negative signals present.
        has_positive = any(s.weight > 0 for s in signals)
        has_negative = any(s.weight < 0 for s in signals)
        if has_positive and has_negative:
            signals.append(Signal(source="contradiction", weight=_CONTRADICTION_PENALTY))

        # CC-001: Compute raw score.
        tier = TIER_MAP[effect.type]
        tier_boost = _TIER_BOOST[tier]
        signal_sum = sum(s.weight for s in signals)
        raw_score = _BASE_CONFIDENCE + tier_boost + signal_sum

        # CC-002: Clamp to [0, 100].
        final_score = max(_SCORE_MIN, min(_SCORE_MAX, raw_score))

        # CC-003: Assign label based on thresholds.
        label = _assign_label(
            final_score,
            contractual_threshold=self._contractual_threshold,
            incidental_threshold=self._incidental_threshold,
        )

        return ClassificationResult(
            label=label,
            score=final_score,
            signals=tuple(signals),
        )


def _assign_label(
    score: int,
    *,
    contractual_threshold: int,
    incidental_threshold: int,
) -> str:
    """Assign a classification label based on the clamped score.

    Per CC-003:
    - 'contractual' when score >= contractual_threshold (inclusive)
    - 'ambiguous' when incidental_threshold <= score < contractual_threshold
    - 'incidental' when score < incidental_threshold

    Args:
        score: Clamped confidence score in [0, 100].
        contractual_threshold: Minimum score for 'contractual' label.
        incidental_threshold: Maximum score (exclusive) for 'incidental' label.

    Returns:
        One of 'contractual', 'ambiguous', or 'incidental'.
    """
    if score >= contractual_threshold:
        return "contractual"
    if score >= incidental_threshold:
        return "ambiguous"
    return "incidental"
