"""Classification engine for side-effect contractual/incidental labelling."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gaze_py.config import GazeConfig
    from gaze_py.taxonomy import Classification, SideEffect


def classify_side_effect(effect: SideEffect, config: GazeConfig) -> Classification:
    """Classify a side effect as contractual/incidental/ambiguous.

    Algorithm:
    1. Base confidence: 50
    2. Tier boost: P0 -> +25, P1 -> +10
    3. Signal analysers (stubbed)
    4. Contradiction penalty: -20 if mixed signals
    5. Clamp to [0, 100]
    6. Label: >= contractual_threshold -> contractual,
              < incidental_threshold -> incidental,
              else ambiguous
    """
    raise NotImplementedError("Classification engine not yet implemented")
