## 1. Replace agent body with Python/pytest adaptation

- [x] 1.1 Read current `.opencode/agents/reviewer-testing.md` to capture the exact frontmatter
- [x] 1.2 Replace the body of `.opencode/agents/reviewer-testing.md` below the frontmatter delimiter with a Python/pytest-adapted version, keeping all six frontmatter fields exactly as-is
- [x] 1.3 Verify version marker reads `<!-- scaffolded by gazepy 0.4.0 -->`
- [x] 1.4 Verify no Go-specific references remain (`*_test.go`, `testing.Short()`, `-race`, `go build`, `t.Errorf`, `t.Fatalf`, `go/packages`, `BenchmarkXxx`, `bench_test.go`, `TestXxx`)

## 2. CI gate

- [x] 2.1 Run `uv run ruff check .` — must pass with no errors (agent `.md` files are not checked by ruff; confirm no Python files were inadvertently touched)
- [x] 2.2 Run `uv run ruff format --check .` — must pass
- [x] 2.3 Run `uv run mypy --strict src/` — must pass
- [x] 2.4 Run `uv run pytest -x --tb=short` — must pass (agent file change has no effect on test results; confirm baseline is green)
