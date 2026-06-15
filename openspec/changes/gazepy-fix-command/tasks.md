## 1. Create command file

- [x] 1.1 Read `.opencode/commands/gaze-fix.md` in full as structural reference
- [x] 1.2 Create `.opencode/commands/gazepy-fix.md` with no-args workflow detection section (adapted from gaze-fix.md; language-agnostic logic unchanged, fallback option updated to `/gazepy fix src/`)
- [x] 1.3 Add batch remediation section: binary resolution (`uv run gazepy` first, then `which gazepy`), `gazepy crap --format=json [path]` and `gazepy quality --format=json [path]` analysis steps
- [x] 1.4 Add target list builder: priority order (`add_tests` desc CRAP → `add_assertions` → `add_docs` → `decompose_and_test`; skip `decompose`; `add_docs` filter: `contract_coverage_reason == "all_effects_ambiguous"` AND `effect_confidence_range[0] >= 58`); apply `--strategy` and `--top=N`
- [x] 1.5 Add per-target processing: read function source via `file`/`line`; look up `tests/test_<module>.py`; extract quality data by function name; delegate to `gazepy-test-generator` agent; `--dry-run` mode shows code without writing
- [x] 1.6 Add verification step: `uv run pytest --tb=short -k "TestName1 or TestName2..."`
- [x] 1.7 Add report template and error handling section

## 2. Verify gaze-fix.md is unmodified

- [x] 2.1 Run `git diff HEAD -- .opencode/commands/gaze-fix.md` and confirm output is empty

## 3. CI gate

- [x] 3.1 Run `uv run ruff check .` — must pass
- [x] 3.2 Run `uv run ruff format --check .` — must pass
- [x] 3.3 Run `uv run mypy --strict src/` — must pass
- [x] 3.4 Run `uv run pytest --cov=gaze_py --cov-fail-under=85` — must pass
