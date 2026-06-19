# Spec: quality-assertions

Assertion detection for the O1 quality assessment pipeline. Walks the body
of a test function using AST-only analysis and classifies each assertion site
by kind, location, depth, and the variable names it references.

---

### Requirement: ast-only-analysis

`detect_assertions()` MUST use Python's `ast` module exclusively. It MUST
NOT execute the analyzed code, import the analyzed module, or use runtime
introspection. All detection is performed on the parsed AST.

#### Scenario: no execution of analyzed code
- **WHEN** a test file imports external modules that are not installed
- **THEN** `detect_assertions()` still succeeds (AST parse does not require
  importable dependencies)

---

### Requirement: stdlib-assert-detection

`detect_assertions()` MUST detect `ast.Assert` nodes and classify each one
into exactly one `AssertionKind` using the following priority order
(first-match-wins):

1. `STDLIB_ERROR_CHECK` — any referenced name in the condition contains
   `"err"` (case-insensitive substring match).
2. `STDLIB_NONE_CHECK` — condition is an `ast.Compare` with `ast.Is` or
   `ast.IsNot` operator and `None` as the comparator.
3. `STDLIB_EQUALITY` — condition is an `ast.Compare` or `ast.BinOp`.
4. `STDLIB_TRUTH` — fallback for all other `ast.Assert` nodes.

Each `ast.Assert` node MUST produce exactly one `AssertionSite`.

#### Scenario: assert with error name → STDLIB_ERROR_CHECK
- **WHEN** test contains `assert err is None`
- **THEN** assertion site has `kind=AssertionKind.STDLIB_ERROR_CHECK`

#### Scenario: assert is None → STDLIB_NONE_CHECK
- **WHEN** test contains `assert result is None` (no "err" in names)
- **THEN** assertion site has `kind=AssertionKind.STDLIB_NONE_CHECK`

#### Scenario: assert equality → STDLIB_EQUALITY
- **WHEN** test contains `assert result == expected`
- **THEN** assertion site has `kind=AssertionKind.STDLIB_EQUALITY`

#### Scenario: bare assert → STDLIB_TRUTH
- **WHEN** test contains `assert result`
- **THEN** assertion site has `kind=AssertionKind.STDLIB_TRUTH`

#### Scenario: assert with message still classified
- **WHEN** test contains `assert result == 42, "wrong value"`
- **THEN** assertion site has `kind=AssertionKind.STDLIB_EQUALITY`

---

### Requirement: pytest-raises-detection

`detect_assertions()` MUST detect `ast.With` nodes where the first context
manager is a call to an attribute named `"raises"` (matching
`pytest.raises(ExcType)`). These MUST produce an `AssertionSite` with
`kind=AssertionKind.STDLIB_RAISES`.

The with-body MUST always be recursed into for nested assertions, regardless
of whether the with-statement itself is a raises context.

#### Scenario: pytest.raises context manager
- **WHEN** test contains `with pytest.raises(ValueError): target(...)`
- **THEN** assertion site has `kind=AssertionKind.STDLIB_RAISES`

#### Scenario: nested assertion inside with block
- **WHEN** test contains `with some_context(): assert result == 1`
- **THEN** the inner `assert result == 1` is also detected as an assertion site

---

### Requirement: unittest-style-detection

`detect_assertions()` MUST detect bare call expression statements of the
form `self.assertXxx(...)` and classify them as follows:

- `self.assertEqual`, `self.assertNotEqual`, `self.assertAlmostEqual`,
  `self.assertGreater`, `self.assertLess`, `self.assertIn`,
  `self.assertNotIn`, `self.assertIs`, `self.assertIsNot` →
  `AssertionKind.UNITTEST_EQUAL`
- `self.assertIsNone`, `self.assertIsNotNone` →
  `AssertionKind.UNITTEST_NONE`
- `self.assertRaises`, `self.assertRaisesRegex` →
  `AssertionKind.UNITTEST_RAISES`

Only calls where the receiver is `self` (an `ast.Name` with `id="self"`)
are matched.

#### Scenario: assertEqual detected
- **WHEN** test contains `self.assertEqual(result, expected)`
- **THEN** assertion site has `kind=AssertionKind.UNITTEST_EQUAL`

#### Scenario: assertRaises detected
- **WHEN** test contains `self.assertRaises(ValueError, target, arg)`
- **THEN** assertion site has `kind=AssertionKind.UNITTEST_RAISES`

#### Scenario: assertIsNone detected
- **WHEN** test contains `self.assertIsNone(result)`
- **THEN** assertion site has `kind=AssertionKind.UNITTEST_NONE`

---

### Requirement: assertion-location

Every `AssertionSite` MUST carry a `location` string in `"file:line:col"`
format (three-part, matching `SideEffect.location` format). When the AST
node has no column information, `col=0` MUST be used:
`f"{filepath}:{node.lineno}:0"`.

#### Scenario: location includes file, line, and column
- **WHEN** an `assert` statement is at line 42, column 4 of `tests/test_foo.py`
- **THEN** `AssertionSite.location == "tests/test_foo.py:42:4"`

#### Scenario: missing column defaults to 0
- **WHEN** an AST node has no `col_offset` attribute
- **THEN** location is `"file:lineno:0"`

---

### Requirement: referenced-names-extraction

Every `AssertionSite` MUST carry a `referenced_names: frozenset[str]`
containing variable names referenced in the assertion expression. The
extraction rules are:

- `ast.Name` → add `node.id`
- `ast.Attribute` → add `node.attr` AND recursively collect from `node.value`
- `ast.Subscript` → collect from `node.value` (e.g., `"result"` from
  `result[0]`) and from the slice
- `ast.Call` → add the function name string (e.g., `"f"` from `f()`);
  collect from arguments

#### Scenario: simple name reference
- **WHEN** assertion is `assert result == 42`
- **THEN** `referenced_names` contains `"result"`

#### Scenario: subscript reference
- **WHEN** assertion is `assert result[0] == 1`
- **THEN** `referenced_names` contains `"result"`

#### Scenario: attribute reference
- **WHEN** assertion is `assert obj.value == 42`
- **THEN** `referenced_names` contains both `"obj"` and `"value"`

#### Scenario: call reference
- **WHEN** assertion is `assert f() == g()`
- **THEN** `referenced_names` contains `"f"` and `"g"`

---

### Requirement: assertion-depth

Every `AssertionSite` MUST carry a `depth: int` field:
- `depth=0` for assertions directly in the test function body.
- `depth=1` through `depth=max_depth` for assertions inside helper
  functions that are recursed into.

#### Scenario: direct assertion has depth 0
- **WHEN** `assert result == 1` is in the test function body
- **THEN** `AssertionSite.depth == 0`

#### Scenario: helper assertion has depth 1
- **WHEN** test calls `assert_valid(result)` and the helper contains
  `assert result is not None`
- **THEN** the inner assertion site has `depth=1`

---

### Requirement: helper-recursion

`detect_assertions()` MUST recurse into helper functions whose names start
with `"assert_"` or `"check_"`, up to `max_depth` levels (default 3).
Helper functions are looked up in `pkg_ast` (a `dict[str, ast.Module]`
mapping module name to parsed AST). Recursion MUST stop at `depth ==
max_depth`. When `pkg_ast` is `None` or empty, helper recursion is disabled.

#### Scenario: assert_ helper recursed
- **WHEN** test calls `assert_valid(x)` and `assert_valid` is defined in
  `pkg_ast` with body `assert x is not None`
- **THEN** the inner assertion is detected at `depth=1`

#### Scenario: recursion stops at max_depth
- **WHEN** `max_depth=1` and a helper calls another helper
- **THEN** the second-level helper is not recursed into

#### Scenario: helper not in pkg_ast is skipped
- **WHEN** test calls `assert_valid(x)` but `assert_valid` is not in `pkg_ast`
- **THEN** no recursion occurs; no assertion is emitted for the helper call

---

### Requirement: compound-statement-traversal

`detect_assertions()` MUST recurse into compound statements (`if`, `for`,
`try`, `while`, etc.) to find assertions nested inside them.

#### Scenario: assertion inside if block
- **WHEN** test contains `if condition: assert result == 1`
- **THEN** the inner assertion is detected

#### Scenario: assertion inside try block
- **WHEN** test contains `try: ... except: assert err is None`
- **THEN** the inner assertion is detected
