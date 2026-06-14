# AST fixture — never executed. Parsed by the quality engine only.


def set_label(obj: object, label: str) -> None:
    """Mutate the label attribute on the given object."""
    obj.label = label  # type: ignore[attr-defined]
