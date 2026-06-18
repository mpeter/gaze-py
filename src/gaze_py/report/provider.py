"""Provider configuration dataclass and synthesizer factory.

Defines ``ProviderConfig`` — the single data transfer object between config
loading and synthesizer instantiation — and ``new_synthesizer_from_config``
which dispatches to the correct ``Synthesizer`` implementation based on the
configured provider.

Design decisions:
- D7: This file mirrors Dewey's ``llm/provider.go`` split.
- D9: ``timeout`` is carried in ``ProviderConfig`` so the factory can pass it
  directly to synthesizer constructors without the CLI reading it separately.
- ``ProviderConfig`` uses mutable ``@dataclass`` (not ``frozen=True``) so the
  CLI can override the ``model`` field in-place after loading (D6 / task 2.3).
- Empty string is the canonical "not configured" sentinel for string fields in
  this DTO. This is a deliberate deviation from CR-003 (None-not-zero) because
  ``ProviderConfig`` is an internal DTO that is never serialised to JSON, and
  empty-string sentinels simplify factory dispatch without ambiguity (spec §1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from gaze_py.report.ai import Synthesizer

# Regex that each user-supplied identifier field (project, region, model) must
# satisfy before being embedded in a URL or subprocess argument.  Rejects
# path-traversal characters (``/``, ``..``), shell metacharacters, and
# whitespace.  Defined at module level as a compiled constant (AP-009).
_SAFE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9\-._:]+$")

# Sentinel for "not configured" — used in factory dispatch.
_EMPTY: str = ""

# Default Ollama base URL when no endpoint is configured.
_OLLAMA_DEFAULT_URL: str = "http://localhost:11434"


@dataclass
class ProviderConfig:
    """Data transfer object carrying AI provider configuration.

    All string fields default to empty string (the "not configured" sentinel).
    ``timeout`` defaults to 120 seconds (per-request HTTP timeout).

    Attributes:
        provider: Provider name — ``"ollama"``, ``"vertex"``, or ``""``
            (empty means "auto-select from model name").
        model: Model identifier (e.g. ``"llama3.2:3b"``).
        endpoint: Custom base URL for the provider. Applies to Ollama only;
            ignored for Vertex. Empty string means use the provider default.
        project: GCP project ID for Vertex AI. Empty string means not
            configured.
        region: GCP region for Vertex AI (e.g. ``"us-east5"``). Empty string
            means not configured.
        timeout: Per-request HTTP timeout in seconds. Must be > 0.
    """

    provider: str = field(default=_EMPTY)
    model: str = field(default=_EMPTY)
    endpoint: str = field(default=_EMPTY)
    project: str = field(default=_EMPTY)
    region: str = field(default=_EMPTY)
    timeout: int = 120


def new_synthesizer_from_config(cfg: ProviderConfig) -> Synthesizer | None:
    """Instantiate the correct ``Synthesizer`` from a ``ProviderConfig``.

    Dispatch rules (applied in order):

    1. Both ``cfg.provider`` and ``cfg.model`` are empty → return ``None``
       (prompt-only mode).
    2. ``cfg.provider`` is ``"ollama"`` **or** ``cfg.provider`` is ``""`` with
       a non-empty ``cfg.model`` → return ``OllamaSynthesizer``.  Setting only
       a model (no explicit provider) implicitly selects Ollama — the
       zero-config local provider.
    3. ``cfg.provider`` is ``"vertex"`` → validate ``project``, ``region``, and
       ``model`` are non-empty and contain only safe characters, then return
       ``VertexSynthesizer``.
    4. Any other ``cfg.provider`` value → raise ``click.ClickException`` naming
       the unknown provider and listing supported values.

    Args:
        cfg: Provider configuration DTO produced by ``read_ai_config``.

    Returns:
        A ``Synthesizer`` instance, or ``None`` when no provider is configured
        (prompt-only mode).

    Raises:
        click.ClickException: When the provider is unknown, or when a Vertex
            field fails validation (missing or contains unsafe characters).
    """
    # Import here to avoid a circular import at module level: provider.py
    # imports from ai.py, and ai.py must not import from provider.py.
    # TYPE_CHECKING guard above handles static analysis; this runtime import
    # is the only place the concrete classes are referenced.
    from gaze_py.report.ai import OllamaSynthesizer, VertexSynthesizer  # noqa: PLC0415

    # Rule 1: both empty → prompt-only mode.
    if cfg.provider == _EMPTY and cfg.model == _EMPTY:
        return None

    # Rule 2: Ollama (explicit or implicit via model-only).
    if cfg.provider in (_EMPTY, "ollama"):
        base_url = cfg.endpoint if cfg.endpoint else _OLLAMA_DEFAULT_URL
        return OllamaSynthesizer(
            base_url=base_url,
            model=cfg.model,
            timeout=cfg.timeout,
        )

    # Rule 3: Vertex — validate required fields and character safety.
    if cfg.provider == "vertex":
        _validate_vertex_config(cfg)
        return VertexSynthesizer(
            project=cfg.project,
            region=cfg.region,
            model=cfg.model,
            timeout=cfg.timeout,
        )

    # Rule 4: unknown provider.
    raise click.ClickException(
        f"Unknown AI provider: {cfg.provider!r}. Supported providers: ollama, vertex."
    )


def _validate_vertex_config(cfg: ProviderConfig) -> None:
    """Validate Vertex-specific fields before constructing ``VertexSynthesizer``.

    Checks that ``project``, ``region``, and ``model`` are non-empty and
    contain only characters that are safe to embed in a URL path segment or
    subprocess argument (alphanumeric, hyphens, dots, underscores, colons).

    Args:
        cfg: Provider configuration DTO to validate.

    Raises:
        click.ClickException: When any required field is empty or contains
            unsafe characters (path-traversal, shell metacharacters, etc.).
    """
    _require_non_empty(cfg.project, "project")
    _require_non_empty(cfg.region, "region")
    _require_non_empty(cfg.model, "model")
    _require_safe_id(cfg.project, "project")
    _require_safe_id(cfg.region, "region")
    _require_safe_id(cfg.model, "model")


def _require_non_empty(value: str, field_name: str) -> None:
    """Raise ``ClickException`` when *value* is an empty string.

    Args:
        value: Field value to check.
        field_name: Human-readable field name for the error message.

    Raises:
        click.ClickException: When *value* is empty.
    """
    if not value:
        raise click.ClickException(
            f"Vertex provider requires {field_name!r} to be set. "
            f"Configure it via .gaze.yaml ai.{field_name} or "
            f"GAZEPY_AI_{field_name.upper()}."
        )


def _require_safe_id(value: str, field_name: str) -> None:
    """Raise ``ClickException`` when *value* contains unsafe characters.

    Validates against ``_SAFE_ID_RE`` (``^[a-zA-Z0-9\\-._:]+$``).  Rejects
    path-traversal sequences (``/``, ``..``), shell metacharacters, and
    whitespace.

    Args:
        value: Field value to validate.
        field_name: Human-readable field name for the error message.

    Raises:
        click.ClickException: When *value* contains characters outside the
            allowed set.
    """
    if not _SAFE_ID_RE.match(value):
        raise click.ClickException(
            f"Invalid characters in {field_name!r}: {value!r}. "
            f"Only alphanumeric characters, hyphens, dots, underscores, "
            f"and colons are allowed."
        )
