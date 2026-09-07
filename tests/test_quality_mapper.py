"""Tests for quality/mapper.py — A.3 assertion-to-effect mapping."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

# CR-004: the mapper's public context accepts TestFunc import bindings; this
# helper supplies that internal pipeline value without duplicating import parsing.
from gaze_py.quality._identity import _collect_module_aliases
from gaze_py.quality.assertions import detect_assertions
from gaze_py.quality.mapper import build_call_bindings, map_assertions_to_effects
from gaze_py.quality.models import TestFunc
from gaze_py.quality.pairing import find_test_functions
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
                module_aliases=_collect_module_aliases(module),
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


def _map_source(src: str, effects: list[SideEffect]) -> list[SideEffectType | None]:
    """Map assertions from source with full test-function context."""
    test_func = _make_test_func("from example import example_fn\n" + textwrap.dedent(src))
    mapped = map_assertions_to_effects(
        detect_assertions(test_func),
        _make_target(effects),
        build_call_bindings(test_func, "example_fn"),
        test_func=test_func,
        target_path=Path("/project/src/example.py"),
        import_root=Path("/project/src"),
    )
    return [effect_type for _, effect_type in mapped]


def _map_import_source(
    tmp_path: Path,
    src: str,
    effects: list[SideEffect],
    *,
    target_path: Path,
) -> list[SideEffectType | None]:
    """Map a source file whose imports participate in target identity."""
    test_path = tmp_path / "test_example.py"
    test_path.write_text(textwrap.dedent(src), encoding="utf-8")
    test_funcs = find_test_functions(test_path)
    assert len(test_funcs) == 1
    test_func = test_funcs[0]
    mapped = map_assertions_to_effects(
        detect_assertions(test_func),
        _make_target(effects),
        build_call_bindings(test_func, "example_fn"),
        test_func=test_func,
        target_path=target_path,
        import_root=Path("/project/src"),
    )
    return [effect_type for _, effect_type in mapped]


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


# ---------------------------------------------------------------------------
# Module-aliased call bindings (#65)
# ---------------------------------------------------------------------------


def test_build_call_bindings_module_aliased_call() -> None:
    """drafts = dq.parse_drafts(msgs) → {"drafts": "return_value"} (#65)."""
    tf = _make_test_func("""
    def test_example() -> None:
        drafts = dq.parse_drafts(msgs)
        assert len(drafts) == 1
    """)
    bindings = build_call_bindings(tf, "parse_drafts")
    assert bindings == {"drafts": "return_value"}


def test_build_call_bindings_aliased_tuple_unpack() -> None:
    """x, err = mod.fn(a) → {"x": "return_value", "err": "error_return"}."""
    tf = _make_test_func("""
    def test_example() -> None:
        x, err = mod.compute(a)
        assert x == 42
    """)
    bindings = build_call_bindings(tf, "compute")
    assert bindings == {"x": "return_value", "err": "error_return"}


def test_build_call_bindings_aliased_void_call() -> None:
    """alias.fn() with no assignment → {} (no binding)."""
    tf = _make_test_func("""
    def test_example() -> None:
        mod.setup()
        assert True
    """)
    bindings = build_call_bindings(tf, "setup")
    assert bindings == {}


# ---------------------------------------------------------------------------
# Annotated assignment bindings (Bug D)
# ---------------------------------------------------------------------------


def test_build_call_bindings_annotated_assignment() -> None:
    """result: int = example_fn(1) → {"result": "return_value"} (Bug D)."""
    tf = _make_test_func("""
    def test_example() -> None:
        result: int = example_fn(1, 2)
        assert result == 3
    """)
    bindings = build_call_bindings(tf, "example_fn")
    assert bindings == {"result": "return_value"}


def test_build_call_bindings_annotated_aliased() -> None:
    """result: int = mod.fn(1) → {"result": "return_value"}."""
    tf = _make_test_func("""
    def test_example() -> None:
        result: int = mod.compute(1, 2)
        assert result == 3
    """)
    bindings = build_call_bindings(tf, "compute")
    assert bindings == {"result": "return_value"}


@pytest.mark.parametrize(
    "body",
    [
        'out, err = capsys.readouterr()\nassert "expected" in out',
        'captured = capsys.readouterr()\nassert "expected" in captured.out',
        'out = capsys.readouterr().out\nassert "expected" in out',
        'assert "expected" in capsys.readouterr().out',
        (
            "captured = capsys.readouterr()\n"
            "actual = json.loads(captured.out)\n"
            'assert actual == {"ok": True}'
        ),
    ],
)
def test_map_attributable_captured_stdout(body: str) -> None:
    """Supported capsys stdout forms map to an existing StdoutWrite effect."""
    capture_body = textwrap.indent(body, "    ")
    mapped = _map_source(
        f"import json\n\ndef test_example(capsys) -> None:\n    result = example_fn()\n"
        f"    assert result == 0\n{capture_body}\n",
        [_make_effect(SideEffectType.ReturnValue), _make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [SideEffectType.ReturnValue, SideEffectType.StdoutWrite]


@pytest.mark.parametrize(
    ("fixture", "stream", "effect_type"),
    [
        ("capsys", "out", SideEffectType.StdoutWrite),
        ("capsys", "err", SideEffectType.StderrWrite),
        ("capfd", "out", SideEffectType.StdoutWrite),
        ("capfd", "err", SideEffectType.StderrWrite),
    ],
)
def test_map_capture_stream_identity(
    fixture: str,
    stream: str,
    effect_type: SideEffectType,
) -> None:
    """Capture attributes preserve stdout/stderr identity for both pytest fixtures."""
    mapped = _map_source(
        f"""
        def test_example({fixture}) -> None:
            example_fn()
            captured = {fixture}.readouterr()
            assert "expected" in captured.{stream}
        """,
        [_make_effect(effect_type)],
    )
    assert mapped == [effect_type]


def test_return_binding_precedes_capture_mapping() -> None:
    """An assertion mentioning result and captured output maps once to ReturnValue."""
    mapped = _map_source(
        """
        from unittest import mock

        def test_example(capsys) -> None:
            result = example_fn()
            captured = capsys.readouterr()
            assert result == 0 and captured.out == "expected"
        """,
        [_make_effect(SideEffectType.ReturnValue), _make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [SideEffectType.ReturnValue]


def test_capture_inside_mock_patch_context_is_conservatively_unmapped() -> None:
    """Even a real mock.patch context has unsupported enter and exit behavior."""
    mapped = _map_source(
        """
        from unittest import mock

        def test_example(capsys) -> None:
            with mock.patch("module.dependency"):
                example_fn()
                captured = capsys.readouterr()
                assert "expected" in captured.out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None]


def test_capture_mapping_after_patch_object_context_is_conservatively_unmapped() -> None:
    """Fieldkit's patch.object shape needs an explicit capture boundary inside with."""
    mapped = _map_source(
        """
        import json
        import src.example as module
        from unittest.mock import MagicMock, patch

        def test_example(capsys) -> None:
            with patch.object(module, "dependency", return_value=MagicMock()):
                result = module.example_fn()
            assert result == 0
            stdout = capsys.readouterr().out
            assert "expected" in stdout
            payload = json.loads(stdout)
            assert payload == {"ok": True}
        """,
        [_make_effect(SideEffectType.ReturnValue), _make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None, None, None]


def test_explicit_capture_boundaries_isolate_unknown_context_output() -> None:
    """Drain-target-save inside with isolates entry noise and preserves the saved snapshot."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            with unknown_context():
                capsys.readouterr()
                example_fn()
                stdout = capsys.readouterr().out
            assert "expected" in stdout
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [SideEffectType.StdoutWrite]


def test_inline_saved_drain_restores_clean_window_before_target() -> None:
    """A definite direct stream read drains ambiguity before a later target call."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            unknown_writer()
            old = capsys.readouterr().out
            example_fn()
            assert "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [SideEffectType.StdoutWrite]


def test_target_argument_call_makes_capture_ambiguous() -> None:
    """A call evaluated as a target argument can also produce captured output."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            example_fn(other_producer())
            assert "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "body",
    [
        """
        captured = capsys.readouterr()
        example_fn()
        assert "old" in captured.out
        """,
        """
        example_fn()
        capsys.readouterr()
        assert "new" in capsys.readouterr().out
        """,
        """
        example_fn()
        out = capsys.readouterr().out
        out = "replacement"
        assert "expected" in out
        """,
        """
        example_fn()
        other_producer()
        assert "expected" in capsys.readouterr().out
        """,
        """
        other_producer()
        example_fn()
        assert "expected" in capsys.readouterr().out
        """,
        """
        example_fn()
        other_producer()
        example_fn()
        assert "expected" in capsys.readouterr().out
        """,
        """
        def nested() -> None:
            example_fn()
        assert "expected" in capsys.readouterr().out
        """,
    ],
)
def test_rejects_unattributable_captured_stdout(body: str) -> None:
    """Ordering, drain, overwrite, ambiguity, and nested calls do not earn credit."""
    test_body = textwrap.indent(textwrap.dedent(body).strip(), "    ")
    mapped = _map_source(
        f"def test_example(capsys) -> None:\n{test_body}\n",
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


def test_rejects_non_fixture_capture_object() -> None:
    """A readouterr method on a non-parameter object is not a pytest capture fixture."""
    mapped = _map_source(
        """
        def test_example() -> None:
            example_fn()
            out = capsys.readouterr().out
            assert "expected" in out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


def test_rejects_reassigned_capture_fixture() -> None:
    """Reassigning capsys removes its fixture provenance."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            capsys = fake_capture
            example_fn()
            assert "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


def test_wrong_stream_does_not_fall_through_to_semantic_mapping() -> None:
    """Captured stderr cannot claim a stdout-only effect through name overlap."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            example_fn()
            captured = capsys.readouterr()
            assert "expected" in captured.err
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="err")],
    )
    assert mapped == [None]


def test_arbitrary_helper_does_not_propagate_capture_provenance() -> None:
    """Only json.loads is a supported value-preserving capture transform."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            example_fn()
            captured = capsys.readouterr()
            actual = arbitrary_helper(captured.out)
            assert actual == "expected"
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="actual")],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "source",
    [
        """
        def test_example(capsys, json) -> None:
            example_fn()
            captured = capsys.readouterr()
            actual = json.loads(captured.out)
            assert actual == {"ok": True}
        """,
        """
        import json

        def test_example(capsys) -> None:
            example_fn()
            captured = capsys.readouterr()
            actual = json.loads(captured.out, object_hook=hook)
            assert actual == {"ok": True}
        """,
    ],
)
def test_unproven_or_callback_json_loads_does_not_propagate(source: str) -> None:
    """Only unshadowed stdlib json.loads with one positional argument is supported."""
    mapped = _map_source(source, [_make_effect(SideEffectType.StdoutWrite, target="actual")])
    assert mapped == [None]


def test_assertion_call_taints_pending_capture() -> None:
    """A producer called inside an assertion makes later capture attribution ambiguous."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            example_fn()
            assert unrelated_writer()
            assert "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None, None]


def test_unrelated_call_inside_capture_assertion_rejects_credit() -> None:
    """A capture assertion with another call has ambiguous output provenance."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            example_fn()
            assert other_producer() and "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "definition",
    [
        "def nested(value=noisy_default()):\n        pass",
        "@noisy_decorator\ndef nested():\n        pass",
        "def nested(value: annotation_factory()):\n        pass",
        "class Nested:\n        noisy_class_body()",
    ],
)
def test_nested_definition_execution_taints_pending_capture(definition: str) -> None:
    """Executable function headers and class definitions make capture ambiguous."""
    nested_definition = textwrap.indent(definition, "    ")
    mapped = _map_source(
        f"def test_example(capsys) -> None:\n    example_fn()\n"
        f'{nested_definition}\n    assert "expected" in capsys.readouterr().out\n',
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None]


def test_non_mock_context_manager_taints_pending_capture() -> None:
    """Unknown context enter/exit behavior makes later capture ambiguous."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            example_fn()
            with noisy_context():
                value = 1
            assert "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None]


def test_mock_patch_callable_factory_taints_pending_capture() -> None:
    """A mock.patch new_callable can produce output while entering the context."""
    mapped = _map_source(
        """
        from unittest import mock

        def test_example(capsys) -> None:
            example_fn()
            with mock.patch("module.name", new_callable=noisy_factory):
                value = 1
            assert "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None]


def test_malformed_assertion_location_remains_unmapped() -> None:
    """Optional AST context does not make legacy malformed locations raise."""
    test_func = _make_test_func(
        """
        def test_example(capsys) -> None:
            example_fn()
            assert "expected" in capsys.readouterr().out
        """
    )
    assertion = AssertionSite(
        location="legacy-location",
        kind=AssertionKind.STDLIB_EQUALITY,
        depth=0,
        referenced_names=frozenset({"out"}),
    )
    mapped = map_assertions_to_effects(
        [assertion],
        _make_target([_make_effect(SideEffectType.StdoutWrite)]),
        {},
        test_func=test_func,
    )
    assert mapped == [(assertion, None)]


def test_qualified_import_alias_matches_exact_target_module() -> None:
    """A qualified call through the target module's import alias earns credit."""
    mapped = _map_source(
        """
        import example as module

        def test_example(capsys) -> None:
            module.example_fn()
            assert "expected" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [SideEffectType.StdoutWrite]


@pytest.mark.parametrize(
    "source",
    [
        """
        import other.example as module

        def test_example(capsys) -> None:
            module.example_fn()
            assert "expected" in capsys.readouterr().out
        """,
        """
        def test_example(capsys) -> None:
            receiver.example_fn()
            assert "expected" in capsys.readouterr().out
        """,
        """
        import src.example as module

        def test_example(capsys) -> None:
            module = unrelated
            module.example_fn()
            assert "expected" in capsys.readouterr().out
        """,
        """
        import src.example as module
        module = unrelated

        def test_example(capsys) -> None:
            module.example_fn()
            assert "expected" in capsys.readouterr().out
        """,
    ],
)
def test_qualified_same_name_without_exact_unshadowed_identity_is_rejected(source: str) -> None:
    """Basename collisions, receivers, and shadowed aliases do not earn capture credit."""
    mapped = _map_source(source, [_make_effect(SideEffectType.StdoutWrite)])
    assert mapped == [None]


@pytest.mark.parametrize(
    "shadow",
    [
        "import unrelated as module",
        "del module",
        "(module := unrelated)",
        'with mock.patch("module.name") as module:\n        pass',
    ],
)
def test_qualified_import_alias_shadowing_is_rejected(shadow: str) -> None:
    """Runtime binding forms invalidate a formerly exact module alias."""
    shadow_code = textwrap.indent(shadow, "    ")
    mapped = _map_source(
        "import src.example as module\nfrom unittest import mock\n\n"
        f"def test_example(capsys) -> None:\n{shadow_code}\n"
        '    module.example_fn()\n    assert "expected" in capsys.readouterr().out\n',
        [_make_effect(SideEffectType.StdoutWrite)],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "body",
    [
        "return\n    example_fn()\n    assert 'out' in capsys.readouterr().out",
        "raise RuntimeError\n    example_fn()\n    assert 'out' in capsys.readouterr().out",
        "False and example_fn()\n    assert 'out' in capsys.readouterr().out",
        "[example_fn() for _ in ()]\n    assert 'out' in capsys.readouterr().out",
        "reader = lambda: capsys.readouterr().out\n    example_fn()\n    assert 'out' in reader()",
    ],
)
def test_council_rejects_unreachable_conditional_or_deferred_capture(body: str) -> None:
    """Unsupported execution evidence cannot establish stream coverage."""
    mapped = _map_source(
        f"def test_example(capsys) -> None:\n    {body}\n",
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "body",
    [
        "unknown_writer()\n    if flag:\n        capsys.readouterr()\n    example_fn()",
        "example_fn()\n    if flag:\n        capsys.readouterr()",
    ],
)
def test_council_possible_drain_taints_instead_of_cleaning(body: str) -> None:
    """A possible capture read invalidates certainty and cannot clean the window."""
    mapped = _map_source(
        f"def test_example(capsys) -> None:\n    {body}\n"
        "    assert 'out' in capsys.readouterr().out\n",
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "header",
    [
        "def nested(value: noisy_annotation(), /):",
        "def nested(*values: noisy_annotation()):",
        "def nested(**values: noisy_annotation()):",
    ],
)
def test_council_all_function_header_annotations_taint_capture(header: str) -> None:
    """Every evaluated parameter annotation can pollute pending output."""
    mapped = _map_source(
        "def test_example(capsys) -> None:\n"
        "    example_fn()\n"
        f"    {header}\n"
        "        pass\n"
        "    assert 'out' in capsys.readouterr().out\n",
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


def test_council_capture_reassignment_replaces_stale_return_role() -> None:
    """Assertion-time roles map a reassigned result only to its captured stream."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            result = example_fn()
            result = capsys.readouterr()
            assert "out" in result.out
        """,
        [
            _make_effect(SideEffectType.ReturnValue, target="result"),
            _make_effect(SideEffectType.StdoutWrite, target="out"),
        ],
    )
    assert mapped == [SideEffectType.StdoutWrite]


def test_council_blocked_capture_overrides_live_return_and_semantic_fallback() -> None:
    """Unsupported capture provenance blocks otherwise tempting return and name matches."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            result = example_fn()
            captured = capsys.readouterr()
            transformed = captured.out.split()
            assert result == 0 and transformed == []
        """,
        [
            _make_effect(SideEffectType.ReturnValue, target="result"),
            _make_effect(SideEffectType.StdoutWrite, target="transformed"),
        ],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "body",
    [
        "captured = capsys.readouterr()\n    left = right = captured.out\n    assert left == 'out'",
        (
            "captured = capsys.readouterr()\n    holder.out = captured.out\n"
            "    assert holder.out == 'out'"
        ),
        (
            "captured = capsys.readouterr()\n    holder['out'] = captured.out\n"
            "    assert holder['out'] == 'out'"
        ),
    ],
)
def test_council_unsupported_capture_storage_stays_blocked(body: str) -> None:
    """Unsupported storage cannot regain credit through semantic overlap."""
    mapped = _map_source(
        "def test_example(capsys) -> None:\n    example_fn()\n    " + body + "\n",
        [_make_effect(SideEffectType.StdoutWrite, target="left holder out")],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "mutation",
    ["items.clear()", "unknown_helper(items)", "items[0] = 'replacement'"],
)
def test_council_json_family_mutation_or_escape_blocks_parent(mutation: str) -> None:
    """Mutation or escape of a JSON descendant invalidates its entire provenance family."""
    mapped = _map_source(
        "import json\n\n"
        "def test_example(capsys) -> None:\n"
        "    example_fn()\n"
        "    captured = capsys.readouterr()\n"
        "    payload = json.loads(captured.out)\n"
        "    items = payload['items']\n"
        f"    {mutation}\n"
        "    assert payload == {'items': []}\n",
        [_make_effect(SideEffectType.StdoutWrite, target="payload")],
    )
    assert mapped == [None]


def test_council_json_index_and_alias_preserve_single_stream() -> None:
    """Read-only indexing and direct aliases retain one JSON provenance family."""
    mapped = _map_source(
        """
        import json

        def test_example(capsys) -> None:
            example_fn()
            payload = json.loads(capsys.readouterr().out)
            items = payload["items"]
            alias = items
            assert "expected" in alias[0]
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="alias")],
    )
    assert mapped == [SideEffectType.StdoutWrite]


@pytest.mark.parametrize(
    "json_import",
    ["import json as serializer", "from json import loads"],
)
def test_council_json_import_aliases_remain_unsupported(json_import: str) -> None:
    """Only the documented plain json module binding preserves provenance."""
    call = "serializer.loads" if "serializer" in json_import else "loads"
    mapped = _map_source(
        f"""
        {json_import}

        def test_example(capsys) -> None:
            example_fn()
            payload = {call}(capsys.readouterr().out)
            assert payload == {{"ok": True}}
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="payload")],
    )
    assert mapped == [None]


def test_council_receiver_target_rejects_module_level_same_name(tmp_path: Path) -> None:
    """A module function call cannot prove output for a same-named class method."""
    test_path = tmp_path / "test_example.py"
    test_path.write_text(
        "import pkg.example as module\n\n"
        "def test_example(capsys) -> None:\n"
        "    module.example_fn()\n"
        "    assert 'out' in capsys.readouterr().out\n",
        encoding="utf-8",
    )
    test_func = find_test_functions(test_path)[0]
    target = _make_target([_make_effect(SideEffectType.StdoutWrite, target="out")])
    target.receiver = "Example"
    mapped = map_assertions_to_effects(
        detect_assertions(test_func),
        target,
        build_call_bindings(test_func, "example_fn"),
        test_func=test_func,
        target_path=Path("/project/src/pkg/example.py"),
        import_root=Path("/project/src"),
    )
    assert [effect for _, effect in mapped] == [None]


@pytest.mark.parametrize(
    ("import_line", "expected"),
    [
        ("from pkg.example import example_fn", SideEffectType.StdoutWrite),
        ("from other.example import example_fn", None),
        ("", None),
    ],
)
def test_council_direct_import_requires_exact_canonical_identity(
    tmp_path: Path,
    import_line: str,
    expected: SideEffectType | None,
) -> None:
    """Bare target calls prove capture only through an exact direct import."""
    mapped = _map_import_source(
        tmp_path,
        f"""
        {import_line}

        def test_example(capsys) -> None:
            example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [expected]


@pytest.mark.parametrize(
    "source",
    [
        """
        from other.example import example_fn
        def test_example() -> None:
            result = example_fn()
            assert result == 0
        """,
        """
        def test_example(example_fn) -> None:
            result = example_fn()
            assert result == 0
        """,
    ],
)
def test_council_known_bare_call_conflicts_reject_legacy_return(
    tmp_path: Path,
    source: str,
) -> None:
    """Known imports and parameters cannot use legacy bare return matching."""
    mapped = _map_import_source(
        tmp_path,
        source,
        [_make_effect(SideEffectType.ReturnValue, target="result")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [None]


def test_council_exact_local_import_establishes_identity(tmp_path: Path) -> None:
    """An ordered local direct import may establish exact target identity."""
    mapped = _map_import_source(
        tmp_path,
        """
        def test_example(capsys) -> None:
            from pkg.example import example_fn
            capsys.readouterr()
            example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [SideEffectType.StdoutWrite]


@pytest.mark.parametrize(
    "source",
    [
        """
        import pkg.example as module
        def test_example(capsys, module) -> None:
            module.example_fn()
            assert "out" in capsys.readouterr().out
        """,
        """
        import pkg.example as module
        def test_example(capsys) -> None:
            module.example_fn()
            module = unrelated
            assert "out" in capsys.readouterr().out
        """,
        """
        import pkg.example as module
        def test_example(capsys) -> None:
            if flag:
                import pkg.example as module
            module.example_fn()
            assert "out" in capsys.readouterr().out
        """,
    ],
)
def test_council_lexical_shadowing_never_exposes_module_binding(
    tmp_path: Path,
    source: str,
) -> None:
    """Parameters, later locals, and conditional imports block module identity."""
    mapped = _map_import_source(
        tmp_path,
        source,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "module_statement",
    [
        "if flag:\n    import other.example as module",
        "from other.example import *",
    ],
)
def test_council_module_conditional_or_wildcard_import_blocks_identity(
    tmp_path: Path,
    module_statement: str,
) -> None:
    """Uncertain module bindings cannot remain trusted target aliases."""
    mapped = _map_import_source(
        tmp_path,
        "import pkg.example as module\n"
        + module_statement
        + "\n\ndef test_example(capsys) -> None:\n"
        "    module.example_fn()\n"
        "    assert 'out' in capsys.readouterr().out\n",
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    ("write", "expected"),
    [
        ("module.setting = 1", SideEffectType.StdoutWrite),
        ("module.example_fn = replacement", None),
    ],
)
def test_council_module_member_write_has_precise_identity_effect(
    tmp_path: Path,
    write: str,
    expected: SideEffectType | None,
) -> None:
    """Unrelated member writes preserve an alias; target replacement invalidates it."""
    mapped = _map_import_source(
        tmp_path,
        f"""
        import pkg.example as module
        def test_example(capsys) -> None:
            {write}
            capsys.readouterr()
            module.example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [expected]


@pytest.mark.parametrize("module", ["example", "src.pkg.example"])
def test_council_suffix_import_collision_is_rejected(tmp_path: Path, module: str) -> None:
    """Only the canonical pkg.example module identity may prove attribution."""
    mapped = _map_import_source(
        tmp_path,
        f"""
        import {module} as target_module
        def test_example(capsys) -> None:
            target_module.example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "conditional_drain",
    ["capsys.readouterr() if flag else None", "flag and capsys.readouterr()"],
)
def test_review_conditional_capture_read_cannot_clean_ambiguous_output(
    conditional_drain: str,
) -> None:
    """A branch-dependent drain cannot make the later capture attributable."""
    mapped = _map_source(
        "def test_example(capsys, flag) -> None:\n"
        '    print("noise")\n'
        f"    {conditional_drain}\n"
        "    example_fn()\n"
        '    assert "out" in capsys.readouterr().out\n',
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


@pytest.mark.parametrize(
    "branch_operation",
    ['payload["items"].clear()', "unknown_helper(payload)"],
)
def test_review_branch_json_mutation_invalidates_provenance_family(
    branch_operation: str,
) -> None:
    """A possible nested mutation invalidates the whole captured JSON family."""
    mapped = _map_source(
        "import json\n\n"
        "def test_example(capsys, flag) -> None:\n"
        "    example_fn()\n"
        "    captured = capsys.readouterr()\n"
        "    payload = json.loads(captured.out)\n"
        "    if flag:\n"
        f"        {branch_operation}\n"
        '    assert payload == {"items": []}\n',
        [_make_effect(SideEffectType.StdoutWrite, target="payload")],
    )
    assert mapped == [None]


def test_review_return_inside_sync_with_ends_enclosing_sequence() -> None:
    """Code after an unconditional return in a sync with body is unreachable."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            with ctx():
                return
            capsys.readouterr()
            example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


def test_review_chained_assignment_invalidates_capture_fixture_binding() -> None:
    """A chained name assignment replaces the trusted fixture binding."""
    mapped = _map_source(
        """
        def test_example(capsys) -> None:
            capsys = other = unrelated
            example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]


def test_review_chained_assignment_invalidates_local_target_import(tmp_path: Path) -> None:
    """A chained name assignment replaces a definite local target import."""
    mapped = _map_import_source(
        tmp_path,
        """
        def test_example(capsys) -> None:
            from pkg.example import example_fn
            capsys.readouterr()
            example_fn = alias = replacement
            example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
        target_path=Path("/project/src/pkg/example.py"),
    )
    assert mapped == [None]


def test_review_nested_json_source_call_taints_later_capture() -> None:
    """A producer nested inside json.loads keeps later captured output ambiguous."""
    mapped = _map_source(
        """
        import json

        def test_example(capsys) -> None:
            example_fn()
            captured = capsys.readouterr()
            capsys.readouterr()
            payload = json.loads(helper(captured.out))
            example_fn()
            assert "out" in capsys.readouterr().out
        """,
        [_make_effect(SideEffectType.StdoutWrite, target="out")],
    )
    assert mapped == [None]
