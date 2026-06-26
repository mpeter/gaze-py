## ADDED Requirements

### Requirement: ProviderConfig dataclass
The system SHALL define a `ProviderConfig` dataclass in `src/gaze_py/report/provider.py`
with fields: `provider: str = ""`, `model: str = ""`, `endpoint: str = ""`,
`project: str = ""`, `region: str = ""`, `timeout: int = 120`. All string fields default to
empty string. `timeout` defaults to 120. The dataclass is the single data transfer object
between config loading and factory instantiation. Empty string (`""`) is the canonical
"not configured" sentinel for string fields in this DTO — this is a deliberate deviation
from CR-003 (None-not-zero) because `ProviderConfig` is an internal DTO that is never
serialized to JSON, and empty-string sentinels simplify factory dispatch without ambiguity.

#### Scenario: Default empty config
- **WHEN** `ProviderConfig()` is constructed with no arguments
- **THEN** all string fields are empty strings, `timeout` is 120, and `new_synthesizer_from_config` returns `None`

#### Scenario: Ollama config with timeout
- **WHEN** `ProviderConfig(provider="ollama", model="llama3.2:3b", timeout=60)` is constructed
- **THEN** `new_synthesizer_from_config` returns an `OllamaSynthesizer` constructed with `timeout=60`

### Requirement: new_synthesizer_from_config factory
The system SHALL implement `new_synthesizer_from_config(cfg: ProviderConfig) -> Synthesizer | None`
in `src/gaze_py/report/provider.py`. Dispatch rules (in order):

1. If both `cfg.provider` and `cfg.model` are empty: return `None` (prompt-only mode)
2. If `cfg.provider` is `"ollama"` **or** `cfg.provider` is `""` with non-empty `cfg.model`:
   return `OllamaSynthesizer(base_url=cfg.endpoint or "http://localhost:11434", model=cfg.model, timeout=cfg.timeout)`
   — setting only a model (no explicit provider) implicitly selects Ollama. This rule is
   intentional: Ollama is the zero-config local provider.
3. If `cfg.provider` is `"vertex"`: validate `project` and `region` are non-empty, validate
   field characters per the security requirement in `ai-synthesizer/spec.md`, then return
   `VertexSynthesizer(project=cfg.project, region=cfg.region, model=cfg.model, timeout=cfg.timeout)`
4. Any other `cfg.provider` value: raise `click.ClickException` naming the unknown provider
   and listing supported values (`ollama`, `vertex`)

#### Scenario: Ollama provider explicit
- **WHEN** `cfg.provider` is `"ollama"` with non-empty `model`
- **THEN** `OllamaSynthesizer` is returned with `base_url` defaulting to `http://localhost:11434` when `cfg.endpoint` is empty

#### Scenario: Ollama provider implicit (model-only)
- **WHEN** `cfg.provider` is `""` and `cfg.model` is `"llama3.2:3b"`
- **THEN** `OllamaSynthesizer` is returned — empty provider with a model name implicitly selects Ollama

#### Scenario: Ollama provider with custom endpoint
- **WHEN** `cfg.provider` is `"ollama"` and `cfg.endpoint` is `"http://myhost:11434"`
- **THEN** `OllamaSynthesizer` is constructed with `base_url="http://myhost:11434"`

#### Scenario: Vertex provider dispatch
- **WHEN** `cfg.provider` is `"vertex"` with non-empty `project`, `region`, and `model`
- **THEN** a `VertexSynthesizer` is returned with the configured values and `timeout=cfg.timeout`

#### Scenario: Vertex missing project
- **WHEN** `cfg.provider` is `"vertex"` and `cfg.project` is empty
- **THEN** `click.ClickException` is raised mentioning "project"

#### Scenario: Vertex missing region
- **WHEN** `cfg.provider` is `"vertex"` and `cfg.region` is empty
- **THEN** `click.ClickException` is raised mentioning "region"

#### Scenario: Unknown provider
- **WHEN** `cfg.provider` is an unrecognised string (e.g., `"anthropic"`)
- **THEN** `click.ClickException` is raised naming the unknown provider and listing `ollama`, `vertex`

#### Scenario: No provider configured
- **WHEN** both `cfg.provider` and `cfg.model` are empty strings
- **THEN** `None` is returned (prompt-only mode)

### Requirement: read_ai_config
The system SHALL implement `read_ai_config(gaze_config: GazeConfig, cli_model: str | None) -> ProviderConfig`
in `src/gaze_py/report/config.py`. It SHALL apply the following precedence (highest to lowest):

1. **`cli_model`**: if non-None, overrides the model field only; all other fields come from lower layers
2. **Env vars** (`GAZEPY_AI_PROVIDER`, `GAZEPY_AI_MODEL`, `GAZEPY_AI_ENDPOINT`, `GAZEPY_AI_PROJECT`, `GAZEPY_AI_REGION`, `GAZEPY_AI_TIMEOUT`): override the corresponding field from lower layers. `GAZEPY_AI_ENDPOINT` applies to Ollama only (sets `endpoint`); for Vertex it is ignored. When `GAZEPY_AI_MODEL` is set but `GAZEPY_AI_PROVIDER` is not set, the provider remains empty — the factory will interpret empty-provider + non-empty-model as Ollama (per the factory dispatch rule above).
3. **`gaze_config.ai_*` flat fields**: values from the `.gaze.yaml` `ai:` section
4. **Defaults**: empty `ProviderConfig()` — prompt-only mode

`GAZEPY_AI_TIMEOUT` is parsed as an integer; invalid values cause `click.ClickException`.

#### Scenario: CLI model override
- **WHEN** `cli_model="gemma3:4b"` is passed and `.gaze.yaml` specifies `ai_provider="ollama"` and `ai_model="llama3.2:3b"`
- **THEN** the returned config has `model="gemma3:4b"` and `provider="ollama"`

#### Scenario: Env var model-only (implicit Ollama)
- **WHEN** `GAZEPY_AI_MODEL=llama3.2:3b` is set, `GAZEPY_AI_PROVIDER` is unset, and no `.gaze.yaml` `ai_*` fields exist
- **THEN** the returned config has `model="llama3.2:3b"` and `provider=""` (the factory will select Ollama via the model-only dispatch rule)

#### Scenario: Env var full Vertex config
- **WHEN** `GAZEPY_AI_PROVIDER=vertex`, `GAZEPY_AI_MODEL=claude-sonnet-4-6`, `GAZEPY_AI_PROJECT=my-proj`, `GAZEPY_AI_REGION=us-east5` are all set
- **THEN** the returned config has all four fields populated

#### Scenario: Config file only
- **WHEN** `.gaze.yaml` has `ai_provider=vertex`, `ai_model=claude-sonnet-4-6`, `ai_project=my-proj`, `ai_region=us-east5`
- **THEN** the returned config has all four fields populated with `timeout=120` (default)

#### Scenario: Config file with timeout
- **WHEN** `.gaze.yaml` has `ai_timeout=60`
- **THEN** the returned config has `timeout=60`

#### Scenario: Nothing configured
- **WHEN** no env vars are set and `.gaze.yaml` has no `ai_*` fields and `cli_model` is `None`
- **THEN** an empty `ProviderConfig()` is returned (prompt-only mode)

### Requirement: GazeConfig ai fields (flat)
The system SHALL add flat fields to `GazeConfig` in `src/gaze_py/config/loader.py` following
the existing flat-field pattern (consistent with `doc_scan_*` fields). Fields to add:
`ai_provider: str = ""`, `ai_model: str = ""`, `ai_endpoint: str = ""`,
`ai_project: str = ""`, `ai_region: str = ""`, `ai_timeout: int = 120`.

These map to the `.gaze.yaml` `ai:` block keys `provider`, `model`, `endpoint`, `project`,
`region`, `timeout` respectively. The `_build_config` function SHALL extract the `ai:` YAML
block as a dict and populate the flat fields from it, consistent with the existing
`classification:` and `scoring:` block parsing pattern. Unknown keys in `ai:` SHALL be
silently ignored for forward-compatibility.

**Rationale for flat fields (not nested dataclass)**: the existing `GazeConfig` uses flat
primitives for all config values (e.g., `doc_scan_timeout: float`, `doc_scan_exclude: list[str]`).
A nested `AiConfig` dataclass would introduce a new pattern, require changes to `_build_config`
beyond adding key extraction, and add complexity without benefit. Flat fields are consistent,
testable, and directly accessible from `read_ai_config()`.

#### Scenario: ai section parsed from .gaze.yaml
- **WHEN** `.gaze.yaml` contains `ai: {provider: ollama, model: llama3.2:3b, timeout: 60}`
- **THEN** `gaze_config.ai_provider == "ollama"`, `gaze_config.ai_model == "llama3.2:3b"`, `gaze_config.ai_timeout == 60`

#### Scenario: Missing ai section
- **WHEN** `.gaze.yaml` has no `ai:` key
- **THEN** all `ai_*` fields on `GazeConfig` use defaults (empty strings, `ai_timeout=120`)

#### Scenario: timeout validation
- **WHEN** `.gaze.yaml` `ai.timeout` is set to a non-positive value (e.g., 0 or -1)
- **THEN** `GazeConfigError` is raised with a message in the format: `"ai.timeout must be > 0, got X in /path/.gaze.yaml"`

#### Scenario: timeout type coercion
- **WHEN** `.gaze.yaml` `ai.timeout` is a float (e.g., `120.5`)
- **THEN** it is truncated to `int` (120) — consistent with the existing `_to_int` helper

#### Scenario: unknown ai keys ignored
- **WHEN** `.gaze.yaml` `ai:` contains a key not in the defined field set (e.g., `ai: {stream: true}`)
- **THEN** the key is silently ignored and no error is raised
