"""Tests for report/provider.py and report/config.py.

Covers all scenarios from the ai-provider-config spec:

Factory dispatch (new_synthesizer_from_config):
- Both empty → None (prompt-only mode)
- Ollama explicit provider
- Ollama implicit (model-only, empty provider)
- Ollama with custom endpoint
- Vertex dispatch (valid config)
- Vertex missing project → ClickException
- Vertex missing region → ClickException
- Unknown provider → ClickException

Input validation (path-traversal and unsafe chars):
- project with path-traversal chars → ClickException mentioning "project"
- region with path-traversal chars → ClickException mentioning "region"
- model with unsafe chars → ClickException mentioning "model"

Config precedence (read_ai_config):
- Nothing configured → empty ProviderConfig
- Config file only (all fields)
- Config file with timeout
- CLI model override (overrides model, keeps provider)
- Env var model-only (implicit Ollama — provider stays empty)
- Env var full Vertex config
- GAZEPY_AI_TIMEOUT invalid value → ClickException
- Env vars override config file fields
- GAZEPY_AI_ENDPOINT written to endpoint field
"""

from __future__ import annotations

import click
import pytest

from gaze_py.config.loader import GazeConfig
from gaze_py.report.ai import OllamaSynthesizer, Synthesizer, VertexSynthesizer
from gaze_py.report.config import read_ai_config
from gaze_py.report.provider import ProviderConfig, new_synthesizer_from_config

# ---------------------------------------------------------------------------
# Named constants to satisfy PLR2004 (no magic values in comparisons)
# ---------------------------------------------------------------------------
_DEFAULT_TIMEOUT = 120
_CUSTOM_TIMEOUT = 60
_OLLAMA_DEFAULT_URL = "http://localhost:11434"
_CUSTOM_ENDPOINT = "http://myhost:11434"
_OLLAMA_MODEL = "llama3.2:3b"
_VERTEX_PROJECT = "my-proj"
_VERTEX_REGION = "us-east5"
_VERTEX_MODEL = "claude-sonnet-4-6"


# ===========================================================================
# ProviderConfig dataclass
# ===========================================================================


class TestProviderConfigDefaults:
    """ProviderConfig() with no arguments uses correct defaults."""

    def test_default_provider_empty(self) -> None:
        """Default provider is empty string."""
        cfg = ProviderConfig()
        assert cfg.provider == ""

    def test_default_model_empty(self) -> None:
        """Default model is empty string."""
        cfg = ProviderConfig()
        assert cfg.model == ""

    def test_default_endpoint_empty(self) -> None:
        """Default endpoint is empty string."""
        cfg = ProviderConfig()
        assert cfg.endpoint == ""

    def test_default_project_empty(self) -> None:
        """Default project is empty string."""
        cfg = ProviderConfig()
        assert cfg.project == ""

    def test_default_region_empty(self) -> None:
        """Default region is empty string."""
        cfg = ProviderConfig()
        assert cfg.region == ""

    def test_default_timeout(self) -> None:
        """Default timeout is 120."""
        cfg = ProviderConfig()
        assert cfg.timeout == _DEFAULT_TIMEOUT

    def test_default_config_returns_none_from_factory(self) -> None:
        """new_synthesizer_from_config(ProviderConfig()) returns None."""
        result = new_synthesizer_from_config(ProviderConfig())
        assert result is None


# ===========================================================================
# Factory dispatch — new_synthesizer_from_config
# ===========================================================================


class TestFactoryDispatchNone:
    """Both provider and model empty → None (prompt-only mode)."""

    def test_both_empty_returns_none(self) -> None:
        """Scenario: No provider configured — both empty → None."""
        cfg = ProviderConfig(provider="", model="")
        result = new_synthesizer_from_config(cfg)
        assert result is None

    def test_empty_provider_empty_model_returns_none(self) -> None:
        """Explicit empty strings → None."""
        cfg = ProviderConfig()
        result = new_synthesizer_from_config(cfg)
        assert result is None


class TestFactoryDispatchOllamaExplicit:
    """Scenario: Ollama provider explicit."""

    def test_ollama_explicit_returns_ollama_synthesizer(self) -> None:
        """cfg.provider='ollama' with model → OllamaSynthesizer."""
        cfg = ProviderConfig(provider="ollama", model=_OLLAMA_MODEL)
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)

    def test_ollama_explicit_satisfies_synthesizer_protocol(self) -> None:
        """OllamaSynthesizer satisfies the Synthesizer Protocol."""
        cfg = ProviderConfig(provider="ollama", model=_OLLAMA_MODEL)
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, Synthesizer)

    def test_ollama_explicit_default_base_url(self) -> None:
        """When endpoint is empty, base_url defaults to http://localhost:11434."""
        cfg = ProviderConfig(provider="ollama", model=_OLLAMA_MODEL, endpoint="")
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)
        assert result._base_url == _OLLAMA_DEFAULT_URL  # noqa: SLF001

    def test_ollama_explicit_timeout_passed(self) -> None:
        """Timeout from ProviderConfig is passed to OllamaSynthesizer."""
        cfg = ProviderConfig(provider="ollama", model=_OLLAMA_MODEL, timeout=_CUSTOM_TIMEOUT)
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)
        assert result._timeout == _CUSTOM_TIMEOUT  # noqa: SLF001

    def test_ollama_explicit_model_passed(self) -> None:
        """Model from ProviderConfig is passed to OllamaSynthesizer."""
        cfg = ProviderConfig(provider="ollama", model=_OLLAMA_MODEL)
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)
        assert result.model_id() == _OLLAMA_MODEL


class TestFactoryDispatchOllamaImplicit:
    """Scenario: Ollama provider implicit (model-only, empty provider)."""

    def test_model_only_returns_ollama_synthesizer(self) -> None:
        """Empty provider + non-empty model → OllamaSynthesizer (implicit Ollama)."""
        cfg = ProviderConfig(provider="", model=_OLLAMA_MODEL)
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)

    def test_model_only_default_base_url(self) -> None:
        """Implicit Ollama uses default base URL when endpoint is empty."""
        cfg = ProviderConfig(provider="", model=_OLLAMA_MODEL, endpoint="")
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)
        assert result._base_url == _OLLAMA_DEFAULT_URL  # noqa: SLF001

    def test_model_only_model_passed(self) -> None:
        """Implicit Ollama receives the configured model."""
        cfg = ProviderConfig(provider="", model=_OLLAMA_MODEL)
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)
        assert result.model_id() == _OLLAMA_MODEL


class TestFactoryDispatchOllamaCustomEndpoint:
    """Scenario: Ollama provider with custom endpoint."""

    def test_custom_endpoint_used_as_base_url(self) -> None:
        """When endpoint is set, OllamaSynthesizer uses it as base_url."""
        cfg = ProviderConfig(
            provider="ollama",
            model=_OLLAMA_MODEL,
            endpoint=_CUSTOM_ENDPOINT,
        )
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)
        assert result._base_url == _CUSTOM_ENDPOINT  # noqa: SLF001

    def test_custom_endpoint_implicit_ollama(self) -> None:
        """Implicit Ollama (empty provider) also uses custom endpoint."""
        cfg = ProviderConfig(provider="", model=_OLLAMA_MODEL, endpoint=_CUSTOM_ENDPOINT)
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, OllamaSynthesizer)
        assert result._base_url == _CUSTOM_ENDPOINT  # noqa: SLF001


class TestFactoryDispatchVertex:
    """Scenario: Vertex provider dispatch."""

    def test_vertex_returns_vertex_synthesizer(self) -> None:
        """cfg.provider='vertex' with valid fields → VertexSynthesizer."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
        )
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, VertexSynthesizer)

    def test_vertex_satisfies_synthesizer_protocol(self) -> None:
        """VertexSynthesizer satisfies the Synthesizer Protocol."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
        )
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, Synthesizer)

    def test_vertex_timeout_passed(self) -> None:
        """Timeout from ProviderConfig is passed to VertexSynthesizer."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
            timeout=_CUSTOM_TIMEOUT,
        )
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, VertexSynthesizer)
        assert result._timeout == _CUSTOM_TIMEOUT  # noqa: SLF001

    def test_vertex_model_passed(self) -> None:
        """Model from ProviderConfig is passed to VertexSynthesizer."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
        )
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, VertexSynthesizer)
        assert result.model_id() == _VERTEX_MODEL

    def test_vertex_endpoint_ignored(self) -> None:
        """Vertex factory ignores the endpoint field (Ollama-only)."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
            endpoint="http://should-be-ignored:11434",
        )
        result = new_synthesizer_from_config(cfg)
        # Should succeed — endpoint is silently ignored for Vertex
        assert isinstance(result, VertexSynthesizer)


class TestFactoryDispatchVertexMissingFields:
    """Vertex provider with missing required fields → ClickException."""

    def test_vertex_missing_project_raises(self) -> None:
        """Scenario: Vertex missing project → ClickException mentioning 'project'."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project="",
            region=_VERTEX_REGION,
        )
        with pytest.raises(click.ClickException, match="project"):
            new_synthesizer_from_config(cfg)

    def test_vertex_missing_region_raises(self) -> None:
        """Scenario: Vertex missing region → ClickException mentioning 'region'."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=_VERTEX_PROJECT,
            region="",
        )
        with pytest.raises(click.ClickException, match="region"):
            new_synthesizer_from_config(cfg)

    def test_vertex_missing_model_raises(self) -> None:
        """Vertex with empty model → ClickException mentioning 'model'."""
        cfg = ProviderConfig(
            provider="vertex",
            model="",
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
        )
        with pytest.raises(click.ClickException, match="model"):
            new_synthesizer_from_config(cfg)


class TestFactoryDispatchUnknownProvider:
    """Scenario: Unknown provider → ClickException."""

    def test_unknown_provider_raises(self) -> None:
        """Unrecognised provider string raises ClickException."""
        cfg = ProviderConfig(provider="anthropic", model=_OLLAMA_MODEL)
        with pytest.raises(click.ClickException):
            new_synthesizer_from_config(cfg)

    def test_unknown_provider_names_provider_in_message(self) -> None:
        """Error message names the unknown provider."""
        cfg = ProviderConfig(provider="anthropic", model=_OLLAMA_MODEL)
        with pytest.raises(click.ClickException, match="anthropic"):
            new_synthesizer_from_config(cfg)

    def test_unknown_provider_lists_supported(self) -> None:
        """Error message lists supported providers (ollama, vertex)."""
        cfg = ProviderConfig(provider="anthropic", model=_OLLAMA_MODEL)
        with pytest.raises(click.ClickException, match="ollama"):
            new_synthesizer_from_config(cfg)

    @pytest.mark.parametrize(
        "provider",
        ["openai", "bedrock", "azure", "cohere", "OLLAMA", "Vertex"],
    )
    def test_various_unknown_providers_raise(self, provider: str) -> None:
        """Any unrecognised provider string raises ClickException."""
        cfg = ProviderConfig(provider=provider, model=_OLLAMA_MODEL)
        with pytest.raises(click.ClickException):
            new_synthesizer_from_config(cfg)


# ===========================================================================
# Input validation — path-traversal and unsafe characters
# ===========================================================================


class TestInputValidation:
    """Scenario: Path-traversal and unsafe characters in Vertex fields."""

    @pytest.mark.parametrize(
        "project",
        [
            "my/project",
            "../etc/passwd",
            "proj ect",
            "proj\x00ect",
            "proj;rm -rf /",
            "proj&bad",
        ],
    )
    def test_project_with_unsafe_chars_raises(self, project: str) -> None:
        """Scenario: Path-traversal characters in project → ClickException mentioning 'project'."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=project,
            region=_VERTEX_REGION,
        )
        with pytest.raises(click.ClickException, match="project"):
            new_synthesizer_from_config(cfg)

    @pytest.mark.parametrize(
        "region",
        [
            "us/east5",
            "../region",
            "us east5",
            "us\x00east5",
        ],
    )
    def test_region_with_unsafe_chars_raises(self, region: str) -> None:
        """Scenario: Path-traversal characters in region → ClickException mentioning 'region'."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=_VERTEX_PROJECT,
            region=region,
        )
        with pytest.raises(click.ClickException, match="region"):
            new_synthesizer_from_config(cfg)

    @pytest.mark.parametrize(
        "model",
        [
            "claude/sonnet",
            "../model",
            "claude sonnet",
            "claude\x00sonnet",
        ],
    )
    def test_model_with_unsafe_chars_raises(self, model: str) -> None:
        """Scenario: Invalid model name → ClickException mentioning 'model'."""
        cfg = ProviderConfig(
            provider="vertex",
            model=model,
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
        )
        with pytest.raises(click.ClickException, match="model"):
            new_synthesizer_from_config(cfg)

    @pytest.mark.parametrize(
        "project",
        [
            "my-project",
            "my_project",
            "my.project",
            "my-project-123",
            "proj:suffix",
        ],
    )
    def test_valid_project_chars_accepted(self, project: str) -> None:
        """Valid project identifiers (alphanumeric, hyphens, dots, underscores, colons) accepted."""
        cfg = ProviderConfig(
            provider="vertex",
            model=_VERTEX_MODEL,
            project=project,
            region=_VERTEX_REGION,
        )
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, VertexSynthesizer)

    @pytest.mark.parametrize(
        "model",
        [
            "llama3.2:3b",
            "claude-sonnet-4-6",
            "gemma3_4b",
            "model-v1.0",
        ],
    )
    def test_valid_model_chars_accepted(self, model: str) -> None:
        """Valid model identifiers are accepted (colons and dots allowed)."""
        cfg = ProviderConfig(
            provider="vertex",
            model=model,
            project=_VERTEX_PROJECT,
            region=_VERTEX_REGION,
        )
        result = new_synthesizer_from_config(cfg)
        assert isinstance(result, VertexSynthesizer)


# ===========================================================================
# read_ai_config — config precedence
# ===========================================================================


class TestReadAiConfigNothingConfigured:
    """Scenario: Nothing configured → empty ProviderConfig."""

    def test_nothing_configured_returns_empty_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no env vars, no config file fields, and cli_model=None → empty ProviderConfig."""
        # Clear all GAZEPY_AI_* env vars
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_MODEL",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)

        gaze_config = GazeConfig()
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.provider == ""
        assert result.model == ""
        assert result.endpoint == ""
        assert result.project == ""
        assert result.region == ""
        assert result.timeout == _DEFAULT_TIMEOUT

    def test_nothing_configured_factory_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty ProviderConfig from read_ai_config → factory returns None."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_MODEL",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)

        gaze_config = GazeConfig()
        cfg = read_ai_config(gaze_config, cli_model=None)
        result = new_synthesizer_from_config(cfg)
        assert result is None


class TestReadAiConfigFileOnly:
    """Scenario: Config file only — all fields populated from GazeConfig."""

    def test_config_file_all_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Scenario: Config file only — all four Vertex fields populated."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_MODEL",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)

        gaze_config = GazeConfig(
            ai_provider="vertex",
            ai_model=_VERTEX_MODEL,
            ai_project=_VERTEX_PROJECT,
            ai_region=_VERTEX_REGION,
        )
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.provider == "vertex"
        assert result.model == _VERTEX_MODEL
        assert result.project == _VERTEX_PROJECT
        assert result.region == _VERTEX_REGION
        assert result.timeout == _DEFAULT_TIMEOUT

    def test_config_file_with_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Scenario: Config file with timeout — ai_timeout=60 is used."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_MODEL",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)

        gaze_config = GazeConfig(ai_timeout=_CUSTOM_TIMEOUT)
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.timeout == _CUSTOM_TIMEOUT


class TestReadAiConfigCliModelOverride:
    """Scenario: CLI model override — overrides model, keeps provider."""

    def test_cli_model_overrides_config_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Scenario: cli_model='gemma3:4b' overrides config model, keeps provider."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_MODEL",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)

        gaze_config = GazeConfig(ai_provider="ollama", ai_model=_OLLAMA_MODEL)
        result = read_ai_config(gaze_config, cli_model="gemma3:4b")

        assert result.model == "gemma3:4b"
        assert result.provider == "ollama"

    def test_cli_model_none_does_not_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """cli_model=None leaves the model from config file unchanged."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_MODEL",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)

        gaze_config = GazeConfig(ai_model=_OLLAMA_MODEL)
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.model == _OLLAMA_MODEL

    def test_cli_model_overrides_env_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI model flag takes precedence over GAZEPY_AI_MODEL env var."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("GAZEPY_AI_MODEL", "env-model")

        gaze_config = GazeConfig()
        result = read_ai_config(gaze_config, cli_model="cli-model")

        assert result.model == "cli-model"


class TestReadAiConfigEnvVarModelOnly:
    """Scenario: Env var model-only (implicit Ollama) — provider stays empty."""

    def test_env_model_only_provider_stays_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Scenario: GAZEPY_AI_MODEL set, GAZEPY_AI_PROVIDER unset → provider=''."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("GAZEPY_AI_MODEL", _OLLAMA_MODEL)

        gaze_config = GazeConfig()
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.model == _OLLAMA_MODEL
        assert result.provider == ""

    def test_env_model_only_factory_selects_ollama(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Factory interprets empty-provider + non-empty model as Ollama."""
        for var in (
            "GAZEPY_AI_PROVIDER",
            "GAZEPY_AI_ENDPOINT",
            "GAZEPY_AI_PROJECT",
            "GAZEPY_AI_REGION",
            "GAZEPY_AI_TIMEOUT",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("GAZEPY_AI_MODEL", _OLLAMA_MODEL)

        gaze_config = GazeConfig()
        cfg = read_ai_config(gaze_config, cli_model=None)
        result = new_synthesizer_from_config(cfg)

        assert isinstance(result, OllamaSynthesizer)


class TestReadAiConfigEnvVarFullVertex:
    """Scenario: Env var full Vertex config — all four fields populated."""

    def test_env_full_vertex_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Scenario: GAZEPY_AI_PROVIDER=vertex + MODEL + PROJECT + REGION all set."""
        monkeypatch.setenv("GAZEPY_AI_PROVIDER", "vertex")
        monkeypatch.setenv("GAZEPY_AI_MODEL", _VERTEX_MODEL)
        monkeypatch.setenv("GAZEPY_AI_PROJECT", _VERTEX_PROJECT)
        monkeypatch.setenv("GAZEPY_AI_REGION", _VERTEX_REGION)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_TIMEOUT", raising=False)

        gaze_config = GazeConfig()
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.provider == "vertex"
        assert result.model == _VERTEX_MODEL
        assert result.project == _VERTEX_PROJECT
        assert result.region == _VERTEX_REGION

    def test_env_vars_override_config_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env vars take precedence over GazeConfig ai_* fields."""
        monkeypatch.setenv("GAZEPY_AI_PROVIDER", "vertex")
        monkeypatch.setenv("GAZEPY_AI_MODEL", "env-model")
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)
        monkeypatch.delenv("GAZEPY_AI_TIMEOUT", raising=False)

        gaze_config = GazeConfig(ai_provider="ollama", ai_model="config-model")
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.provider == "vertex"
        assert result.model == "env-model"

    def test_env_endpoint_written_to_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GAZEPY_AI_ENDPOINT is always written to ProviderConfig.endpoint."""
        monkeypatch.setenv("GAZEPY_AI_ENDPOINT", _CUSTOM_ENDPOINT)
        monkeypatch.delenv("GAZEPY_AI_PROVIDER", raising=False)
        monkeypatch.delenv("GAZEPY_AI_MODEL", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)
        monkeypatch.delenv("GAZEPY_AI_TIMEOUT", raising=False)

        gaze_config = GazeConfig()
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.endpoint == _CUSTOM_ENDPOINT

    def test_env_timeout_parsed_as_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GAZEPY_AI_TIMEOUT is parsed as an integer."""
        monkeypatch.setenv("GAZEPY_AI_TIMEOUT", "60")
        monkeypatch.delenv("GAZEPY_AI_PROVIDER", raising=False)
        monkeypatch.delenv("GAZEPY_AI_MODEL", raising=False)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)

        gaze_config = GazeConfig()
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.timeout == _CUSTOM_TIMEOUT
        assert isinstance(result.timeout, int)


class TestReadAiConfigTimeoutInvalidValue:
    """Scenario: GAZEPY_AI_TIMEOUT invalid value → ClickException."""

    @pytest.mark.parametrize(
        "bad_value",
        ["not-a-number", "12.5abc", "two", "", "  "],
    )
    def test_invalid_timeout_raises_click_exception(
        self, monkeypatch: pytest.MonkeyPatch, bad_value: str
    ) -> None:
        """Scenario: GAZEPY_AI_TIMEOUT non-integer → ClickException."""
        monkeypatch.setenv("GAZEPY_AI_TIMEOUT", bad_value)
        monkeypatch.delenv("GAZEPY_AI_PROVIDER", raising=False)
        monkeypatch.delenv("GAZEPY_AI_MODEL", raising=False)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)

        gaze_config = GazeConfig()
        with pytest.raises(click.ClickException):
            read_ai_config(gaze_config, cli_model=None)

    def test_invalid_timeout_message_mentions_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ClickException message mentions GAZEPY_AI_TIMEOUT."""
        monkeypatch.setenv("GAZEPY_AI_TIMEOUT", "not-a-number")
        monkeypatch.delenv("GAZEPY_AI_PROVIDER", raising=False)
        monkeypatch.delenv("GAZEPY_AI_MODEL", raising=False)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)

        gaze_config = GazeConfig()
        with pytest.raises(click.ClickException, match="GAZEPY_AI_TIMEOUT"):
            read_ai_config(gaze_config, cli_model=None)

    def test_float_string_timeout_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GAZEPY_AI_TIMEOUT='120.5' (float string) raises ClickException."""
        monkeypatch.setenv("GAZEPY_AI_TIMEOUT", "120.5")
        monkeypatch.delenv("GAZEPY_AI_PROVIDER", raising=False)
        monkeypatch.delenv("GAZEPY_AI_MODEL", raising=False)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)

        gaze_config = GazeConfig()
        with pytest.raises(click.ClickException):
            read_ai_config(gaze_config, cli_model=None)


class TestReadAiConfigPrecedenceOrder:
    """Verify the three-layer precedence: cli_model > env > config file."""

    def test_env_overrides_config_file_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var GAZEPY_AI_PROVIDER overrides GazeConfig.ai_provider."""
        monkeypatch.setenv("GAZEPY_AI_PROVIDER", "vertex")
        monkeypatch.delenv("GAZEPY_AI_MODEL", raising=False)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)
        monkeypatch.delenv("GAZEPY_AI_TIMEOUT", raising=False)

        gaze_config = GazeConfig(ai_provider="ollama")
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.provider == "vertex"

    def test_config_file_used_when_no_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GazeConfig.ai_provider is used when GAZEPY_AI_PROVIDER is not set."""
        monkeypatch.delenv("GAZEPY_AI_PROVIDER", raising=False)
        monkeypatch.delenv("GAZEPY_AI_MODEL", raising=False)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)
        monkeypatch.delenv("GAZEPY_AI_TIMEOUT", raising=False)

        gaze_config = GazeConfig(ai_provider="ollama", ai_model=_OLLAMA_MODEL)
        result = read_ai_config(gaze_config, cli_model=None)

        assert result.provider == "ollama"
        assert result.model == _OLLAMA_MODEL

    def test_cli_model_highest_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """cli_model takes precedence over both env var and config file model."""
        monkeypatch.setenv("GAZEPY_AI_MODEL", "env-model")
        monkeypatch.delenv("GAZEPY_AI_PROVIDER", raising=False)
        monkeypatch.delenv("GAZEPY_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_PROJECT", raising=False)
        monkeypatch.delenv("GAZEPY_AI_REGION", raising=False)
        monkeypatch.delenv("GAZEPY_AI_TIMEOUT", raising=False)

        gaze_config = GazeConfig(ai_model="config-model")
        result = read_ai_config(gaze_config, cli_model="cli-model")

        assert result.model == "cli-model"
