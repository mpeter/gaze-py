---
name: testing-patterns
description: Python/pytest testing patterns for gaze-py
tags: [testing, python, pytest, patterns]
---

# Testing Patterns

Python/pytest testing conventions for gaze-py. All rules derived from
TC-001–TC-013 in `.opencode/uf/packs/python.md` plus gaze-py–specific
AST-only isolation constraints.

## Framework

`pytest` only. No `unittest`, `testify`, or external assertion libraries.
Use plain `assert` statements and `pytest.raises` directly. Run via:

```bash
uv run pytest                                          # all tests
uv run pytest -m "not slow"                           # fast tests only
uv run pytest --cov=gaze_py --cov-fail-under=85       # with coverage gate
uv run pytest --tb=short -k "test_name_pattern"       # targeted run
```

## Test Naming

`test_<function>_<scenario>` — snake_case, descriptive scenario suffix.

```python
def test_score_returns_zero_on_empty_input() -> None: ...
def test_classify_raises_on_invalid_threshold() -> None: ...
def test_scan_docs_degrades_gracefully_on_timeout() -> None: ...
```

## Isolation Patterns

### Filesystem

```python
def test_writes_output_file(tmp_path: Path) -> None:
    result_file = tmp_path / "result.json"
    write_result(result_file, data)
    assert result_file.read_text() == expected
```

### Patching external calls

```python
def test_binary_resolution_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = resolve_binary()
    assert result is None
```

### Captured output

```python
def test_emits_warning_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    warn_user("something failed")
    captured = capsys.readouterr()
    assert "something failed" in captured.err
```

## Markers

```python
@pytest.mark.slow          # excluded from fast runs (-m "not slow")
@pytest.mark.parametrize   # table-driven tests
```

## Assertion Style

**Specific values, not truthiness** (TC-006):

```python
# Correct
assert result.crap == pytest.approx(12.5, rel=1e-3)
assert result.quadrant == "Q2"
assert result.effects == ["ReturnValue", "RaisedException"]

# Wrong — too weak
assert result is not None
assert result.crap > 0
assert len(result.effects) > 0
```

**Floats** — always `pytest.approx`:

```python
assert score == pytest.approx(0.75, rel=1e-3)
```

**Exceptions** — always with `match=` (TC-008):

```python
with pytest.raises(ValueError, match="threshold must be between 0 and 100"):
    ClassificationEngine(contractual_threshold=150)
```

**Return values** — always captured and asserted (TC-007):

```python
result = analyze(source)
assert result.function_count == 3
assert result.scores[0].function == "my_func"
```

## GazeCRAP Visibility

When `gazepy quality` runs against this test suite, it scores each test's
**GazeCRAP contract coverage** — what fraction of the production function's
contractual effects are verified by assertions. This is a self-referential
quality gate: the tool measures itself.

A test earns coverage only when assertions **directly reference** the bound
return value. See CR-007 in `.opencode/uf/packs/python-custom.md` for the
full rule.

**Quick reference:**

```python
# VISIBLE — include at least one of these before derived-variable assertions
result = fn(...)
assert result                          # truthiness ✓
assert result is None                  # none check ✓  (only for T | None returns)
assert len(result) == 3                # length ✓
assert isinstance(result, SomeType)   # type check ✓
assert result == expected_value        # equality ✓
assert result[0].name == "foo"         # subscript ✓

# INVISIBLE — breaks the binding chain
result = fn(...)
items = [x.name for x in result]      # intermediate variable
assert "foo" in items                  # "result" absent → 0% coverage ✗
```

Check your test suite's contract coverage:
```bash
uv run gazepy quality src/gaze_py/ --tests tests/
```

Target: ≥95% average contract coverage across paired tests.

## Parametrize

Use `@pytest.mark.parametrize` for table-driven tests — never a `for`
loop inside a test function (TC-005):

```python
@pytest.mark.parametrize(
    ("coverage", "complexity", "expected_crap"),
    [
        (0.0, 1, 2.0),
        (1.0, 5, 5.0),
        (0.5, 3, pytest.approx(4.125, rel=1e-3)),
    ],
)
def test_crap_formula(coverage: float, complexity: int, expected_crap: float) -> None:
    assert compute_crap(coverage, complexity) == expected_crap
```

## Testdata Fixtures (AST-only isolation)

Files under `tests/testdata/` are **static source fixtures** for the
AST analysis engine. They MUST NOT be imported or executed (CR-002).

Rules:
- No `__init__.py` under `tests/testdata/`
- `pyproject.toml` sets `norecursedirs = ["tests/testdata"]` so pytest
  never collects them
- Read their source text with `pathlib.Path.read_text()` or `ast.parse()`
- Never `import` or `exec()` them — they contain bare call sites and
  intentionally incomplete code that will fail at import time

```python
# Correct — read as text for AST analysis
def test_detects_return_value_effect() -> None:
    source = Path("tests/testdata/analysis/simple_return.py").read_text()
    tree = ast.parse(source)
    effects = detect_effects(tree)
    assert SideEffectType.ReturnValue in effects

# Wrong — never do this
from tests.testdata.analysis import simple_return   # will fail
import tests.testdata.analysis.simple_return        # will fail
```

## Coverage Gate

CI enforces `--cov-fail-under=85`. Check locally before committing:

```bash
uv run pytest --cov=gaze_py --cov-fail-under=85 --cov-report=term-missing
```

The 85% floor is a protected gate — never lower it to make a PR pass.
If coverage drops, add tests; do not lower the threshold.
