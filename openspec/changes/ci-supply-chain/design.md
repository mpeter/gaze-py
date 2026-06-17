## Context

Constitution Principle VII (Supply Chain Integrity) requires: (a) SHA pins
kept current via automated tooling, (b) committed lock file, (c) dependency
justification. The lock file (uv.lock) and SHA pins are already in place,
but no automated tooling (Dependabot/Renovate) exists to keep the pins
current. The SRE reviewer identified three HIGH findings in review council
Iteration 1:

1. Missing `.github/dependabot.yml` — SHA pins will silently rot
2. Astroid pin `>=3.0` with no upper bound — major version breakage risk
3. Release smoke test warns instead of failing — broken publishes appear
   successful

## Goals / Non-Goals

**Goals:**
- Create Dependabot configuration for `github-actions` and `pip` ecosystems
- Tighten astroid version constraint to prevent silent major-version breakage
- Make the release smoke test a hard gate (exit 1 on failure)

**Non-Goals:**
- No production code changes
- No new features or capabilities
- Not adding Renovate (Dependabot is the GitHub-native solution and
  Constitution VII names it explicitly)
- Not adding a `.github/dependabot.yml` for Docker or other ecosystems
  (gaze-py has no Docker dependencies)

## Decisions

### D1 — Dependabot ecosystems

Configure two ecosystems:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
```

**Why `pip` and not `uv`?** Dependabot does not have a `uv` ecosystem.
The `pip` ecosystem reads `pyproject.toml` and `requirements*.txt` files,
which is sufficient for detecting outdated dependencies. `uv.lock` updates
are handled by running `uv sync` after Dependabot PRs merge.

**Why weekly?** Daily is too noisy for a project with a small dependency
surface. Monthly is too slow for security patches. Weekly is the standard
cadence recommended by Constitution VII.

### D2 — Astroid upper bound

Change `astroid>=3.0` to `astroid>=3.0,<5` in `pyproject.toml`.

**Why `<5` and not `<4.2` or `<5.0`?** The CI tests against 4.1.2 (which
is in the 4.x series). Pinning `<4.2` would be too tight — minor releases
within 4.x are expected to be compatible. Pinning `<5` allows all 4.x
releases while protecting against the next major version.

**Why not `>=4.0,<5`?** The CHANGELOG notes "Astroid 3.x compatibility is
asserted." While CI only tests 4.1.2, the code does not use any 4.x-specific
APIs (it uses `infer()`, `MANAGER`, and `safe_infer()` which exist in 3.x).
Keeping `>=3.0` preserves the claim. If a user has astroid 3.x pinned
elsewhere, gaze-py will still work.

After updating `pyproject.toml`, run `uv lock` to regenerate `uv.lock`.
The locked version (4.1.2) satisfies both constraints, so no functional
change is expected.

### D3 — Release smoke test exit code

Change line 126 of `.github/workflows/release.yml` from:

```bash
echo "::warning::Smoke test timed out after 150s — verify manually at https://pypi.org/p/gaze-py"
```

to:

```bash
echo "::error::Smoke test timed out after 150s — verify manually at https://pypi.org/p/gaze-py"
exit 1
```

**Why fail the workflow?** The tag has already been pushed and the package
has already been uploaded. Failing the workflow does not undo the publish
(which is correct — partial rollback is worse). But it does make the failure
visible in the GitHub Actions UI and in Slack/email notifications. The
current `::warning` is easy to miss.

**Rollback if smoke test is flaky?** PyPI index propagation can take
2-5 minutes on busy days. The current 150s (5 × 30s) timeout handles most
cases. If false positives become a problem, increase the retry count or
delay — but the exit code should remain non-zero. A flaky test that
sometimes reports success is worse than one that conservatively fails.

## Risks / Trade-offs

- [Risk] Dependabot PRs add review burden
  → Mitigation: Weekly cadence limits to ~2-3 PRs per week max. GitHub
  actions ecosystem PRs auto-merge if CI passes (consider adding
  auto-merge for patch updates in the future).

- [Risk] Astroid `<5` upper bound may block users who upgrade to astroid 5.x
  → Mitigation: When astroid 5.x is released, test compatibility and
  update the constraint. Dependabot will surface the update automatically.

- [Risk] Smoke test exit 1 may cause false-negative release failures
  → Mitigation: The 150s timeout is generous. If flaky, increase
  retry count. Do not revert to warning-only — that masks real failures.
