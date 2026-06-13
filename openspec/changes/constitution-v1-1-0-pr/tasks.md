<!--
  [P] marks tasks eligible for parallel execution.
  Add [P] when a task: (a) touches different files from
  other [P] tasks in the group, (b) has no dependency
  on prior tasks in the group, (c) can safely execute
  without ordering constraints.
  Do NOT add [P] when tasks modify the same file —
  parallel workers will cause merge conflicts.
  Tasks without [P] run sequentially first, then [P]
  tasks run in parallel.
  Note: all tasks in this change are sequential by nature;
  no [P] markers are used.
-->

## 0. Pre-flight

- [ ] 0.1 Verify `pyproject.toml` status: `ls pyproject.toml 2>/dev/null && echo EXISTS || echo ABSENT`
- [ ] 0.2 If `pyproject.toml` EXISTS: verify `uv.lock` is committed (`git ls-files uv.lock`). If `uv.lock` is absent, run `uv sync` and stage it for inclusion in the constitution amendment commit — Principle VII is already active.
- [ ] 0.3 If `pyproject.toml` ABSENT: confirm that Principle VII's lock file clause remains correctly conditioned on the prerequisite; no action needed.

## 1. Branch and Commit

- [ ] 1.1 Verify no branch named `opsx/constitution-v1.1.0` already exists: `git branch | grep constitution`. If it exists, delete it: `git branch -D opsx/constitution-v1.1.0`
- [ ] 1.2 Create and switch to branch: `git checkout -b opsx/constitution-v1.1.0`
- [ ] 1.3 Stage only the amendment files: `git add .specify/memory/constitution.md .github/workflows/test.yml .github/dependabot.yml`
- [ ] 1.4 Verify staged diff is exactly the three expected files: `git diff --cached --name-only` (MUST show only `.specify/memory/constitution.md`, `.github/workflows/test.yml`, and `.github/dependabot.yml`)
- [ ] 1.5 Commit with full body (subject + SYNC IMPACT REPORT summary):
  ```
  git commit -m "chore: ratify gaze-py constitution v1.1.1

  MINOR v1.1.0 — 2026-06-13
  Parent constitution: Unbound Force Org Constitution v1.2.0
  Added principles:
    VI.  Composability First — standalone installability; no hard inter-hero
         prerequisites; extension points at module interfaces
    VII. Supply Chain Integrity — committed lock file; CI actions pinned by
         commit SHA; dependency justification required before adding new deps
  Org principle scoped out:
    I. Autonomous Collaboration (org v1.2.0) — not applicable to a standalone
    CLI tool. Revisit if gaze-py gains a service mode or participates in a hero pipeline.

  PATCH v1.1.1 — 2026-06-13
  Clarified effect taxonomy count: 37 (header) → 38 (correct per EC-001).
  The 37-vs-38 discrepancy is a documentation bug; enumeration yields 38
  (P0=5 P1=8 P2=10 P3=9 P4=6). Tests MUST assert 38.

  CI: actions/checkout@v4.2.2 and setup-uv@v5.4.2 pinned by SHA.
  Note: uv sync --frozen deferred until pyproject.toml + uv.lock are committed (001-initial-port).
  Dependabot: .github/dependabot.yml added (github-actions, weekly, Conventional Commits prefix)."
  ```
- [ ] 1.6 Verify commit contains exactly the three expected files: `git show --name-only HEAD` (MUST show `.specify/memory/constitution.md`, `.github/workflows/test.yml`, `.github/dependabot.yml`)
- [ ] 1.7 Verify unrelated files remain as working-tree modifications only: `git status` (AGENTS.md, python-custom.md, agent-file-template.md MUST appear as modified but unstaged)
- [ ] 1.8 Push branch: `git push -u origin opsx/constitution-v1.1.0`

## 2. CI Gate

- [ ] 2.1 Wait for GitHub Actions `test.yml` to complete on `opsx/constitution-v1.1.0`, or run the full local CI gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ && uv run pytest --cov=gaze --cov-fail-under=85`
- [ ] 2.1a Note: `uv sync` (without `--frozen`) will succeed even without `pyproject.toml` — steps after it (mypy, pytest) will fail if `src/` does not exist. For this PR, lint and format-check are the only passing gates; mypy and pytest require the `001-initial-port` source files. This is expected and acceptable — CI is partially gated pending that change.
- [ ] 2.2 Confirm all steps are green. If any step fails: fix the flagged file, `git commit --amend` or add a fixup commit, push, and re-check CI before proceeding.

## 3. Review Council

- [ ] 3.1 Run `/review-council` against the branch diff
- [ ] 3.2 Confirm APPROVE from Divisor Guard, Architect, SRE, and Adversary (these four have meaningful surface on this change; output from other reviewers is advisory)
- [ ] 3.3 If any applicable reviewer returns REQUEST CHANGES: edit the flagged file on the branch, commit a fixup (`git commit -m "fix: address review-council findings"`), push, and re-run `/review-council` against the updated diff

## 4. Pull Request

- [ ] 4.1 Draft PR body containing all required elements (see spec Scenario "PR description complete") and save to `/tmp/pr-body.md`
- [ ] 4.2 Open PR: `gh pr create --base main --head opsx/constitution-v1.1.0 --title "chore: ratify gaze-py constitution v1.1.1" --body-file /tmp/pr-body.md`
- [ ] 4.3 Confirm PR is created and URL is returned
- [ ] 4.4 Hand off PR URL to human reviewer — constitution amendments MUST be merged by a human reviewer; agent self-merge is not permitted. Instruct the reviewer to use merge commit (not squash, not rebase): `gh pr merge --merge <PR-number>`
