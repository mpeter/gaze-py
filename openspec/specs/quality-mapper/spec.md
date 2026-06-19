# Spec: quality-mapper

Assertion-to-effect mapping for the O1 quality assessment pipeline. Maps
each assertion site detected in a test function to the side effect type it
most likely exercises, using three passes in first-match-wins order.

---

### Requirement: output-length-invariant

`map_assertions_to_effects()` MUST return a list with exactly one entry per
input assertion. The output length MUST always equal `len(assertions)`.
Every assertion gets an entry — `None` is used when no effect can be matched.

#### Scenario: all assertions mapped
- **WHEN** 3 assertions are passed and all match
- **THEN** the result list has exactly 3 entries, all with non-None effect types

#### Scenario: unmapped assertions use None
- **WHEN** an assertion cannot be matched by any pass
- **THEN** its entry in the result is `(assertion, None)`

---

### Requirement: first-match-wins

The three mapping passes MUST be applied in order (Pass 1 → Pass 2 → Pass 3).
Once an assertion is matched in an earlier pass, it MUST NOT be re-evaluated
in later passes. A `matched: set[int]` of already-matched assertion indices
MUST be maintained across all three passes to prevent double-counting.

#### Scenario: pass 1 match prevents pass 2 re-evaluation
- **WHEN** an assertion references a bound return-value variable AND is also
  a raises-kind assertion
- **THEN** it is matched by Pass 1 as `ReturnValue`; Pass 2 does not re-match it

---

### Requirement: pass-1-binding-match

Pass 1 MUST scan `call_bindings` (produced by `build_call_bindings()`) and
map assertions whose `referenced_names` contain a bound variable name:

- Role `"return_value"` → maps to `SideEffectType.ReturnValue`
- Role `"error_return"` → maps to `SideEffectType.ErrorReturn`

#### Scenario: return value binding matched
- **WHEN** `call_bindings={"result": "return_value"}` and assertion references `"result"`
- **THEN** assertion maps to `SideEffectType.ReturnValue`

#### Scenario: error return binding matched
- **WHEN** `call_bindings={"err": "error_return"}` and assertion references `"err"`
- **THEN** assertion maps to `SideEffectType.ErrorReturn`

---

### Requirement: pass-2-exception-match

Pass 2 MUST match unmatched assertions whose `kind` is
`AssertionKind.STDLIB_RAISES` or `AssertionKind.UNITTEST_RAISES` and map
them to `SideEffectType.ErrorReturn`.

#### Scenario: pytest.raises maps to ErrorReturn
- **WHEN** assertion has `kind=STDLIB_RAISES` and was not matched by Pass 1
- **THEN** assertion maps to `SideEffectType.ErrorReturn`

#### Scenario: self.assertRaises maps to ErrorReturn
- **WHEN** assertion has `kind=UNITTEST_RAISES` and was not matched by Pass 1
- **THEN** assertion maps to `SideEffectType.ErrorReturn`

---

### Requirement: pass-3-semantic-match

Pass 3 MUST match remaining unmatched assertions by checking whether any
name in `assertion.referenced_names` appears as a substring in
`effect.target` for any effect on the production `FunctionTarget`. The
first matching effect's `.type` (not `.effect_type`) is used. When no
effect matches, the assertion maps to `None`.

#### Scenario: name overlap with effect target
- **WHEN** assertion references `"output_file"` and an effect has
  `target` containing `"output_file"`
- **THEN** assertion maps to that effect's `SideEffectType`

#### Scenario: no name overlap → None
- **WHEN** no effect target contains any of the assertion's referenced names
- **THEN** assertion maps to `None`

---

### Requirement: call-bindings-construction

`build_call_bindings(test_func, target_name)` MUST scan the test function
body for `ast.Assign` nodes where the right-hand side is a direct call to
`target_name` (an `ast.Call` with `ast.Name` func matching `target_name`).

Binding rules:
- Single `ast.Name` target: `{"name": "return_value"}`
- `ast.Tuple` target with 2+ elements:
  - Index 0 (if `ast.Name`): `"return_value"`
  - Index 1 (if `ast.Name`): `"error_return"`
  - Indices 2+: ignored (only first two bindings named)
- Void call (no assignment): no binding produced

#### Scenario: single return value binding
- **WHEN** test contains `result = compute(x)`
- **THEN** `build_call_bindings()` returns `{"result": "return_value"}`

#### Scenario: tuple unpacking binding
- **WHEN** test contains `value, err = compute(x)`
- **THEN** `build_call_bindings()` returns
  `{"value": "return_value", "err": "error_return"}`

#### Scenario: three-element tuple — only first two bound
- **WHEN** test contains `a, b, c = compute(x)`
- **THEN** `build_call_bindings()` returns
  `{"a": "return_value", "b": "error_return"}` (c is ignored)

#### Scenario: void call produces no binding
- **WHEN** test contains `compute(x)` with no assignment
- **THEN** `build_call_bindings()` returns `{}`

#### Scenario: method call not matched
- **WHEN** test contains `result = obj.compute(x)`
- **THEN** `build_call_bindings()` returns `{}` (method calls are not matched)

---

### Requirement: effect-field-name

All mapper code MUST use `effect.type` (not `effect.effect_type`) when
accessing the `SideEffectType` of a `SideEffect` object. The canonical
field name on `SideEffect` is `type`.

#### Scenario: correct field name used in pass 3
- **WHEN** Pass 3 matches an effect
- **THEN** the result tuple contains `effect.type` (a `SideEffectType` value),
  not `effect.effect_type`
