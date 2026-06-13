"""Configuration loader for ``.gaze.yaml``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ClassificationThresholds:
    """Confidence thresholds for contractual / incidental labelling."""

    contractual: int = 80
    incidental: int = 50


@dataclass
class DocScanConfig:
    """Settings for documentation scanning."""

    exclude: list[str] = field(default_factory=lambda: ["vendor/**"])
    include: Optional[list[str]] = None
    timeout: str = "30s"


@dataclass
class ClassificationConfig:
    """Wraps thresholds and doc-scan settings."""

    thresholds: ClassificationThresholds = field(default_factory=ClassificationThresholds)
    doc_scan: DocScanConfig = field(default_factory=DocScanConfig)


@dataclass
class GazeConfig:
    """Top-level gaze configuration."""

    classification: ClassificationConfig = field(default_factory=ClassificationConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> GazeConfig:
        """Load configuration from a YAML file.

        Search order when *path* is ``None``:
        1. ``.gaze.yaml`` in the current directory
        2. ``.gaze.yml`` in the current directory

        Returns sensible defaults if no config file is found.
        """
        if path is not None:
            config_path = Path(path)
        else:
            for candidate in (".gaze.yaml", ".gaze.yml"):
                config_path = Path(candidate)
                if config_path.is_file():
                    break
            else:
                return cls()

        if not config_path.is_file():
            return cls()

        with config_path.open() as fh:
            raw = yaml.safe_load(fh)

        if not isinstance(raw, dict):
            return cls()

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, data: dict[str, object]) -> GazeConfig:
        classification_data = data.get("classification", {})
        if not isinstance(classification_data, dict):
            return cls()

        thresholds_data = classification_data.get("thresholds", {})
        thresholds = ClassificationThresholds(
            contractual=int(thresholds_data.get("contractual", 80)) if isinstance(thresholds_data, dict) else 80,
            incidental=int(thresholds_data.get("incidental", 50)) if isinstance(thresholds_data, dict) else 50,
        )

        doc_scan_data = classification_data.get("doc_scan", {})
        if isinstance(doc_scan_data, dict):
            doc_scan = DocScanConfig(
                exclude=doc_scan_data.get("exclude", ["vendor/**"]),
                include=doc_scan_data.get("include"),
                timeout=doc_scan_data.get("timeout", "30s"),
            )
        else:
            doc_scan = DocScanConfig()

        return cls(
            classification=ClassificationConfig(
                thresholds=thresholds,
                doc_scan=doc_scan,
            )
        )
