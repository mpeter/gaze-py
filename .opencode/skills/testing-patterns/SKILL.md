---
name: testing-patterns
description: Python/pytest testing patterns for gaze-py
tags: [testing, python, pytest, patterns]
---

# Testing Patterns

Python/pytest conventions for gaze-py.

## Framework

`pytest` only. Plain `assert` statements, `pytest.raises`, and `pytest.approx`.
No unittest, no testify equivalent, no external assertion libraries.

## Test Naming

`test_<function>_<scenario>` — e.g., `test_cyclomatic_complexity_empty_function`,
`test_load_config_missing_file_raises`.

## Runner

```bash
# Dev loop (fast — excludes slow)
uv run pytest -m "not slow"

# Full CI gate
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze_py --cov-fail-under=85
```

## Isolation Patterns

### Filesystem Tests

```python
def test_something(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("key: value")
    # tmp_path is automatically cleaned up after the test
```

### Monkeypatching

```python
def test_something(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_VAR", "test_value")
    monkeypatch.setattr(module, "function", mock_fn)
```

### Output Capture

```python
def test_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    my_function()
    captured = capsys.readouterr()
    assert "expected output" in captured.out
```

## Markers

```python
@pytest.mark.slow
def test_full_pipeline_integration() -> None:
    # Excluded from dev loop via: uv run pytest -m "not slow"
    ...

@pytest.mark.parametrize("input,expected", [
    (0, 1),
    (5, 6),
])
def test_something_parametrized(input: int, expected: int) -> None:
    assert my_function(input) == expected
```

## Assertions

```python
# Specific values — not just truthiness
assert result == expected_value
assert result.field == "specific_string"
assert len(result.items) == 3

# Exceptions
with pytest.raises(ValueError, match="specific message"):
    function_that_raises()

# Floats
assert score == pytest.approx(0.75, rel=1e-3)
```

## Testdata Fixtures

Static source files for AST analysis live under `tests/testdata/`:

```
tests/testdata/
├── analysis/     # .py fixtures for side-effect detection tests
└── quality/      # .py fixtures for assertion mapping tests
```

Rules:
- No `__init__.py` in testdata directories
- Not collected by pytest (`norecursedirs = ["tests/testdata"]` in pyproject.toml)
- Never import from testdata files — they are analyzed via AST, never executed
- Never import from `tests.*` in testdata files

## AST-Only Isolation

gaze-py analyzes code via AST. Tests MUST reflect this constraint:

```python
# CORRECT — parse as AST, never import
import ast
source = Path("tests/testdata/analysis/my_fixture.py").read_text()
tree = ast.parse(source)

# WRONG — importing analyzed modules violates the AST-only contract
from tests.testdata.analysis import my_fixture  # forbidden
```

## Coverage

Coverage floor: `--cov-fail-under=85`. This is a gate, not a target.
New code must not lower coverage. Check with:

```bash
uv run pytest --cov=gaze_py --cov-report=term-missing
```
