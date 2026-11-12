# repository-workflow Specification

## Purpose
How requirements, history and governance are kept in this repository: OpenSpec is the single
requirements pipeline, the constitution lives in the OpenSpec tree, and finished specs are preserved
in the archive.

## Requirements

### Requirement: OpenSpec is the only requirements pipeline

Requirements and acceptance criteria for this repository SHALL live in OpenSpec
changes under `openspec/changes/` and canonical specs under `openspec/specs/`.
The repository SHALL NOT carry a second pipeline of its own (a `specs/` tree
or the commands, skills and tooling directory that served it).

#### Scenario: No second pipeline remains

- **WHEN** the repository is searched for the second pipeline's commands, tooling directory and name
- **THEN** no tracked file or file name matches

#### Scenario: Workflow guidance names OpenSpec

- **WHEN** AGENTS.md describes the specification workflow
- **THEN** it names `/opsx-propose`, `/opsx-apply` and `/opsx-archive` and names no other pipeline

### Requirement: Governance lives in the OpenSpec tree

The constitution SHALL live at `openspec/constitution.md`. Every agent and command that reads it SHALL reference that path and no other.

#### Scenario: Constitution references resolve

- **WHEN** agents and commands are searched for the constitution's old location
- **THEN** none match

### Requirement: Historical specs are preserved

Finished strategic specs SHALL be kept under `openspec/changes/archive/` with their original content. Task state SHALL change only where evidence supports it, cited in the task, and unconfirmed items SHALL be marked `(unverified: …)`.

#### Scenario: Archive content is intact

- **WHEN** an archived spec's `plan.md`, `spec.md` and `tasks.md` are compared with their pre-migration versions
- **THEN** `plan.md` and `spec.md` are identical and `tasks.md` differs only by appended evidence and reconciliation text

### Requirement: Open follow-ups stay tracked

Work that the migration finds unfinished SHALL be recorded as `.backlog/` items or OpenSpec changes before the old tracking is removed.

#### Scenario: Deferred parity items are tracked

- **WHEN** `.backlog/` is listed
- **THEN** it contains items for C.3, G.2 and the canonical spec headers

### Requirement: The migration passes the repository gates

The migrated repository SHALL pass `ruff check`, `ruff format --check`, `mypy --strict` and `pytest` with its 85% coverage floor, and every OpenSpec change SHALL validate.

#### Scenario: Gates pass on the committed revision

- **WHEN** the gates run on the migrated revision
- **THEN** all pass and `openspec validate --changes` reports no failures
