## Context

`gazepy report` is a stub that exits 1. The existing `_run_crap()` and
`_enrich_with_quality()` helpers already produce the combined CRAP +
quality payload. The `gaze-reporter.md` prompt is already bundled. The
only missing pieces are: payload serialization, prompt loading, and an
LLM call.

The O5 wire-up (`--max-gaze-crapload` enforcement) is included because
the stale warning message appears in three commands and the fix is
trivial now that `_enrich_with_quality()` populates
`result.summary.gaze_crapload`.

## Goals / Non-Goals

### Goals

- `gazepy report PATH` produces a narrative report when `--ai` is
  provided; emits the JSON payload to stdout when `--ai` is omitted
- Three subprocess adapters: `opencode`, `ollama`, `claude`
- `--max-gaze-crapload` enforced in `crap` and `self-check`
- `--tests` on `report` enables quality enrichment (optional)
- No new Python runtime dependencies

### Non-Goals

- SDK-based adapters (Change 4B)
- Streaming (Change 4B)
- `--baseline` delta reporting (Change 4B)
- AI-assisted assertion mapping (separate change)

## Decisions

### D1: Pipeline

```
report(path, --ai, --model, --tests, ...)
  1. Validate PATH
  2. Acquire coverage_data (--coverprofile or auto-run pytest)
  3. result = _run_crap(src, coverage_data, config)
  4. _enrich_with_quality(result, src, tests_path, ...)   # optional
  5. payload = _assemble_report_payload(result)           # JSON string
  6. if --ai is None: click.echo(payload); return
  7. prompt = _load_report_prompt(Path.cwd())
  8. response = call_ai(prompt, payload, provider=ai, model=model, timeout=ai_timeout)
  9. click.echo(response)
```

Step 4 is optional: if no tests path resolves (no `--tests` and
auto-discovery finds nothing), `_enrich_with_quality()` is skipped.
The report still runs with CRAP-only data. The AI prompt instructs the
model to note when GazeCRAP data is absent.

### D2: Payload assembly

`_assemble_report_payload(result: AnalysisResult) -> str`

Returns `to_json(result)` — the same JSON that `gazepy crap --format=json`
produces. This includes CRAP scores, GazeCRAP scores, quadrants,
contract coverage, fix strategies, recommended actions. No additional
transformation. Reuse the existing serializer.

The payload is passed to the AI as the user message. The system prompt
(gaze-reporter.md) instructs the AI how to interpret and narrate it.

### D3: Prompt loading

`_load_report_prompt(workdir: Path) -> str`

1. Check `workdir / ".opencode" / "agents" / "gaze-reporter.md"`.
   If it exists: read, strip YAML frontmatter, return.
2. Else: read the bundled asset at
   `src/gaze_py/cli/assets/agents/gaze-reporter.md`, strip frontmatter,
   return.

Frontmatter stripping: content between the first `---\n` and the next
`\n---` line is removed. If no frontmatter, content is returned
unchanged. Same algorithm as Go's `stripFrontmatter()`.

### D4: AI adapters — subprocess only

`call_ai(prompt, payload, *, provider, model=None, timeout=120, _subprocess_run=subprocess.run) -> str`

The `_subprocess_run` parameter is the injection point for tests —
pass a mock to avoid spawning real subprocesses.

Provider detection via `shutil.which()`. If the provider binary is not
found, raise `click.ClickException` with install hint.

**`opencode` adapter**:

```bash
opencode run --model <model> "<prompt>\n\n<payload>"
```

If `model` is None, omit `--model` (uses opencode's configured
default). Captures stdout. `opencode run` is non-interactive and
returns the model response on stdout. Default provider.

**`ollama` adapter**:

```bash
echo "<prompt>\n\n<payload>" | ollama run <model>
```

Model is required for ollama (no default). If model is None, raise
`ClickException`. Communicates via stdin pipe.

**`claude` adapter** (Anthropic CLI):

```bash
claude -p "<prompt>" "<payload>"
```

Or if the `claude` binary is unavailable, raise `ClickException` with:
`"Install the Anthropic CLI: pip install anthropic-cli"`.

### D5: Default provider and model

Default `--ai`: `None` (JSON-only mode, no AI call).
Default `--model`: `None` (each adapter uses its own default).

When `--ai opencode` and `--model` is not set: `opencode run` runs with
its configured model (currently `google-vertex/claude-sonnet-4-6@default`
in this environment). No hardcoded model name in the code.

### D6: O5 wire-up — max-gaze-crapload enforcement

In `crap` command body, replace:
```python
if max_gaze_crapload > 0:
    click.echo("Warning: --max-gaze-crapload is not enforced until O1 ...", err=True)
```
with:
```python
if (
    max_gaze_crapload > 0
    and result.summary.gaze_crapload is not None
    and result.summary.gaze_crapload > max_gaze_crapload
):
    click.echo(
        f"CI gate: gaze_crapload={result.summary.gaze_crapload} "
        f"exceeds --max-gaze-crapload={max_gaze_crapload}",
        err=True,
    )
    raise SystemExit(1)
```

Same fix in `self-check`. The `report` command also accepts
`--max-gaze-crapload` (already in its Click decorators); wire up the
same enforcement there.

Update help text for `--max-gaze-crapload` in all three commands from:
`"CI gate: accepted, enforcement deferred until O1. 0 = no limit."`
to:
`"CI gate: fail (exit 1) when gaze_crapload exceeds this value. 0 = no limit."`

### D7: `report` command flags

Existing stub already declares all flags via Click decorators. The real
implementation uses: `--ai`, `--model`, `--coverprofile`, `--tests`
(new, same as `crap`), `--format` (kept for JSON-only mode),
`--max-crapload`, `--max-gaze-crapload`, `--min-contract-coverage`,
`--ai-timeout`.

`--format` in JSON mode emits `to_json(result)` (same as
`gazepy crap --format=json`). In AI mode, `--format` is ignored —
the AI response is always plain text.

### D8: Version bump

0.5.0 → 0.5.1 (patch). These changes are:
- New optional capability (report command) — additive
- O5 enforcement — bug fix (stale warning → correct enforcement)
- No breaking changes, no new required deps

## Risks / Trade-offs

**Risk: `opencode run` message length limit.** Large codebases produce
large JSON payloads. opencode's message handling is tested up to the
context window limit. For typical Python projects (< 200 functions) the
payload is < 50KB — well within limits. For larger projects, the
`--path` argument can target a subdirectory.

**Risk: `ollama run` streaming vs. capture.** `ollama run` by default
streams to stdout. With `capture_output=True`, all output is captured
after completion. No partial output during long generations. Acceptable
for the CLI use case; streaming is deferred to Change 4B.

**Risk: Stale gaze-reporter.md prompt.** The bundled prompt was written
for Go gaze output format. The Python JSON payload has the same top-
level structure (`functions`, `summary`) but Python-specific field
names (`line_coverage`, not `LineCoverage`). The prompt uses
`snake_case` field names throughout — compatible with gaze-py output.
Verified by inspection.
