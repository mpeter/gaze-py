"""AI provider configuration loading with env-var and CLI-flag precedence.

Implements ``read_ai_config`` which assembles a ``ProviderConfig`` from three
layers (highest to lowest priority):

1. ``cli_model`` — overrides the ``model`` field only.
2. Environment variables — ``GAZEPY_AI_PROVIDER``, ``GAZEPY_AI_MODEL``,
   ``GAZEPY_AI_ENDPOINT``, ``GAZEPY_AI_PROJECT``, ``GAZEPY_AI_REGION``,
   ``GAZEPY_AI_TIMEOUT``.
3. ``GazeConfig.ai_*`` flat fields — values from the ``.gaze.yaml`` ``ai:``
   section.
4. Defaults — empty ``ProviderConfig()`` (prompt-only mode).

Design decisions:
- D4: Precedence order mirrors Dewey's ``llm/config.go`` pattern.
- D8: ``GazeConfig`` uses flat ``ai_*`` fields (not a nested dataclass) for
  consistency with the existing config pattern.
- ``GAZEPY_AI_ENDPOINT`` applies to Ollama only; it is always written to
  ``ProviderConfig.endpoint`` here.  The factory ignores ``endpoint`` when
  constructing ``VertexSynthesizer``.
- When ``GAZEPY_AI_MODEL`` is set but ``GAZEPY_AI_PROVIDER`` is not, the
  provider remains empty — the factory interprets empty-provider + non-empty
  model as Ollama (dispatch rule 2 in ``new_synthesizer_from_config``).
"""

from __future__ import annotations

import os

import click

from gaze_py.config.loader import GazeConfig
from gaze_py.report.provider import ProviderConfig

# Environment variable names — defined as module-level constants so they are
# easy to grep and cannot be silently misspelled at call sites.
_ENV_PROVIDER: str = "GAZEPY_AI_PROVIDER"
_ENV_MODEL: str = "GAZEPY_AI_MODEL"
_ENV_ENDPOINT: str = "GAZEPY_AI_ENDPOINT"
_ENV_PROJECT: str = "GAZEPY_AI_PROJECT"
_ENV_REGION: str = "GAZEPY_AI_REGION"
_ENV_TIMEOUT: str = "GAZEPY_AI_TIMEOUT"


def read_ai_config(
    gaze_config: GazeConfig,
    cli_model: str | None,
) -> ProviderConfig:
    """Assemble a ``ProviderConfig`` from config file, env vars, and CLI flags.

    Applies the following precedence (highest to lowest):

    1. ``cli_model`` — overrides the ``model`` field only; all other fields
       come from lower layers.
    2. Environment variables — each ``GAZEPY_AI_*`` var overrides the
       corresponding field from lower layers.
    3. ``gaze_config.ai_*`` flat fields — values from ``.gaze.yaml``.
    4. Defaults — empty ``ProviderConfig()`` (prompt-only mode).

    ``GAZEPY_AI_TIMEOUT`` is parsed as an integer; a non-integer value raises
    ``click.ClickException`` with a descriptive message.

    Args:
        gaze_config: Loaded ``GazeConfig`` instance (may carry ``ai_*`` fields
            from ``.gaze.yaml``).
        cli_model: Model name from the ``--model`` CLI flag, or ``None`` when
            the flag was not supplied.

    Returns:
        ``ProviderConfig`` populated from the highest-priority source for each
        field.

    Raises:
        click.ClickException: When ``GAZEPY_AI_TIMEOUT`` is set but cannot be
            parsed as a positive integer.
    """
    cfg = ProviderConfig()

    # Layer 3: populate from GazeConfig ai_* fields (lowest non-default layer).
    cfg.provider = gaze_config.ai_provider
    cfg.model = gaze_config.ai_model
    cfg.endpoint = gaze_config.ai_endpoint
    cfg.project = gaze_config.ai_project
    cfg.region = gaze_config.ai_region
    cfg.timeout = gaze_config.ai_timeout

    # Layer 2: env vars override the config-file layer.
    _apply_env_vars(cfg)

    # Layer 1: CLI model flag overrides the model field only.
    if cli_model is not None:
        cfg.model = cli_model

    return cfg


def _apply_env_vars(cfg: ProviderConfig) -> None:
    """Override ``cfg`` fields from ``GAZEPY_AI_*`` environment variables.

    Each env var is applied only when it is set (non-None).  An empty string
    value IS applied — callers can explicitly clear a config-file field by
    setting the env var to ``""``.

    ``GAZEPY_AI_TIMEOUT`` is parsed as an integer.  A non-integer value raises
    ``click.ClickException``.

    Args:
        cfg: ``ProviderConfig`` to mutate in-place.

    Raises:
        click.ClickException: When ``GAZEPY_AI_TIMEOUT`` is set but cannot be
            parsed as an integer.
    """
    provider_env = os.environ.get(_ENV_PROVIDER)
    if provider_env is not None:
        cfg.provider = provider_env

    model_env = os.environ.get(_ENV_MODEL)
    if model_env is not None:
        cfg.model = model_env

    endpoint_env = os.environ.get(_ENV_ENDPOINT)
    if endpoint_env is not None:
        cfg.endpoint = endpoint_env

    project_env = os.environ.get(_ENV_PROJECT)
    if project_env is not None:
        cfg.project = project_env

    region_env = os.environ.get(_ENV_REGION)
    if region_env is not None:
        cfg.region = region_env

    timeout_env = os.environ.get(_ENV_TIMEOUT)
    if timeout_env is not None:
        cfg.timeout = _parse_timeout_env(timeout_env)


def _parse_timeout_env(raw: str) -> int:
    """Parse ``GAZEPY_AI_TIMEOUT`` as an integer.

    Args:
        raw: Raw string value of the ``GAZEPY_AI_TIMEOUT`` env var.

    Returns:
        Integer timeout value.

    Raises:
        click.ClickException: When *raw* cannot be parsed as an integer.
    """
    try:
        return int(raw)
    except ValueError:
        raise click.ClickException(
            f"Invalid value for {_ENV_TIMEOUT}: {raw!r} is not an integer. "
            f"Set {_ENV_TIMEOUT} to a positive integer (e.g. 120)."
        ) from None
