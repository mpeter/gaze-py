---
pack_id: python
language: Python
version: 2.0.0
---

# Convention Pack: Python

## Coding Style

- **CS-001** [MUST] Format all Python source files with `ruff format`. No manual formatting overrides.
- **CS-002** [MUST] Organize imports with `ruff` (isort-compatible) in three groups separated by blank lines: standard library, third-party packages, internal packages. All imports MUST be at module level. Inline imports (inside function bodies) are forbidden except to break a genuine circular import (document why at the import site), inside `if TYPE_CHECKING:` guards, or for conditional optional dependencies guarded by `try/except ImportError`. Enforced by ruff `PLC0415`.
- **CS-003** [MUST] Use `snake_case` for functions, methods, variables, and modules. Use `PascalCase` for classes. Use `UPPER_SNAKE_CASE` for module-level constants.
- **CS-004** [MUST] Add Google-style docstrings on all public functions, methods, classes, and modules. Docstrings MUST include a summary line, `Args:` section (all parameters), `Returns:` section, and `Raises:` section for any exceptions the caller must handle. Document parameter units and valid ranges when they are not obvious from the type (e.g., `coverage_pct: float — line coverage percentage in the range 0–100, not 0.0–1.0`).
- **CS-005** [MUST] Use type annotations on all function signatures (parameters and return types), public and private. Use `from __future__ import annotations` for forward references. Never use `# type: ignore` — if the type system cannot be satisfied, fix the annotation or use `typing.cast()` paired with a runtime `assert isinstance(...)` check.
- **CS-006** [MUST] Raise specific exception types with descriptive messages. Never use bare `raise` or catch bare `except:`. Prefer custom exception classes for domain errors. When raising inside an `except` block, always chain: `raise X from e` to preserve the original traceback, or `raise X from None` when the original exception is an irrelevant implementation detail. Enforced by ruff `B904`.
- **CS-007** [MUST] Avoid mutable module-level variables. No global mutable state. Prefer dependency injection and function parameters.
- **CS-008** [MUST] Use `click` for CLI command routing and option/argument parsing. Use `click.echo()` for all output — never `print()`. Route errors to stderr with `err=True`. Exit with `raise SystemExit(1)` for errors, not `sys.exit()`.
- **CS-009** [MUST] Use `rich` for terminal output formatting (tables, panels, progress bars). Do not use bare `print()` for user-facing output.
- **CS-010** [SHOULD] Keep functions focused on a single responsibility. Extract helper functions when a function exceeds ~50 lines.
- **CS-011** [SHOULD] Use `dataclasses` or `NamedTuple` for structured data types. Avoid plain dicts for domain objects.
- **CS-012** [SHOULD] Use `Enum` or `StrEnum` instead of raw string/int literals for domain values and classification labels.
- **CS-013** [MUST] Follow PEP 8 naming conventions. Prefix private/internal names with a single underscore.
- **CS-014** [MUST] Prefer explicit precondition checks (LBYL) over catching exceptions for control flow. Check conditions before acting — do not use exceptions to detect normal program states. `try/except` is appropriate at CLI/API error boundaries, for third-party API calls where the call is the authoritative test, and when adding context before re-raising. In all other cases, check first.

  ```python
  # CORRECT
  if key in mapping:
      value = mapping[key]
      process(value)

  # WRONG — exception as control flow
  try:
      value = mapping[key]
      process(value)
  except KeyError:
      pass
  ```

- **CS-015** [MUST] Never catch an exception and do nothing. At minimum, emit a `warnings.warn()` with `stacklevel=2` so the failure is diagnosable. Silent `except: pass` and silent `except Exception: pass` blocks are forbidden.

  ```python
  # WRONG
  try:
      optional_feature()
  except Exception:
      pass

  # CORRECT
  try:
      optional_feature()
  except Exception as e:
      warnings.warn(f"Optional feature failed: {e}", stacklevel=2)
  ```

- **CS-016** [MUST] Functions with four or more parameters beyond `self` MUST use `*` to enforce keyword-only arguments at the call site. This prevents silent argument transposition bugs and makes call sites self-documenting. Exceptions: Click callback parameters (Click injects by position) and `@abstractmethod` stubs in ABCs.

  ```python
  # CORRECT
  def fetch_data(
      url: str,
      *,
      timeout: float,
      retries: int,
      auth_token: str,
  ) -> Response: ...

  # WRONG — positional; caller cannot tell which arg is which
  def fetch_data(url: str, timeout: float, retries: int, auth_token: str) -> Response: ...
  ```

---

## Architectural Patterns

- **AP-001** [MUST] Use the `src/` layout: all package code lives under `src/<package>/`. Tests live under `tests/` at the project root. Configure `pythonpath = ["src"]` in `[tool.pytest.ini_options]` so tests can import the package without installation.
- **AP-002** [MUST] Implement core business logic as standalone functions or classes. CLI commands delegate to core modules — no business logic in the CLI layer.
- **AP-003** [MUST] Use `dataclasses` with JSON serialization for all domain types. Include `to_dict()` methods for JSON output. Use `@dataclass(frozen=True)` for value objects that should not be mutated after construction.
- **AP-004** [MUST] Use `importlib.resources` or `importlib.metadata` for bundling static assets. Do not rely on `__file__` paths at runtime.
- **AP-005** [SHOULD] Implement the file ownership model: classify files as tool-owned (auto-updated on re-run) or user-owned (never overwritten without `--force`).
- **AP-006** [MUST] Keep package boundaries clean. Each subpackage owns one layer of the domain. No subpackage may import from a subpackage at the same or higher level — imports flow in one direction: toward the domain core (taxonomy, exceptions), never sideways.
- **AP-007** [MUST] Use `abc.ABC` with `@abstractmethod` for interfaces where you own all implementations. Use `typing.Protocol` for structural typing against external libraries or minimal duck-typed interfaces you do not control. Decision rule: if you will write all the implementations, use ABC; if you are wrapping something you don't own, use Protocol.

  ```python
  # CORRECT — owned interface
  from abc import ABC, abstractmethod

  class Formatter(ABC):
      @abstractmethod
      def write(self, results: list[AnalysisResult], out: IO[str]) -> None:
          """Write results to out."""

  # CORRECT — external library facade
  from typing import Protocol

  class HttpClient(Protocol):
      def get(self, url: str) -> Response: ...
  ```

- **AP-008** [MUST] Domain exception classes MUST be defined in the package's taxonomy or exceptions module. No subpackage may define an exception that other subpackages need to import — that creates coupling in the wrong direction. Both importer and importee should depend on the shared exceptions module, not on each other.

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

- **TC-001** [MUST] Use `pytest` as the test framework. Do not use `unittest.TestCase` style tests or inherit from `unittest.TestCase`. Do not import from `unittest.mock` — use pytest's `monkeypatch` fixture instead.
- **TC-002** [MUST] Use `assert` statements directly. No custom assertion helper libraries.
- **TC-003** [MUST] Name test files `test_*.py` and test functions `test_*`. Use descriptive names that convey the scenario being tested (e.g., `test_formula_zero_coverage_returns_max_crap`).
- **TC-004** [MUST] Use `tmp_path` fixture for all tests that touch the filesystem. No shared mutable state between test cases.
- **TC-005** [MUST] Use `@pytest.mark.parametrize` for table-driven tests. Never use a `for` loop inside a test to exercise multiple inputs — a loop reports only one failure even when multiple cases fail, and the test name does not communicate which case failed.

  ```python
  # WRONG
  def test_tier_names() -> None:
      for name in ["P0", "P1", "P2"]:
          assert name in TIERS

  # CORRECT
  @pytest.mark.parametrize("name", ["P0", "P1", "P2"])
  def test_tier_name_present(name: str) -> None:
      assert name in TIERS
  ```

- **TC-006** [SHOULD] Use `@pytest.fixture` for shared setup. Prefer function-scoped fixtures to minimize coupling. Keep fixture chains shallow — a five-level fixture chain where the outermost fixture does not use the innermost's fields is a smell.
- **TC-007** [SHOULD] Name acceptance tests after spec success criteria (e.g., `test_sc001_comprehensive_detection`).
- **TC-008** [MUST] Assert specific expected values — not just truthiness, non-emptiness, or exit codes. Assert return values, dataclass fields, and JSON structure. For CLI tests, assert at least one property of the output content, not only the exit code.
- **TC-009** [MUST] Ensure tests do not depend on execution order. Each test MUST be independently runnable.
- **TC-010** [SHOULD] Use `pytest.mark.slow` to mark tests that spawn subprocesses or analyze entire projects. Skip them with `-m "not slow"` in fast CI.
- **TC-011** [SHOULD] Place test fixtures (sample source files for analysis) in `tests/testdata/` directories. Add `norecursedirs = ["tests/testdata"]` to `[tool.pytest.ini_options]` to prevent pytest from collecting fixture files as tests.
- **TC-012** [MUST] Test error paths and edge cases, not just happy paths. Every public function MUST have at least one failure-case test.
- **TC-013** [MUST] Do not test private (underscore-prefixed) functions directly unless the public API cannot exercise the scenario without prohibitive fixture complexity. If direct testing of a private function is justified, the test file MUST include a comment explaining why the public API is insufficient. Tests of private functions that duplicate public-API coverage MUST be removed.

---

## Documentation Requirements

- **DR-001** [MUST] Write docstrings on every public function, method, class, and module. Use Google-style docstring format with `Args:`, `Returns:`, and `Raises:` sections.
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
| `B` | CS-006 exception chaining (B904), general bugbear patterns |
| `PL` | CS-016 keyword-only args (PLR0913), CS-002 inline imports (PLC0415) |
| `TRY` | CS-014 LBYL boundary discipline (TRY300) |
| `EM` | CS-006 exception message hygiene (EM101, EM102) |
| `G` | CS-015 logging format correctness |

Suggested ignores for rules enforced by review convention rather than as hard
errors: `PLR0913` (too-many-arguments), `PLC0415` (import not at top-level),
`TRY003` (long exception messages), `EM101`/`EM102` (string literals in raise).

---

## Custom Rules

<!-- This section is intentionally empty in the canonical pack. Project-specific custom rules belong in python-custom.md -->
