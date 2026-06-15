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
-->

<!--
  PREREQUISITE: This change is best implemented after gap-hints
  (openspec/changes/gap-hints) is merged. The report command payload
  will include gap_hints when gap-hints is available, making the
  AI output more actionable. The report command works without it
  (CRAP-only payload) but is more useful with it.
-->

## 1. O5 wire-up — max-gaze-crapload enforcement

- [ ] 1.1 In `src/gaze_py/cli/main.py`, fix the `crap` command body
      (around line 382). Replace the stale warning block:
      ```python
      if max_gaze_crapload > 0:
          click.echo("Warning: --max-gaze-crapload is not enforced until O1 ...", err=True)
      ```
      with real enforcement (D6):
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
      Apply the same fix to `self-check` (around line 1530).
      Update help text for `--max-gaze-crapload` in both commands to:
      `"CI gate: fail (exit 1) when gaze_crapload exceeds this value. 0 = no limit."`

## 2. AI adapter module

- [ ] 2.1 Create `src/gaze_py/report/ai.py`:

      ```python
      """Subprocess-based AI adapters for gazepy report.

      Provides call_ai() which dispatches to one of three subprocess
      adapters: opencode, ollama, or claude CLI. No Python SDK
      dependencies — each adapter shells out to an external binary.

      The _subprocess_run parameter is injectable for testing.
      """
      from __future__ import annotations

      import shutil
      import subprocess
      from typing import Any

      import click


      def call_ai(
          prompt: str,
          payload: str,
          *,
          provider: str,
          model: str | None = None,
          timeout: int = 120,
          _subprocess_run: Any = subprocess.run,
      ) -> str:
          """Call an AI provider via subprocess and return the response.

          Args:
              prompt: System/instruction prompt (from gaze-reporter.md).
              payload: Analysis JSON to interpret.
              provider: One of "opencode", "ollama", "claude".
              model: Provider-specific model identifier. Required for
                  ollama. Optional for opencode (uses configured default)
                  and claude (uses API default).
              timeout: Subprocess timeout in seconds.
              _subprocess_run: Injection point for testing (default:
                  subprocess.run).

          Returns:
              AI response text.

          Raises:
              click.ClickException: Provider binary not found, subprocess
                  failed, or timed out.
          """
          match provider:
              case "opencode":
                  return _call_opencode(prompt, payload, model, timeout, _subprocess_run)
              case "ollama":
                  return _call_ollama(prompt, payload, model, timeout, _subprocess_run)
              case "claude":
                  return _call_claude(prompt, payload, model, timeout, _subprocess_run)
              case _:
                  raise click.ClickException(
                      f"Unknown AI provider: {provider!r}. "
                      f"Supported: opencode, ollama, claude."
                  )
      ```

      Implement `_call_opencode`, `_call_ollama`, `_call_claude`
      per D4. Each:
      - Checks `shutil.which(binary)` → ClickException if not found
      - Calls `_subprocess_run([...], capture_output=True, text=True, timeout=timeout)`
      - On `subprocess.TimeoutExpired`: raise ClickException "timed out
        after {timeout}s — try --ai-timeout with a larger value"
      - On non-zero returncode: raise ClickException with stderr content
      - Returns `result.stdout.strip()`

      **opencode adapter**: `opencode run "{prompt}\n\n{payload}"`
      with `--model {model}` when model is not None.

      **ollama adapter**: requires model; fails if model is None.
      Pass prompt+payload via stdin: `["ollama", "run", model]` with
      `input=f"{prompt}\n\n{payload}"`.

      **claude adapter**: `["claude", "-p", prompt, payload]`.

## 3. Report pipeline helpers

- [ ] 3.1 Add `_load_report_prompt(workdir: Path) -> str` to
      `src/gaze_py/cli/main.py` (or `src/gaze_py/report/ai.py` —
      either is acceptable; place it where `_assemble_report_payload`
      lives for co-location):

      ```python
      def _load_report_prompt(workdir: Path) -> str:
          """Load the gaze-reporter system prompt.

          Checks for a local .opencode/agents/gaze-reporter.md first
          (user override). Falls back to the bundled asset.

          Args:
              workdir: Project root to search for local override.

          Returns:
              System prompt string with YAML frontmatter stripped.
          """
          local = workdir / ".opencode" / "agents" / "gaze-reporter.md"
          if local.exists():
              content = local.read_text(encoding="utf-8")
          else:
              bundled = Path(__file__).parent / "assets" / "agents" / "gaze-reporter.md"
              content = bundled.read_text(encoding="utf-8")
          return _strip_frontmatter(content)


      def _strip_frontmatter(content: str) -> str:
          """Remove YAML frontmatter block from content.

          Frontmatter is the block between the first '---\\n' and the
          next '\\n---' line. Returns content unchanged if no frontmatter.
          """
          if not content.startswith("---"):
              return content
          rest = content[3:].lstrip("\n")
          idx = rest.find("\n---")
          if idx < 0:
              return content
          after = rest[idx + 4:]
          return after.lstrip("\n")
      ```

- [ ] 3.2 Add `_assemble_report_payload(result: AnalysisResult) -> str`
      to `src/gaze_py/cli/main.py`:
      ```python
      def _assemble_report_payload(result: AnalysisResult) -> str:
          """Serialize the analysis result as the AI report payload.

          Returns the same JSON that 'gazepy crap --format=json' produces.
          """
          from gaze_py.report.json_formatter import to_json
          return to_json(result)
      ```

## 4. Report command implementation

- [ ] 4.1 In `src/gaze_py/cli/main.py`, add `--tests` option to the
      `report` command (same pattern as `crap`):
      ```python
      @click.option("--tests", "tests_path", default=None,
                    help="Test directory or file. Auto-discovered if omitted.")
      ```
      Add `tests_path: str | None = None` to the `report` signature.

- [ ] 4.2 Replace the stub body of `report()` with the real pipeline
      per D1. Key notes:
      - Use `import shutil` to check provider availability
      - When `--ai` is None (default): `_emit(result, output_format)`;
        emit a note to stderr: `"Tip: pass --ai opencode to get a
        narrative report."` then return. Do NOT exit 1.
      - When `--ai` is provided: call `call_ai()` from
        `gaze_py.report.ai`; use lazy import inside the function body
        (same pattern as `build_contract_coverage_map` in the crap
        command — avoids loading `ai.py` on every `report` invocation
        without `--ai`).
      - Apply the same `--max-gaze-crapload` enforcement as task 1.1.
      - Wire `--min-contract-coverage` enforcement (already in the stub
        Click decorators — connect to `_check_min_contract_coverage()`
        on the quality-enriched reports when `--tests` resolves).

## 5. Tests

- [ ] 5.1 [P] Create `tests/test_report_ai.py`:
      - `test_call_ai_opencode_success` — mock `_subprocess_run` to
        return `CompletedProcess(stdout="report text", returncode=0)`;
        assert `call_ai("prompt", "payload", provider="opencode")`
        returns `"report text"`
      - `test_call_ai_opencode_with_model` — verify `--model <model>`
        appears in the subprocess args when model is provided
      - `test_call_ai_ollama_requires_model` — `call_ai(..., provider="ollama",
        model=None)` raises `ClickException` containing "model"
      - `test_call_ai_provider_not_found` — mock `shutil.which` to
        return `None`; assert `ClickException` raised with install hint
      - `test_call_ai_timeout` — mock `_subprocess_run` to raise
        `subprocess.TimeoutExpired(cmd=[], timeout=30)`; assert
        `ClickException` raised mentioning "timed out"
      - `test_call_ai_nonzero_exit` — mock returncode=1, stderr="err";
        assert `ClickException` raised containing "err"
      - `test_call_ai_unknown_provider` — `provider="unknown"` raises
        `ClickException`

- [ ] 5.2 [P] Append to `tests/test_cli.py` (no modification to
      existing tests):
      - `test_max_gaze_crapload_exits_1_when_exceeded` — run `crap` on
        `tests/testdata/quality/src/` with `--tests tests/testdata/quality/tests/`
        and `--max-gaze-crapload=0` (any gaze_crapload value > 0 triggers
        exit 1). Assert exit code == 1 and stderr contains "CI gate".
        Note: `detect_and_classify` currently has GazeCRAP=90.0 on
        gaze-py itself; on the quality fixture use a value low enough
        that GazeCRAPload > 0 fires.
      - `test_max_gaze_crapload_help_text_updated` — `gazepy crap --help`
        output does NOT contain "deferred until O1"
      - `test_report_no_ai_emits_json` — `gazepy report` without `--ai`
        on `tests/testdata/quality/src/` exits 0 and stdout is valid JSON
        containing "functions" and "summary"
      - `test_report_with_ai_calls_subprocess` — patch `call_ai` to
        return "narrative text"; assert report command exits 0 and
        stdout == "narrative text"
      - `test_load_report_prompt_uses_local_override` — create a temp
        `workdir/.opencode/agents/gaze-reporter.md` with known content;
        assert `_load_report_prompt(workdir)` returns that content
        (frontmatter stripped)
      - `test_load_report_prompt_falls_back_to_bundled` — when no local
        file exists, assert `_load_report_prompt(tmp_path)` returns a
        non-empty string (the bundled prompt)

## 6. Version bump + CHANGELOG

- [ ] 6.1 Bump version `0.5.0` → `0.5.1` in `pyproject.toml` and
      `src/gaze_py/__init__.py`.

- [ ] 6.2 Add CHANGELOG entry under `## [Unreleased]`:
      ```
      ### Added
      - `gazepy report`: AI-powered narrative reports via subprocess
        adapters (opencode, ollama, claude). Pass --ai opencode to
        generate a report. Without --ai, emits the JSON payload.
      - `gazepy report --tests`: optional quality enrichment for
        GazeCRAP, quadrant, and gap hint data in the report payload.

      ### Fixed
      - `--max-gaze-crapload` now enforced in `crap` and `self-check`
        commands (O5). Previously emitted a stale "deferred until O1"
        warning; O1 has been shipped since v0.3.
      ```

## 7. CI gate

- [ ] 7.1 [P] `uv run ruff check .`
- [ ] 7.2 [P] `uv run ruff format --check .`
- [ ] 7.3 [P] `uv run mypy --strict src/`
- [ ] 7.4     `uv run pytest -m "not slow" --cov=gaze_py --cov-fail-under=85`
