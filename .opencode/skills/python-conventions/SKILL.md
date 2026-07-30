---
name: python-conventions
description: >
  Non-negotiable coding, architecture, testing, type-annotation, and gaze-visibility
  rules for gaze-py Python source, folding the default and python convention packs
  (default.md, python.md, python-custom.md) into one load. Use whenever creating,
  editing, or reviewing any .py file under src/gaze_py/ or tests/, before writing a
  spec that touches Python code, or when checking whether a change follows a CS/AP/
  SC/TC/TA/DR/CR pack rule.
tags: [always-on, python, conventions, quality]
---

# Python Conventions (gaze-py)

Folds `.opencode/uf/packs/default.md`, `python.md`, and `python-custom.md` into a
single artifact-triggered load. Load this skill instead of reading the three pack
files separately — content below is copied verbatim from each, labeled by source.

**Precedence**: `python.md` and `python-custom.md` take precedence over `default.md`
on any overlapping rule ID (e.g. `CS-001` means different things in each pack — the
Python-specific text wins). `default.md` supplies language-agnostic architectural
principles not restated in `python.md` (dependency injection, interface segregation,
etc.) — those still apply.

**Not folded here** (different audience, load separately if relevant):
`severity.md` — Divisor Council review-persona severity taxonomy, not for authoring
code. `content.md` / `content-custom.md` — writing standards for content agents
(Scribe/Herald/Envoy: docs, blog, PR/comms), not for source code.

---

## Source: `python.md` (canonical for Python — apply first)

### Coding Style

- **CS-001** [MUST] Format all Python source files with `ruff format`. No manual formatting overrides.
- **CS-002** [MUST] Organize imports with `ruff` (isort-compatible) in three groups separated by blank lines: standard library, third-party packages, internal packages. All imports MUST be at module level. Inline imports are forbidden except inside `if TYPE_CHECKING:` guards, to break a genuine circular import (document why), or for conditional optional dependencies guarded by `try/except ImportError`. Enforced by ruff `PLC0415`.
- **CS-003** [MUST] Use `snake_case` for functions, methods, variables, and modules. Use `PascalCase` for classes. Use `UPPER_SNAKE_CASE` for module-level constants.
- **CS-004** [MUST] Add Google-style docstrings on all public functions, methods, classes, and modules. Docstrings MUST include a summary line, `Args:`, `Returns:`, and `Raises:` sections.
- **CS-005** [MUST] Use type annotations on all function signatures (parameters and return types), public and private. Use `from __future__ import annotations` for forward references. Never use `# type: ignore` — fix the annotation or use `typing.cast()` paired with a runtime `assert isinstance(...)` check.
- **CS-006** [MUST] Raise specific exception types with descriptive messages. Never use bare `raise` or catch bare `except:`. When raising inside an `except` block, always chain: `raise X from e` to preserve the traceback, or `raise X from None` when the original is an irrelevant implementation detail. Enforced by ruff `B904`.
- **CS-007** [MUST] Avoid mutable module-level variables. No global mutable state. Prefer dependency injection and function parameters.
- **CS-008** [MUST] Use `None` as default for optional arguments and initialize inside the function body. The mutable-default prohibition is carried by CS-023.
- **CS-009** [MUST] Use `click` for CLI command routing and option/argument parsing. Use `click.echo()` for all output — never `print()`. Route errors to stderr with `err=True`. Exit with `raise SystemExit(1)` for errors, not `sys.exit()`.
- **CS-010** [MUST] Use `rich` for terminal output formatting (tables, panels, progress bars). Do not use bare `print()` for user-facing output. **gaze-py exception**: see CR-006 below — `report/text_formatter.py` uses plain string formatting, not `rich`.
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
- **CS-024** [MUST] Re-exports from `__init__.py` MUST be explicit: `from .module import Thing as Thing`. Implicit re-exports are forbidden. Enforced by mypy `--no-implicit-reexport`. **gaze-py tightens this further**: see CR-001 below — no re-exports at all.
- **CS-025** [MUST] Never emit placeholder strings in output consumed by users or tooling. Fields that cannot be populated MUST be `None`/`null` — not `"unknown"`, `"n/a"`, or `0`.
- **CS-026** [MUST] Keep context manager expressions inline in `with` statements. Do not extract them to intermediate variables — the `__enter__`/`__exit__` lifecycle must be visible at a glance.

### Architectural Patterns

- **AP-001** [MUST] Use the `src/` layout: all package code lives under `src/<package>/`. Tests live under `tests/` at the project root. Configure `pythonpath = ["src"]` in `[tool.pytest.ini_options]`.
- **AP-002** [MUST] Implement core business logic as standalone functions or classes. CLI commands delegate to core modules — no business logic in the CLI layer.
- **AP-003** [MUST] Use `dataclasses` with JSON serialization for all domain types. Include `to_dict()` methods for JSON output. Use `@dataclass(frozen=True)` for value objects. **gaze-py deviation**: see CR-005 below — uses `dataclasses.asdict()` + `_json_default`, not per-class `to_dict()`.
- **AP-004** [MUST] Use `importlib.resources` or `importlib.metadata` for bundling static assets. Do not rely on `__file__` paths at runtime.
- **AP-005** [SHOULD] Implement the file ownership model: classify files as tool-owned (auto-updated on re-run) or user-owned (never overwritten without `--force`).
- **AP-006** [MUST] Keep package boundaries clean. Imports flow in one direction: toward the domain core (taxonomy, exceptions), never sideways between subpackages at the same or higher level.
- **AP-007** [MUST] Use `abc.ABC` with `@abstractmethod` for interfaces where you own all implementations. Use `typing.Protocol` for structural typing against external libraries or duck-typed interfaces you do not control.
- **AP-008** [MUST] Domain exception classes MUST be defined in the package's taxonomy or exceptions module. No subpackage may define an exception that other subpackages import — both should depend on the shared exceptions module.
- **AP-009** [MUST] Avoid computation and I/O at module level. Module-level code runs at import time — defer with `@cache`-decorated functions. Primitive constants and `frozenset` literals are acceptable at module level.
- **AP-010** [MUST] Use `pyproject.toml` as the project configuration file. Do not use `setup.py`, `setup.cfg`, or `requirements.txt` as the primary project definition.

### Security Checks

- **SC-001** [MUST] Never hardcode secrets, API keys, tokens, or credentials in source code or bundled assets.
- **SC-002** [MUST] Never commit `.env` files, credential JSON files, or private keys to the repository.
- **SC-003** [MUST] Use `pathlib.Path` for all filesystem path construction. Never concatenate paths with string operations or `os.path.join` with unsanitized input.
- **SC-004** [MUST] Validate target directories before writing files. Ensure the path is within the expected root and does not escape via `..` traversal. Use `Path.resolve()` to canonicalize before comparison.
- **SC-005** [MUST] Set safe file permissions when creating files: `0o644` for regular files, `0o755` for executable scripts and directories.
- **SC-006** [SHOULD] Pin dependency versions in `pyproject.toml` or `uv.lock`. Audit dependencies for known vulnerabilities periodically.

### Testing Conventions

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
- **TC-013** [MUST] Do not test private (underscore-prefixed) functions directly unless the public API cannot exercise the scenario without prohibitive fixture complexity. If justified, include a comment explaining why. **gaze-py**: see CR-004 below for the exact comment requirement.
- **TC-014** [MUST] Do not add parameters to test fakes or fixtures that are not exercised by actual production code paths. Speculative infrastructure ("might be useful later") is dead code.

### Type Annotations

- **TA-001** [MUST] Run a type checker (`mypy` or `pyright`) in CI. Address type errors — do not disable the type checker globally.
- **TA-002** [MUST] Use built-in generics for Python 3.10+: `list[str]`, `dict[str, int]`, `X | None`. Do not use `typing.Optional`, `typing.Union`, `typing.List`, or `typing.Dict` in new code.
- **TA-003** [MUST] Use `abc.ABC` for owned interfaces and `typing.Protocol` for structural typing against external code. See AP-007.
- **TA-004** [MUST] Use `Literal` types for strings or integers compared with `==` or `in` against a fixed set of valid values. Bare `str` allows typos caught only at runtime.
- **TA-005** [MUST] Add a runtime `isinstance()` assertion before every `typing.cast()` call, unless the type was just narrowed by an explicit type guard. `typing.cast()` is compile-time only and provides no runtime safety without the assertion.

### Documentation Requirements

- **DR-001** [MUST] Write docstrings on every public function, method, class, and module. Use Google-style format with `Args:`, `Returns:`, and `Raises:` sections.
- **DR-002** [MUST] Use RFC 2119 language (MUST, SHOULD, MAY, MUST NOT) for all requirement statements in specifications and governance documents.
- **DR-003** [SHOULD] Write acceptance criteria in Given/When/Then format with specific, verifiable outcomes.
- **DR-004** [SHOULD] Number functional requirements as FR-NNN and success criteria as SC-NNN in specification artifacts.
- **DR-005** [MUST] Use Conventional Commits format for all commit messages: `type: description` (e.g., `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).

### Ruff Rule Groups

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

## Source: `python-custom.md` (gaze-py-specific — extends `python.md`)

CR-001 through CR-006 replace/extend the corresponding items above. Rules originally
proposed here that turned out to be universal (LBYL, no `type: ignore`, keyword-only
args, no inline imports, exception chaining, no silent swallowing, parametrize over
loops, monkeypatch) were promoted into `python.md` above (CS-005/006/015-017,
TC-001/005) and are not repeated.

### CR-001: No Re-Exports from `__init__.py`

[MUST] Every symbol has exactly one canonical import path. Do not re-export
symbols from `__init__.py` to create a shorter import alias.

`__init__.py` files MUST contain only:
- `__version__` (package root only)
- A module-level docstring
- Nothing else

```python
# WRONG — src/gaze/__init__.py
from gaze.taxonomy import SideEffect  # creates a second import path
__all__ = ["SideEffect"]

# CORRECT — callers import from the canonical location
from gaze.taxonomy import SideEffect
```

This makes the dependency graph explicit and prevents hidden coupling between
subpackages. It also ensures that `import gaze` does not transitively import the
entire package.

### CR-002: Testdata Fixtures Are Not Tests

[MUST] Files under `tests/testdata/` are static source fixtures for the analysis
engine to parse. They MUST NOT:

- Import from `tests.*` or any other package path
- Have `__init__.py` files (testdata directories are not packages)
- Contain real test logic that pytest should collect and run
- Be collected by pytest

`pyproject.toml` MUST include `norecursedirs = ["tests/testdata"]`.

If a fixture file must reference a name that is defined elsewhere, it MUST NOT use
an import statement. Add `# ruff: noqa: F821` as a file-level comment to suppress
undefined-name warnings on intentional bare call sites, and add a comment explaining
the file is parsed as AST and never executed.

```python
# CORRECT — tests/testdata/quality/test_basic.py
# ruff: noqa: F821
# Parsed as AST by the quality engine. Never executed.

def test_compute() -> None:
    result = compute(1, 2)  # bare call — engine detects by name
    assert result == 3
```

### CR-003: No Placeholder Values in Production Output

[MUST] Never emit hardcoded placeholder strings in output that users or downstream
tooling will consume. If a field cannot be populated, emit `None` / `null` in JSON —
not strings like `"test.py:?"`, `"<unknown>"`, or `"n/a"`.

Per porting contract OC-003, fields that depend on optional capabilities MUST be
null/absent when the capability has not run — not zero-valued. This allows consumers
to distinguish "not computed" from "computed as zero."

```python
# WRONG — appears verbatim in JSON, indistinguishable from real data
location = "test.py:?"
gaze_crap: float = 0.0

# CORRECT
location: str | None = None     # serialises as null
gaze_crap: float | None = None  # serialises as null
```

If a field is conditionally unavailable, the domain type MUST reflect that with
`field_name: T | None` and the JSON schema MUST mark it nullable.

### CR-004: Test Private Functions Only Through Their Public Contract

[MUST] Do not import and test underscore-prefixed private functions directly unless
the public API cannot exercise the scenario without prohibitive fixture complexity.
If direct testing of a private function is justified, the test MUST include a
comment explaining why:

```python
# Testing _iter_test_functions directly because map_assertions() requires
# a real filesystem path and an AnalysisResult; constructing both for a
# two-line class-method scenario would obscure what is being tested.
from gaze.quality import _iter_test_functions
```

Without this comment, the test will be rejected in review. Private function tests
that duplicate coverage already provided by public-API tests MUST be deleted.

### CR-005: JSON Serialization via `dataclasses.asdict()` (AP-003 Deviation)

[MUST] This project uses `dataclasses.asdict()` + a custom `_json_default` encoder
for JSON serialization of domain types, rather than individual `to_dict()` methods
as specified in AP-003 above.

**Rationale**: `asdict()` handles the full nested dataclass tree recursively
(AnalysisResult → FunctionTarget → Score → SideEffect → Signal →
ClassificationResult) without boilerplate. Writing individual `to_dict()` methods
on 7+ dataclasses would duplicate the recursive walk and create drift risk when
fields are added.

The `_json_default(obj)` function in `report/json_formatter.py` handles types that
`asdict()` cannot serialize automatically:
- Any `enum.Enum` instance (non-StrEnum): call `.value`
- Any other non-serializable type: raise `TypeError`

`StrEnum` members (`SideEffectType`) serialize automatically as their string value.
No `to_dict()` methods are added to domain dataclasses.

This deviation is pre-approved and does NOT require a review exception on a per-PR
basis.

### CR-006: No `rich` Dependency for Agent-Consumed Output (CS-010 Exception)

[MUST] `python.md` CS-010 requires `rich` for terminal output formatting. gaze-py's
text output is consumed primarily by automated agents (the `gaze-reporter` agent),
not interactive terminal users. Adding `rich` adds a transitive dependency footprint
for no user-facing benefit.

**Approved exception**: `report/text_formatter.py` MUST use plain string formatting
(`str.format()`, f-strings) — NOT `rich.Console`, `rich.Table`, or any `rich.*` API.
Output is routed through `click.echo()` in the CLI layer per CS-009 (never `print()`
directly).

If a future change adds interactive terminal features intended for human users,
`rich` SHOULD be added as a dependency at that point.

### CR-007: Tests MUST Be Gaze-Visible (Direct-Assertion Pattern)

[MUST] gaze-py runs `gazepy quality` against its own test suite to compute GazeCRAP
contract coverage. A test earns non-zero contract coverage only when at least one
assertion **directly references** the variable bound to the production function's
return value.

The assertion mapper (Pass 1) builds call bindings from direct assignment:
`result = fn(...)`. It then checks whether any assertion's `referenced_names`
intersect those bindings. Intermediate variable assignments break the chain: if a
test does `result = fn(...); derived = list(result); assert x in derived`, the name
`result` does not appear in `derived`'s assertion and Pass 1 fails, yielding 0%
contract coverage.

```python
# CORRECT — gaze-visible (Pass 1 fires, ReturnValue covered)
result = target_function(...)
assert result                          # ← MUST appear before derived variables
assert isinstance(result, SomeType)   # also acceptable
assert len(result) == 3               # also acceptable (result in subscript)
assert result == expected_value        # also acceptable

# WRONG — 0% contract coverage even though functionally correct
result = target_function(...)
items = [x.name for x in result]      # breaks the chain
assert "foo" in items                  # "result" not referenced → 0%
```

**Rule**: include at least one of the acceptable assertion forms before any
derived-variable assertions. One line is sufficient.

**`pytest.raises()` note**: `pytest.raises(SomeError)` maps to `ErrorReturn` via
Pass 2 — but only if the production function has a `raise` statement visible in its
own AST body (not only in private helpers it calls). If the function delegates all
raises to private helpers, `pytest.raises()` tests will get 0% contract coverage
regardless.

**CliRunner note**: `assert result.exit_code == N` satisfies CR-007 for CLI tests
because `result` is assigned from `runner.invoke(...)` and directly referenced in
the assertion.

---

## Source: `default.md` (language-agnostic floor — applies where not superseded above)

`default-custom.md` is currently empty (no gaze-py-specific extensions of this pack).

Every rule below was checked by **topic**, not by ID number — `default.md` and
`python.md` reuse the same CS/AP/SC/TC/DR numbering for unrelated rules (e.g.
`default.md` CS-002 is "no dead code"; `python.md` CS-002 is "import organization").
An ID match between the two packs is coincidental, not a supersession signal.

### Coding Style

- **CS-002** [MUST] Code MUST NOT contain dead code — unreachable branches, commented-out blocks, or unused imports, variables, functions, or types.
- **CS-003** [MUST] Identifiers MUST use meaningful, descriptive names that convey purpose (distinct from `python.md` CS-003/014, which govern casing only — not descriptiveness). Single-letter names acceptable only for conventional loop indices and very short lambdas.
- **CS-004** [MUST] Code MUST follow the DRY principle. Identical or nearly identical logic appearing in more than two locations MUST be extracted into a shared function, method, or module.
- **CS-007** [SHOULD] Magic numbers and hardcoded string literals SHOULD be extracted into named constants or configuration values. Exceptions: `0`, `1`, `-1`, empty string, and boolean literals used in obvious contexts.

### Architectural Patterns

- **AP-001** [MUST] Each module, class, or package MUST have a single, well-defined responsibility (Single Responsibility Principle) — at the module/class level; `python.md` CS-011 covers this only at function granularity.
- **AP-002** [SHOULD] Dependencies SHOULD be injected rather than hard-instantiated. Functions and constructors SHOULD accept interfaces or abstractions rather than concrete implementations, enabling testing and substitution.
- **AP-004** [SHOULD] Interfaces SHOULD be narrow and client-specific rather than broad and general-purpose (Interface Segregation Principle). Consumers SHOULD NOT be forced to depend on methods they do not use.
- **AP-005** [MUST] Circular dependencies between packages, modules, or layers MUST NOT exist. If module A imports module B, module B MUST NOT import module A (directly or transitively).

### Security Checks

- **SC-002** [MUST] All external input (user input, API payloads, file contents, environment variables used as data) MUST be validated and sanitized before use. Validation MUST reject unexpected types, lengths, and formats.
- **SC-004** [MUST] Database queries constructed with external input MUST use parameterized queries or prepared statements. String concatenation or interpolation for query construction MUST NOT be used. *(N/A — gaze-py has no database layer; retained for completeness.)*
- **SC-005** [SHOULD] Dependencies SHOULD be reviewed for known vulnerabilities before adoption and periodically thereafter.

### Testing Conventions

- **TC-001** [MUST] New functionality MUST be accompanied by tests that exercise the primary success path AND at least one failure/edge case path. (`python.md` TC-012 mandates the failure-case half only; this adds the success-path requirement.)
- **TC-006** [MUST] Bug fixes MUST include a regression test that reproduces the original failure and verifies the fix. The test MUST fail without the fix and pass with it.
- **TC-008** [SHOULD] Tests SHOULD avoid testing implementation details. Prefer testing observable behavior (inputs and outputs, side effects) over internal state or private method calls.

### Documentation Requirements

- **DR-002** [SHOULD] Configuration options, environment variables, and feature flags SHOULD be documented in the project README or a dedicated configuration reference, including defaults, valid ranges, and examples.
- **DR-003** [SHOULD] User-visible changes (new features, breaking changes, deprecations, bug fixes) SHOULD be recorded in a changelog or release notes, following the project's established format.

`default.md`'s CS-001 (formatting tool), CS-005 (import organization), CS-006
(error handling/no silent swallow), CS-008 (function size), AP-003 (separation of
concerns), SC-001 (no hardcoded secrets), SC-003 (path traversal), TC-002–005/007
(isolation, assertions, execution order, naming), and DR-001/DR-004 (docstrings,
commit messages) are omitted above — each has a genuine `python.md` counterpart
covering the same topic (verified by content, not ID). Full text of every
`default.md` rule remains at `.opencode/uf/packs/default.md` if verification is
needed.
