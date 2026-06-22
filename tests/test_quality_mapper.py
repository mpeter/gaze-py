"""Tests for quality/mapper.py — A.3 assertion-to-effect mapping."""

from __future__ import annotations

import ast
import textwrap

from gaze_py.quality.mapper import build_call_bindings, map_assertions_to_effects
from gaze_py.quality.models import TestFunc
from gaze_py.taxonomy.effects import SideEffectType, Tier
from gaze_py.taxonomy.models import AssertionKind, AssertionSite, FunctionTarget, SideEffect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_func(src: str, name: str = "test_example") -> TestFunc:
    """Parse src and return a TestFunc for the named function."""
    module = ast.parse(textwrap.dedent(src))
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return TestFunc(
                name=name,
                filename="test_example.py",
                lineno=node.lineno,
                node=node,
            )
    raise ValueError(f"Function {name!r} not found in source")


def _make_assertion(
    kind: AssertionKind,
    names: frozenset[str] | None = None,
) -> AssertionSite:
    """Create a minimal AssertionSite."""
    return AssertionSite(
        location="test_example.py:1:0",
        kind=kind,
        depth=0,
        referenced_names=names or frozenset(),
    )


def _make_effect(
    effect_type: SideEffectType,
    target: str = "example_fn",
) -> SideEffect:
    """Create a minimal SideEffect."""
    return SideEffect(
        id="se-00000000",
        type=effect_type,
        tier=Tier.P0,
        location="src/example.py:1:0",
        description="test effect",
        target=target,
    )


def _make_target(effects: list[SideEffect] | None = None) -> FunctionTarget:
    """Create a minimal FunctionTarget."""
    return FunctionTarget(
        function="example_fn",
        file_path="src/example.py",
        line=1,
        complexity=1,
        package="src/example.py",
        receiver=None,
        signature="def example_fn()",
        effects=effects or [],
    )


# ---------------------------------------------------------------------------
# build_call_bindings tests
# ---------------------------------------------------------------------------


def test_build_call_bindings_single_return() -> None:
    """result = target(...) → {"result": "return_value"}."""
    tf = _make_test_func("""
    def test_example() -> None:
        result = example_fn(1, 2)
        assert result == 3
    """)
    bindings = build_call_bindings(tf, "example_fn")
    assert bindings == {"result": "return_value"}


def test_build_call_bindings_tuple_unpack() -> None:
    """x, err = target(...) → {"x": "return_value", "err": "error_return"}."""
    tf = _make_test_func("""
    def test_example() -> None:
        x, err = example_fn(1)
    """)
    bindings = build_call_bindings(tf, "example_fn")
    assert bindings == {"x": "return_value", "err": "error_return"}


def test_build_call_bindings_three_element_unpack() -> None:
    """a, b, c = target(...) → only first two named; index 2+ ignored."""
    tf = _make_test_func("""
    def test_example() -> None:
        a, b, c = example_fn(1)
    """)
    bindings = build_call_bindings(tf, "example_fn")
    assert bindings == {"a": "return_value", "b": "error_return"}
    assert "c" not in bindings


def test_build_call_bindings_void_call() -> None:
    """Void call (no assignment) → empty bindings."""
    tf = _make_test_func("""
    def test_example() -> None:
        example_fn(1)
    """)
    bindings = build_call_bindings(tf, "example_fn")
    assert bindings == {}


def test_build_call_bindings_no_matching_call() -> None:
    """Call to different function → empty bindings."""
    tf = _make_test_func("""
    def test_example() -> None:
        result = other_fn(1)
    """)
    bindings = build_call_bindings(tf, "example_fn")
    assert bindings == {}


# ---------------------------------------------------------------------------
# map_assertions_to_effects tests
# ---------------------------------------------------------------------------


def test_map_return_value_binding() -> None:
    """Return value binding → maps to ReturnValue (Pass 1)."""
    assertion = _make_assertion(AssertionKind.STDLIB_EQUALITY, frozenset({"result"}))
    target = _make_target([_make_effect(SideEffectType.ReturnValue)])
    bindings = {"result": "return_value"}
    mapped = map_assertions_to_effects([assertion], target, bindings)
    assert len(mapped) == 1
    assert mapped[0][1] == SideEffectType.ReturnValue


def test_map_error_return_binding() -> None:
    """Error return binding → maps to ErrorReturn (Pass 1)."""
    assertion = _make_assertion(AssertionKind.STDLIB_EQUALITY, frozenset({"err"}))
    target = _make_target([_make_effect(SideEffectType.ErrorReturn)])
    bindings = {"err": "error_return"}
    mapped = map_assertions_to_effects([assertion], target, bindings)
    assert len(mapped) == 1
    assert mapped[0][1] == SideEffectType.ErrorReturn


def test_map_pytest_raises() -> None:
    """STDLIB_RAISES kind → maps to ErrorReturn (Pass 2).

    pytest.raises() asserts that the target raises an exception, which
    corresponds to the ErrorReturn effect type in the taxonomy.
    """
    assertion = _make_assertion(AssertionKind.STDLIB_RAISES, frozenset({"ValueError"}))
    target = _make_target([_make_effect(SideEffectType.ErrorReturn)])
    bindings: dict[str, str] = {}
    mapped = map_assertions_to_effects([assertion], target, bindings)
    assert len(mapped) == 1
    assert mapped[0][1] == SideEffectType.ErrorReturn


def test_map_pass3_name_match_contractual() -> None:
    """Assertion referencing name matching GlobalMutation effect target → maps to it (Pass 3)."""
    # The effect target is "example_fn" — the assertion references "example_fn".
    assertion = _make_assertion(
        AssertionKind.STDLIB_EQUALITY,
        frozenset({"example_fn"}),
    )
    effect = _make_effect(SideEffectType.GlobalMutation, target="example_fn")
    target = _make_target([effect])
    bindings: dict[str, str] = {}
    mapped = map_assertions_to_effects([assertion], target, bindings)
    assert len(mapped) == 1
    assert mapped[0][1] == SideEffectType.GlobalMutation


def test_map_pass3_incidental_effect() -> None:
    """Assertion matching an incidental effect target → maps to that effect type (Pass 3)."""
    # LogWrite is typically incidental; we just test the mapping logic here.
    assertion = _make_assertion(
        AssertionKind.STDLIB_EQUALITY,
        frozenset({"example_fn"}),
    )
    effect = _make_effect(SideEffectType.LogWrite, target="example_fn")
    target = _make_target([effect])
    bindings: dict[str, str] = {}
    mapped = map_assertions_to_effects([assertion], target, bindings)
    assert len(mapped) == 1
    assert mapped[0][1] == SideEffectType.LogWrite


def test_map_first_match_wins_pass1_over_pass2() -> None:
    """Assertion matching Pass 1 (binding) AND Pass 2 (raises kind) → matched by Pass 1 only."""
    # kind=STDLIB_RAISES AND name in call_bindings → Pass 1 wins.
    assertion = _make_assertion(
        AssertionKind.STDLIB_RAISES,
        frozenset({"result"}),
    )
    target = _make_target([_make_effect(SideEffectType.ReturnValue)])
    bindings = {"result": "return_value"}
    mapped = map_assertions_to_effects([assertion], target, bindings)
    assert len(mapped) == 1
    # Pass 1 matched → ReturnValue, NOT RaiseException.
    assert mapped[0][1] == SideEffectType.ReturnValue
    # Verify it appears exactly once (not duplicated).
    assert len(mapped) == 1


def test_map_unmapped_assertion() -> None:
    """Assertion with no binding, no raises kind, no name match → None.

    Uses names that are not substrings of the effect target ("example_fn")
    to ensure Pass 3 does not accidentally match via substring.
    """
    # "zzz" is not a substring of "example_fn".
    assertion = _make_assertion(AssertionKind.STDLIB_TRUTH, frozenset({"zzz"}))
    target = _make_target([_make_effect(SideEffectType.ReturnValue)])
    bindings: dict[str, str] = {}
    mapped = map_assertions_to_effects([assertion], target, bindings)
    assert len(mapped) == 1
    assert mapped[0][1] is None


def test_map_no_effects_all_unmapped() -> None:
    """Function with no effects → all assertions unmapped."""
    assertions = [
        _make_assertion(AssertionKind.STDLIB_EQUALITY, frozenset({"x"})),
        _make_assertion(AssertionKind.STDLIB_TRUTH, frozenset({"y"})),
    ]
    target = _make_target([])  # no effects
    bindings: dict[str, str] = {}
    mapped = map_assertions_to_effects(assertions, target, bindings)
    assert len(mapped) == len(assertions)
    assert all(et is None for _, et in mapped)


def test_map_multiple_bindings() -> None:
    """Multiple bindings in same test (result, err) → two separate entries."""
    a1 = _make_assertion(AssertionKind.STDLIB_EQUALITY, frozenset({"result"}))
    a2 = _make_assertion(AssertionKind.STDLIB_NONE_CHECK, frozenset({"err"}))
    target = _make_target(
        [
            _make_effect(SideEffectType.ReturnValue),
            _make_effect(SideEffectType.ErrorReturn),
        ]
    )
    bindings = {"result": "return_value", "err": "error_return"}
    mapped = map_assertions_to_effects([a1, a2], target, bindings)
    assert len(mapped) == 2
    types = {et for _, et in mapped}
    assert SideEffectType.ReturnValue in types
    assert SideEffectType.ErrorReturn in types


def test_map_output_length_equals_input_length() -> None:
    """Output length MUST equal input length for every case."""
    assertions = [
        _make_assertion(AssertionKind.STDLIB_EQUALITY, frozenset({"result"})),
        _make_assertion(AssertionKind.STDLIB_RAISES, frozenset()),
        _make_assertion(AssertionKind.STDLIB_TRUTH, frozenset({"x"})),
    ]
    target = _make_target([_make_effect(SideEffectType.ReturnValue)])
    bindings = {"result": "return_value"}
    mapped = map_assertions_to_effects(assertions, target, bindings)
    assert len(mapped) == len(assertions)


def test_map_output_length_no_effects() -> None:
    """Output length equals input length when target has no effects."""
    assertions = [
        _make_assertion(AssertionKind.STDLIB_EQUALITY, frozenset({"x"})),
        _make_assertion(AssertionKind.STDLIB_TRUTH, frozenset({"y"})),
    ]
    target = _make_target([])
    mapped = map_assertions_to_effects(assertions, target, {})
    assert len(mapped) == len(assertions)


def test_map_output_length_all_unmapped() -> None:
    """Output length equals input length when all assertions are unmapped.

    Uses names that are not substrings of the effect target ("example_fn")
    to ensure Pass 3 does not accidentally match via substring.
    """
    # "qqq", "www", "yyy" are not substrings of "example_fn".
    assertions = [
        _make_assertion(AssertionKind.STDLIB_TRUTH, frozenset({"qqq"})),
        _make_assertion(AssertionKind.STDLIB_TRUTH, frozenset({"www"})),
        _make_assertion(AssertionKind.STDLIB_TRUTH, frozenset({"yyy"})),
    ]
    target = _make_target([_make_effect(SideEffectType.ReturnValue)])
    mapped = map_assertions_to_effects(assertions, target, {})
    assert len(mapped) == len(assertions)
    assert all(et is None for _, et in mapped)
