## Context

The original implementation plan is preserved in full in [plan.md](plan.md).
Four stories aligned Go gaze output, added baseline comparison, cleaned up
documentation, and prepared v0.7.0. JSON schema compatibility was the critical
path because baseline comparison consumes that schema.

## Decisions

- Add target identity and metadata at serialization boundaries; keep detection
  and scoring unchanged.
- Compare baseline/current results in a pure comparison module using stable
  package/function keys; resolve configured defaults at the CLI boundary.
- Keep baseline comparison opt-in, with explicit-path errors and warnings for
  invalid auto-discovered files.
- Use AST-only tests, synthetic fixtures, and the existing 85% coverage floor.
- Test before publishing, publish before pushing the release tag, and smoke-test
  the published package before announcing the release.

## Historical implementation detail

See [plan.md](plan.md) for the complete technical context, project structure,
story dependencies, comparison rules, and risk analysis. This archive does not
reapply its requirements to the newer canonical specifications.
