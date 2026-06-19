# Spec: quality-pairing

Test-target pairing for the O1 quality assessment pipeline. Discovers test
functions in a test path and pairs each one with its most likely production
function target using four strategies in priority order.

---

### Requirement: find-test-functions

`find_test_functions(filepath)` SHALL parse a Python source file using
`ast.parse()` and return all test functions found. It MUST collect:
- Top-level `FunctionDef` nodes whose name starts with `"test_"`.
- Methods of `ClassDef` nodes whose class name starts with `"Test"` and
  whose method name starts with `"test_"`.

It MUST return an empty list (not raise) when the file cannot be parsed due
to `OSError`, `SyntaxError`, or `ValueError`.

#### Scenario: top-level test function collected
- **WHEN** a file contains `def test_compute(): ...` at module level
- **THEN** `find_test_functions()` returns one `TestFunc` with `name="test_compute"`

#### Scenario: unittest class method collected
- **WHEN** a file contains `class TestFoo: def test_bar(self): ...`
- **THEN** `find_test_functions()` returns one `TestFunc` with `name="test_bar"`

#### Scenario: non-test function excluded
- **WHEN** a file contains `def helper(): ...` and `def compute(): ...`
- **THEN** `find_test_functions()` returns an empty list

#### Scenario: unparseable file returns empty list
- **WHEN** the file has a syntax error or cannot be read
- **THEN** `find_test_functions()` returns `[]` without raising

---

### Requirement: strategy-1-name-convention

`pair_to_targets()` SHALL implement Strategy 1 (name convention) as the
highest-priority strategy. It MUST strip the `"test_"` prefix from the test
function name and compare the remainder against production function names.

- **Exact match** (case-sensitive): confidence MUST be `0.9`;
  `inference_method` MUST be `"name_convention"`.
- **Case-insensitive match** (when no exact match): confidence MUST be `0.7`;
  `inference_method` MUST be `"name_convention"`.
- Strategy 1 MUST fire before Strategies 2, 3, and 4.

#### Scenario: exact name match
- **WHEN** test function is `test_compute` and source contains `compute`
- **THEN** pair has `target_name="compute"`, `inference_method="name_convention"`,
  `confidence=0.9`

#### Scenario: case-insensitive name match
- **WHEN** test function is `test_Compute` and source contains `compute` (no exact match)
- **THEN** pair has `target_name="compute"`, `inference_method="name_convention"`,
  `confidence=0.7`

---

### Requirement: strategy-2-call-graph

`pair_to_targets()` SHALL implement Strategy 2 (AST call graph) when
Strategy 1 finds no match. It MUST perform a deep `ast.walk()` over the
entire test function body (including nested functions, comprehensions, and
`with` blocks) and return the first production function name found in a
direct call (`ast.Name` node). Confidence MUST be `0.8`;
`inference_method` MUST be `"call_graph"`.

`_extract_call_name()` MUST return `None` for method calls and qualified
names — only bare `name(...)` calls are matched.

#### Scenario: direct call in test body
- **WHEN** test body contains `result = process(x)` and `process` is a source function
- **THEN** pair has `target_name="process"`, `inference_method="call_graph"`,
  `confidence=0.8`

#### Scenario: method call not matched by strategy 2
- **WHEN** test body contains only `obj.method()` and `method` is a source function
- **THEN** Strategy 2 finds no match (falls through to Strategy 3 or unmatched)

---

### Requirement: strategy-3-transitive-astroid

`pair_to_targets()` SHALL implement Strategy 3 (transitive call graph via
Astroid) when Strategies 1 and 2 both fail, and only when `astroid_graph`
is provided. It MUST perform a BFS over the Astroid-inferred call graph
up to depth 5, comparing the short name (last segment after `.`) of each
callee FQN against the set of source function names. Confidence MUST be
`0.75`; `inference_method` MUST be `"call_graph_transitive"`.

`_build_astroid_graph()` MUST:
- Call `MANAGER.clear_cache()` at the start of every invocation.
- Load each file via `MANAGER.ast_from_file()`.
- Catch `AstroidBuildingError` per file and emit a `sys.stderr` warning;
  the graph is partial but no exception is raised.
- Catch `InferenceError` per call site and continue.
- Return a `dict[str, set[str]]` mapping caller FQN to callee FQNs.

`_pair_astroid()` MUST use `graph.get(fqn, set())` (never `graph[fqn]`)
to avoid `KeyError` for callees that were never themselves callers.

#### Scenario: transitive match via Astroid
- **WHEN** test calls `engine.classify()` and `classify` transitively calls
  `caller_signal` (a source function), and Strategies 1 and 2 found no match
- **THEN** pair has `target_name="caller_signal"`,
  `inference_method="call_graph_transitive"`, `confidence=0.75`

#### Scenario: strategy 3 skipped when graph not provided
- **WHEN** `astroid_graph=None` is passed to `pair_to_targets()`
- **THEN** Strategy 3 is not attempted; result is `"unmatched"` if Strategies 1
  and 2 also fail

#### Scenario: AstroidBuildingError produces partial graph
- **WHEN** one source file raises `AstroidBuildingError` during graph construction
- **THEN** a warning is written to stderr, the file is skipped, and the graph
  is returned with the remaining files' data (no exception raised)

---

### Requirement: strategy-4-unmatched

When all three strategies fail, `pair_to_targets()` MUST return a
`TestTargetPair` with `target_name=None`, `inference_method="unmatched"`,
and `confidence=0.0`.

When `source_functions` is empty, `pair_to_targets()` MUST return
immediately with `method="unmatched"` without attempting any strategy.

#### Scenario: no source functions
- **WHEN** `source_functions=[]` is passed
- **THEN** pair has `target_name=None`, `inference_method="unmatched"`,
  `confidence=0.0`

#### Scenario: no strategy matches
- **WHEN** test function is `test_xyz` and no source function matches by name,
  call, or transitive call
- **THEN** pair has `target_name=None`, `inference_method="unmatched"`,
  `confidence=0.0`

---

### Requirement: private-function-inclusion

Both public and private (underscore-prefixed) production functions SHALL be
included in the pairing target set by default. `assess()` MUST call
`detect_and_classify()` with `include_unexported=True` (the default).

The `_` prefix in Python is a naming convention, not an access boundary.
Excluding private functions by default was a Go-porting assumption that does
not hold for Python.

#### Scenario: private function paired via name convention
- **WHEN** test function is `test__validate` and source contains `_validate`
- **THEN** pair has `target_name="_validate"`, `inference_method="name_convention"`,
  `confidence=0.9`

#### Scenario: private function appears in pairing target set
- **WHEN** `assess()` is called with default `include_unexported=True`
- **THEN** underscore-prefixed functions are included in `source_targets` and
  are eligible for pairing

---

### Requirement: assess-result-structure

`assess()` MUST return an `AssessResult` dataclass with two fields:
- `reports: tuple[QualityReport, ...]` — one entry per discovered test
  function (paired or unmatched). Every entry has a non-empty `test_function`.
- `untested: tuple[QualityReport, ...]` — one entry per production function
  with detected effects that was never the `target_function` of any
  test-keyed report. Every entry uses `test_function=""` as a sentinel.

`untested` MUST be empty when `target_func` filtering is active (filtered
runs cannot reliably determine which functions are truly untested).

`assess()` MUST return `AssessResult(reports=(), untested=())` (not raise)
when no test functions are found in `tests_path`.

#### Scenario: assess returns reports and untested
- **WHEN** `assess()` runs against a source with 5 functions and tests that
  pair to 2 of them
- **THEN** `result.reports` has 2 entries (one per test function) and
  `result.untested` has 3 entries (one per unmatched source function with effects)

#### Scenario: no test functions found
- **WHEN** `tests_path` contains no test functions
- **THEN** `assess()` returns `AssessResult(reports=(), untested=())`

#### Scenario: filtered assess has empty untested
- **WHEN** `assess()` is called with `target_func="compute"`
- **THEN** `result.untested` is `()`

---

### Requirement: astroid-graph-built-once

`assess()` MUST build the Astroid call graph exactly once per call via
`_build_astroid_graph(test_files, src_files)` and pass the resulting
`dict[str, set[str]]` to each `pair_to_targets()` call. Building the graph
once amortizes the Astroid loading cost across all test functions.

#### Scenario: graph built once per assess call
- **WHEN** `assess()` processes 10 test functions
- **THEN** `_build_astroid_graph()` is called exactly once, not 10 times
