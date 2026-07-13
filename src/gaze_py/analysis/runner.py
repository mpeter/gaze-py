"""High-level pipeline runner for detect+classify analysis."""

from __future__ import annotations

import ast
import dataclasses
import warnings
from pathlib import Path

from gaze_py.analysis.detector import FileDetector
from gaze_py.analysis.docscan import scan_docs
from gaze_py.analysis.files import collect_py_files
from gaze_py.classify.engine import ClassificationEngine
from gaze_py.config.loader import GazeConfig
from gaze_py.taxonomy.exceptions import GazeParseError
from gaze_py.taxonomy.models import FunctionTarget


def project_docs_text(src_path: Path, config: GazeConfig) -> str | None:
    """Scan project docs and return their combined text for Signal 5 (O3).

    Wraps scan_docs with the graceful-degradation contract every classify
    path shares: a docscan failure must never abort analysis (Principle VI),
    so any exception degrades to None with a warning.

    Args:
        src_path: Source directory or file whose project docs to scan.
        config: GazeConfig providing doc-scan excludes and timeout.

    Returns:
        Combined doc text, or None when no docs were found or the scan failed.
    """
    # BLE001 suppression is justified: scan failure must never abort
    # analysis (Principle VI graceful degradation).
    try:
        entries = scan_docs(src_path, config)
        joined = "\n".join(e.content for e in entries)
        return joined if joined.strip() else None
    except Exception as exc:  # noqa: BLE001
        warnings.warn(
            f"docscan failed, continuing without doc augmentation: {exc}",
            stacklevel=2,
        )
        return None


def build_caller_map(py_files: list[Path]) -> dict[str, int]:
    """Count distinct referencing modules per function name (Signal 3, CC-005).

    Go parity (classify/callers.go): the caller signal counts distinct
    *packages* that reference the function via TypesInfo.Uses, excluding the
    package that defines it, each counted once. The Python analog counts
    distinct *modules* (files) that reference the function's name, excluding
    every module that defines a function of that name.

    A module "references" a name when the name appears as an ``ast.Name``
    load/store, an ``ast.Attribute`` attr (``mod.fn``, ``obj.method``), or a
    ``from x import name`` alias. This is name-based, not type-resolved:
    two same-named functions in different modules share one count — the same
    granularity as the detector's ``callers.get(fn_name)`` lookup, and the
    conservative direction (over-counting popular names inflates a +5/+15
    signal, never fabricates a contractual label on its own).

    Files that fail to parse are skipped silently — the map is a scoring
    signal, not analysis output; detection itself warns on the same files.

    Args:
        py_files: Python source files that make up the analyzed tree.

    Returns:
        Mapping of simple function name → distinct referencing-module count,
        suitable for FileDetector.detect(callers=...).
    """
    defined_in: dict[str, set[Path]] = {}
    referenced_in: dict[str, set[Path]] = {}

    for py_file in py_files:
        try:
            module = ast.parse(
                py_file.read_text(encoding="utf-8", errors="replace"),
                filename=str(py_file),
            )
        except (OSError, SyntaxError, ValueError):
            continue

        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined_in.setdefault(node.name, set()).add(py_file)
            elif isinstance(node, ast.Name):
                referenced_in.setdefault(node.id, set()).add(py_file)
            elif isinstance(node, ast.Attribute):
                referenced_in.setdefault(node.attr, set()).add(py_file)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    referenced_in.setdefault(alias.name, set()).add(py_file)

    return {
        name: count
        for name, defining_files in defined_in.items()
        if (count := len(referenced_in.get(name, set()) - defining_files)) > 0
    }


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
        List of FunctionTarget with effects populated; each SideEffect
        carries its own classification (SideEffect.classification), matching
        the Go schema's per-effect attachment. The legacy per-function
        FunctionTarget.classification slot is left as None — it could only
        hold one result and silently kept the last effect's.
    """
    root = src_path if src_path.is_dir() else src_path.parent
    py_files = collect_py_files(src_path)
    engine = ClassificationEngine(
        config.contractual_threshold,
        config.incidental_threshold,
        project_docs_text=docs_text,
    )
    # Signal 3 (caller dependency): count distinct referencing modules across
    # the analyzed tree. Previously hardcoded to None, so the implemented
    # caller_signal never fired anywhere.
    callers = build_caller_map(py_files)
    all_targets: list[FunctionTarget] = []

    for py_file in py_files:
        try:
            targets = FileDetector.detect(py_file, root=root, callers=callers)
        except GazeParseError as e:
            warnings.warn(f"Skipping {py_file}: {e}", stacklevel=2)
            continue

        for target in targets:
            if not include_unexported and target.function.startswith("_"):
                continue
            if function_filter is not None and target.function != function_filter:
                continue
            # Classify each effect and attach the result to the effect itself
            # (SideEffect is frozen — rebuild via dataclasses.replace). The
            # detector-captured context (docstring, class bases, return hint,
            # receiver) feeds Signals 1/2/5, which previously ran blind here.
            target.effects = [
                dataclasses.replace(
                    effect,
                    classification=engine.classify(
                        effect,
                        target,
                        class_bases=target.class_bases,
                        docstring=target.docstring,
                        return_type_hint=target.return_type_hint,
                        receiver_name=target.receiver,
                    ),
                )
                for effect in target.effects
            ]
            all_targets.append(target)

    return all_targets
