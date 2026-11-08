"""Regression coverage for recorded subprocess invocation attribution.

All source strings are parsed, never imported or executed.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gaze_py.analysis.detector import FileDetector
from gaze_py.config.loader import GazeConfig
from gaze_py.quality.assertions import detect_assertions
from gaze_py.quality.mapper import map_assertions_to_effects
from gaze_py.quality.pairing import find_test_functions
from gaze_py.quality.pipeline import assess, build_contract_coverage_map
from gaze_py.taxonomy.effects import SideEffectType

_PRODUCTION = '''
import subprocess

def run_worker(args: list[str]) -> str:
    """Run the worker and return stdout."""
    result = subprocess.run(["worker", *args], capture_output=True, text=True,
                            timeout=30, check=False)
    if result.returncode != 0:
        raise RuntimeError("worker failed")
    return result.stdout
'''

_TEST = """
import subprocess
import client
from client import run_worker

def test_worker(monkeypatch):
    received = {}

    def replacement(argv, **options):
        received.update(args=argv, **options)
        return subprocess.CompletedProcess(argv, 0, stdout="payload", stderr="")

    monkeypatch.setattr(client.subprocess, "run", replacement)
    result = run_worker(["list"])
    assert result == "payload"
    assert received == {"args": ["worker", "list"], "capture_output": True,
                        "text": True, "timeout": 30, "check": False}
"""


def _map_invocation(
    tmp_path: Path, source: str, production: str = _PRODUCTION, *, package: bool = False
) -> list[SideEffectType | None]:
    """Exercise real analysis, pairing, assertion detection and mapping."""
    source_dir = tmp_path / "pkg" if package else tmp_path
    source_dir.mkdir(exist_ok=True)
    target_path = source_dir / "client.py"
    target_path.write_text(textwrap.dedent(production), encoding="utf-8")
    test_path = tmp_path / "test_client.py"
    test_path.write_text(textwrap.dedent(source), encoding="utf-8")
    target = FileDetector.detect(target_path, root=tmp_path)[0]
    test_func = find_test_functions(test_path)[0]
    mapped = map_assertions_to_effects(
        detect_assertions(test_func),
        target,
        {},
        test_func=test_func,
        target_path=target_path,
        import_root=tmp_path,
    )
    return [
        effect
        for _, effect in sorted(mapped, key=lambda pair: int(pair[0].location.rsplit(":", 2)[1]))
    ]


def test_received_invocation_maps_to_spawn(tmp_path: Path) -> None:
    """A real received-arguments assertion covers spawn, not error return."""
    mapped = _map_invocation(tmp_path, _TEST)
    assert mapped == [SideEffectType.ReturnValue, SideEffectType.GoroutineSpawn]


def test_from_package_patch_owner_and_arbitrary_record_names(tmp_path: Path) -> None:
    """Resolve the original package-import form without depending on record names."""
    source = (
        _TEST.replace("import client", "from pkg import client")
        .replace("from client import", "from pkg.client import")
        .replace("received", "observed")
        .replace("replacement", "stand_in")
        .replace("argv", "arguments")
        .replace("options", "settings")
    )
    mapped = _map_invocation(tmp_path, source, package=True)
    assert mapped == [SideEffectType.ReturnValue, SideEffectType.GoroutineSpawn]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("assert received ==", "unrelated = {}\n    assert unrelated =="),
        ('result = run_worker(["list"])', 'result = other_worker(["list"])'),
        ('monkeypatch.setattr(client.subprocess, "run", replacement)', "pass"),
        ("assert received ==", "received = {}\n    assert received =="),
        ("assert received ==", 'received.update(args=["wrong"])\n    assert received =='),
        ('client.subprocess, "run"', 'client.subprocess, "Popen"'),
        ("monkeypatch.setattr", "client = other_client\n    monkeypatch.setattr"),
        ("monkeypatch.setattr", "monkeypatch = other_patch\n    monkeypatch.setattr"),
        (
            'result = run_worker(["list"])',
            'replacement(["other"])\n    result = run_worker(["list"])',
        ),
        ("assert received ==", 'run_worker(["other"])\n    assert received =='),
        (
            'result = run_worker(["list"])',
            'assert received == {}\n    result = run_worker(["list"])',
        ),
        ("received.update(args=argv, **options)", 'received.update(args=["wrong"], **options)'),
        ("assert received ==", "alias = received\n    alias.clear()\n    assert received =="),
        ("assert received ==", "monkeypatch.undo()\n    assert received =="),
        ('"run", replacement', '"run", other_fake'),
        ('client.subprocess, "run"', 'unrelated.subprocess, "run"'),
        ("assert received ==", 'received["args"] = []\n    assert received =='),
        ('assert result == "payload"', 'assert unknown() == "payload"'),
        ("monkeypatch.setattr", "replacement = other_fake\n    monkeypatch.setattr"),
        ('result = run_worker(["list"])', 'received = run_worker(["list"])'),
        ('result = run_worker(["list"])', 'holder.value = run_worker(["list"])'),
        ('result = run_worker(["list"])', 'if ready:\n        result = run_worker(["list"])'),
        ("def replacement(argv, **options):", "def replacement(subprocess, **options):"),
    ],
    ids=[
        "unrelated-record",
        "unrelated-target",
        "unused-fake",
        "rebound-record",
        "overwritten-record",
        "wrong-boundary",
        "shadowed-module",
        "shadowed-fixture",
        "shared-fake",
        "multiple-exercises",
        "early-empty-assertion",
        "fabricated-record",
        "escaped-record",
        "patch-undone",
        "different-fake",
        "different-module",
        "subscript-overwrite",
        "assertion-call",
        "fake-rebound",
        "target-overwrites-record",
        "escaping-target-result",
        "conditional-target",
        "fake-shadows-subprocess",
    ],
)
def test_missing_or_ambiguous_invocation_is_unmapped(tmp_path: Path, old: str, new: str) -> None:
    """Missing causal evidence must not grant spawn coverage."""
    mapped = _map_invocation(tmp_path, _TEST.replace(old, new))
    if old == 'result = run_worker(["list"])' and new.startswith("assert"):
        assert mapped[0] is None
    else:
        assert mapped[-1] is None


@pytest.mark.parametrize(
    ("caller_count", "confidence", "total", "percentage"),
    [(0, 69, 2, 50.0), (1, 74, 2, 50.0), (2, 79, 3, 200 / 3)],
)
def test_caller_promotion_preserves_max_per_test_policy(
    *, tmp_path: Path, caller_count: int, confidence: int, total: int, percentage: float
) -> None:
    """Attribution improves one success test, never unions it with error tests."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text(_PRODUCTION, encoding="utf-8")
    for number in range(caller_count):
        (src / f"caller_{number}.py").write_text(
            'from client import run_worker\n\ndef use_worker():\n    return run_worker(["list"])\n',
            encoding="utf-8",
        )
    tests = tmp_path / "test_client.py"
    tests.write_text(
        _TEST
        + """
import pytest

def test_worker_failure(monkeypatch):
    def failing(argv, **options):
        return subprocess.CompletedProcess(argv, 9, stdout="", stderr="failure")
    monkeypatch.setattr(client.subprocess, "run", failing)
    with pytest.raises(RuntimeError, match="worker failed"):
        run_worker(["list"])
""",
        encoding="utf-8",
    )
    config = GazeConfig(contractual_threshold=75, incidental_threshold=50)
    result = assess(src, tests, config=config, target_func="run_worker")
    assert len(result.reports) == 2
    success = next(report for report in result.reports if report.test_function == "test_worker")
    assert success.target_function is not None
    spawn = next(
        effect
        for effect in success.target_function.effects
        if effect.type == SideEffectType.GoroutineSpawn
    )
    assert spawn.classification is not None
    assert spawn.classification.score == confidence
    assert success.contract_coverage is not None
    assert success.contract_coverage.total_contractual == total
    assert success.contract_coverage.percentage == pytest.approx(percentage)
    coverage = build_contract_coverage_map(src, tests, config)
    assert coverage[("run_worker", "client.py")].percentage == pytest.approx(percentage)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("import subprocess", "import subprocess\nsubprocess.run = unrelated"),
        ("result = subprocess.run", "subprocess = other\n    result = subprocess.run"),
        ("result = subprocess.run", 'return "early"\n    result = subprocess.run'),
        ("result = subprocess.run", "import subprocess\n    result = subprocess.run"),
        ("result = subprocess.run", "helper()\n    result = subprocess.run"),
        (
            "import subprocess",
            "import subprocess\n\ndef RuntimeError(message):\n    return message",
        ),
    ],
    ids=[
        "module-boundary-replaced",
        "local-boundary-replaced",
        "unreachable-boundary",
        "local-import",
        "unknown-producer",
        "shadowed-error-constructor",
    ],
)
def test_uncertain_production_boundary_is_unmapped(tmp_path: Path, old: str, new: str) -> None:
    """A detected spawn effect alone does not establish the patched boundary."""
    mapped = _map_invocation(tmp_path, _TEST, _PRODUCTION.replace(old, new))
    assert mapped[-1] is None


def test_from_package_owner_replaced_at_module_scope_is_unmapped(tmp_path: Path) -> None:
    """From-imported module members cannot bypass replacement checks."""
    source = _TEST.replace(
        "import client", "from pkg import client\nclient.subprocess = other"
    ).replace("from client import", "from pkg.client import")
    mapped = _map_invocation(tmp_path, source, package=True)
    assert mapped[-1] is None
