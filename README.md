# gaze-py

Python-native GazeCRAP analysis engine — the Python companion to [gaze](https://github.com/unbound-force/gaze).

Part of the [Unbound Force](https://unboundforce.dev/) project.

## Overview

`gaze-py` provides contract-aware test quality analysis for Python codebases. It detects observable side effects in functions, classifies them as contractual or incidental, and computes GazeCRAP scores that measure both complexity and meaningful test coverage.

The `gaze-dispatch` shim (installed by `uf init`) automatically selects between the Go gaze and gaze-py based on the project's primary language.

## Quick Start

```bash
uv sync
uv run gaze-py analyze [module]
```

## Status

🚧 Early development — scaffolded, core types and CRAP formula implemented.

## License

Apache 2.0
