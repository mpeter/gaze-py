## Context

`.github/workflows/test.yml` pins two external dependencies:

| Item | Current | Target |
|---|---|---|
| `astral-sh/setup-uv` action | `d4b2f3b6...` (v5.4.2) | `fac544c0...` (v8.2.0) |
| uv binary | `0.7.8` | `0.11.21` |

The action is three major versions behind. `setup-uv` v8.0.0 introduced immutable releases and eliminated floating major/minor tags (`@v5`, `@v8`) — the security posture Principle VII (Supply Chain Integrity) is designed to enforce. Staying on v5.x means we are running on a pre-hardening release.

The uv binary pin (`0.7.8`) is fourteen minor versions behind current stable. While no specific bug affects the current test matrix, running a significantly stale binary is unnecessary operational risk.

## Goals / Non-Goals

**Goals:**
- Update `setup-uv` action reference to v8.2.0 with verified commit SHA
- Update uv binary pin to current stable (0.11.21)
- Confirm CI passes after the upgrade

**Non-Goals:**
- Changing any CI logic, test commands, Python version matrix, or other workflow steps
- Upgrading `actions/checkout` (already at v4.2.2, current)
- Adding new CI steps

## Decisions

**Decision: Target v8.2.0, not v8.1.0**

v8.2.0 is the current latest release as of 2026-06-03. There is no reason to pin to a non-latest patch — both are on the hardened immutable-release track.

**Decision: Upgrade action and uv binary in one PR**

Both are maintenance-only changes to the same file with no logic impact. A single PR keeps the diff minimal and the audit trail clean. They are not independently testable at the spec level.

**Decision: No breaking changes to address**

`setup-uv` v8.0.0 has two breaking changes:
1. Old `manifest-file` format removed — not used in this workflow.
2. Floating major/minor tags eliminated — we already use SHA pinning, so this has no impact.

The `version:` input for the uv binary is unchanged in v8.x. No migration steps are required.

**Decision: SHA verification method**

Per Principle VII, the SHA MUST be verified against the published tag before committing:

```bash
gh api repos/astral-sh/setup-uv/git/ref/tags/v8.2.0
```

Expected response: `object.type: "commit"`, `object.sha: "fac544c07dec837d0ccb6301d7b5580bf5edae39"`.

## Risks / Trade-offs

[Risk] v8.2.0 introduces an undocumented breaking change not visible in release notes → Mitigation: run CI locally before opening PR; if red, pin to v8.1.0 (`08807647e7069bb48b6ef5acd8ec9567f424441b`) as a fallback.

[Risk] uv 0.11.21 changes resolution behaviour and breaks `uv sync --frozen` → Mitigation: the lock file does not exist yet (no `pyproject.toml`), so `uv sync --frozen` will fail regardless of uv version until the lock file is committed. This risk is dormant until the initial-port change adds `pyproject.toml`.
