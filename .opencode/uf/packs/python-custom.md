---
pack_id: python-custom
language: Python
version: 2.0.0
---

# Custom Rules: Python (gaze-py)

Project-specific Python conventions that extend the canonical Python convention
pack. Rules in this file are loaded alongside `python.md` by Cobalt-Crush
(during implementation) and all Divisor persona agents (during review).

Source: derived from [Dignified Python](https://dagster.io/blog/dignified-python-10-rules-to-improve-your-llm-agents)
and the audit findings from the first implementation pass.

Use the `CR-NNN` prefix for all custom rules. Use `[MUST]`, `[SHOULD]`, or
`[MAY]` severity indicators per RFC 2119.

---

## CR-001: Look Before You Leap (LBYL)

[MUST] Prefer explicit precondition checks over `try/except` for control flow.
Check conditions before acting — do not use exceptions to detect normal
program states.

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

`try/except` is acceptable in exactly three situations:

1. **CLI/API error boundaries** — the outermost handler that converts exceptions
   to user-facing messages and exit codes.
2. **Third-party API calls** — where the call itself is the authoritative test
   (e.g., a network request, subprocess, or file open where checking first
   would be a race condition).
3. **Adding context before re-raising** — wrapping a low-level exception in a
   domain exception with additional context.

In all other cases, check first.

---

## CR-002: No `type: ignore` Suppressions

[MUST] Never use `# type: ignore` comments. A `type: ignore` comment means
one of two things, both of which require a real fix:

- The type annotation is wrong → fix the annotation.
- The code is doing something the type system cannot verify → use
  `typing.cast()` paired with a runtime `assert isinstance(...)`.

```python
# WRONG
results: list[AnalysisResult] = raw  # type: ignore[assignment]

# CORRECT — fix the return type so it is accurate
def _analyze(path: Path) -> list[AnalysisResult]:
    ...

# CORRECT — cast with runtime guard when unavoidable
assert isinstance(raw, list) and all(isinstance(r, AnalysisResult) for r in raw)
results = cast(list[AnalysisResult], raw)
```

Zero `# type: ignore` comments are permitted in `src/`. Test files may use
them only with an inline justification comment explaining why the type
system cannot be satisfied correctly.

---

## CR-003: Keyword-Only Arguments for Functions with 4+ Parameters

[MUST] Any function with four or more parameters beyond `self` MUST use `*`
to enforce keyword-only arguments at the call site. This makes call sites
self-documenting and prevents silent argument transposition bugs.

```python
# CORRECT
def map_assertions(
    test_source: str,
    target_func: str,
    target_effects: list[SideEffect],
    *,
    warn: bool = True,
    confidence_threshold: int = 70,
) -> QualityReport:
    ...

# WRONG — positional args are ambiguous at call site
def map_assertions(
    test_source: str,
    target_func: str,
    target_effects: list[SideEffect],
    warn: bool = True,
    confidence_threshold: int = 70,
) -> QualityReport:
    ...
```

Exceptions: `self`, Click callback parameters (Click injects by position),
and `@abstractmethod` stubs in ABCs (avoid forcing all implementations
to match a signature).

---

## CR-004: No Inline Imports

[MUST] All imports MUST be at module level. Inline imports (imports inside
function bodies) are forbidden except in three specific cases:

1. **Breaking a genuine circular import** — document why at the import site.
2. **`TYPE_CHECKING` guard** — `if TYPE_CHECKING: import X` for type-only
   references that would cause circular imports at runtime.
3. **Conditional optional dependency** — importing a library that may not
   be installed, guarded by a `try/except ImportError`.

```python
# WRONG — inline import without justification
def my_function() -> None:
    import ast
    tree = ast.parse(source)

# CORRECT — module level
import ast

def my_function() -> None:
    tree = ast.parse(source)
```

The test suite is not exempt. If six test functions all need `ast`, import
it once at the top of the test module.

---

## CR-005: Exception Chaining

[MUST] When raising an exception inside an `except` block, always chain it
explicitly. Use `raise X from e` to preserve the original traceback, or
`raise X from None` when the original exception is an irrelevant
implementation detail.

```python
# CORRECT — preserve traceback
try:
    parse_config(path)
except ValueError as e:
    raise GazeParseError(f"Invalid config at {path}: {e}") from e

# CORRECT — intentionally break chain
try:
    fetch_from_cache(key)
except KeyError:
    raise ValueError(f"Unknown key: {key}") from None

# WRONG — missing chain (ruff B904)
try:
    parse_config(path)
except ValueError:
    raise GazeParseError("Invalid config")
```

Enforced by ruff rule `B904`.

---

## CR-006: No Silent Exception Swallowing

[MUST] Never catch an exception and do nothing. At minimum, emit a warning.
Silent `except: pass` and silent `except Exception: pass` blocks are
forbidden — they make failures impossible to diagnose.

```python
# WRONG — silent swallow
try:
    optional_feature()
except Exception:
    pass

# CORRECT — at minimum, warn
try:
    optional_feature()
except Exception as e:
    warnings.warn(f"Optional feature failed: {e}", stacklevel=2)

# CORRECT — let it bubble (the default; no try/except needed)
optional_feature()
```

---

## CR-007: No Re-Exports from `__init__.py`

[MUST] Every symbol has exactly one canonical import path. Do not re-export
symbols from `__init__.py` to create a shorter import alias.

```python
# WRONG — src/gaze_py/__init__.py
from gaze_py.taxonomy import SideEffect  # creates a second import path
__all__ = ["SideEffect"]

# CORRECT — callers import from the canonical location
from gaze_py.taxonomy import SideEffect
```

`__init__.py` files MUST contain only:
- `__version__` (package root only)
- A module-level docstring
- Nothing else

This makes the dependency graph explicit and prevents hidden coupling between
subpackages.

---

## CR-008: Domain Exceptions Belong in `exceptions` or `taxonomy`

[MUST] Domain exception classes MUST be defined in `src/gaze_py/taxonomy/`
(or a dedicated `src/gaze_py/exceptions.py` if the taxonomy module becomes
crowded). No subpackage may define an exception class that other subpackages
need to import — that creates a coupling in the wrong direction.

```python
# WRONG — analysis/ defines an exception that quality/ imports
# src/gaze_py/analysis/__init__.py
class GazeParseError(Exception): ...

# src/gaze_py/quality/__init__.py
from gaze_py.analysis import GazeParseError  # wrong direction

# CORRECT — both import from taxonomy
# src/gaze_py/taxonomy/__init__.py
class GazeParseError(Exception): ...

# src/gaze_py/analysis/__init__.py
from gaze_py.taxonomy import GazeParseError

# src/gaze_py/quality/__init__.py
from gaze_py.taxonomy import GazeParseError
```

---

## CR-009: ABCs for Internal Interfaces

[MUST] When defining an interface that gaze-py owns all implementations of,
use `abc.ABC` with `@abstractmethod`. Use `typing.Protocol` only for
structural typing against external libraries or minimal duck-typed interfaces
that gaze-py does not control.

```python
# CORRECT — internal interface with owned implementations
from abc import ABC, abstractmethod

class Formatter(ABC):
    @abstractmethod
    def write(self, results: list[AnalysisResult], out: IO[str]) -> None:
        """Write analysis results to out."""

# CORRECT — external library facade
from typing import Protocol

class ASTVisitable(Protocol):
    def visit(self, node: ast.AST) -> None: ...
```

AP-007 in `python.md` currently says "prefer Protocol" — this rule overrides
it for gaze-py: prefer ABC for owned interfaces, Protocol for external facades.

---

## CR-010: Testdata Fixtures Are Not Tests

[MUST] Files under `tests/testdata/` are static analysis fixtures — source
files for the engine to parse. They MUST NOT:

- Import from `tests.*` or any other package path
- Be importable as Python modules (no `__init__.py` in testdata directories)
- Contain assertions or test logic
- Be collected by pytest

If a fixture file must reference a name from another fixture file, it MUST
NOT use an import statement. The engine detects calls by AST node, not by
resolved symbol. Use `# ruff: noqa: F821` to suppress undefined-name
warnings on bare call sites.

```python
# CORRECT — fixture file with no imports
# tests/testdata/quality/test_basic.py

# ruff: noqa: F821
# This file is parsed as AST by the quality engine — never executed.

def test_compute() -> None:
    result = compute(1, 2)  # bare call — engine detects this
    assert result == 3
```

`pyproject.toml` MUST include `norecursedirs = ["tests/testdata"]` to
prevent pytest from collecting these files.

---

## CR-011: Parametrize Over Loops in Tests

[MUST] Never write a `for` loop inside a test function to exercise multiple
inputs. Use `@pytest.mark.parametrize`. A loop inside a test reports only
one failure even when multiple cases fail, and the test name does not
communicate which case failed.

```python
# WRONG
def test_p0_types() -> None:
    for name in {"ReturnValue", "ErrorReturn", "SentinelError"}:
        assert hasattr(SideEffectType, name)

# CORRECT
@pytest.mark.parametrize("name", ["ReturnValue", "ErrorReturn", "SentinelError"])
def test_p0_type_exists(name: str) -> None:
    assert hasattr(SideEffectType, name)
```

---

## CR-012: Test Private Functions Only Through Their Public Contract

[MUST] Do not import and test underscore-prefixed private functions directly
unless the function is complex enough to warrant isolated testing AND a
comment documents why the public API is insufficient to exercise the
scenario.

If a private function needs direct tests, the test file MUST include:

```python
# Testing _foo directly because: <reason why map_assertions() cannot
# exercise this scenario without prohibitive fixture complexity>
from gaze_py.quality import _foo
```

Without this comment, the test will be rejected in review. Private function
tests that duplicate coverage already provided by public API tests MUST be
deleted.

---

## CR-013: No Placeholder Values in Production Output

[MUST] Never emit hardcoded placeholder strings in output that users will
see. If a field cannot be populated, it MUST be `None` / `null` in JSON,
not a string like `"test.py:?"` or `"<unknown>"`.

```python
# WRONG
location = "test.py:?"  # appears verbatim in JSON output

# CORRECT
location: str | None = None  # serialises as null
```

If a field is conditionally unavailable, the domain type MUST reflect that
with `field: str | None` and the JSON schema MUST mark it nullable.

---

## CR-014: `monkeypatch` Over `unittest.mock`

[MUST] Use pytest's `monkeypatch` fixture for all patching in tests. Do not
import from `unittest.mock`. `monkeypatch` is automatically scoped to the
test, whereas `unittest.mock.patch` requires explicit cleanup and is not
idiomatic pytest.

```python
# WRONG
from unittest.mock import patch

def test_something(tmp_path: Path) -> None:
    with patch("pathlib.Path.read_text", side_effect=OSError("denied")):
        ...

# CORRECT
def test_something(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "read_text", lambda self: (_ for _ in ()).throw(OSError("denied")))
    ...
```

---

## CR-015: Nullable Fields Must Be `None`, Not Zero or Empty

[MUST] Fields that are conditionally computed (e.g., `gaze_crap`,
`contract_coverage`, `quadrant`) MUST be `None` / absent in JSON when the
capability has not run — not zero-valued. This allows consumers to
distinguish "not computed" from "computed as zero."

Per porting contract OC-003: a port MUST NOT emit `0.0` where `null` is
the correct representation of "not available."

```python
# WRONG — zero is indistinguishable from "not computed"
gaze_crap: float = 0.0

# CORRECT
gaze_crap: float | None = None
```
