# Design — Change 002: Deferred Capabilities

> Architectural notes and design decisions for each deferred item. This is a
> **reference design** only — not an implementation plan. Each item will be
> fully specified in its own future OpenSpec change before implementation begins.

---

## O1 — Quality Assessment

O1 is the most architecturally significant deferred item. It adds a new
subpackage `src/gaze/quality/` with four components:

```
src/gaze/quality/
├── __init__.py
├── pairing.py       # Test-target pairing (O1-A)
├── assertions.py    # Assertion detection (O1-B)
├── mapper.py        # Assertion → effect mapping (O1-C)
└── coverage.py      # Contract coverage computation (O1-D)
```

### Test-Target Pairing (O1-A)

The pairing heuristic has two passes, run in order:

**Pass 1 — Name-based**: For each test file `test_foo.py` or `foo_test.py`,
look for a sibling or parent module named `foo.py`. For each test class
`TestBar`, look for a function or class named `bar` or `_bar` in the
production module. For each test function `test_baz_*`, look for `baz` or
`_baz`. Confidence: HIGH.

**Pass 2 — Call-graph-based**: Walk each test function's AST and collect all
`ast.Call` nodes where the function name matches a known production function.
Use this to supplement or correct name-based pairing. Confidence: MEDIUM.

The output is a `PairMap: dict[str, list[str]]` mapping test function
qualified names to lists of production function qualified names. A test with
no match has an empty list. This is passed to the assertion mapper.

### Assertion Detection (O1-B)

A single `AssertionVisitor(ast.NodeVisitor)` walks each test function body and
collects `AssertionSite` objects (location, type, subject expression). The five
canonical assertion types map to Python patterns as follows:

| Type | Python patterns |
|---|---|
| `equality` | `assert a == b`, `assert a != b`, `assertEqual(a, b)` |
| `error_check` | `with pytest.raises(E):`, `assertRaises(E)` |
| `nil_check` | `assert x is None`, `assert x is not None`, `assertIsNone(x)` |
| `diff_check` | `assert a == {"key": val}` (dict/list literal RHS) |
| `custom` | `capsys.readouterr()`, `caplog.records`, `.assert_called*()` on mocks, `assert X in Y` (containment) |

### Assertion Mapping (O1-C)

Mapping is a multi-pass pipeline. Each pass tries to link an `AssertionSite`
to a `SideEffect`:

1. **Direct**: assertion subject is the variable holding the function's return value
2. **Root resolution**: trace `result = fn(args)` back through assignment chain
3. **Call matching**: assertion is directly on `fn(args)` inline
4. **Helper bridging**: assertion is in a helper function called from the test

Passes run in order; first successful match wins. An assertion with no match
is recorded as `unmapped_assertions` in the output (canonical OC-002 field).

### Contract Coverage (O1-D)

```python
def contract_coverage(effects: list[SideEffect], mappings: list[AssertionMapping]) -> float | None:
    contractual = [e for e in effects if e.classification.label == "contractual"]
    if not contractual:
        return None  # reason code set separately
    covered = {m.side_effect_id for m in mappings if m.side_effect_id in {e.id for e in contractual}}
    return len(covered) / len(contractual) * 100.0
```

---

## Cyclomatic Complexity Algorithm

The reference Go implementation computes complexity by counting:
- `if` / `else if` statements: +1 each
- `for` / `while` loops: +1 each
- `case` labels in `switch`: +1 each
- `&&` / `||` boolean operators: +1 each
- baseline per function: +1

Python equivalent:
- `ast.If`: +1 (each `elif` is a nested `ast.If`, so +1 each)
- `ast.For` / `ast.While`: +1 each
- `ast.ExceptHandler`: +1 each (each `except` clause)
- `BoolOp(op=And|Or)` in conditions: +1 per operator
- `ast.comprehension` with `if`: +1 per `if` clause
- baseline: 1

Nested `ast.FunctionDef` / `ast.AsyncFunctionDef` inside the function body
are NOT counted — each function is measured independently.

The recommended implementation is to compute from AST directly (no external
library dependency). `radon` would also work but adds a dependency.

---

## O2 — AI-Powered Reports

The adapter pattern for O2:

```python
class AIAdapter(Protocol):
    def report(self, system_prompt: str, payload: dict) -> str: ...

class ClaudeAdapter:
    def report(self, system_prompt: str, payload: dict) -> str:
        # subprocess call to `claude` CLI or API
        ...

class OpenCodeAdapter:
    def report(self, system_prompt: str, payload: dict) -> str:
        # uses opencode context
        ...
```

The CLI flag `--ai-report [claude|opencode|ollama]` selects the adapter. If
the binary is not found, fall back with a warning.

---

## O3 — Document Scanning

Walk the project root looking for markdown and text files (excluding paths in
`classification.doc_scan.exclude`). For each file, run the same keyword scan
as the docstring signal (Signal 5) but attribute the source as `"godoc"`. The
resulting signals are merged with per-function signals during classification.

Document scanning is a project-level operation, not a per-function operation.
The signals it produces are "project-level" signals applied to all functions
in the scanned project — not targeted at specific functions.

---

## O5 — CI Threshold Enforcement

> **Cross-spec note (cli-parity change)**: The cli-parity change removes CRAP
> scoring from `analyze` entirely. O5 threshold enforcement MUST target the
> `crap` command, NOT `analyze`. The design below is superseded — update any
> future O5 implementation to use `gazepy crap --max-crapload N` instead of
> `gazepy analyze --max-crapload N`.

Add threshold flags to the CLI `crap` command (NOT `analyze`):

```
gazepy crap <path> \
  --max-crapload 10 \
  --max-gaze-crapload 5
```

Exit codes:
- 0: all thresholds met (or thresholds not specified)
- 1: one or more thresholds violated
- 2: threshold specified requires O1 but O1 has not run (warning + exit 0)

---

## PyPI Release Workflow

```yaml
# .github/workflows/release.yml
on:
  push:
    tags: ["v*.*.*"]
jobs:
  release:
    steps:
      - uv build
      - uv publish --token ${{ secrets.PYPI_TOKEN }}
```

Version is `src/gaze/__init__.py:__version__`. Version bump is manual (no
automated tooling). Tag creation triggers the release.

---

## Dependency Map (what blocks what)

```
O1-A (pairing)
  └─→ O1-B (assertion detection)
        └─→ O1-C (assertion mapping)
              └─→ O1-D (contract coverage)
                    ├─→ O1-E (GazeCRAP, quadrant, fix_strategy, gaze_crapload, etc.)
                    ├─→ O1-F (effect_confidence_range)
                    ├─→ O2 (AI reports — benefits from contract_coverage data)
                    └─→ O5 (--min-contract-coverage flag)

O3 (document scanning) — feeds into R2 (classification, Signal 5)
  └─→ O7 full (doc_scan.exclude, doc_scan.timeout config keys)

Complexity algorithm — feeds into R3 (CRAP scoring)
  └─→ O5 (--max-crapload flag can only be meaningful with correct complexity)

PyPI publication — independent of all above
```
