"""Output formatting and AI synthesis layer for gazepy report.

Submodules:

- ``json_formatter``: Serializes ``AnalysisResult`` to JSON
  (``analysis_to_json()``, ``quality_to_json()``). Uses ``dataclasses.asdict()``
  + a custom ``_json_default`` encoder (CR-005 deviation from AP-003).
- ``text_formatter``: Serializes ``AnalysisResult`` to plain text
  (``to_text()``). No rich dependency (CR-006 exception to CS-009).
- ``ai``: Defines the ``Synthesizer`` Protocol and three concrete
  implementations: ``NoopSynthesizer`` (test double, exported),
  ``OllamaSynthesizer`` (HTTP POST to Ollama /api/generate), and
  ``VertexSynthesizer`` (HTTP POST to Vertex AI rawPredict with gcloud auth).
- ``provider``: ``ProviderConfig`` dataclass (config DTO) and
  ``new_synthesizer_from_config()`` factory that dispatches to the correct
  ``Synthesizer`` implementation based on the configured provider.
- ``config``: ``read_ai_config()`` assembles a ``ProviderConfig`` from three
  layers: CLI ``--model`` flag > ``GAZEPY_AI_*`` env vars > ``.gaze.yaml``
  ``ai:`` section > empty defaults (prompt-only mode).
"""
