# ruff: noqa: F821
# AST fixture — never executed. Parsed by the quality engine only.


def test_set_label() -> None:
    obj = object()
    set_label(obj, "hello")
    assert obj.label == "hello"
