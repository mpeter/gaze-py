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

## 1. SHA Verification

- [ ] 1.1 Verify setup-uv v8.2.0 SHA: `gh api repos/astral-sh/setup-uv/git/ref/tags/v8.2.0`
- [ ] 1.2 Confirm response shows `object.type: "commit"` and `object.sha: "fac544c07dec837d0ccb6301d7b5580bf5edae39"`
- [ ] 1.3 Verify uv 0.11.21 is current stable: `gh api repos/astral-sh/uv/releases/latest` — confirm `tag_name: "0.11.21"` (or note if a newer version has released and update the target accordingly)

## 2. Edit Workflow

- [ ] 2.1 Create branch: `git checkout -b opsx/upgrade-setup-uv`
- [ ] 2.2 Edit `.github/workflows/test.yml` line 18: replace `astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86  # v5.4.2` with `astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39  # v8.2.0`
- [ ] 2.3 Edit `.github/workflows/test.yml` line 20: replace `version: "0.7.8"` with `version: "0.11.21"`
- [ ] 2.4 Verify the two edits and no other lines changed: `git diff .github/workflows/test.yml`

## 3. CI Verification

- [ ] 3.1 Stage and commit: `git add .github/workflows/test.yml && git commit -m "chore: upgrade setup-uv v5.4.2 → v8.2.0, uv 0.7.8 → 0.11.21"`
- [ ] 3.2 Push branch: `git push -u origin opsx/upgrade-setup-uv`
- [ ] 3.3 Wait for GitHub Actions `test.yml` to complete on the branch, or run lint/format/type steps locally: `uv run ruff check . && uv run ruff format --check .`
- [ ] 3.4 If CI red due to action upgrade: pin to v8.1.0 (`08807647e7069bb48b6ef5acd8ec9567f424441b`) instead — update line 18, amend the commit, push, re-check CI

## 4. Pull Request

- [ ] 4.1 Open PR: `gh pr create --base main --head opsx/upgrade-setup-uv --title "chore: upgrade setup-uv v5.4.2 → v8.2.0, uv 0.7.8 → 0.11.21" --body "Upgrades astral-sh/setup-uv from v5.4.2 to v8.2.0 (SHA-verified) and uv binary pin from 0.7.8 to 0.11.21. No logic changes. Satisfies Principle VII (Supply Chain Integrity) — keeping SHA-pinned actions on current stable. Breaking change assessment: none (manifest-file old format not used; floating tags not used)."`
- [ ] 4.2 Confirm CI green on the PR before merging
- [ ] 4.3 Merge PR: `gh pr merge --merge opsx/upgrade-setup-uv`
