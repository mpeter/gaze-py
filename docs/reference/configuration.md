# Configuration (.gaze.yaml)

gaze-py reads configuration from `.gaze.yaml`. The file is discovered by walking up from the analysis path, stopping at the project root (`pyproject.toml` or `.git`). When no `.gaze.yaml` is found, all defaults apply.

Unknown keys are silently ignored for forward-compatibility.

## Example

```yaml
contractual_threshold: 80
incidental_threshold: 50
crap_threshold: 15.0
gaze_crap_threshold: 15.0
doc_scan_exclude:
  - vendor/**
  - node_modules/**
  - .git/**
  - testdata/**
  - CHANGELOG.md
  - CONTRIBUTING.md
doc_scan_include: []
doc_scan_timeout: 30.0
```

## Keys

### `contractual_threshold`

| | |
|---|---|
| Type | integer |
| Default | `80` |
| Valid range | [0, 100] |

Minimum confidence score for a side effect to be classified as **contractual**. Effects with a confidence score at or above this value are labeled contractual.

Override per-run with `--contractual-threshold`.

---

### `incidental_threshold`

| | |
|---|---|
| Type | integer |
| Default | `50` |
| Valid range | [0, 100] |

Maximum confidence score (exclusive) for a side effect to be classified as **incidental**. Effects with a confidence score below this value are labeled incidental. Effects between `incidental_threshold` and `contractual_threshold` are labeled ambiguous.

Override per-run with `--incidental-threshold`.

---

### `crap_threshold`

| | |
|---|---|
| Type | float |
| Default | `15.0` |
| Valid range | > 0 |

CRAP score threshold for CRAPload computation. Functions with a CRAP score above this value are counted in CRAPload. Used by `gazepy crap`, `gazepy report`, and `gazepy self-check`.

Override per-run with `--crap-threshold`.

---

### `gaze_crap_threshold`

| | |
|---|---|
| Type | float |
| Default | `15.0` |
| Valid range | > 0 |

GazeCRAP score threshold for GazeCRAPload computation. Used alongside `crap_threshold` when GazeCRAP scores are available.

Override per-run with `--gaze-crap-threshold`.

---

### `doc_scan_exclude`

| | |
|---|---|
| Type | list of glob strings |
| Default | `["vendor/**", "node_modules/**", ".git/**", "testdata/**", "CHANGELOG.md", "CONTRIBUTING.md"]` |

Glob patterns for `.md` files to exclude during document scanning. Patterns are matched against paths relative to the repository root using `fnmatch`. Used by `gazepy docscan` and the `gazepy report` pipeline.

Override per-run with `--exclude` (repeatable; replaces config excludes entirely when provided).

---

### `doc_scan_include`

| | |
|---|---|
| Type | list of glob strings |
| Default | `[]` (no filter — all files included) |

Glob patterns for `.md` files to include during document scanning. When non-empty, only files matching at least one pattern are returned. An empty list means all files pass the include filter.

Override per-run with `--include` (repeatable; replaces config includes entirely when provided).

---

### `doc_scan_timeout`

| | |
|---|---|
| Type | float |
| Default | `30.0` |
| Valid range | > 0 |

Maximum seconds to spend scanning documents. Used by `gazepy docscan` to prevent unbounded scans on large repositories.

Override per-run with `--timeout`.
