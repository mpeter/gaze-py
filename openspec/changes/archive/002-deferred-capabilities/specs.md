# Delta Specs — Change 002: Deferred Capabilities

> This spec is a **tracking document**. It records requirements for each
> deferred item so they can be sequenced into future changes. Requirements
> marked `[BLOCKED]` cannot be implemented until their dependency is complete.
> Each section maps to one future OpenSpec change.

---

## ADDED Requirements (deferred — not implemented in 001)

---

### Requirement: O1-A Test-Target Pairing

The quality engine MUST heuristically pair each test function with the
production function(s) it targets, using at minimum:
1. **Name-based**: `TestFoo` / `test_foo_*` → `Foo` / `foo` in the same or
   imported module
2. **Call-graph-based**: walk the test function body's AST and identify
   production function names that are called directly

A port MAY implement additional strategies (import analysis, fixture tracing).
Pairing is probabilistic — a test may map to zero, one, or many targets.

#### Scenario: Name-based pairing
- **GIVEN** a test function named `test_compute_score` in `test_scorer.py`
- **WHEN** target inference runs against `scorer.py`
- **THEN** `compute_score` in `scorer.py` is identified as a likely target

#### Scenario: Class-based pairing
- **GIVEN** a test class `TestYamlLine` with method `test_plain_value`
- **WHEN** target inference runs
- **THEN** `_yaml_line` (or `yaml_line`) in the production module is the
  likely target

#### Scenario: No match — zero targets
- **GIVEN** a test function with no recognizable name relationship to any
  production function
- **WHEN** target inference runs
- **THEN** the test is recorded with zero targets (not an error)

---

### Requirement: O1-B Assertion Detection

The quality engine MUST detect assertion sites in test function bodies.
Assertion types MUST include the five canonical types from taxonomy-reference.md:

| Type | Description |
|---|---|
| `equality` | `assert x == y`, `assertEqual(x, y)` |
| `error_check` | `pytest.raises(E)`, `with pytest.raises(E, match=...)` |
| `nil_check` | `assert x is None`, `assert x is not None` |
| `diff_check` | Structural comparison (e.g., `assert x == {"key": val}`) |
| `custom` | Framework-specific patterns: `capsys.readouterr()`, `caplog.records`, mock `.assert_called*()` methods |

#### Scenario: Equality assertion detected
- **GIVEN** a test body containing `assert result == expected`
- **WHEN** assertion detection runs
- **THEN** an assertion of type `equality` is recorded

#### Scenario: pytest.raises detected
- **GIVEN** a test body containing `with pytest.raises(ValueError):`
- **WHEN** assertion detection runs
- **THEN** an assertion of type `error_check` is recorded

#### Scenario: capsys assertion detected
- **GIVEN** a test body containing `out = capsys.readouterr().out; assert "foo" in out`
- **WHEN** assertion detection runs
- **THEN** an assertion of type `custom` is recorded

---

### Requirement: O1-C Assertion Mapping

The quality engine MUST map each detected assertion to the side effect(s) it
verifies, using multiple passes per contracts.md O1:

1. **Direct identity match**: assertion directly names the effect's target variable
2. **Indirect root resolution**: trace assignment chain to effect origin
3. **Inline call matching**: assertion is on the return value of the call-under-test
4. **Helper function bridging**: assertion is in a shared helper called from the test

An assertion MAY map to zero effects (e.g., asserts on test infrastructure).
An effect MAY have zero mapped assertions (uncovered) or many.

#### Scenario: Return value asserted
- **GIVEN** `result = compute(x); assert result == 42`
- **WHEN** assertion mapping runs against a function with a `ReturnValue` effect
- **THEN** the `equality` assertion is mapped to the `ReturnValue` effect

#### Scenario: Exception asserted
- **GIVEN** `with pytest.raises(FileNotFoundError):`
- **WHEN** assertion mapping runs against a function with an `ErrorReturn` effect
- **THEN** the `error_check` assertion is mapped to the `ErrorReturn` effect

#### Scenario: Uncovered contractual effect
- **GIVEN** a function with a `ReceiverMutation` effect and no assertion on `self`
- **WHEN** assertion mapping runs
- **THEN** the `ReceiverMutation` effect has zero mapped assertions

---

### Requirement: O1-D Contract Coverage

The quality engine MUST compute contract coverage as:
```
contract_coverage = (contractual effects with ≥1 mapped assertion) /
                    (total contractual effects) × 100
```

When total contractual effects is zero, `contract_coverage` MUST be `null`
and `contract_coverage_reason` MUST be set to the appropriate reason code.

`contract_coverage_reason` MUST use exactly these values from taxonomy-reference.md:

| Reason | Condition |
|---|---|
| `all_effects_ambiguous` | All effects classified ambiguous; no contractual effects |
| `no_effects_detected` | Function has no detected side effects |
| `no_test_coverage` | Effects exist but no test targets this function |
| `no_assertions_mapped` | Tests exist but no assertions mapped to effects |
| *(empty / null)* | Normal coverage — no special explanation |

#### Scenario: Full contract coverage
- **GIVEN** a function with 3 contractual effects all having ≥1 assertion
- **WHEN** contract coverage is computed
- **THEN** `contract_coverage` is 100.0

#### Scenario: Partial contract coverage
- **GIVEN** a function with 4 contractual effects, 2 with assertions and 2 without
- **WHEN** contract coverage is computed
- **THEN** `contract_coverage` is 50.0

#### Scenario: No test coverage reason
- **GIVEN** a function with contractual effects but no test targets it
- **WHEN** contract coverage is computed
- **THEN** `contract_coverage` is null and `contract_coverage_reason` is
  `"no_test_coverage"`

---

### Requirement: O1-E GazeCRAP and Dependent Fields [BLOCKED: O1-D]

Once contract_coverage is available, these currently-null fields MUST be
populated:

- `gaze_crap` — computed from the GazeCRAP formula (SC-002)
- `quadrant` — Q1/Q2/Q3/Q4 per SC-004
- `fix_strategy` — including `add_assertions` (rule 3, Q3) which was
  previously unreachable without GazeCRAP
- `gaze_crapload` — count of functions where GazeCRAP >= threshold (SC-003)
- `avg_contract_coverage` — mean contract coverage across all functions
- `quadrant_counts` — count per quadrant
- `fix_strategy_counts` — count per fix strategy

#### Scenario: GazeCRAP populated
- **GIVEN** O1 has run and contract_coverage is 60.0 for a function with
  complexity 5
- **WHEN** scoring runs
- **THEN** `gaze_crap` equals `5² × (1 - 60/100)³ + 5 = 5.32`

#### Scenario: add_assertions strategy unlocked
- **GIVEN** a function in Q3 (CRAP < threshold, GazeCRAP >= threshold)
- **THEN** `fix_strategy` is `add_assertions`

---

### Requirement: O1-F effect_confidence_range [BLOCKED: O1-D]

Once classification runs with real assertion data, the `effect_confidence_range`
field MUST be populated as `[min_score, max_score]` (both ints) representing
the range of confidence scores across all effects on a given function.

When a function has no effects, `effect_confidence_range` MUST be null.

#### Scenario: Range computed
- **GIVEN** a function with 3 effects having confidence scores 75, 60, 85
- **THEN** `effect_confidence_range` is [60, 85]

---

### Requirement: O2 AI-Powered Reports

The implementation MAY pipe combined analysis JSON to an AI model (Claude,
Gemini, OpenCode) for narrative interpretation. The AI report MUST be:
- An adapter pattern — one interface, multiple backend implementations
- Triggered by a separate CLI flag (e.g., `--ai-report`) rather than always-on
- Appended to or separate from the standard JSON/text output
- Gracefully degraded when no AI backend is available

No behavioral contracts from contracts.md apply to AI reports (O2 is
uncontracted). The adapter interface is left to the implementer.

---

### Requirement: O3 Document Scanning

The classification engine MAY scan project documentation files (README.md,
architecture docs, API docs) for behavioral keywords that contribute to
Signal 5 (Documentation / `godoc`). When O3 is active:

- Behavioral keywords found in docs MUST use the same weight rules as
  inline docstrings (+15 direct, +5 indirect, -15 incidental)
- The `source` field on the resulting signal MUST be `"godoc"` (same as
  inline docstring) to preserve schema compatibility
- O3 is disabled by default; enabled via `.gaze.yaml` or `--doc-scan` flag
- Excluded paths (vendor, node_modules, .git, testdata, etc.) MUST be
  configurable per O7

---

### Requirement: O4 Interactive TUI

The implementation MAY provide a terminal UI for browsing results
interactively. No behavioral contracts apply. The TUI is a presentation layer
only and must not affect JSON/text output.

---

### Requirement: O5 CI Threshold Enforcement

The CLI MUST support threshold flags that cause a non-zero exit when violated:

| Flag | Threshold | Contract |
|---|---|---|
| `--max-crapload N` | Exit non-zero when CRAPload > N | SC-003 |
| `--max-gaze-crapload N` | Exit non-zero when GazeCRAPload > N | SC-003 |
| `--min-contract-coverage P` | Exit non-zero when avg_contract_coverage < P% | O1-D |

`--max-gaze-crapload` and `--min-contract-coverage` require O1 to be
implemented; they MUST be no-ops (with a warning) when O1 has not run.

#### Scenario: CRAPload threshold exceeded
- **GIVEN** `--max-crapload 5` and CRAPload is 8
- **WHEN** `gazepy crap` runs
- **THEN** exit code is non-zero

#### Scenario: Gaze threshold without O1
- **GIVEN** `--max-gaze-crapload 3` and O1 has not run
- **WHEN** `gazepy crap` runs
- **THEN** exit code is 0 and a warning is emitted noting GazeCRAP is unavailable

---

### Requirement: O6 Coverage Profile Reuse (Full)

Change 001 accepts `--coverage-json <path>` pointing to a `coverage.py` JSON
export. Full O6 also supports:

- `--coverprofile <path>` pointing to a `.coverage` binary file (runs
  `coverage json` internally if needed)
- Running `coverage run pytest` internally if neither flag is provided and
  a `pytest.ini` / `pyproject.toml` is found in the project root
- Caching coverage results to avoid re-running tests on unchanged code

The existing `--coverage-json` flag remains the primary interface. Full O6
adds convenience wrappers. No behavioral contracts apply.

---

### Requirement: O7 Configuration File (Full)

Change 001 loads `contractual_threshold`, `incidental_threshold`,
`crap_threshold`, `gaze_crap_threshold` from `.gaze.yaml`. Full O7 adds:

| Setting | Default | Requires |
|---|---|---|
| `classification.doc_scan.exclude` | vendor, node_modules, .git, testdata | O3 |
| `classification.doc_scan.timeout` | 30s | O3 |
| `output.max_recommended_actions` | 20 | none |
| `output.text_format` | full / compact / minimal | none |

---

### Requirement: Cyclomatic Complexity Algorithm

Change 001 does not specify which algorithm computes cyclomatic complexity —
it accepts complexity as an external value or leaves it implementation-defined.
A future change MUST specify:

- Which AST node types increment the complexity counter: `if`, `elif`,
  `for`, `while`, `except`, `with` (multiple context managers), `assert`,
  boolean operators (`and`/`or`) in conditions, comprehension `if` clauses
- Baseline complexity for a function with no branches: 1
- How nested functions are handled: outer function does NOT include inner
  function's branches (each function is measured independently)
- Whether to use an external library (e.g., `radon`, `mccabe`) or compute
  from AST directly
- At minimum one test that computes CRAP from a real Python function (not
  pre-supplied complexity numbers) to verify the algorithm

#### Scenario: Simple branching function
- **GIVEN** a function with one `if` and one `elif`
- **WHEN** complexity is computed
- **THEN** complexity is 3 (baseline 1 + 2 branches)

#### Scenario: Nested function excluded
- **GIVEN** an outer function with one `if`, containing an inner `def` with
  three `if` statements
- **WHEN** complexity of the outer function is computed
- **THEN** complexity is 2 (baseline 1 + 1 branch, inner def not counted)

---

### Requirement: PyPI Publication

The `gaze-py` package MUST be publishable to PyPI so that
`uv tool install gaze-py` works for end users. A future change MUST implement:

- GitHub Actions release workflow triggered on version tag (`v*.*.*`)
- `uv build` + `uv publish` with PyPI token from GitHub secrets
- Version bump process (update `__version__` in `src/gaze_py/__init__.py`)
- Confirmation that the `gaze-py` PyPI name is available and claimed before
  first publish (the existing `gaze` package on PyPI is unrelated; `gaze-py`
  as a name must be verified separately)

---

### Requirement: P3/P4 No-Equivalent Types (Revisit)

The following types currently have no-op detection. A future change MAY
implement detection if a suitable Python pattern is identified:

| Type | Tier | Current status | Possible future mapping |
|---|---|---|---|
| WaitGroupOp | P3 | No-op | `asyncio.gather()` / `asyncio.wait()` patterns? |
| AtomicOp | P3 | No-op | `threading.local()` mutations? Unlikely — GIL makes this moot |
| RecoverBehavior | P3 | No-op | `contextlib.suppress()` patterns? |
| UnsafeMutation | P4 | No-op | Already covered by CgoCall for ctypes |
| SyncPoolOp | P4 | No-op | No Python equivalent — close permanently |

Any implementation of these types MUST go through a new OpenSpec change and
include porting contract alignment review.
