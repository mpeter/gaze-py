## Context

gaze-py has no user-facing docs. The Go gaze sibling has 30+ docs files covering installation, concepts, guides, CLI reference, and architecture. The porting contracts (`docs/porting/`) are the authoritative source for taxonomy and scoring details, but they target implementors, not users.

This change creates a `docs/` tree adapted from Go gaze, accurate for Python AST-only detection, and scoped to what gaze-py currently implements.

## Goals / Non-Goals

**Goals:**
- Ship a minimal viable docs tree: installation, concepts (taxonomy + scoring), CLI reference for all 8 commands, configuration reference, glossary
- Adapt Go gaze content — correct all Go-specific references (goroutine → subprocess spawn, SSA → AST-only, Go stdlib patterns → Python stdlib patterns)
- Accurately represent current detection status per command (what's implemented vs. not)
- Use content pack voice rules (VB-001 through VB-006): active voice, no weasel words, accurate scope

**Non-Goals:**
- Guides (improving-scores, ci-integration, ai-reports, opencode-integration) — out of scope for this change
- Architecture docs (contributing, extending, architecture overview) — out of scope
- Website/MkDocs configuration — files are standalone markdown, no build tooling added
- README changes — tracked separately
- `release.yml` — already exists and is complete

## Decisions

**D-1: Adapt Go gaze docs, do not copy verbatim.**
Go gaze references SSA analysis, goroutine spawning, `go` statements, Go stdlib imports, and 37 effect types (documentation bug — actual count is 38). All of these need Python-correct equivalents. Verbatim copy would ship incorrect content.

**D-2: Taxonomy table uses 38 types and marks detection status accurately.**
The Python AST-only engine does not implement all 38 types. The concepts/side-effects.md table MUST use "Implemented (AST)" vs. "Not implemented" per actual `SideEffectType` and detector coverage — not aspirational status.

**D-3: No build tooling added.**
docs/ is plain markdown. No MkDocs, Sphinx, or mkdocstrings. Keeps the change self-contained and avoids new dependencies.

**D-4: CLI reference pages generated from `--help` output plus prose.**
Each `docs/reference/cli/<cmd>.md` file includes: synopsis, description, options table (from `--help`), output format description, and an example. This makes the pages useful even without running the tool.

## Risks / Trade-offs

- [Risk] Detection status in taxonomy table drifts as new effects are implemented → Mitigation: table notes "as of v0.6.0" with a pointer to `SideEffectType` enum in source
- [Risk] Go gaze concepts/side-effects.md says "37 types" (doc bug) — if copied verbatim, we perpetuate the error → Mitigation: enumerate from source, assert 38
- [Risk] CLI `--help` output changes across versions → Mitigation: document as of current CLI version, options tables are prose-adjacent not machine-generated
