# gaze-py Development Guidelines

Auto-generated from active feature plans. Last updated: [DATE]

## Active Feature

[FEATURE NAME AND LINK TO PLAN]

## Active Technologies

- **Language**: Python 3.11+
- **Package manager**: uv
- **CLI framework**: Click
- **Output formatting**: click.echo() — no Rich (CR-006)
- **Analysis**: Python `ast` module (AST-only, no execution)
- **Testing**: pytest + pytest-cov
- **Linting**: ruff
- **Type checking**: mypy --strict

## Project Structure

```text
src/gaze_py/
├── taxonomy/     # Domain types — SideEffect, FunctionTarget, etc.
├── analysis/     # AST side-effect detection engine
├── quality/      # Assertion mapper and contract coverage
├── crap/         # CRAP and GazeCRAP scoring formulas
├── classify/     # Classification engine (ABC interface)
├── config/       # .gaze.yaml configuration loading
├── report/       # JSON and text formatters, JSON schemas
└── cli/          # Click command group (gazepy entrypoint)

tests/
├── test_*.py         # Real pytest tests
└── testdata/         # Static AST analysis fixtures (never collected by pytest)
```

## Commands

```bash
uv run pytest -m "not slow"                          # Fast test run
uv run ruff check . && uv run mypy --strict src/     # Lint + typecheck
uv run pytest --cov=gaze_py --cov-fail-under=85      # Full CI gate
uv run gazepy --help                                 # CLI entry point
```

## Code Style

- All imports at module level (CR-004)
- LBYL over EAFP — check conditions before acting (CS-014)
- No `# type: ignore` — fix the type or use `cast()` with assert (CS-005)
- Keyword-only args for functions with 4+ params (CS-016)
- Exception chaining always — `raise X from e` or `from None` (CS-006)
- ABCs for owned interfaces, Protocol for external facades (AP-007)
- Domain exceptions in `taxonomy/` only (AP-008)
- No placeholder output — unavailable fields are `None`, not `"unknown"` (CR-003)

## Recent Changes

[LAST 3 FEATURES AND WHAT THEY ADDED]

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
