"""High-level pipeline runner for detect+classify analysis."""

from __future__ import annotations

import warnings
from pathlib import Path

from gaze_py.analysis.detector import FileDetector
from gaze_py.analysis.files import collect_py_files
from gaze_py.classify.engine import ClassificationEngine
from gaze_py.config.loader import GazeConfig
from gaze_py.taxonomy.exceptions import GazeParseError
from gaze_py.taxonomy.models import FunctionTarget


def detect_and_classify(
    src_path: Path,
    *,
    config: GazeConfig,
    include_unexported: bool = False,
    function_filter: str | None = None,
    docs_text: str | None = None,
) -> list[FunctionTarget]:
    """Run the detect + classify pipeline on src_path.

    Detects side effects in all Python files under src_path, classifies each
    effect using the ClassificationEngine, and returns the resulting targets.
    Files that fail to parse emit a warning and are skipped (M1 fix).

    Args:
        src_path: Source directory or file to analyze.
        config: GazeConfig with classification thresholds.
        include_unexported: Include underscore-prefixed functions.
        function_filter: If set, only return functions matching this name.
        docs_text: Combined text from project documentation files (O3 doc
            scanning). When provided, augments Signal 5 (docstring_signal)
            for all classified functions. Default: None (no augmentation).

    Returns:
        List of FunctionTarget with effects and classification populated.
    """
    root = src_path if src_path.is_dir() else src_path.parent
    py_files = collect_py_files(src_path)
    engine = ClassificationEngine(
        config.contractual_threshold,
        config.incidental_threshold,
        project_docs_text=docs_text,
    )
    all_targets: list[FunctionTarget] = []

    for py_file in py_files:
        try:
            targets = FileDetector.detect(py_file, root=root, callers=None)
        except GazeParseError as e:
            warnings.warn(f"Skipping {py_file}: {e}", stacklevel=2)
            continue

        for target in targets:
            if not include_unexported and target.function.startswith("_"):
                continue
            if function_filter is not None and target.function != function_filter:
                continue
            for effect in target.effects:
                target.classification = engine.classify(effect, target)
            all_targets.append(target)

    return all_targets
