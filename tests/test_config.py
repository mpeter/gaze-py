"""Tests for config/loader.py — GazeConfig loading and validation.

Covers all 8 scenarios from task 2.5:
1. Happy path: all four threshold fields load correctly
2. Missing file: no .gaze.yaml found → defaults apply
3. Invalid YAML: malformed .gaze.yaml → GazeConfigError raised
4. Bad threshold: contractual_threshold=150 → GazeConfigError raised
5. Bad threshold: crap_threshold=-1 → GazeConfigError raised
6. Unknown keys: unrecognised key → silently ignored
7. Walk terminates at project root sentinel (pyproject.toml)
8. GazeConfigError from invalid YAML has __cause__ set and message contains file path
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gaze_py.config.loader import GazeConfig, load_config
from gaze_py.taxonomy.exceptions import GazeConfigError

# Default threshold values from GazeConfig — used as named constants to satisfy PLR2004.
_DEFAULT_CONTRACTUAL = 80
_DEFAULT_INCIDENTAL = 50
_DEFAULT_CRAP = 15.0
_DEFAULT_GAZE_CRAP = 15.0


class TestHappyPath:
    """Scenario 1: .gaze.yaml with all four threshold fields loads correctly."""

    def test_all_fields_loaded(self, tmp_path: Path) -> None:
        """All four threshold fields are read from .gaze.yaml."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text(
            "classification:\n"
            "  thresholds:\n"
            "    contractual: 90\n"
            "    incidental: 40\n"
            "scoring:\n"
            "  crap_threshold: 20.0\n"
            "  gaze_crap_threshold: 25.0\n"
        )
        cfg = load_config(tmp_path)

        assert cfg.contractual_threshold == 90  # noqa: PLR2004
        assert cfg.incidental_threshold == 40  # noqa: PLR2004
        assert cfg.crap_threshold == 20.0  # noqa: PLR2004
        assert cfg.gaze_crap_threshold == 25.0  # noqa: PLR2004

    def test_partial_fields_use_defaults_for_missing(self, tmp_path: Path) -> None:
        """Fields not present in .gaze.yaml fall back to defaults."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("classification:\n  thresholds:\n    contractual: 85\n")
        cfg = load_config(tmp_path)

        assert cfg.contractual_threshold == 85  # noqa: PLR2004
        # Remaining fields use defaults
        assert cfg.incidental_threshold == _DEFAULT_INCIDENTAL
        assert cfg.crap_threshold == _DEFAULT_CRAP
        assert cfg.gaze_crap_threshold == _DEFAULT_GAZE_CRAP

    def test_start_from_file_path(self, tmp_path: Path) -> None:
        """load_config accepts a file path and searches from its parent."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("scoring:\n  crap_threshold: 10.0\n")
        source_file = tmp_path / "module.py"
        source_file.write_text("# placeholder\n")

        cfg = load_config(source_file)
        assert cfg.crap_threshold == 10.0  # noqa: PLR2004


class TestMissingFile:
    """Scenario 2: no .gaze.yaml found → defaults apply."""

    def test_defaults_when_no_config(self, tmp_path: Path) -> None:
        """Returns default GazeConfig when no .gaze.yaml is found."""
        # Place a sentinel so the walk stops at tmp_path
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        cfg = load_config(tmp_path)

        assert cfg.contractual_threshold == _DEFAULT_CONTRACTUAL
        assert cfg.incidental_threshold == _DEFAULT_INCIDENTAL
        assert cfg.crap_threshold == _DEFAULT_CRAP
        assert cfg.gaze_crap_threshold == _DEFAULT_GAZE_CRAP

    def test_default_config_is_gazeconfig_instance(self, tmp_path: Path) -> None:
        """Returns a GazeConfig instance even when no file is found."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        cfg = load_config(tmp_path)
        assert isinstance(cfg, GazeConfig)


class TestInvalidYaml:
    """Scenario 3: malformed .gaze.yaml → GazeConfigError raised."""

    def test_malformed_yaml_raises_config_error(self, tmp_path: Path) -> None:
        """Malformed YAML content raises GazeConfigError."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("classification:\n  thresholds:\n    contractual: [\n")

        with pytest.raises(GazeConfigError, match="Failed to parse"):
            load_config(tmp_path)


class TestBadThresholds:
    """Scenarios 4 and 5: out-of-range threshold values → GazeConfigError."""

    def test_contractual_threshold_above_100_raises(self, tmp_path: Path) -> None:
        """contractual_threshold=150 raises GazeConfigError."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("classification:\n  thresholds:\n    contractual: 150\n")

        with pytest.raises(GazeConfigError, match="contractual_threshold"):
            load_config(tmp_path)

    def test_contractual_threshold_below_0_raises(self, tmp_path: Path) -> None:
        """contractual_threshold=-1 raises GazeConfigError."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("classification:\n  thresholds:\n    contractual: -1\n")

        with pytest.raises(GazeConfigError, match="contractual_threshold"):
            load_config(tmp_path)

    def test_crap_threshold_negative_raises(self, tmp_path: Path) -> None:
        """crap_threshold=-1 raises GazeConfigError."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("scoring:\n  crap_threshold: -1\n")

        with pytest.raises(GazeConfigError, match="crap_threshold"):
            load_config(tmp_path)

    def test_crap_threshold_zero_raises(self, tmp_path: Path) -> None:
        """crap_threshold=0 raises GazeConfigError (must be > 0)."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("scoring:\n  crap_threshold: 0\n")

        with pytest.raises(GazeConfigError, match="crap_threshold"):
            load_config(tmp_path)

    def test_gaze_crap_threshold_negative_raises(self, tmp_path: Path) -> None:
        """gaze_crap_threshold=-5 raises GazeConfigError."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("scoring:\n  gaze_crap_threshold: -5\n")

        with pytest.raises(GazeConfigError, match="gaze_crap_threshold"):
            load_config(tmp_path)

    def test_incidental_threshold_above_100_raises(self, tmp_path: Path) -> None:
        """incidental_threshold=101 raises GazeConfigError."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("classification:\n  thresholds:\n    incidental: 101\n")

        with pytest.raises(GazeConfigError, match="incidental_threshold"):
            load_config(tmp_path)


class TestUnknownKeys:
    """Scenario 6: unknown keys are silently ignored."""

    def test_unknown_top_level_key_ignored(self, tmp_path: Path) -> None:
        """An unrecognised top-level key does not raise and defaults apply."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("unknown_future_key: some_value\nanother_unknown: 42\n")

        cfg = load_config(tmp_path)

        # Defaults are used for all known fields
        assert cfg.contractual_threshold == _DEFAULT_CONTRACTUAL
        assert cfg.incidental_threshold == _DEFAULT_INCIDENTAL
        assert cfg.crap_threshold == _DEFAULT_CRAP
        assert cfg.gaze_crap_threshold == _DEFAULT_GAZE_CRAP

    def test_unknown_nested_key_ignored(self, tmp_path: Path) -> None:
        """Unknown keys nested under known sections are silently ignored."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text(
            "classification:\n"
            "  thresholds:\n"
            "    contractual: 85\n"
            "    future_threshold: 99\n"
            "scoring:\n"
            "  crap_threshold: 12.0\n"
            "  future_metric: enabled\n"
        )

        cfg = load_config(tmp_path)
        assert cfg.contractual_threshold == 85  # noqa: PLR2004
        assert cfg.crap_threshold == 12.0  # noqa: PLR2004


class TestWalkTermination:
    """Scenario 7: walk terminates at project root sentinel."""

    def test_walk_stops_at_pyproject_toml(self, tmp_path: Path) -> None:
        """Walk stops at directory containing pyproject.toml.

        A .gaze.yaml placed ABOVE the pyproject.toml sentinel must NOT be read.
        """
        # Layout:
        #   tmp_path/
        #     .gaze.yaml          ← above the sentinel, must NOT be read
        #     project/
        #       pyproject.toml    ← sentinel
        #       src/
        #         module.py       ← start_path
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        src_dir = project_dir / "src"
        src_dir.mkdir()

        # Config above the sentinel — should be ignored
        above_config = tmp_path / ".gaze.yaml"
        above_config.write_text("scoring:\n  crap_threshold: 99.0\n")

        # Sentinel at project root
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        # Start from inside the project
        start = src_dir / "module.py"
        start.write_text("# placeholder\n")

        cfg = load_config(start)

        # Must use defaults, not the 99.0 from the above-sentinel config
        assert cfg.crap_threshold == _DEFAULT_CRAP

    def test_walk_stops_at_git_directory(self, tmp_path: Path) -> None:
        """Walk stops at directory containing .git."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        above_config = tmp_path / ".gaze.yaml"
        above_config.write_text("scoring:\n  crap_threshold: 99.0\n")

        cfg = load_config(project_dir)
        assert cfg.crap_threshold == _DEFAULT_CRAP

    def test_config_within_project_is_found(self, tmp_path: Path) -> None:
        """A .gaze.yaml inside the project boundary IS found."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        # Config inside the project boundary
        (project_dir / ".gaze.yaml").write_text("scoring:\n  crap_threshold: 7.5\n")

        cfg = load_config(project_dir)
        assert cfg.crap_threshold == 7.5  # noqa: PLR2004


class TestExceptionChaining:
    """Scenario 8: GazeConfigError from invalid YAML has __cause__ and file path."""

    def test_yaml_error_has_cause(self, tmp_path: Path) -> None:
        """GazeConfigError wrapping a YAMLError has __cause__ set."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("classification:\n  thresholds:\n    contractual: [\n")

        with pytest.raises(GazeConfigError) as exc_info:
            load_config(tmp_path)

        assert exc_info.value.__cause__ is not None

    def test_yaml_error_message_contains_file_path(self, tmp_path: Path) -> None:
        """GazeConfigError message contains the path to the offending file."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("classification:\n  thresholds:\n    contractual: [\n")

        with pytest.raises(GazeConfigError) as exc_info:
            load_config(tmp_path)

        assert str(config_file) in str(exc_info.value)

    def test_gazeconfig_error_is_value_error(self, tmp_path: Path) -> None:
        """GazeConfigError is a subclass of ValueError."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("scoring:\n  crap_threshold: -1\n")

        with pytest.raises(ValueError):
            load_config(tmp_path)


# Default ai field values — named constants to satisfy PLR2004.
_DEFAULT_AI_PROVIDER = ""
_DEFAULT_AI_MODEL = ""
_DEFAULT_AI_ENDPOINT = ""
_DEFAULT_AI_PROJECT = ""
_DEFAULT_AI_REGION = ""
_DEFAULT_AI_TIMEOUT = 120


class TestAiFields:
    """Tests for ai_* flat fields on GazeConfig (Section 1 of ai-http-adapters)."""

    def test_ai_section_parsed(self, tmp_path: Path) -> None:
        """ai: block fields are read from .gaze.yaml into flat ai_* fields."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text(
            "ai:\n"
            "  provider: ollama\n"
            "  model: llama3.2:3b\n"
            "  endpoint: http://myhost:11434\n"
            "  project: my-proj\n"
            "  region: us-east5\n"
            "  timeout: 60\n"
        )
        cfg = load_config(tmp_path)

        assert cfg.ai_provider == "ollama"
        assert cfg.ai_model == "llama3.2:3b"
        assert cfg.ai_endpoint == "http://myhost:11434"
        assert cfg.ai_project == "my-proj"
        assert cfg.ai_region == "us-east5"
        assert cfg.ai_timeout == 60  # noqa: PLR2004

    def test_missing_ai_section_uses_defaults(self, tmp_path: Path) -> None:
        """When .gaze.yaml has no ai: key, all ai_* fields use defaults."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("scoring:\n  crap_threshold: 10.0\n")
        cfg = load_config(tmp_path)

        assert cfg.ai_provider == _DEFAULT_AI_PROVIDER
        assert cfg.ai_model == _DEFAULT_AI_MODEL
        assert cfg.ai_endpoint == _DEFAULT_AI_ENDPOINT
        assert cfg.ai_project == _DEFAULT_AI_PROJECT
        assert cfg.ai_region == _DEFAULT_AI_REGION
        assert cfg.ai_timeout == _DEFAULT_AI_TIMEOUT

    def test_default_gazeconfig_has_ai_defaults(self) -> None:
        """GazeConfig() constructed with no arguments has correct ai_* defaults."""
        cfg = GazeConfig()

        assert cfg.ai_provider == _DEFAULT_AI_PROVIDER
        assert cfg.ai_model == _DEFAULT_AI_MODEL
        assert cfg.ai_endpoint == _DEFAULT_AI_ENDPOINT
        assert cfg.ai_project == _DEFAULT_AI_PROJECT
        assert cfg.ai_region == _DEFAULT_AI_REGION
        assert cfg.ai_timeout == _DEFAULT_AI_TIMEOUT

    def test_ai_timeout_zero_raises(self, tmp_path: Path) -> None:
        """ai.timeout=0 raises GazeConfigError with the required message format."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("ai:\n  timeout: 0\n")

        with pytest.raises(GazeConfigError, match=r"ai\.timeout must be > 0, got 0"):
            load_config(tmp_path)

    def test_ai_timeout_negative_raises(self, tmp_path: Path) -> None:
        """ai.timeout=-1 raises GazeConfigError with the required message format."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("ai:\n  timeout: -1\n")

        with pytest.raises(GazeConfigError, match=r"ai\.timeout must be > 0, got -1"):
            load_config(tmp_path)

    def test_ai_timeout_error_contains_path(self, tmp_path: Path) -> None:
        """GazeConfigError for ai.timeout includes the config file path."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("ai:\n  timeout: 0\n")

        with pytest.raises(GazeConfigError) as exc_info:
            load_config(tmp_path)

        assert str(config_file) in str(exc_info.value)

    def test_ai_timeout_float_coerced_to_int(self, tmp_path: Path) -> None:
        """ai.timeout as a float (e.g. 120.5) is truncated to int via _to_int."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("ai:\n  timeout: 120.5\n")
        cfg = load_config(tmp_path)

        assert cfg.ai_timeout == 120  # noqa: PLR2004
        assert isinstance(cfg.ai_timeout, int)

    def test_ai_unknown_keys_ignored(self, tmp_path: Path) -> None:
        """Unknown keys inside ai: are silently ignored; no error is raised."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text(
            "ai:\n"
            "  provider: ollama\n"
            "  model: llama3.2:3b\n"
            "  stream: true\n"
            "  future_key: some_value\n"
        )
        cfg = load_config(tmp_path)

        assert cfg.ai_provider == "ollama"
        assert cfg.ai_model == "llama3.2:3b"

    def test_ai_partial_fields_use_defaults_for_missing(self, tmp_path: Path) -> None:
        """Only specified ai: keys are set; unspecified ones keep defaults."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text("ai:\n  provider: vertex\n  model: claude-sonnet-4-6\n")
        cfg = load_config(tmp_path)

        assert cfg.ai_provider == "vertex"
        assert cfg.ai_model == "claude-sonnet-4-6"
        assert cfg.ai_endpoint == _DEFAULT_AI_ENDPOINT
        assert cfg.ai_project == _DEFAULT_AI_PROJECT
        assert cfg.ai_region == _DEFAULT_AI_REGION
        assert cfg.ai_timeout == _DEFAULT_AI_TIMEOUT

    def test_ai_section_coexists_with_other_sections(self, tmp_path: Path) -> None:
        """ai: fields are parsed correctly alongside classification: and scoring:."""
        config_file = tmp_path / ".gaze.yaml"
        config_file.write_text(
            "classification:\n"
            "  thresholds:\n"
            "    contractual: 90\n"
            "scoring:\n"
            "  crap_threshold: 20.0\n"
            "ai:\n"
            "  provider: ollama\n"
            "  timeout: 30\n"
        )
        cfg = load_config(tmp_path)

        assert cfg.contractual_threshold == 90  # noqa: PLR2004
        assert cfg.crap_threshold == 20.0  # noqa: PLR2004
        assert cfg.ai_provider == "ollama"
        assert cfg.ai_timeout == 30  # noqa: PLR2004
