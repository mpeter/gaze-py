---
pack_id: python
language: Python
version: 1.0.0
---

# Convention Pack: Python

## Coding Style

- **CS-001** [MUST] Format all Python source files with `ruff format`. No manual formatting overrides.
- **CS-002** [MUST] Organize imports with `ruff` (isort-compatible) in three groups separated by blank lines: standard library, third-party packages, internal packages.
- **CS-003** [MUST] Use `snake_case` for functions, methods, variables, and modules. Use `PascalCase` for classes. Use `UPPER_SNAKE_CASE` for module-level constants.
- **CS-004** [MUST] Add docstrings on all public functions, methods, classes, and modules. Docstrings MUST describe purpose, parameters, return values, and notable exceptions.
- **CS-005** [MUST] Use type annotations on all public function signatures (parameters and return types). Use `from __future__ import annotations` for forward references.
- **CS-006** [MUST] Raise specific exception types with descriptive messages. Never use bare `raise` or catch bare `except:`. Prefer custom exception classes for domain errors.
- **CS-007** [MUST] Avoid mutable module-level variables. No global mutable state. Prefer dependency injection and function parameters.
- **CS-008** [MUST] Use `click` for CLI command routing and option/argument parsing.
- **CS-009** [MUST] Use `rich` for terminal output formatting (tables, panels, progress bars). Do not use bare `print()` for user-facing output.
- **CS-010** [SHOULD] Keep functions focused on a single responsibility. Extract helper functions when a function exceeds ~50 lines.
- **CS-011** [SHOULD] Use `dataclasses` or `NamedTuple` for structured data types. Avoid plain dicts for domain objects.
- **CS-012** [SHOULD] Use `Enum` or `StrEnum` instead of raw string/int literals for domain values and classification labels.
- **CS-013** [MUST] Follow PEP 8 naming conventions. Prefix private/internal names with a single underscore.

## Architectural Patterns

- **AP-001** [MUST] Use the `src/` layout: all package code lives under `src/gaze_py/`. Tests live under `tests/` at the project root.
- **AP-002** [MUST] Implement core business logic as standalone functions or classes. CLI commands delegate to core modules — no business logic in the CLI layer.
- **AP-003** [MUST] Use `dataclasses` with JSON serialization for all domain types (side effects, analysis results, CRAP scores). Include `to_dict()` methods for JSON output.
- **AP-004** [MUST] Use `importlib.resources` or `importlib.metadata` for bundling static assets. Do not rely on `__file__` paths at runtime.
- **AP-005** [SHOULD] Implement the file ownership model: classify files as tool-owned (auto-updated on re-run) or user-owned (never overwritten without `--force`).
- **AP-006** [MUST] Keep package boundaries clean. CLI code lives in `src/gaze_py/cli/`. Core analysis lives in `src/gaze_py/analysis/`. Domain types live in `src/gaze_py/taxonomy/`.
- **AP-007** [SHOULD] Use Protocol classes (from `typing`) for dependency injection boundaries rather than abstract base classes, enabling structural subtyping.

## Security Checks

- **SC-001** [MUST] Never hardcode secrets, API keys, tokens, or credentials in source code or bundled assets.
- **SC-002** [MUST] Never commit `.env` files, credential JSON files, or private keys to the repository.
- **SC-003** [MUST] Use `pathlib.Path` for all filesystem path construction. Never concatenate paths with string operations or `os.path.join` with unsanitized input.
- **SC-004** [MUST] Validate target directories before writing files. Ensure the path is within the expected root and does not escape via `..` traversal. Use `Path.resolve()` to canonicalize.
- **SC-005** [MUST] Set safe file permissions when creating files: `0o644` for regular files, `0o755` for executable scripts and directories.
- **SC-006** [SHOULD] Pin dependency versions in `pyproject.toml` or `uv.lock`. Audit dependencies for known vulnerabilities periodically.

## Testing Conventions

- **TC-001** [MUST] Use `pytest` as the test framework. Do not use `unittest.TestCase` style tests.
- **TC-002** [MUST] Use `pytest` assertions (`assert x == y`) directly. No custom assertion helper libraries.
- **TC-003** [MUST] Name test files `test_*.py` and test functions `test_*`. Use descriptive names that convey the scenario (e.g., `test_formula_zero_coverage_returns_max_crap`).
- **TC-004** [MUST] Use `tmp_path` fixture for all tests that touch the filesystem. No shared mutable state between test cases.
- **TC-005** [MUST] Use `pytest.mark.parametrize` for table-driven tests when exercising multiple input/output combinations.
- **TC-006** [SHOULD] Use fixtures (`@pytest.fixture`) for shared setup. Prefer function-scoped fixtures to minimize test coupling.
- **TC-007** [SHOULD] Name acceptance tests after spec success criteria (e.g., `test_sc001_comprehensive_detection`).
- **TC-008** [MUST] Verify specific expected values in assertions — not just truthiness or length checks. Assert return values, dataclass fields, and collection contents.
- **TC-009** [MUST] Ensure tests do not depend on execution order. Each test MUST be independently runnable.
- **TC-010** [SHOULD] Use `pytest.mark.slow` to mark tests that spawn subprocesses or analyze entire projects. Skip them with `-m "not slow"` in fast CI.
- **TC-011** [SHOULD] Place test fixtures (sample Python packages for analysis) in `tests/testdata/` directories.
- **TC-012** [MUST] Test error paths and edge cases, not just happy paths. Every public function MUST have at least one failure-case test.

## Documentation Requirements

- **DR-001** [MUST] Write docstrings on every public function, method, class, and module. Use Google-style docstring format.
- **DR-002** [MUST] Use RFC 2119 language (MUST, SHOULD, MAY, MUST NOT) for all requirement statements in specifications and governance documents.
- **DR-003** [SHOULD] Write acceptance criteria in Given/When/Then format with specific, verifiable outcomes.
- **DR-004** [SHOULD] Number functional requirements as FR-NNN and success criteria as SC-NNN in specification artifacts.
- **DR-005** [MUST] Use Conventional Commits format for all commit messages: `type: description` (e.g., `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).

## Custom Rules

<!-- This section is intentionally empty in the canonical pack. Project-specific custom rules belong in python-custom.md -->
