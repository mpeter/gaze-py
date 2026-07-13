"""Tests for the detect+classify runner — per-effect classification (G2/G3).

Covers the two pipeline gaps from docs/audit-2026-07-12.md:

- G2: classification is attached per effect (SideEffect.classification),
  matching Go's schema (types.go SideEffect.Classification). The legacy
  per-function slot silently kept only the last effect's result and is no
  longer populated.
- G3: the runner threads detector-captured context — docstring, class
  bases, return type hint, receiver — into ClassificationEngine.classify(),
  so Signals 1/2/5 no longer run blind in the analyze/crap path.

All tests write fixture source into tmp_path and run detect_and_classify().
"""

from __future__ import annotations

from pathlib import Path

from gaze_py.analysis.runner import detect_and_classify
from gaze_py.config.loader import GazeConfig
from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.models import FunctionTarget

_MULTI_EFFECT_SOURCE = '''\
class Store:
    def save_user(self, user) -> bool:
        """Persists the user to the database and returns success."""
        self.last_user = user
        print("saved")
        return True
'''


def _analyze(tmp_path: Path, source: str) -> list[FunctionTarget]:
    """Write source to tmp_path and run the detect+classify pipeline."""
    (tmp_path / "fixture.py").write_text(source, encoding="utf-8")
    return detect_and_classify(tmp_path, config=GazeConfig())


def _single_target(tmp_path: Path, source: str, name: str) -> FunctionTarget:
    """Analyze source and return the single named target."""
    targets = [t for t in _analyze(tmp_path, source) if t.function == name]
    assert len(targets) == 1, f"expected exactly one target named {name!r}"
    return targets[0]


class TestPerEffectClassification:
    """G2: every effect carries its own classification."""

    def test_every_effect_carries_classification(self, tmp_path: Path) -> None:
        """All detected effects have a non-None classification attached."""
        target = _single_target(tmp_path, _MULTI_EFFECT_SOURCE, "save_user")
        assert len(target.effects) >= 3, f"expected >=3 effects, got {target.effects}"
        for effect in target.effects:
            assert effect.classification is not None, f"{effect.type} has no classification"

    def test_multi_effect_labels_are_independent(self, tmp_path: Path) -> None:
        """Effects on one function classify independently, not last-wins.

        ReceiverMutation on a docstring-documented public method is
        contractual; StdoutWrite on the same method is not — a per-function
        single slot could never represent both.
        """
        target = _single_target(tmp_path, _MULTI_EFFECT_SOURCE, "save_user")
        by_type = {e.type: e.classification for e in target.effects}
        assert by_type[SideEffectType.ReceiverMutation] is not None
        assert by_type[SideEffectType.StdoutWrite] is not None
        assert by_type[SideEffectType.ReceiverMutation].label == "contractual"
        assert by_type[SideEffectType.StdoutWrite].label != "contractual"

    def test_legacy_function_slot_not_populated(self, tmp_path: Path) -> None:
        """The per-function classification slot stays None (G2)."""
        target = _single_target(tmp_path, _MULTI_EFFECT_SOURCE, "save_user")
        assert target.classification is None


class TestContextThreading:
    """G3: detector context reaches the classification signals."""

    def test_docstring_reaches_docstring_signal(self, tmp_path: Path) -> None:
        """A 'returns'-documenting docstring produces a direct godoc signal.

        Before G3 the runner never passed the function docstring, so Signal 5
        could only ever see project docs text.
        """
        source = '''\
def compute(x: int) -> int:
    """Returns the doubled value."""
    return x * 2
'''
        target = _single_target(tmp_path, source, "compute")
        return_effects = [e for e in target.effects if e.type == SideEffectType.ReturnValue]
        assert len(return_effects) == 1
        classification = return_effects[0].classification
        assert classification is not None
        sources = {s.source for s in classification.signals}
        assert "godoc" in sources, f"docstring signal missing; got {sources}"

    def test_return_annotation_reaches_visibility_signal(self, tmp_path: Path) -> None:
        """A return type hint contributes the visibility signal (Signal 2)."""
        source = "def compute(x: int) -> int:\n    return x * 2\n"
        target = _single_target(tmp_path, source, "compute")
        classification = target.effects[0].classification
        assert classification is not None
        sources = {s.source for s in classification.signals}
        assert "visibility" in sources, f"visibility signal missing; got {sources}"

    def test_abc_base_reaches_interface_signal(self, tmp_path: Path) -> None:
        """Methods on an ABC subclass get the +30 interface signal (Signal 1)."""
        source = """\
from abc import ABC

class Repo(ABC):
    def save(self, item):
        self.items = item
"""
        target = _single_target(tmp_path, source, "save")
        classification = target.effects[0].classification
        assert classification is not None
        sources = {s.source for s in classification.signals}
        assert "interface" in sources, f"interface signal missing; got {sources}"

    def test_detector_captures_context_fields(self, tmp_path: Path) -> None:
        """FunctionTarget carries docstring, class bases, and return hint."""
        source = '''\
from abc import ABC

class Repo(ABC):
    def save(self, item) -> bool:
        """Saves the item."""
        self.items = item
        return True
'''
        target = _single_target(tmp_path, source, "save")
        assert target.docstring == "Saves the item."
        assert target.class_bases == ["ABC"]
        assert target.return_type_hint == "bool"
        assert target.receiver == "Repo"

    def test_module_level_function_has_no_class_context(self, tmp_path: Path) -> None:
        """Standalone functions have None class_bases and receiver."""
        source = "def compute(x):\n    return x\n"
        target = _single_target(tmp_path, source, "compute")
        assert target.class_bases is None
        assert target.receiver is None
        assert target.docstring is None
        assert target.return_type_hint is None


class TestCallerSignalWiring:
    """Signal 3: build_caller_map counts referencing modules; runner wires it.

    Regression: detect_and_classify hardcoded callers=None, so the
    implemented caller_signal never fired anywhere in gaze-py. Go parity
    (classify/callers.go): distinct packages referencing the function,
    excluding the definer, weight 1→+5, 2–3→+10, 4+→+15.
    """

    def test_build_caller_map_counts_distinct_modules(self, tmp_path: Path) -> None:
        """Two referencing modules → count 2; defining module excluded."""
        from gaze_py.analysis.runner import build_caller_map

        (tmp_path / "core.py").write_text("def shared_helper():\n    return 1\n", encoding="utf-8")
        (tmp_path / "user_a.py").write_text(
            "from core import shared_helper\n\ndef go_a():\n    return shared_helper()\n",
            encoding="utf-8",
        )
        (tmp_path / "user_b.py").write_text(
            "import core\n\ndef go_b():\n    return core.shared_helper()\n",
            encoding="utf-8",
        )

        callers = build_caller_map(sorted(tmp_path.glob("*.py")))
        assert callers.get("shared_helper") == 2
        # go_a / go_b are referenced nowhere else → absent (count 0 omitted).
        assert "go_a" not in callers
        assert "go_b" not in callers

    def test_defining_module_self_reference_not_counted(self, tmp_path: Path) -> None:
        """Recursion / same-module calls do not count as callers (Go parity)."""
        from gaze_py.analysis.runner import build_caller_map

        (tmp_path / "solo.py").write_text("def lonely():\n    return lonely()\n", encoding="utf-8")
        callers = build_caller_map([tmp_path / "solo.py"])
        assert "lonely" not in callers

    def test_caller_signal_fires_in_detect_and_classify(self, tmp_path: Path) -> None:
        """A function referenced from another module carries the caller signal."""
        (tmp_path / "core.py").write_text(
            "def compute_answer():\n    return 42\n", encoding="utf-8"
        )
        (tmp_path / "consumer.py").write_text(
            "from core import compute_answer\n\ndef wrap():\n    return compute_answer()\n",
            encoding="utf-8",
        )

        targets = detect_and_classify(tmp_path, config=GazeConfig())
        target = next(t for t in targets if t.function == "compute_answer")
        assert target.caller_count == 1
        effect = target.effects[0]
        assert effect.classification is not None
        sources = {s.source: s.weight for s in effect.classification.signals}
        assert sources.get("caller") == 5, f"expected caller signal +5, got signals: {sources}"
