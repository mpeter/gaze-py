# gaze-py

**Contract-aware test quality analysis for Python.**

Line coverage tells you which lines ran. It does not tell you whether your tests actually verified anything.

A function can have 90% line coverage and tests that assert on nothing contractually meaningful — type checks, logging calls, internal state — while leaving return values, error paths, and mutations completely unverified. That function is dangerous to change, and traditional coverage metrics will not warn you.

gaze-py fixes this by working from first principles:

1. **Detect** every observable side effect a function produces (return values, exceptions raised, attribute mutations, global mutations, I/O writes, etc.)
2. **Classify** each effect as *contractual* (part of the function's public obligation), *incidental* (an implementation detail), or *ambiguous*
3. **Measure** whether your tests actually assert on the contractual effects — and flag the ones they don't

This produces three actionable metrics: **Contract Coverage** (percentage of contractual effects asserted on), **Over-Specification Score** (assertions on implementation details), and **GazeCRAP** (a risk score combining cyclomatic complexity with contract coverage).

gaze-py is the Python companion to [gaze](https://github.com/unbound-force/gaze), the Go implementation. Both produce schema-compatible JSON output and share the same side-effect taxonomy. The `uf init` command from [unbound-force](https://github.com/unbound-force/unbound-force) automatically selects between them based on project language.

## Quick Start

```bash
# Install
pip install gaze-py
# or
uv tool install gaze-py

# Analyze side effects in your source
gaze-py analyze src/mypackage/ --format=text

# Full quality report (side effects + assertion mapping + GazeCRAP scores)
gaze-py report src/mypackage/ tests/ --format=json

# Map test assertions to side effects for one subpackage
gaze-py quality tests/ --format=text
```

## Commands

| Command | Description |
|---------|-------------|
| `gaze-py analyze <src>` | Detect side effects in Python functions |
| `gaze-py quality <tests>` | Map test assertions to detected side effects |
| `gaze-py report <src> <tests>` | Full pipeline: detect → map → GazeCRAP scores |
| `gaze-py crap <src>` | Compute CRAP scores (complexity × line coverage) |
| `gaze-py schema` | Print the JSON Schema for analysis output |

All commands support `--format=text` (default) and `--format=json`.

## Installation

```bash
# Recommended: uv tool install (isolated, always on PATH)
uv tool install gaze-py

# Or pip
pip install gaze-py

# Or from source
git clone https://github.com/mpeter/gaze-py
cd gaze-py
uv sync
uv run gaze-py --help
```

Requires Python 3.11+.

## How It Works

gaze-py uses Python's `ast` module to statically analyze function bodies. No execution required — analysis runs on source files directly.

**Side effect detection** (`analysis/`): `ast.NodeVisitor` walks each function body detecting `ast.Return`, `ast.Raise`, `ast.Global`+store, `ast.Attribute` mutations on `self`, mutating method calls on arguments, and I/O patterns (`print`, `sys.stderr.write`, `os.environ`, etc.).

**Assertion mapping** (`quality/`): Scans test files by inspecting what each test function *calls* (not by filename convention), then maps `assert` statements and `pytest.raises` contexts to the detected side effects of the called function.

**GazeCRAP scoring** (`crap/`): Substitutes contract coverage for line coverage in the CRAP formula: `CC² × (1 - contract_coverage)³ + CC`. A function with complexity 5 and 0% contract coverage scores 30. The same function fully covered scores 5.

## JSON Schema

gaze-py output is schema-compatible with [gaze](https://github.com/unbound-force/gaze) (Go). The analysis report schema:

```json
{
  "version": "0.1.0",
  "results": [
    {
      "target": { "package": "mymod.utils", "function": "parse", "location": "src/mymod/utils/__init__.py:12" },
      "side_effects": [
        { "id": "se-a1b2c3d4", "type": "ReturnValue", "tier": "P0", "location": "...", "description": "..." },
        { "id": "se-e5f6g7h8", "type": "ErrorReturn",  "tier": "P0", "location": "...", "description": "..." }
      ],
      "metadata": { "gaze_py_version": "0.1.0", "python_version": "3.12.3", "duration_ms": 14 }
    }
  ]
}
```

## Related

- [gaze](https://github.com/unbound-force/gaze) — the Go implementation, same concepts and schema
- [unbound-force](https://github.com/unbound-force/unbound-force) — the AI agent swarm that uses gaze-py as its Python quality gate

## License

Apache 2.0
