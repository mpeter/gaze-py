---
pack_id: python-custom
language: Python
version: 2.0.0
---

# Custom Rules: Python (gaze-py)

Project-specific Python conventions that extend the canonical Python convention
pack. Rules in this file are loaded alongside `python.md` by Cobalt-Crush
(during implementation) and all Divisor persona agents (during review).

Rules moved to `python.md` (universal): CR-001 LBYL, CR-002 no type:ignore,
CR-003 keyword-only args, CR-004 no inline imports, CR-005 exception chaining,
CR-006 no silent swallowing, CR-011 parametrize over loops, CR-014 monkeypatch.
AP-007 (ABC vs Protocol) reconciled in `python.md`.

Use the `CR-NNN` prefix for all custom rules. Use `[MUST]`, `[SHOULD]`, or
`[MAY]` severity indicators per RFC 2119.

---

## CR-001: No Re-Exports from `__init__.py`

[MUST] Every symbol has exactly one canonical import path. Do not re-export
symbols from `__init__.py` to create a shorter import alias.

`__init__.py` files MUST contain only:
- `__version__` (package root only)
- A module-level docstring
- Nothing else

```python
# WRONG — src/gaze_py/__init__.py
from gaze_py.taxonomy import SideEffect  # creates a second import path
__all__ = ["SideEffect"]

# CORRECT — callers import from the canonical location
from gaze_py.taxonomy import SideEffect
```

This makes the dependency graph explicit and prevents hidden coupling between
subpackages. It also ensures that `import gaze_py` does not transitively
import the entire package.

---

## CR-002: Testdata Fixtures Are Not Tests

[MUST] Files under `tests/testdata/` are static source fixtures for the
analysis engine to parse. They MUST NOT:

- Import from `tests.*` or any other package path
- Have `__init__.py` files (testdata directories are not packages)
- Contain real test logic that pytest should collect and run
- Be collected by pytest

`pyproject.toml` MUST include `norecursedirs = ["tests/testdata"]`.

If a fixture file must reference a name that is defined elsewhere, it MUST
NOT use an import statement. Add `# ruff: noqa: F821` as a file-level
comment to suppress undefined-name warnings on intentional bare call sites,
and add a comment explaining the file is parsed as AST and never executed.

```python
# CORRECT — tests/testdata/quality/test_basic.py
# ruff: noqa: F821
# Parsed as AST by the quality engine. Never executed.

def test_compute() -> None:
    result = compute(1, 2)  # bare call — engine detects by name
    assert result == 3
```

---

## CR-003: No Placeholder Values in Production Output

[MUST] Never emit hardcoded placeholder strings in output that users or
downstream tooling will consume. If a field cannot be populated, emit
`None` / `null` in JSON — not strings like `"test.py:?"`, `"<unknown>"`,
or `"n/a"`.

Per porting contract OC-003, fields that depend on optional capabilities
MUST be null/absent when the capability has not run — not zero-valued.
This allows consumers to distinguish "not computed" from "computed as zero."

```python
# WRONG — appears verbatim in JSON, indistinguishable from real data
location = "test.py:?"
gaze_crap: float = 0.0

# CORRECT
location: str | None = None     # serialises as null
gaze_crap: float | None = None  # serialises as null
```

If a field is conditionally unavailable, the domain type MUST reflect that
with `field_name: T | None` and the JSON schema MUST mark it nullable.

---

## CR-004: Test Private Functions Only Through Their Public Contract

[MUST] Do not import and test underscore-prefixed private functions directly
unless the public API cannot exercise the scenario without prohibitive
fixture complexity. If direct testing of a private function is justified,
the test MUST include a comment explaining why:

```python
# Testing _iter_test_functions directly because map_assertions() requires
# a real filesystem path and an AnalysisResult; constructing both for a
# two-line class-method scenario would obscure what is being tested.
from gaze_py.quality import _iter_test_functions
```

Without this comment, the test will be rejected in review. Private function
tests that duplicate coverage already provided by public-API tests MUST be
deleted.
