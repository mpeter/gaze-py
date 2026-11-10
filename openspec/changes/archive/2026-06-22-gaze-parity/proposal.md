## Why

The parity effort aligned gaze-py's JSON schema with Go gaze, implemented
baseline comparison, removed stale documentation, and prepared v0.7.0.
The full original requirements remain verbatim in [spec.md](spec.md).

## What Changes

- Wrap JSON results with target identity and metadata and align quality output.
- Implement opt-in baseline comparison with actionable errors and CI verdicts.
- Refresh documentation, consolidate the changelog, and prepare release gates.
- Archive this finished historical effort, preserving unverified release and
  housekeeping tasks rather than claiming they ran.

## Impact

Original implementation and release planning are preserved in [plan.md](plan.md)
and [design.md](design.md). Later archived changes already evolved canonical
specifications; this archival conversion does not merge historical deltas.

## Archive evidence

Reconciled on 2026-11-10. PR #50 merged Stories 1–3 and release preparation;
the v0.7.0 tag exists, but PyPI's version endpoint returns HTTP 404. The
repository now targets 0.9.3. See [tasks.md](tasks.md) for task-level evidence,
superseded steps, and untracked follow-ups. Archived does not mean every
original release operation was completed.
