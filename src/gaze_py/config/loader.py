"""Configuration loader for gaze-py.

Discovers and parses .gaze.yaml by walking up from the analysis start path.
Walk stops at the first ancestor containing pyproject.toml or .git (project
root sentinel) to prevent reading config files above the project boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from gaze_py.taxonomy.exceptions import GazeConfigError

# Sentinel files/directories that mark the project root.
# Walk stops at the first ancestor that contains any of these.
SENTINELS: frozenset[str] = frozenset({"pyproject.toml", ".git"})

# Valid range for percentage thresholds: [0, 100].
_THRESHOLD_MAX: int = 100
_THRESHOLD_MIN: int = 0


@dataclass
class GazeConfig:
    """Configuration values loaded from .gaze.yaml.

    All fields have defaults that match the porting contract defaults.
    Unknown YAML keys are silently ignored for forward-compatibility.

    Attributes:
        contractual_threshold: Minimum confidence score for "contractual"
            label. Must be in [0, 100]. Default: 80.
        incidental_threshold: Maximum confidence score (exclusive) for
            "incidental" label. Must be in [0, 100]. Default: 50.
        crap_threshold: CRAP score threshold for CRAPload. Must be > 0.
            Default: 15.0.
        gaze_crap_threshold: GazeCRAP score threshold for GazeCRAPload.
            Must be > 0. Default: 15.0.
        doc_scan_exclude: Glob patterns for .md files to exclude during
            document scanning. Matched against paths relative to the repo
            root using fnmatch. Default matches Go reference excludes.
        doc_scan_include: Glob patterns for .md files to include during
            document scanning. When non-empty, only matching files are
            returned. Default: [] (no filter — all files included).
        doc_scan_timeout: Maximum seconds to spend scanning documents.
            Must be > 0. Default: 30.0.
    """

    contractual_threshold: int = 80
    incidental_threshold: int = 50
    crap_threshold: float = 15.0
    gaze_crap_threshold: float = 15.0
    doc_scan_exclude: list[str] = field(
        default_factory=lambda: [
            "vendor/**",
            "node_modules/**",
            ".git/**",
            "testdata/**",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
        ]
    )
    doc_scan_include: list[str] = field(default_factory=list)
    doc_scan_timeout: float = 30.0


def load_config_explicit(config_path: Path) -> GazeConfig:
    """Load configuration from an explicit .gaze.yaml file path.

    Use when the caller provides a specific config file path via a CLI flag
    rather than relying on walk-up auto-discovery.

    Args:
        config_path: Path to the .gaze.yaml file to load.

    Returns:
        GazeConfig populated from the file.

    Raises:
        GazeConfigError: When the file cannot be read, parsed, or validated.
    """
    return _parse_config(config_path, config_path.parent)


def load_config(start_path: Path) -> GazeConfig:
    """Walk up from start_path to find and load .gaze.yaml.

    Resolves start_path to an absolute path before walking. Stops at the
    first ancestor containing pyproject.toml or .git. Returns defaults when
    no .gaze.yaml is found.

    Args:
        start_path: Path to start the upward search from. May be a file or
            directory. Resolved with Path.resolve() before walking.

    Returns:
        GazeConfig populated from the discovered .gaze.yaml, or a default
        GazeConfig when no config file is found.

    Raises:
        GazeConfigError: When .gaze.yaml exists but cannot be parsed as YAML,
            or when a configuration value fails validation.
    """
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    while True:
        # Check project boundary FIRST — do not read config above the root.
        if any((current / s).exists() for s in SENTINELS):
            candidate = current / ".gaze.yaml"
            if candidate.exists():
                return _parse_config(candidate, current)
            break  # at project root; no config found

        candidate = current / ".gaze.yaml"
        if candidate.exists():
            return _parse_config(candidate, current)

        parent = current.parent
        if parent == current:  # filesystem root reached
            break
        current = parent

    return GazeConfig()


def _parse_config(candidate: Path, _current: Path) -> GazeConfig:
    """Read and parse a .gaze.yaml file.

    Args:
        candidate: Path to the .gaze.yaml file.
        _current: Directory containing the config file (unused; reserved for
            future use such as relative path resolution).

    Returns:
        GazeConfig populated from the YAML file.

    Raises:
        GazeConfigError: When the file cannot be parsed as YAML or a value
            fails validation.
    """
    try:
        raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    except OSError as e:
        raise GazeConfigError(f"Cannot read {candidate}: {e}") from e
    except yaml.YAMLError as e:
        raise GazeConfigError(f"Failed to parse {candidate}: {e}") from e
    return _build_config(raw, candidate)


def _to_int(value: object, field: str, path: Path) -> int:
    """Coerce a YAML scalar to int, raising GazeConfigError on failure.

    Args:
        value: Raw YAML value (may be int, float, or str from YAML parsing).
        field: Field name for error messages.
        path: Config file path for error messages.

    Returns:
        Integer representation of value.

    Raises:
        GazeConfigError: When value cannot be converted to int.
    """
    if isinstance(value, (int, float)):
        return int(value)
    raise GazeConfigError(f"Invalid value for {field} in {path}: expected number, got {value!r}")


def _to_float(value: object, field: str, path: Path) -> float:
    """Coerce a YAML scalar to float, raising GazeConfigError on failure.

    Args:
        value: Raw YAML value (may be int, float, or str from YAML parsing).
        field: Field name for error messages.
        path: Config file path for error messages.

    Returns:
        Float representation of value.

    Raises:
        GazeConfigError: When value cannot be converted to float.
    """
    if isinstance(value, (int, float)):
        return float(value)
    raise GazeConfigError(f"Invalid value for {field} in {path}: expected number, got {value!r}")


def _build_config(raw: dict[str, object], path: Path) -> GazeConfig:
    """Build a GazeConfig from a parsed YAML dict.

    Unknown keys are silently ignored for forward-compatibility.

    Args:
        raw: Parsed YAML content as a dict.
        path: Path to the config file (used in error messages).

    Returns:
        GazeConfig with values from raw, falling back to defaults.

    Raises:
        GazeConfigError: When a value fails range validation.
    """
    cfg = GazeConfig()

    classification = raw.get("classification", {})
    thresholds: dict[str, object] = {}
    if isinstance(classification, dict):
        thresholds_raw = classification.get("thresholds", {})
        if isinstance(thresholds_raw, dict):
            thresholds = thresholds_raw

    scoring_raw = raw.get("scoring", {})
    scoring: dict[str, object] = scoring_raw if isinstance(scoring_raw, dict) else {}

    if "contractual" in thresholds:
        cfg.contractual_threshold = _to_int(thresholds["contractual"], "contractual", path)
    if "incidental" in thresholds:
        cfg.incidental_threshold = _to_int(thresholds["incidental"], "incidental", path)
    if "crap_threshold" in scoring:
        cfg.crap_threshold = _to_float(scoring["crap_threshold"], "crap_threshold", path)
    if "gaze_crap_threshold" in scoring:
        cfg.gaze_crap_threshold = _to_float(
            scoring["gaze_crap_threshold"], "gaze_crap_threshold", path
        )

    doc_scan_raw = classification.get("doc_scan", {}) if isinstance(classification, dict) else {}
    doc_scan: dict[str, object] = doc_scan_raw if isinstance(doc_scan_raw, dict) else {}
    if "exclude" in doc_scan:
        exclude_val = doc_scan["exclude"]
        if isinstance(exclude_val, list):
            cfg.doc_scan_exclude = [str(v) for v in exclude_val]
    if "include" in doc_scan:
        include_val = doc_scan["include"]
        if isinstance(include_val, list):
            cfg.doc_scan_include = [str(v) for v in include_val]
    if "timeout" in doc_scan:
        cfg.doc_scan_timeout = _to_float(doc_scan["timeout"], "doc_scan.timeout", path)

    _validate(cfg, path)
    return cfg


def _validate(cfg: GazeConfig, path: Path) -> None:
    """Validate all threshold values are within sane ranges.

    Args:
        cfg: GazeConfig to validate.
        path: Path to the config file (used in error messages).

    Raises:
        GazeConfigError: When any threshold value is out of range.
    """
    if not (_THRESHOLD_MIN <= cfg.contractual_threshold <= _THRESHOLD_MAX):
        raise GazeConfigError(
            f"contractual_threshold must be in [0, 100], got {cfg.contractual_threshold} in {path}"
        )
    if not (_THRESHOLD_MIN <= cfg.incidental_threshold <= _THRESHOLD_MAX):
        raise GazeConfigError(
            f"incidental_threshold must be in [0, 100], got {cfg.incidental_threshold} in {path}"
        )
    if cfg.crap_threshold <= 0:
        raise GazeConfigError(f"crap_threshold must be > 0, got {cfg.crap_threshold} in {path}")
    if cfg.gaze_crap_threshold <= 0:
        raise GazeConfigError(
            f"gaze_crap_threshold must be > 0, got {cfg.gaze_crap_threshold} in {path}"
        )
    if cfg.doc_scan_timeout <= 0:
        raise GazeConfigError(
            f"doc_scan.timeout must be positive, got {cfg.doc_scan_timeout} in {path}"
        )
