---
description: >
  Run the OpenSpec implementation pipeline autonomously:
  review specs, implement with parallel Swarm workers,
  review code, store learnings, and present demo
  instructions. Exits to the human only when it genuinely
  needs human judgment.
---
<!-- scaffolded by uf vdev -->

# Command: /unleash

## Description

Autonomous pipeline execution for OpenSpec changes.
Takes artifacts prepared by `/opsx-propose` from
`openspec/changes/` to demo-ready code in a single command.
Orchestrates 5 steps: spec review, implement, code review,
retrospective, and demo. Exits gracefully when
human judgment is needed and resumes from where it left
off on re-run.

## Usage

```
/unleash
```

## Instructions

### 0. Startup Cleanup

Before any pipeline logic, clean up stale worktrees from
previous interrupted runs:

1. Call `swarm_worktree_list` with the project path.
2. If any worktrees exist, call `swarm_worktree_cleanup`
   with `cleanup_all: true` to remove them.
3. This cleanup does NOT affect resumability -- change
   artifacts and task checkboxes live in the main working
   directory, not in worktrees.

If `swarm_worktree_list` is not available (Replicator
not installed), skip this step silently.

### 1. Branch Safety Gate

Get the current branch:

```bash
git rev-parse --abbrev-ref HEAD
```

- If on `main`: **STOP** with error:
  > "Cannot run /unleash on main. Must be on an OpenSpec
  > (`opsx/*`) feature branch."

- If on `opsx/*`: **OpenSpec change detected.**
  Extract the change name from the branch:
  `opsx/<name>` → `<name>`.
  Set `FEATURE_DIR = openspec/changes/<name>/`.

  Check if `FEATURE_DIR/tasks.md` exists. If not:
  **STOP** with error:
  > "No tasks.md found for change `<name>`. Run
  > `/opsx-propose` first."

  Announce: "Detected OpenSpec change: `<name>`"

- If the branch does not match `opsx/*`:
  **STOP** with error:
  > "Unrecognized branch pattern. /unleash requires an
  > OpenSpec branch (`opsx/*`). Run `/opsx-propose`
  > to create one."

### 2. Resumability Detection

Probe filesystem state to determine which steps are
already complete. Check in order:

Proposal, design, requirement specs, and tasks are prepared
by `/opsx-propose` according to the change's schema.

1. **Spec review done?** Read `FEATURE_DIR/tasks.md`
   and check for the `<!-- spec-review: passed -->` HTML
   comment marker.

2. **Implementation done?** Read `FEATURE_DIR/tasks.md`
   and check if all task checkboxes are `[x]` (no
   `- [ ]` lines remain in the task phases).

3. **Code review done?** Read `FEATURE_DIR/tasks.md`
   and check for the `<!-- code-review: passed -->` HTML
   comment marker.

Display the detection results:

```
Detected: OpenSpec change — artifacts from /opsx-propose
  spec-review [status]  implement [status]  code-review [status]
```

Skip all steps that are detected as complete. Resume
from the first incomplete step.

If ALL steps are complete (all tasks done, tests pass):
skip directly to step 4 (retrospective) since it is
idempotent.

### 3. Step 1 -- Spec Review

Review the spec artifacts using the review council in
spec review mode for consistency analysis and quality
validation of the OpenSpec artifacts against
`openspec/constitution.md`.

1. Read the full contents of
   `.opencode/commands/review-council.md`.
2. Delegate to the `cobalt-crush-dev` agent via the Task
   tool with the review council's instructions, adding
   the explicit mode override: "Run in **Spec Review
   Mode** -- review the spec artifacts in `FEATURE_DIR`,
   not code."
3. Collect the review results.

**Processing results**:

- If all reviewers APPROVE: write the spec review marker
  to `FEATURE_DIR/tasks.md`:
  ```
  <!-- spec-review: passed -->
  ```
  Append this marker at the very end of
  `FEATURE_DIR/tasks.md`. Proceed to step 2.

- If only LOW and MEDIUM findings exist: auto-fix them
  (the review council handles this per its hybrid fix
  policy). After fixes, re-run the review. If all
  APPROVE after fixes, write the marker and proceed.

- If HIGH or CRITICAL findings remain after auto-fixing
  LOW/MEDIUM: **EXIT** with the findings:

  ```
  ## /unleash paused at: spec review

  **Reason**: HIGH/CRITICAL findings in spec artifacts

  ### Findings

  [list each HIGH/CRITICAL finding with context]

  ### What to do next
  Clarify the affected artifacts in `FEATURE_DIR` to
  address the findings, then re-run `/unleash`.

  ### Then resume
  Run `/unleash` to continue from spec review.
  ```

### 4. Step 2 -- Implement

Follow `/opsx-apply` for the selected change, using the
phase execution strategy below for its tasks.

Parse `FEATURE_DIR/tasks.md` for phases and execute
tasks.

**Derive build/test commands**: Read all files in
`.github/workflows/` to identify the exact CI commands
(build, test, vet, lint). Do NOT hardcode language-
specific commands -- the workflow files are the source
of truth. This is the same pattern used by
`/review-council` Phase 1a.

**For each phase in tasks.md**:

1. Separate tasks into two groups:
   - **Sequential** (no `[P]` marker): run first, in
     order
   - **Parallel** (`[P]` marker): run after sequential
     tasks complete

2. **Sequential execution**: for each non-`[P]` task,
   delegate to the `cobalt-crush-dev` agent via the Task
   tool with the task description as the prompt. After
   the agent completes, mark the task `[x]` in
   `tasks.md` immediately.

3. **Parallel execution**: check if
   `swarm_worktree_create` is available.

   **If Swarm worktrees are available**:

   a. Get the current commit hash:
      ```bash
      git rev-parse HEAD
      ```

   b. Limit concurrent workers to 4. If more than 4
      `[P]` tasks exist in the phase, batch them: run
      the first 4, wait for all to complete, then run
      the next batch.

   c. For each `[P]` task in the current batch:
      - Call `swarm_worktree_create` with the project
        path, task ID, and current commit hash to create
        a dedicated worktree.
      - Call `swarm_spawn_subtask` with the task
        description, files from the task, and the
        worktree path.

   d. Wait for all workers in the batch to complete.

   e. **If any worker fails**: stop spawning new workers
      (do not start the next batch). Wait for any
      already-running workers to complete or fail. Then
      call `swarm_worktree_cleanup` with `cleanup_all:
      true` to remove all worktrees. **EXIT** with error
      context:

      ```
      ## /unleash paused at: implement (Phase N)

      **Reason**: Parallel worker failed

      **Failed task**: [task ID and description]
      **Error**: [error details from worker]

      ### What to do next
      Fix the issue described above, then re-run
      `/unleash`.

      ### Then resume
      Run `/unleash` to continue from the failed phase.
      ```

   f. After all workers in a batch complete successfully,
      merge each worktree back:
      - Call `swarm_worktree_merge` for each worktree.
        This uses cherry-pick to apply the worker's
        commits to the main branch.
      - After each merge, check for conflict markers
        (`<<<<<<<`, `=======`, `>>>>>>>`) in the
        affected files.
      - If NO conflict markers remain: merge succeeded.
        Call `swarm_worktree_cleanup` for that worktree.
      - If conflict markers remain: auto-resolution
        failed. Call `swarm_worktree_cleanup` with
        `cleanup_all: true`. **EXIT** with conflict
        details:

        ```
        ## /unleash paused at: implement (Phase N)

        **Reason**: Worktree merge conflict

        **Conflicting files**:
        [list files with conflict markers]

        ### What to do next
        Resolve the merge conflicts manually, then
        re-run `/unleash`.

        ### Then resume
        Run `/unleash` to continue from the current
        phase.
        ```

   g. Mark each successfully merged `[P]` task as `[x]`
      in `tasks.md`.

   **If Swarm worktrees are NOT available**: fall back to
   sequential execution for `[P]` tasks. Announce:
   > "Swarm worktrees not available -- executing parallel
   > tasks sequentially. Install Replicator for
   > parallel execution."

   Execute each `[P]` task sequentially via the
   `cobalt-crush-dev` agent, same as non-`[P]` tasks.

   **SwarmMail file reservations**: if `swarmmail_reserve`
   is available, reserve file paths for each parallel
   worker before spawning. If SwarmMail is NOT available,
   proceed without file locks -- worktree isolation
   provides sufficient protection for parallel workers.

4. **Phase checkpoint**: after all tasks in the phase
   are complete (both sequential and parallel), run the
   CI build and test commands derived from
   `.github/workflows/`.
   - If all pass: proceed to the next phase.
   - If any fail: **EXIT** with the failure details:

     ```
     ## /unleash paused at: implement (Phase N checkpoint)

     **Reason**: Build or test failure after Phase N

     **Failed command**: [the command that failed]
     **Output**: [error output]

     ### What to do next
     Fix the build/test failure, then re-run `/unleash`.

     ### Then resume
     Run `/unleash` to continue from the next phase.
     ```

### 5. Step 3 -- Code Review

Review the implementation using the review council in
code review mode. This includes the Phase 1a CI hard
gate, Phase 1b Gaze quality analysis (if available), and
Divisor agent reviews.

1. Read the full contents of
   `.opencode/commands/review-council.md`.
2. Delegate to the `cobalt-crush-dev` agent via the Task
   tool with the review council's instructions, adding
   the explicit mode override: "Run in **Code Review
   Mode** -- review the implementation code in
   `FEATURE_DIR`."
3. Collect the review results.

**If Gaze is not installed**: the review council will
skip Phase 1b with an informational note. This is
non-blocking -- code review proceeds without Gaze
quality data.

**Processing results**:

- If all reviewers APPROVE (and CI passes):
  Write the code review marker to
  `FEATURE_DIR/tasks.md`:
  ```
  <!-- code-review: passed -->
  ```
  Append this marker at the very end of
  `FEATURE_DIR/tasks.md` (after the spec-review marker
  if present). Proceed to step 4.

- If findings exist: attempt to fix them. For each
  iteration (up to 3 total):
  a. Address the findings by making code fixes.
  b. Re-run the review council in code review mode.
  c. If all APPROVE: proceed to step 4.

- If 3 iterations are exhausted with remaining findings:
  **EXIT** with the persistent issues:

  ```
  ## /unleash paused at: code review

  **Reason**: 3 review iterations exhausted

  ### Persistent findings

  [list each finding that persists across iterations,
   noting which were fixed vs. which remain]

  ### Circular dependencies (if any)

  [if fixing one reviewer's finding causes another
   reviewer's check to fail, describe the cycle]

  ### What to do next
  Fix the outstanding findings manually, then re-run
  `/unleash`.

  ### Then resume
  Run `/unleash` to continue from code review.
  ```

### 6. Step 4 -- Retrospective

Analyze the session and store learnings in semantic
memory.

1. Review the session: tasks completed, review findings
   encountered, fixes applied, patterns discovered.

2. Compose at least one learning as a natural language
   paragraph (Dewey's semantic search works best on
   narrative text, not bullet lists). Categorize each
   learning as one of:
   - **Patterns**: coding/design patterns that worked
     well
   - **Gotchas**: unexpected issues or edge cases
   - **Review Insights**: what the review council found
     and how it was fixed
   - **File-Specific**: learnings about specific files
     that future workers should know

3. **If Dewey is available** (`dewey_store_learning` tool
   exists): store each learning via `dewey_store_learning`
   with tags including:
   - The branch name (e.g., `opsx/unleash-command`)
   - The current date (e.g., `2026-03-29`)
   - The learning category (e.g., `pattern`, `gotcha`,
     `review-insight`, `file-specific`)

4. **If Dewey is NOT available**: skip the storage
   step with an informational note:
   > "Dewey not available -- retrospective learnings
   > not stored. Install Dewey for semantic memory."

   Display the learnings in the output so they are not
   lost.

### 7. Step 5 -- Demo

Present structured demo instructions to the developer.

1. **What Was Built**:
   - Read the change proposal from
     `FEATURE_DIR/proposal.md`. Summarize what was
     implemented.

2. **How to Verify**:
   - Generate verification steps from the requirement
     scenarios in `FEATURE_DIR/specs/` and the
     implementation tasks in `FEATURE_DIR/tasks.md`.

3. **Key Files Changed**: run:
   ```bash
   git diff --name-only main...HEAD
   ```
   List the changed files grouped by directory.

4. **Test Results**: summarize the test output from the
   most recent build/test checkpoint.

5. **Next Steps**: always present these options:
   - `/finale` to commit, push, create PR, and return
     to main
   - Refine the OpenSpec artifacts and re-run `/unleash`
   - `/opsx-archive` to archive the completed change

Format the output as:

```
## What Was Built

[summary from change proposal]

## How to Verify

[verification commands from requirement scenarios and tasks]

## Key Files Changed

[grouped file list from git diff]

## Test Results

[pass/fail summary with counts]

## Next Steps

- Run `/finale` to create PR and watch CI
- Refine the OpenSpec artifacts and re-run `/unleash` to iterate
- Run `/opsx-archive` when the change is complete
```

## Guardrails

- **NEVER run on `main`** -- the command is for OpenSpec
  (`opsx/*`) feature branches
- **NEVER skip spec review exit on HIGH/CRITICAL** --
  these findings block implementation to prevent wasted
  effort on a flawed spec
- **NEVER merge worktrees with unresolved semantic
  conflicts** -- conflict markers in files after
  cherry-pick mean the merge failed and requires human
  resolution
- **ALWAYS present exit messages with actionable next
  steps** -- every exit point must tell the developer
  what happened, what to do, and how to resume
- **ALWAYS store at least one learning in retrospective**
  -- the retrospective is the swarm's memory; skipping
  it means the same mistakes will be repeated
- **ALWAYS clean up worktrees** -- stale worktrees waste
  disk space and can cause confusion on re-runs
- **NEVER create WorkflowInstance objects** -- `/unleash`
  operates at the OpenSpec change level, not the hero
  lifecycle workflow level (Specs 008/012/016)
- **NEVER hardcode build/test commands** -- derive them
  from `.github/workflows/` (CI files are source of
  truth)
