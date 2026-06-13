## Why

The `quality` and `report` commands derive the target source function
from the test file name (`test_apply_intel.py` → `apply_intel`). This
convention fails for:

1. **Module-named test files**: `test_apply_intel.py` tests many
   functions in `apply_intel.py`, not one function named `apply_intel`.
2. **Class-based test suites**: `class TestNamesInFile: def test_extracts_names`
   — `_find_test_function_body()` only finds the first top-level
   `test_` function, skipping class methods entirely.
3. **Scenario-named tests**: `test_skips_red_hat` tests `names_in_file()`,
   not a function called `skips_red_hat`.

This is a bad assumption in the tool, not a problem with the user's
project. Standard pytest projects name test files after the module
they test. gaze-py must infer target functions from what tests
actually call, not from the test file's name.

Observed on fieldkit-cmd: 855 functions analyzed, 0 quality mappings.
Expected: ~300+ mappings across 40+ test files.

## What Changes

### `src/gaze_py/quality.py`

Replace `_find_test_function_body()` with two new functions:

- `_iter_test_functions(tree)` — yields `(qualified_name, body)` for
  every test function in the module, including class methods
  (`TestFoo.test_bar`). Top-level `def test_*` and
  `class TestFoo: def test_*` are both found.

- `_extract_called_names(body)` — returns the set of plain function
  names called anywhere in a test body, by scanning `ast.Call` nodes.
  Handles `foo()`, `module.foo()`, inline calls inside assertions,
  and `pytest.raises` context bodies.

Update `map_assertions()` to:
1. Iterate all test functions (not just the first).
2. Filter to those whose bodies call `target_func`.
3. Merge the filtered bodies and run `AssertionVisitor` once.
4. Fall back to all bodies if none specifically call `target_func`
   (preserves existing behaviour for simple cases).
5. Populate `test_function` field with the actual test method names
   found (e.g. `"TestNamesInFile.test_extracts_names, ..."`) instead
   of the placeholder `"<test_function>"`.

### `src/gaze_py/cli.py` — `report` command

Replace the per-test-file loop (filename → function name heuristic)
with an inverted index approach:

1. Pre-parse all test files once: collect all function names called
   across all test bodies in each file.
2. Build an inverted index: `{function_name: [test_file_source, ...]}`
3. For each source function with side effects, look up the index to
   find which test files call it.
4. Concatenate the relevant test sources and call `map_assertions()`.

This is O(test_files) instead of O(source_functions × test_files),
and correctly handles all naming conventions without heuristics.

Also fix `report` command output: emit `quality_reports +
quality_summary` JSON instead of `analysis` JSON. The `report`
command's purpose is the quality pipeline, not raw side effects.

## Capabilities

### New Capabilities
- `_iter_test_functions(tree)`: yields all test functions including
  class methods, in source order
- `_extract_called_names(body)`: returns set of function names called
  in a test body via AST scan

### Modified Capabilities
- `map_assertions()`: now scans all test bodies for calls to
  `target_func` rather than only the first top-level test function;
  `test_function` field now populated with real test method names
- `report` CLI command: uses inverted index for function-to-test
  matching; emits quality JSON instead of analysis JSON

### Removed Capabilities
- `_find_test_function_body()`: replaced by `_iter_test_functions()`
- Filename-convention heuristic (`test_foo.py → foo`) in `report`
  command: replaced by call-scanning

## Impact

- `src/gaze_py/quality.py`: `_find_test_function_body` removed;
  `_iter_test_functions`, `_extract_called_names` added;
  `map_assertions` signature unchanged, behaviour extended
- `src/gaze_py/cli.py`: `report` command Phase 2 rewritten;
  Phase 3 output changed from analysis to quality JSON
- `tests/test_cli.py`: `test_sc030_report_json_exit_0` updated to
  expect quality JSON keys (`quality_reports`) instead of analysis
  keys (`version`, `results`)
- No changes to `taxonomy.py`, `analysis.py`, `report/`, `crap.py`
- No changes to JSON schema — `map_assertions` signature is unchanged;
  `_iter_test_functions` and `_extract_called_names` are internal

## Constitution Alignment

### I. Accuracy

**Assessment**: PASS

The change eliminates a systematic false-negative: all source
functions called by tests were previously reported as having 0%
contract coverage when tests used standard naming conventions. Fixing
this directly advances the constitution's accuracy requirement.
False negatives MUST be driven toward zero.

### II. Minimal Assumptions

**Assessment**: PASS

The previous implementation assumed `test_foo.py → foo()` naming.
This change replaces that assumption with observation: inspect what
the test actually calls. The fallback (use all test bodies if none
specifically call `target_func`) preserves behaviour for the simple
case with no added assumptions. No source annotation required.

### III. Actionable Output

**Assessment**: PASS

`map_assertions()` now populates `QualityReport.test_function` with
real test method names (e.g. `"TestNamesInFile.test_extracts_names"`)
instead of the placeholder `"<test_function>"`. Reports identify the
specific test and specific unasserted change. The `report` command
now emits quality metrics (coverage %, gap hints) rather than raw
side-effect lists, which is what the command was documented to do.

### IV. Testability

**Assessment**: PASS

`_iter_test_functions` and `_extract_called_names` are pure functions
operating on `ast.Module` / `list[ast.stmt]` — testable in isolation
with no external dependencies. Existing `test_quality.py` tests
continue to pass (the `map_assertions` signature is unchanged).
New tests cover: class-method test discovery, call-name extraction,
multi-test-function merging, and fallback behaviour.
