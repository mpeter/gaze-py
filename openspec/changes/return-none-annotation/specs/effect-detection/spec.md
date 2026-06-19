## MODIFIED Requirements

### Requirement: EC-005 Language Adaptation
#### Scenario: return None without annotation is treated as void (G.1 decision)

> **Design decision EC-005/G.1 — 2026-06-18**: `return None` without a return
> type annotation is idiomatically equivalent to a bare `return` in Python.
> Unannotated `return None` is the conventional way to make an implicit `None`
> return explicit for readability — it does not signal that `None` is a
> meaningful return value to callers. Treating it as `ReturnValue` would produce
> false positives on a large class of Python functions that are semantically
> void. This decision is documented in `detector.py` `visit_Return` with
> reference to EC-005/G.1 and the spec archive.

- **WHEN** a function contains `return None` with no return type annotation
- **THEN** the detector does NOT emit a `ReturnValue` effect
- **AND** this is intentional: unannotated `return None` is idiomatically
  equivalent to bare `return` in Python
- **AND** the decision is documented in `detector.py` `visit_Return` with
  reference to EC-005/G.1 and the spec archive

**Contrast with the annotated case** (existing normative requirement in
`openspec/specs/effect-detection/spec.md`, EC-002 "ReturnValue — annotated
return None with non-None annotation"):

- **WHEN** a function is annotated `-> Item | None` (or any non-None return
  type) and the body contains `return None`
- **THEN** a `ReturnValue` effect IS present — the annotation signals that
  `None` is a meaningful member of the return type, not a void sentinel

**Summary of the complete `return None` decision matrix**:

| Return statement | Annotation present? | ReturnValue emitted? |
|-----------------|--------------------|--------------------|
| `return None` | No annotation | No — treated as void (G.1) |
| `return None` | `-> T \| None` or any non-None type | Yes — None is meaningful |
| `return None` | `-> None` | No — explicit void annotation |
| bare `return` | Any | No — no value expression |
| `return <expr>` (non-None) | Any | Yes |
