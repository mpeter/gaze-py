## Context

`gazepy init` copies bundled assets into a project's `.opencode/`. Tool-owned
files are overwritten when their content differs; user-owned files are skipped
when present. Init only ever writes the files in its asset map; it has never
deleted anything.

## Decisions

### A command file that is no longer shipped stays where it is

Projects initialized by earlier releases hold the retired `testreview` command
under `.opencode/commands/` as a tool-owned copy. When it leaves the asset map, `gazepy init` neither
updates, reports nor removes it.

- Deleting is rejected: init has no deletion path, the file may have been edited
  or may still be wanted, and a surprise `rm` in a user's `.opencode/` is worse
  than a stale file.
- Reporting it is rejected: that would put the old command name back into init
  output and code, and re-introduce special-casing for one release.
- The stale file keeps working or not by itself; users delete it when they choose.
  The CHANGELOG entry tells them it is no longer maintained.

The behavior is specified generically (init leaves unmanaged files under
`.opencode/` untouched, with and without `--force`) so it also covers future
retirements, and is tested with a neutral filename.

### Release as 0.10.0, not 1.0.0; bump in the release commit

The constitution requires a MAJOR bump for breaking changes to public APIs,
JSON output schemas or analysis behavior. This change removes an optional
prompt file that `gazepy init` deployed: no CLI flag, exit code, output schema,
Python API or analysis result changes, and the project is pre-1.0. It is
recorded as breaking in the proposal and CHANGELOG and should ship as a MINOR
release, 0.9.3 to 0.10.0. Version bumps in this repository are separate
`chore(release)` commits, so this change adds a CHANGELOG entry under
Unreleased and leaves the version files alone. The maintainer confirms the
MINOR choice at release time.

## Risks

- Users who ran the retired command lose updates to it. Mitigation: CHANGELOG.
- Shipped `reviewer-testing.md` assumes `openspec/constitution.md` exists; it
  already tells the reviewer to proceed without it when absent.
