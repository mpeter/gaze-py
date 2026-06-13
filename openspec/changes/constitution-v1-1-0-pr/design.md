## Context

The gaze-py constitution v1.1.0 amendment was authored in-session and is currently sitting as unstaged modifications on `main`. Two files contain the amendment changes:

- `.specify/memory/constitution.md` — v1.0.0 → v1.1.0 (two new principles, parent constitution reference, updated compliance review clause)
- `.github/workflows/test.yml` — floating action tags replaced with commit-SHA pins; `uv sync` updated to `--frozen` for lock file reproducibility

The session also modified `.opencode/uf/packs/python-custom.md`, `.specify/templates/agent-file-template.md`, and `AGENTS.md` as part of unrelated convention-pack and template updates. These belong to separate changes and MUST NOT be included in the constitution amendment commit.

The constitution's own Governance section requires all amendments go through a PR with review-council approval. This design covers the mechanical steps to satisfy that requirement.

## Goals / Non-Goals

**Goals:**
- Get the constitution v1.1.0 amendment onto a dedicated branch with a clean, scoped commit
- Obtain APPROVE from all applicable Divisor reviewers via `/review-council`
- Merge the amendment to `main` via PR

**Non-Goals:**
- Modifying any content of the amendment itself (that work is done)
- Running `/review-council` on any other open branch or change
- Touching production code, tests, or specs

## Decisions

**Decision: Which files to stage**

Only `.specify/memory/constitution.md`, `.github/workflows/test.yml`, and `.github/dependabot.yml` belong in this commit. Use `git add <path>` for each file explicitly rather than `git add .`. Verify with `git diff --cached --name-only` before committing.

**Decision: Branch name**

`opsx/constitution-v1.1.0` — follows the `opsx/<name>` convention used by existing branches in this repo (`opsx/fix-fixture-imports`, `opsx/quality-call-scanning`, `opsx/rename-binary-gazepy`).

**Decision: Which reviewers to invoke**

The `/review-council` command runs all nine configured Divisor reviewers. `AGENTS.md` lists the canonical review-council gate as: Adversary, Architect, Guard, Tester. For this change — governance documents and CI config only, no production code, tests, or APIs — the applicable reviewers and their surface are:

| Reviewer | Relevance | In AGENTS.md gate? |
|---|---|---|
| Divisor Guard | Constitution compliance, plan alignment — primary reviewer | Yes |
| Divisor Architect | New principles affect structural conventions | Yes |
| Divisor SRE | CI action SHA pinning is an operational change | No (see note) |
| Divisor Adversary | Principle VII (Supply Chain Integrity) is a security principle | Yes |

**Note on SRE vs. Tester**: `AGENTS.md` lists Tester in the canonical gate; this change substitutes SRE because the change has no test code surface and has meaningful CI/operational surface (SHA-pinned actions, `uv sync --frozen`). Tester has no coverage, analysis, or assertion-contract surface on a governance-only change. This is a change-specific reviewer selection, not a permanent override of the AGENTS.md gate. A follow-up should update `AGENTS.md` to clarify that SRE is included in the review-council roster for CI-touching changes.

All nine reviewers run; their output is evaluated with this context in mind. OUTPUT from Scribe, Herald, Envoy, Curator, and Testing is advisory for this change type.

**Decision: Merge strategy**

Merge commit (not squash, not rebase) — the amendment commit body contains the full SYNC IMPACT REPORT summary, which must be preserved verbatim in `main`'s history for governance auditability. Use `gh pr merge --merge <PR-number>`. Human merge is required for constitution amendments per the Governance section; agent self-merge is not permitted.

**Decision: Commit body**

The commit MUST include a body containing the SYNC IMPACT REPORT summary from the constitution header. The full subject + body:

```
chore: ratify gaze-py constitution v1.1.0

Version change: 1.0.0 → 1.1.0
Amendment date: 2026-06-13
Parent constitution: Unbound Force Org Constitution v1.2.0

Added principles:
  VI.  Composability First — standalone installability; no hard inter-hero prerequisites;
       extension points at module interfaces
  VII. Supply Chain Integrity — committed lock file; CI actions pinned by commit SHA;
       dependency justification required before adding new deps

Org principle scoped out:
  I. Autonomous Collaboration (org v1.2.0) — not applicable to a standalone CLI tool.
  Revisit if gaze-py gains a service mode or participates in a hero pipeline.

CI change: uv sync --frozen; actions/checkout@v4.2.2 and setup-uv@v5.4.2 pinned by SHA.
```

## Risks / Trade-offs

[Risk] Review-council raises REQUEST CHANGES on principle wording → Resolve by editing `.specify/memory/constitution.md` on the branch, re-running review-council, then adding a fixup commit before the PR.

[Risk] `git add` accidentally stages unrelated session changes → Mitigation: explicitly name each file path in the `git add` command; verify with `git diff --cached --name-only` before committing. After the commit, run `git show --name-only HEAD` to confirm exactly the two expected files.

[Risk] Branch already exists from a prior attempt → Mitigation: check with `git branch` first; if it exists, delete and recreate: `git branch -D opsx/constitution-v1.1.0 && git checkout -b opsx/constitution-v1.1.0`.

[Risk] PR merge fails (CI red, merge conflict) → Mitigation: if CI red, fix the flagged file, commit, re-push. If merge conflict (another commit landed on `main` before the PR merged), rebase the branch: `git rebase main` and force-push.
