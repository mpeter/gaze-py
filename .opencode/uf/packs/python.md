---
pack_id: python
language: Python
version: 3.0.0
---
<!-- scaffolded by uf vdev -->

# Convention Pack: Python

## Coding Style

- **CS-001** [MUST] Format all Python source files with `ruff format`. No manual formatting overrides.
- **CS-002** [MUST] Organize imports with `ruff` (isort-compatible) in three groups separated by blank lines: standard library, third-party packages, internal packages. All imports MUST be at module level. Inline imports are forbidden except inside `if TYPE_CHECKING:` guards, to break a genuine circular import (document why), or for conditional optional dependencies guarded by `try/except ImportError`. Enforced by ruff `PLC0415`.
- **CS-003** [MUST] Use `snake_case` for functions, methods, variables, and modules. Use `PascalCase` for classes. Use `UPPER_SNAKE_CASE` for module-level constants.
- **CS-004** [MUST] Add Google-style docstrings on all public functions, methods, classes, and modules. Docstrings MUST include a summary line, `Args:`, `Returns:`, and `Raises:` sections.
- **CS-005** [MUST] Use type annotations on all function signatures (parameters and return types), public and private. Use `from __future__ import annotations` for forward references. Never use `# type: ignore` — fix the annotation or use `typing.cast()` paired with a runtime `assert isinstance(...)` check.
- **CS-006** [MUST] Raise specific exception types with descriptive messages. Never use bare `raise` or catch bare `except:`. When raising inside an `except` block, always chain: `raise X from e` to preserve the traceback, or `raise X from None` when the original is an irrelevant implementation detail. Enforced by ruff `B904`.
- **CS-007** [MUST] Avoid mutable module-level variables. No global mutable state. Prefer dependency injection and function parameters.
- **CS-008** [MUST] Use `None` as default for optional arguments and initialize inside the function body. The mutable-default prohibition is carried by CS-023.
- **CS-009** [MUST] Use `click` for CLI command routing and option/argument parsing. Use `click.echo()` for all output — never `print()`. Route errors to stderr with `err=True`. Exit with `raise SystemExit(1)` for errors, not `sys.exit()`.
- **CS-010** [MUST] Use `rich` for terminal output formatting (tables, panels, progress bars). Do not use bare `print()` for user-facing output.
- **CS-011** [SHOULD] Keep functions focused on a single responsibility. Extract helper functions when a function exceeds ~50 lines.
- **CS-012** [SHOULD] Use `dataclasses` or `NamedTuple` for structured data types. Avoid plain dicts for domain objects.
- **CS-013** [SHOULD] Use `Enum` or `StrEnum` instead of raw string/int literals for domain values and classification labels.
- **CS-014** [MUST] Follow PEP 8 naming conventions. Prefix private/internal names with a single underscore.
- **CS-015** [SHOULD] Prefer explicit precondition checks (LBYL) for local attribute and type checks where the precondition is cheap and non-racy. EAFP is appropriate at I/O and third-party API call boundaries, or when the operation itself is the authoritative test.
- **CS-016** [MUST] Never catch an exception and do nothing. At minimum, emit `warnings.warn()` with `stacklevel=2`. Silent `except: pass` and silent `except Exception: pass` blocks are forbidden.
- **CS-017** [MUST] Functions with four or more parameters beyond `self` MUST use `*` to enforce keyword-only arguments at the call site. Exceptions: Click callback parameters and `@abstractmethod` stubs in ABCs.
- **CS-018** [MUST] Magic methods (`__len__`, `__bool__`, `__contains__`) and `@property` accessors MUST be O(1). Never iterate, perform I/O, or compute in them.
- **CS-019** [SHOULD] Declare variables at the site of use. Avoid early declarations used 10 or more lines later. If a value is used only once, inline it at the call site.
- **CS-020** [SHOULD] Do not destructure objects into single-use locals. Access fields directly at the call site unless the name meaningfully aids readability.
- **CS-021** [MUST] Maximum indentation depth is 4 levels. Extract helper functions when exceeded.
- **CS-022** [MUST] Always specify `encoding=` when reading or writing text files. Never rely on the platform default. Enforced by ruff `PLW1514`.
- **CS-023** [MUST] Never use mutable objects (`list`, `dict`, `set`) as default parameter values. Use `None` and initialize inside the function body. Immutable `None` defaults are acceptable. Enforced by ruff `B006`.
- **CS-024** [MUST] Re-exports from `__init__.py` MUST be explicit: `from .module import Thing as Thing`. Implicit re-exports are forbidden. Enforced by mypy `--no-implicit-reexport`.
- **CS-025** [MUST] Never emit placeholder strings in output consumed by users or tooling. Fields that cannot be populated MUST be `None`/`null` — not `"unknown"`, `"n/a"`, or `0`.
- **CS-026** [MUST] Keep context manager expressions inline in `with` statements. Do not extract them to intermediate variables — the `__enter__`/`__exit__` lifecycle must be visible at a glance.

---

## Architectural Patterns

- **AP-001** [MUST] Use the `src/` layout: all package code lives under `src/<package>/`. Tests live under `tests/` at the project root. Configure `pythonpath = ["src"]` in `[tool.pytest.ini_options]`.
- **AP-002** [MUST] Implement core business logic as standalone functions or classes. CLI commands delegate to core modules — no business logic in the CLI layer.
- **AP-003** [MUST] Use `dataclasses` with JSON serialization for all domain types. Include `to_dict()` methods for JSON output. Use `@dataclass(frozen=True)` for value objects.
- **AP-004** [MUST] Use `importlib.resources` or `importlib.metadata` for bundling static assets. Do not rely on `__file__` paths at runtime.
- **AP-005** [SHOULD] Implement the file ownership model: classify files as tool-owned (auto-updated on re-run) or user-owned (never overwritten without `--force`).
- **AP-006** [MUST] Keep package boundaries clean. Imports flow in one direction: toward the domain core (taxonomy, exceptions), never sideways between subpackages at the same or higher level.
- **AP-007** [MUST] Use `abc.ABC` with `@abstractmethod` for interfaces where you own all implementations. Use `typing.Protocol` for structural typing against external libraries or duck-typed interfaces you do not control.
- **AP-008** [MUST] Domain exception classes MUST be defined in the package's taxonomy or exceptions module. No subpackage may define an exception that other subpackages import — both should depend on the shared exceptions module.
- **AP-009** [MUST] Avoid computation and I/O at module level. Module-level code runs at import time — defer with `@cache`-decorated functions. Primitive constants and `frozenset` literals are acceptable at module level.
- **AP-010** [MUST] Use `pyproject.toml` as the project configuration file. Do not use `setup.py`, `setup.cfg`, or `requirements.txt` as the primary project definition.

---

## Security Checks

- **SC-001** [MUST] Never hardcode secrets, API keys, tokens, or credentials in source code or bundled assets.
- **SC-002** [MUST] Never commit `.env` files, credential JSON files, or private keys to the repository.
- **SC-003** [MUST] Use `pathlib.Path` for all filesystem path construction. Never concatenate paths with string operations or `os.path.join` with unsanitized input.
- **SC-004** [MUST] Validate target directories before writing files. Ensure the path is within the expected root and does not escape via `..` traversal. Use `Path.resolve()` to canonicalize before comparison.
- **SC-005** [MUST] Set safe file permissions when creating files: `0o644` for regular files, `0o755` for executable scripts and directories.
- **SC-006** [SHOULD] Pin dependency versions in `pyproject.toml` or `uv.lock`. Audit dependencies for known vulnerabilities periodically.

---

## Testing Conventions

- **TC-001** [MUST] Use `pytest` as the test framework. Do not use `unittest.TestCase` style tests. Use `monkeypatch` for simple value/attribute substitution. Use `pytest-mock` or `unittest.mock` for complex mock behavior requiring call tracking, `side_effect`, or `return_value` configuration.
- **TC-002** [MUST] Use `assert` statements directly. No custom assertion helper libraries.
- **TC-003** [MUST] Name test files `test_*.py` and test functions `test_*`. Use descriptive names that convey the scenario being tested.
- **TC-004** [MUST] Use `tmp_path` fixture for all tests that touch the filesystem. No shared mutable state between test cases.
- **TC-005** [MUST] Use `@pytest.mark.parametrize` for table-driven tests. Never use a `for` loop inside a test to exercise multiple inputs — a loop reports only one failure and the test name does not communicate which case failed.
- **TC-006** [SHOULD] Use `@pytest.fixture` for shared setup. Prefer function-scoped fixtures to minimize coupling.
- **TC-007** [SHOULD] Name acceptance tests after spec success criteria (e.g., `test_sc001_comprehensive_detection`).
- **TC-008** [MUST] Assert specific expected values — not just truthiness, non-emptiness, or exit codes. Assert return values, dataclass fields, and JSON structure.
- **TC-009** [MUST] Ensure tests do not depend on execution order. Each test MUST be independently runnable.
- **TC-010** [SHOULD] Use `pytest.mark.slow` to mark tests that spawn subprocesses or analyze entire projects.
- **TC-011** [SHOULD] Place test fixtures in `tests/testdata/` directories. Add `norecursedirs = ["tests/testdata"]` to `[tool.pytest.ini_options]` to prevent pytest from collecting them as tests.
- **TC-012** [MUST] Test error paths and edge cases, not just happy paths. Every public function MUST have at least one failure-case test.
- **TC-013** [MUST] Do not test private (underscore-prefixed) functions directly unless the public API cannot exercise the scenario without prohibitive fixture complexity. If justified, include a comment explaining why the public API is insufficient.
- **TC-014** [MUST] Do not add parameters to test fakes or fixtures that are not exercised by actual production code paths. Speculative infrastructure ("might be useful later") is dead code.

---

## Type Annotations

- **TA-001** [MUST] Run a type checker (`mypy` or `pyright`) in CI. Address type errors — do not disable the type checker globally.
- **TA-002** [MUST] Use built-in generics for Python 3.10+: `list[str]`, `dict[str, int]`, `X | None`. Do not use `typing.Optional`, `typing.Union`, `typing.List`, or `typing.Dict` in new code.
- **TA-003** [MUST] Use `abc.ABC` for owned interfaces and `typing.Protocol` for structural typing against external code. See AP-007.
- **TA-004** [MUST] Use `Literal` types for strings or integers compared with `==` or `in` against a fixed set of valid values. Bare `str` allows typos caught only at runtime.
- **TA-005** [MUST] Add a runtime `isinstance()` assertion before every `typing.cast()` call, unless the type was just narrowed by an explicit type guard. `typing.cast()` is compile-time only and provides no runtime safety without the assertion.

---

## Documentation Requirements

- **DR-001** [MUST] Write docstrings on every public function, method, class, and module. Use Google-style format with `Args:`, `Returns:`, and `Raises:` sections.
- **DR-002** [MUST] Use RFC 2119 language (MUST, SHOULD, MAY, MUST NOT) for all requirement statements in specifications and governance documents.
- **DR-003** [SHOULD] Write acceptance criteria in Given/When/Then format with specific, verifiable outcomes.
- **DR-004** [SHOULD] Number functional requirements as FR-NNN and success criteria as SC-NNN in specification artifacts.
- **DR-005** [MUST] Use Conventional Commits format for all commit messages: `type: description` (e.g., `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).

---

## Ruff Rule Groups

The following ruff rule groups enforce the conventions above. Include them in
`[tool.ruff.lint] select` for any project using this pack:

| Group | Rules enforced |
|-------|---------------|
| `B` | CS-006 exception chaining (B904), CS-023 mutable defaults (B006) |
| `PL` | CS-017 keyword-only args (PLR0913), CS-002 inline imports (PLC0415) |
| `TRY` | CS-015 LBYL boundary discipline (TRY300) |
| `EM` | CS-006 exception message hygiene (EM101, EM102) |
| `G` | CS-016 logging format correctness |
| `W` | CS-022 encoding= on file I/O (PLW1514) |

Suggested ignores: `PLR0913` (too-many-arguments), `PLC0415` (import not at top-level),
`TRY003` (long exception messages), `EM101`/`EM102` (string literals in raise).

---

## Custom Rules

<!-- This section is intentionally empty in the canonical pack. Project-specific custom rules belong in python-custom.md -->
