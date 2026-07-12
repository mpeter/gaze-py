"""Tests for the AST detector — EC-002, EC-003, EC-004, EC-005.

All tests run against static testdata fixtures in tests/testdata/analysis/.
The detector is imported from gaze_py.analysis.detector.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from gaze_py.analysis.detector import FileDetector, _build_signature, _format_annotation
from gaze_py.taxonomy.effects import SideEffectType
from gaze_py.taxonomy.exceptions import GazeParseError

# Re-exported at module level so inline imports inside test functions are not needed.
# All tests import FileDetector and SideEffectType from here.

FIXTURES = Path(__file__).parent / "testdata" / "analysis"
# Use the fixtures directory as the "project root" for relative path computation
ROOT = FIXTURES


# ---------------------------------------------------------------------------
# EC-002: P0 Zero Tolerance — one test per P0 type, no disjunctive "or"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,expected_type",
    [
        ("return_value.py", "ReturnValue"),
        ("error_return.py", "ErrorReturn"),
        ("receiver_mutation.py", "ReceiverMutation"),
        ("pointer_arg_mutation.py", "PointerArgMutation"),
    ],
)
def test_p0_detected(fixture: str, expected_type: str) -> None:
    """EC-002: Each P0 effect type is detected with zero false negatives."""
    targets = FileDetector.detect(FIXTURES / fixture, root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType(expected_type) for e in all_effects), (
        f"Expected {expected_type} in effects from {fixture}, got: {[e.type for e in all_effects]}"
    )


def test_sentinel_error_direct() -> None:
    """EC-002: SentinelError detected for class inheriting directly from Exception."""
    targets = FileDetector.detect(FIXTURES / "sentinel_error.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.SentinelError for e in all_effects), (
        f"Expected SentinelError in effects, got: {[e.type for e in all_effects]}"
    )


def test_sentinel_error_transitive() -> None:
    """EC-002: SentinelError detected for class inheriting transitively from Exception."""
    targets = FileDetector.detect(FIXTURES / "sentinel_error_transitive.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.SentinelError for e in all_effects), (
        f"Expected SentinelError (transitive) in effects, got: {[e.type for e in all_effects]}"
    )


def test_sentinel_error_not_for_nested_class(tmp_path: Path) -> None:
    """EC-002: SentinelError NOT detected for exception class defined inside a function."""
    src = tmp_path / "nested_exc.py"
    src.write_text(
        "def outer():\n    class InnerError(Exception):\n        pass\n    raise InnerError('x')\n"
    )
    targets = FileDetector.detect(src, root=tmp_path)
    all_effects = [e for t in targets for e in t.effects]
    assert not any(e.type == SideEffectType.SentinelError for e in all_effects), (
        "SentinelError should NOT be detected for nested exception class"
    )


# ---------------------------------------------------------------------------
# EC-002: ReturnValue annotation exception
# ---------------------------------------------------------------------------


def test_return_value_annotation_exception() -> None:
    """EC-002: return None with annotation -> Item | None IS a ReturnValue."""
    targets = FileDetector.detect(FIXTURES / "return_value_annotation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ReturnValue for e in all_effects), (
        "Expected ReturnValue from annotated function returning None"
    )


def test_explicit_return_none_without_annotation_is_not_return_value(
    tmp_path: Path,
) -> None:
    """EC-002: explicit return None without annotation → no ReturnValue."""
    src = tmp_path / "explicit_none.py"
    src.write_text("def f():\n    return None\n")
    targets = FileDetector.detect(src, root=tmp_path)
    all_effects = [e for t in targets for e in t.effects]
    assert not any(e.type == SideEffectType.ReturnValue for e in all_effects), (
        "return None without annotation should NOT produce ReturnValue"
    )


# ---------------------------------------------------------------------------
# EC-002: Pure function → zero effects
# ---------------------------------------------------------------------------


def test_pure_function_zero_effects() -> None:
    """EC-002: Pure function with body `pass` produces zero effects."""
    targets = FileDetector.detect(FIXTURES / "pure_function.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert all_effects == [], (
        f"Expected zero effects from pure_function.py, got: {[e.type for e in all_effects]}"
    )


# ---------------------------------------------------------------------------
# EC-002: Failure mode — syntax error raises GazeParseError
# ---------------------------------------------------------------------------


def test_syntax_error_raises_gaze_parse_error() -> None:
    """EC-002: Syntactically invalid file raises GazeParseError (not silent empty)."""
    with pytest.raises(GazeParseError) as exc_info:
        FileDetector.detect(FIXTURES / "syntax_error.py", root=ROOT)

    # EC-004: error must carry the file path in its message
    assert "syntax_error.py" in str(exc_info.value), (
        "GazeParseError message must contain the file path"
    )


# ---------------------------------------------------------------------------
# EC-003: Deterministic IDs — same source → same IDs across runs
# ---------------------------------------------------------------------------


def test_deterministic_ids() -> None:
    """EC-003: Analyzing the same file twice produces identical effect IDs."""
    targets1 = FileDetector.detect(FIXTURES / "return_value.py", root=ROOT)
    targets2 = FileDetector.detect(FIXTURES / "return_value.py", root=ROOT)

    ids1 = sorted(e.id for t in targets1 for e in t.effects)
    ids2 = sorted(e.id for t in targets2 for e in t.effects)
    assert ids1 == ids2, "Effect IDs must be deterministic across runs"
    assert ids1, "Expected at least one effect ID"


def test_stable_ids_use_relative_path(tmp_path: Path) -> None:
    """EC-003: IDs use relative path, so they are stable across machines."""
    # Create the same source at two different absolute paths
    src_a = tmp_path / "dir_a" / "myfile.py"
    src_b = tmp_path / "dir_b" / "myfile.py"
    src_a.parent.mkdir()
    src_b.parent.mkdir()
    code = "def f():\n    return 42\n"
    src_a.write_text(code)
    src_b.write_text(code)

    # Use each file's parent as root so the relative path is "myfile.py" in both cases
    targets_a = FileDetector.detect(src_a, root=src_a.parent)
    targets_b = FileDetector.detect(src_b, root=src_b.parent)

    ids_a = sorted(e.id for t in targets_a for e in t.effects)
    ids_b = sorted(e.id for t in targets_b for e in t.effects)
    assert ids_a == ids_b, (
        "Effect IDs must be stable across different absolute paths when relative path is the same"
    )


# ---------------------------------------------------------------------------
# EC-004: Effect structure — all required fields present
# ---------------------------------------------------------------------------


def test_effect_fields_present() -> None:
    """EC-004: Every detected effect has all required fields non-null."""
    targets = FileDetector.detect(FIXTURES / "return_value.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert all_effects, "Expected at least one effect"

    # Use all() with a descriptive assertion message rather than a for-loop.
    assert all(e.id for e in all_effects), "All effects must have non-empty id"
    assert all(e.type for e in all_effects), "All effects must have non-empty type"
    assert all(e.tier for e in all_effects), "All effects must have non-empty tier"
    assert all(e.location for e in all_effects), "All effects must have non-empty location"
    assert all(e.description for e in all_effects), "All effects must have non-empty description"
    assert all(e.target for e in all_effects), "All effects must have non-empty target"
    # classification is None before classification runs — that is correct


def test_location_format() -> None:
    """EC-004: location field matches 'file:line:col' pattern (two colons)."""
    targets = FileDetector.detect(FIXTURES / "return_value.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert all_effects, "Expected at least one effect"

    location_pattern = re.compile(r".+:\d+:\d+")
    for effect in all_effects:
        assert location_pattern.match(effect.location), (
            f"location '{effect.location}' does not match 'file:line:col' pattern"
        )


# ---------------------------------------------------------------------------
# EC-005: Python-specific effects
# ---------------------------------------------------------------------------


def test_channel_send_detected() -> None:
    """EC-005: ChannelSend detected from queue.put() on a parameter."""
    targets = FileDetector.detect(FIXTURES / "channel_send.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ChannelSend for e in all_effects), (
        f"Expected ChannelSend, got: {[e.type for e in all_effects]}"
    )


def test_mutex_op_detected() -> None:
    """EC-005: MutexOp detected from 'with lock:' where lock is a parameter."""
    targets = FileDetector.detect(FIXTURES / "mutex_op.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.MutexOp for e in all_effects), (
        f"Expected MutexOp, got: {[e.type for e in all_effects]}"
    )


def test_filesystem_meta_detected() -> None:
    """EC-005: FileSystemMeta detected from os.chmod()."""
    targets = FileDetector.detect(FIXTURES / "filesystem_meta.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FileSystemMeta for e in all_effects), (
        f"Expected FileSystemMeta, got: {[e.type for e in all_effects]}"
    )


def test_database_transaction_detected() -> None:
    """EC-005: DatabaseTransaction detected from 'with connection:' pattern."""
    targets = FileDetector.detect(FIXTURES / "db_transaction.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.DatabaseTransaction for e in all_effects), (
        f"Expected DatabaseTransaction, got: {[e.type for e in all_effects]}"
    )


def test_writer_output_detected() -> None:
    """EC-005: WriterOutput detected from .write() on a parameter named 'writer'."""
    targets = FileDetector.detect(FIXTURES / "writer_output.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.WriterOutput for e in all_effects), (
        f"Expected WriterOutput, got: {[e.type for e in all_effects]}"
    )


def test_deferred_return_mutation_detected() -> None:
    """EC-005: DeferredReturnMutation detected from finally block assignment."""
    targets = FileDetector.detect(FIXTURES / "deferred_return_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.DeferredReturnMutation for e in all_effects), (
        f"Expected DeferredReturnMutation, got: {[e.type for e in all_effects]}"
    )


def test_stderr_write_detected() -> None:
    """EC-005: StderrWrite detected from sys.stderr.write(...)."""
    targets = FileDetector.detect(FIXTURES / "stderr_write.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.StderrWrite for e in all_effects), (
        f"Expected StderrWrite, got: {[e.type for e in all_effects]}"
    )


def test_env_var_mutation_detected() -> None:
    """EC-005: EnvVarMutation detected from os.environ[key] = val."""
    targets = FileDetector.detect(FIXTURES / "env_var_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.EnvVarMutation for e in all_effects), (
        f"Expected EnvVarMutation, got: {[e.type for e in all_effects]}"
    )


def test_time_dependency_detected() -> None:
    """EC-005: TimeDependency detected from time.time()."""
    targets = FileDetector.detect(FIXTURES / "time_dependency.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.TimeDependency for e in all_effects), (
        f"Expected TimeDependency, got: {[e.type for e in all_effects]}"
    )


def test_closure_capture_mutation_detected() -> None:
    """EC-005: ClosureCaptureMutation detected from nonlocal + assignment in inner function."""
    targets = FileDetector.detect(FIXTURES / "closure_capture_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ClosureCaptureMutation for e in all_effects), (
        f"Expected ClosureCaptureMutation, got: {[e.type for e in all_effects]}"
    )


# ---------------------------------------------------------------------------
# Panic vs ProcessExit disambiguation
# ---------------------------------------------------------------------------


def test_raise_system_exit_is_panic(tmp_path: Path) -> None:
    """Panic: raise SystemExit (bare) → Panic effect."""
    src = tmp_path / "panic_bare.py"
    src.write_text("def f():\n    raise SystemExit\n")
    targets = FileDetector.detect(src, root=tmp_path)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.Panic for e in all_effects), (
        f"Expected Panic from 'raise SystemExit', got: {[e.type for e in all_effects]}"
    )


def test_raise_system_exit_with_arg_is_panic(tmp_path: Path) -> None:
    """Panic: raise SystemExit(1) → Panic effect."""
    src = tmp_path / "panic_arg.py"
    src.write_text("def f():\n    raise SystemExit(1)\n")
    targets = FileDetector.detect(src, root=tmp_path)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.Panic for e in all_effects), (
        f"Expected Panic from 'raise SystemExit(1)', got: {[e.type for e in all_effects]}"
    )


@pytest.mark.parametrize(
    "code,expected_type",
    [
        ("import sys\ndef f():\n    sys.exit(0)\n", "ProcessExit"),
        ("import os\ndef f():\n    os._exit(1)\n", "ProcessExit"),
        ("import os\ndef f():\n    os.abort()\n", "ProcessExit"),
    ],
)
def test_process_exit_detected(tmp_path: Path, code: str, expected_type: str) -> None:
    """ProcessExit: sys.exit/os._exit/os.abort → ProcessExit (not Panic)."""
    src = tmp_path / "proc_exit.py"
    src.write_text(code)
    targets = FileDetector.detect(src, root=tmp_path)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType(expected_type) for e in all_effects), (
        f"Expected {expected_type}, got: {[e.type for e in all_effects]}"
    )
    # Ensure no overlap with Panic
    assert not any(e.type == SideEffectType.Panic for e in all_effects), (
        "ProcessExit calls must not produce Panic"
    )


# ---------------------------------------------------------------------------
# PointerArgMutation vs SliceMutation disambiguation
# ---------------------------------------------------------------------------


def test_item_assignment_is_pointer_arg_mutation() -> None:
    """PointerArgMutation (P0): param[key] = val → PointerArgMutation, not SliceMutation."""
    targets = FileDetector.detect(FIXTURES / "pointer_arg_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.PointerArgMutation for e in all_effects), (
        "Expected PointerArgMutation from item assignment"
    )
    assert not any(e.type == SideEffectType.SliceMutation for e in all_effects), (
        "Item assignment must NOT produce SliceMutation"
    )


def test_append_is_slice_mutation_not_pointer_arg() -> None:
    """SliceMutation (P1): param.append() → SliceMutation, not PointerArgMutation."""
    targets = FileDetector.detect(FIXTURES / "slice_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.SliceMutation for e in all_effects), (
        "Expected SliceMutation from param.append()"
    )
    assert not any(e.type == SideEffectType.PointerArgMutation for e in all_effects), (
        "param.append() must NOT produce PointerArgMutation"
    )


# EC-001/EC-005: Permanently closed types — AtomicOp and SyncPoolOp
#         have no Python equivalent and are never detected.


@pytest.mark.parametrize(
    "noop_type",
    ["AtomicOp", "SyncPoolOp"],
)
def test_permanently_closed_types_never_emitted(noop_type: str, tmp_path: Path) -> None:
    """EC-001/EC-005: AtomicOp and SyncPoolOp have no Python equivalent — permanently closed."""
    source = textwrap.dedent("""
        import threading
        def f():
            x = threading.local()
            x.value = 42
    """)
    path = tmp_path / "atomic_like.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    all_effects = [e for t in targets for e in t.effects]
    assert not any(e.type == SideEffectType(noop_type) for e in all_effects)


# ---------------------------------------------------------------------------
# Additional P1/P2/P3/P4 effect coverage
# ---------------------------------------------------------------------------


def test_map_mutation_detected() -> None:
    """MapMutation (P1): param.update() → MapMutation."""
    targets = FileDetector.detect(FIXTURES / "map_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.MapMutation for e in all_effects), (
        f"Expected MapMutation, got: {[e.type for e in all_effects]}"
    )


def test_global_mutation_detected() -> None:
    """GlobalMutation (P1): explicit global + assignment → GlobalMutation."""
    targets = FileDetector.detect(FIXTURES / "global_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.GlobalMutation for e in all_effects), (
        f"Expected GlobalMutation, got: {[e.type for e in all_effects]}"
    )


def test_http_response_write_detected() -> None:
    """HTTPResponseWrite (P1): response.write() → HTTPResponseWrite."""
    targets = FileDetector.detect(FIXTURES / "http_response_write.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.HTTPResponseWrite for e in all_effects), (
        f"Expected HTTPResponseWrite, got: {[e.type for e in all_effects]}"
    )


def test_channel_close_detected() -> None:
    """ChannelClose (P1): q.close() on a parameter → ChannelClose."""
    targets = FileDetector.detect(FIXTURES / "channel_close.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ChannelClose for e in all_effects), (
        f"Expected ChannelClose, got: {[e.type for e in all_effects]}"
    )


def test_filesystem_write_detected() -> None:
    """FileSystemWrite (P2): open(path, 'w') → FileSystemWrite."""
    targets = FileDetector.detect(FIXTURES / "filesystem_write.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FileSystemWrite for e in all_effects), (
        f"Expected FileSystemWrite, got: {[e.type for e in all_effects]}"
    )


def test_filesystem_delete_detected() -> None:
    """FileSystemDelete (P2): os.remove() → FileSystemDelete."""
    targets = FileDetector.detect(FIXTURES / "filesystem_delete.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FileSystemDelete for e in all_effects), (
        f"Expected FileSystemDelete, got: {[e.type for e in all_effects]}"
    )


def test_database_write_detected() -> None:
    """DatabaseWrite (P2): cursor.execute() → DatabaseWrite."""
    targets = FileDetector.detect(FIXTURES / "db_write.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.DatabaseWrite for e in all_effects), (
        f"Expected DatabaseWrite, got: {[e.type for e in all_effects]}"
    )


def test_goroutine_spawn_detected() -> None:
    """GoroutineSpawn (P2): threading.Thread → GoroutineSpawn."""
    targets = FileDetector.detect(FIXTURES / "thread_spawn.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.GoroutineSpawn for e in all_effects), (
        f"Expected GoroutineSpawn, got: {[e.type for e in all_effects]}"
    )


def test_context_cancellation_detected() -> None:
    """ContextCancellation (P2): task.cancel() → ContextCancellation."""
    targets = FileDetector.detect(FIXTURES / "context_cancellation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ContextCancellation for e in all_effects), (
        f"Expected ContextCancellation, got: {[e.type for e in all_effects]}"
    )


def test_log_write_detected() -> None:
    """LogWrite (P2): logging.info() → LogWrite."""
    targets = FileDetector.detect(FIXTURES / "log_write.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.LogWrite for e in all_effects), (
        f"Expected LogWrite, got: {[e.type for e in all_effects]}"
    )


def test_callback_invocation_detected() -> None:
    """CallbackInvocation (P2): calling a parameter directly → CallbackInvocation."""
    targets = FileDetector.detect(FIXTURES / "callback_invoke.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.CallbackInvocation for e in all_effects), (
        f"Expected CallbackInvocation, got: {[e.type for e in all_effects]}"
    )


def test_stdout_write_detected() -> None:
    """StdoutWrite (P3): print() → StdoutWrite."""
    targets = FileDetector.detect(FIXTURES / "stdout_write.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.StdoutWrite for e in all_effects), (
        f"Expected StdoutWrite, got: {[e.type for e in all_effects]}"
    )


# ---------------------------------------------------------------------------
# Phase 2: New detector tests (tasks 2.1–2.21)
# ---------------------------------------------------------------------------


def test_filesystem_pathlib_delete_detected() -> None:
    """EC-005: FileSystemDelete detected from Path.unlink()."""
    targets = FileDetector.detect(FIXTURES / "filesystem_pathlib_delete.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FileSystemDelete for e in all_effects), (
        f"Expected FileSystemDelete, got: {[e.type for e in all_effects]}"
    )


def test_filesystem_pathlib_meta_detected() -> None:
    """EC-005: FileSystemMeta detected from Path.chmod()."""
    targets = FileDetector.detect(FIXTURES / "filesystem_pathlib_meta.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FileSystemMeta for e in all_effects), (
        f"Expected FileSystemMeta, got: {[e.type for e in all_effects]}"
    )


@pytest.mark.parametrize("method", ["write_text", "write_bytes"])
def test_filesystem_pathlib_write_detected(method: str) -> None:
    """EC-005: FileSystemWrite detected from Path.write_text/write_bytes()."""
    targets = FileDetector.detect(FIXTURES / "filesystem_pathlib_write.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FileSystemWrite for e in all_effects), (
        f"Expected FileSystemWrite, got: {[e.type for e in all_effects]}"
    )


@pytest.mark.parametrize(
    "fixture",
    [
        "reflection_mutation_setattr.py",
        "reflection_mutation_dunder.py",
    ],
)
def test_reflection_mutation_detected(fixture: str) -> None:
    """EC-005: ReflectionMutation detected from setattr() and obj.__setattr__()."""
    targets = FileDetector.detect(FIXTURES / fixture, root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ReflectionMutation for e in all_effects), (
        f"Expected ReflectionMutation in {fixture}, got: {[e.type for e in all_effects]}"
    )


def test_goroutine_spawn_executor_detected() -> None:
    """EC-005: GoroutineSpawn detected from executor.submit()."""
    targets = FileDetector.detect(FIXTURES / "goroutine_spawn_executor.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.GoroutineSpawn for e in all_effects), (
        f"Expected GoroutineSpawn, got: {[e.type for e in all_effects]}"
    )


def test_finalizer_registration_detected() -> None:
    """EC-005: FinalizerRegistration detected from weakref.finalize()."""
    targets = FileDetector.detect(FIXTURES / "finalizer_registration.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FinalizerRegistration for e in all_effects), (
        f"Expected FinalizerRegistration, got: {[e.type for e in all_effects]}"
    )


def test_cgo_call_detected() -> None:
    """EC-005: CgoCall detected from ctypes.CDLL()."""
    targets = FileDetector.detect(FIXTURES / "cgo_call.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.CgoCall for e in all_effects), (
        f"Expected CgoCall, got: {[e.type for e in all_effects]}"
    )


def test_stdout_write_sys_write_detected() -> None:
    """EC-005: StdoutWrite detected from sys.stdout.write()."""
    targets = FileDetector.detect(FIXTURES / "stdout_write_sys.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.StdoutWrite for e in all_effects), (
        f"Expected StdoutWrite, got: {[e.type for e in all_effects]}"
    )


def test_context_cancellation_event_set_detected() -> None:
    """EC-005: ContextCancellation detected from event.set() on a parameter.

    Covers detector.py lines 877-884 (.set() branch of _handle_param_attr_call).
    """
    targets = FileDetector.detect(FIXTURES / "context_cancellation_event.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ContextCancellation for e in all_effects), (
        f"Expected ContextCancellation, got: {[e.type for e in all_effects]}"
    )


def test_global_mutation_simple_assign_detected() -> None:
    """EC-005: GlobalMutation detected from simple assignment to global variable.

    Covers visit_Assign GlobalMutation branch (detector.py:530); distinct from
    test_global_mutation_detected() which covers visit_AugAssign via global_mutation.py.
    """
    targets = FileDetector.detect(FIXTURES / "global_mutation_simple_assign.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.GlobalMutation for e in all_effects), (
        f"Expected GlobalMutation, got: {[e.type for e in all_effects]}"
    )


def test_receiver_mutation_augmented_assign_detected() -> None:
    """EC-005: ReceiverMutation detected from self.x += 1 in a method.

    Covers visit_AugAssign ReceiverMutation branch (detector.py:547).
    """
    targets = FileDetector.detect(FIXTURES / "receiver_mutation_augassign.py", root=ROOT)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ReceiverMutation for e in all_effects), (
        f"Expected ReceiverMutation, got: {[e.type for e in all_effects]}"
    )


def test_open_keyword_mode_produces_filesystem_write(tmp_path: Path) -> None:
    """EC-002: open() with mode='w' as keyword arg → FileSystemWrite.

    Covers _extract_open_mode keyword path (detector.py:1074-1077).
    """
    src = tmp_path / "example.py"
    src.write_text("def f(path):\n    open(path, mode='w')\n")
    targets = FileDetector.detect(src, root=tmp_path)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.FileSystemWrite for e in all_effects), (
        f"Expected FileSystemWrite from open(mode='w'), got: {[e.type for e in all_effects]}"
    )


def test_vararg_param_triggers_slice_mutation_detection(tmp_path: Path) -> None:
    """EC-002: *args param captured and .append() triggers SliceMutation.

    # CR-004: _extract_params tested indirectly — *args capture only observable
    # via effect detection on the resulting parameter set.
    """
    src = tmp_path / "example.py"
    src.write_text("def f(*args):\n    args.append(1)\n")
    targets = FileDetector.detect(src, root=tmp_path)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.SliceMutation for e in all_effects), (
        f"Expected SliceMutation from *args.append(), got: {[e.type for e in all_effects]}"
    )


def test_kwarg_param_triggers_map_mutation_detection(tmp_path: Path) -> None:
    """EC-002: **kwargs param captured and .update() triggers MapMutation.

    # CR-004: _extract_params tested indirectly — **kwargs capture only observable
    # via effect detection on the resulting parameter set.
    """
    src = tmp_path / "example.py"
    src.write_text('def f(**kwargs):\n    kwargs.update({"x": 1})\n')
    targets = FileDetector.detect(src, root=tmp_path)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.MapMutation for e in all_effects), (
        f"Expected MapMutation from **kwargs.update(), got: {[e.type for e in all_effects]}"
    )


def test_detect_raises_gaze_parse_error_on_unreadable_file(tmp_path: Path) -> None:
    """EC-002: FileDetector.detect() raises GazeParseError when file is unreadable."""
    src = tmp_path / "secret.py"
    src.write_text("def f(): pass\n")
    # Probe: skip if chmod is not enforced (e.g. running as root)
    src.chmod(0o000)
    try:
        src.read_text()
        pytest.skip("chmod 000 not enforced in this environment")
    except OSError:
        pass
    try:
        with pytest.raises(GazeParseError):
            FileDetector.detect(src, root=tmp_path)
    finally:
        src.chmod(0o644)  # always restore so tmp_path cleanup succeeds


def test_detect_uses_filename_when_path_outside_root(tmp_path: Path) -> None:
    """EC-002: detect() uses filename-only when path is outside root."""
    src = tmp_path / "mymodule.py"
    src.write_text("def f(): pass\n")
    # Use a sibling dir that is guaranteed not to be an ancestor of tmp_path
    other_root = tmp_path.parent / "nonexistent_sibling_xyz"
    targets = FileDetector.detect(src, root=other_root)
    assert targets
    assert any(t.file_path == src.name for t in targets), (
        f"Expected file_path={src.name!r}, got: {[t.file_path for t in targets]}"
    )


def test_deferred_return_mutation_not_produced_without_finally(tmp_path: Path) -> None:
    """EC-002: try/except without finally → no DeferredReturnMutation."""
    src = tmp_path / "example.py"
    src.write_text(
        "def f():\n    x = 1\n    try:\n        return x\n    except Exception:\n        pass\n"
    )
    targets = FileDetector.detect(src, root=tmp_path)
    assert targets  # confirms file was parsed
    all_effects = [e for t in targets for e in t.effects]
    assert not any(e.type == SideEffectType.DeferredReturnMutation for e in all_effects), (
        f"Unexpected DeferredReturnMutation without finally: {[e.type for e in all_effects]}"
    )


def test_deferred_return_mutation_via_finally_augassign(tmp_path: Path) -> None:
    """EC-002: finally block with augmented assignment → DeferredReturnMutation.

    Covers detector.py:1000-1001.
    """
    src = tmp_path / "example.py"
    src.write_text(
        "def f():\n    x = 1\n    try:\n        return x\n    finally:\n        x += 1\n"
    )
    targets = FileDetector.detect(src, root=tmp_path)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.DeferredReturnMutation for e in all_effects), (
        f"Expected DeferredReturnMutation from finally: {[e.type for e in all_effects]}"
    )


def test_finally_nonmatching_name_produces_no_deferred_mutation(tmp_path: Path) -> None:
    """EC-002: finally assigns to z but y/e returned → no DeferredReturnMutation (no overlap).

    Covers handler-body recursion (detector.py:1042).
    """
    src = tmp_path / "example.py"
    src.write_text(
        "def f():\n"
        "    y = 1\n"
        "    try:\n"
        "        return y\n"
        "    except Exception as e:\n"
        "        return e\n"
        "    finally:\n"
        "        z = 0\n"
    )
    targets = FileDetector.detect(src, root=tmp_path)
    assert targets  # parse succeeded
    all_effects = [e for t in targets for e in t.effects]
    assert not any(e.type == SideEffectType.DeferredReturnMutation for e in all_effects), (
        f"Unexpected DeferredReturnMutation (no overlap): {[e.type for e in all_effects]}"
    )


def test_closure_capture_mutation_via_augmented_assign(tmp_path: Path) -> None:
    """EC-002: nonlocal + augmented assign → ClosureCaptureMutation.

    Covers detector.py:1207-1220.
    """
    src = tmp_path / "example.py"
    src.write_text(
        "def outer():\n"
        "    x = 0\n"
        "    def inner():\n"
        "        nonlocal x\n"
        "        x += 1\n"
        "    return inner\n"
    )
    targets = FileDetector.detect(src, root=tmp_path)
    assert targets
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.ClosureCaptureMutation for e in all_effects), (
        f"Expected ClosureCaptureMutation, got: {[e.type for e in all_effects]}"
    )


def test_caller_count_reflects_callers_map_value() -> None:
    """EC-002: callers dict populates FunctionTarget.caller_count.

    Covers detector.py:1346. Note: the function in pure_function.py is named 'pure'.
    """
    targets = FileDetector.detect(FIXTURES / "pure_function.py", root=ROOT, callers={"pure": 5})
    assert targets
    matched = [t for t in targets if t.function == "pure"]
    assert matched, f"pure not found in targets: {[t.function for t in targets]}"
    assert matched[0].caller_count == 5, (  # noqa: PLR2004
        f"Expected caller_count=5, got {matched[0].caller_count}"
    )


# ---------------------------------------------------------------------------
# RecoverBehavior (P3) — visit_Try / visit_TryStar
# ---------------------------------------------------------------------------


def test_recover_behavior_assignment_in_handler() -> None:
    """RecoverBehavior: assignment in except → detected."""
    targets = FileDetector.detect(FIXTURES / "recover_behavior.py", root=ROOT)
    fn = next(t for t in targets if t.function == "parse_int_with_fallback")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.RecoverBehavior)
    assert count == 1


def test_recover_behavior_bare_pass() -> None:
    """RecoverBehavior: bare pass in except → detected (suppression)."""
    targets = FileDetector.detect(FIXTURES / "recover_behavior.py", root=ROOT)
    fn = next(t for t in targets if t.function == "suppress_error")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.RecoverBehavior)
    assert count == 1


def test_recover_behavior_return_only_in_handler() -> None:
    """RecoverBehavior: return-only handler → detected."""
    targets = FileDetector.detect(FIXTURES / "recover_behavior.py", root=ROOT)
    fn = next(t for t in targets if t.function == "return_none_on_error")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.RecoverBehavior)
    assert count == 1


def test_recover_behavior_not_emitted_for_reraise() -> None:
    """RecoverBehavior: bare re-raise → NOT detected."""
    targets = FileDetector.detect(FIXTURES / "recover_behavior.py", root=ROOT)
    fn = next(t for t in targets if t.function == "reraise_is_not_recovery")
    assert not any(e.type == SideEffectType.RecoverBehavior for e in fn.effects)


def test_recover_behavior_not_emitted_for_transform_reraise() -> None:
    """RecoverBehavior: transform-and-reraise → NOT detected."""
    targets = FileDetector.detect(FIXTURES / "recover_behavior.py", root=ROOT)
    fn = next(t for t in targets if t.function == "transform_reraise_is_not_recovery")
    assert not any(e.type == SideEffectType.RecoverBehavior for e in fn.effects)


def test_recover_behavior_emitted_once_per_function() -> None:
    """RecoverBehavior: two qualifying try blocks → exactly ONE emission."""
    targets = FileDetector.detect(FIXTURES / "recover_behavior.py", root=ROOT)
    fn = next(t for t in targets if t.function == "double_try_recovers_once")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.RecoverBehavior)
    assert count == 1


def test_recover_behavior_flag_resets_between_functions() -> None:
    """RecoverBehavior: per-function isolation — full file detection."""
    targets = FileDetector.detect(FIXTURES / "recover_behavior.py", root=ROOT)
    by_name = {t.function: t for t in targets}
    rb = SideEffectType.RecoverBehavior
    assert sum(1 for e in by_name["parse_int_with_fallback"].effects if e.type == rb) == 1
    assert sum(1 for e in by_name["suppress_error"].effects if e.type == rb) == 1
    assert sum(1 for e in by_name["reraise_is_not_recovery"].effects if e.type == rb) == 0
    assert sum(1 for e in by_name["transform_reraise_is_not_recovery"].effects if e.type == rb) == 0


def test_recover_behavior_except_star(tmp_path: Path) -> None:
    """RecoverBehavior: visit_TryStar fires on except* (Python 3.11+)."""
    source = textwrap.dedent("""
        def f(value):
            try:
                return int(value)
            except* ValueError:
                return None
    """)
    path = tmp_path / "except_star.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.RecoverBehavior)
    assert count == 1


# ---------------------------------------------------------------------------
# WaitGroupOp (P3) — asyncio / threading.Barrier / concurrent.futures
# ---------------------------------------------------------------------------


def test_wait_group_op_asyncio_gather() -> None:
    """WaitGroupOp: asyncio.gather → detected."""
    targets = FileDetector.detect(FIXTURES / "wait_group_op.py", root=ROOT)
    fn = next(t for t in targets if t.function == "gather_tasks")
    assert any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_asyncio_gather_bare_call(tmp_path: Path) -> None:
    """WaitGroupOp: asyncio.gather without await → detected (fires on ast.Call)."""
    source = textwrap.dedent("""
        import asyncio
        def f(t1, t2):
            asyncio.gather(t1, t2)
    """)
    path = tmp_path / "gather_bare.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_asyncio_wait() -> None:
    """WaitGroupOp: asyncio.wait → detected."""
    targets = FileDetector.detect(FIXTURES / "wait_group_op.py", root=ROOT)
    fn = next(t for t in targets if t.function == "wait_tasks")
    assert any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_task_group() -> None:
    """WaitGroupOp: async with asyncio.TaskGroup() → detected."""
    targets = FileDetector.detect(FIXTURES / "wait_group_op.py", root=ROOT)
    fn = next(t for t in targets if t.function == "task_group_sync")
    assert any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_not_emitted_for_sync_with(tmp_path: Path) -> None:
    """WaitGroupOp: plain with lock: → NOT detected (only MutexOp)."""
    source = textwrap.dedent("""
        def f(lock):
            with lock:
                pass
    """)
    path = tmp_path / "sync_with.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert not any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_not_emitted_for_async_with_lock(tmp_path: Path) -> None:
    """WaitGroupOp: async with lock: (non-TaskGroup) → NOT detected."""
    source = textwrap.dedent("""
        async def f(lock):
            async with lock:
                pass
    """)
    path = tmp_path / "async_with_lock.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert not any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_futures_wait() -> None:
    """WaitGroupOp: futures.wait() via alias import → detected."""
    targets = FileDetector.detect(FIXTURES / "wait_group_op.py", root=ROOT)
    fn = next(t for t in targets if t.function == "futures_wait")
    assert any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_barrier_wait() -> None:
    """WaitGroupOp: threading.Barrier.wait() → detected."""
    targets = FileDetector.detect(FIXTURES / "wait_group_op.py", root=ROOT)
    fn = next(t for t in targets if t.function == "barrier_sync")
    assert any(e.type == SideEffectType.WaitGroupOp for e in fn.effects)


def test_wait_group_op_multiple_emissions(tmp_path: Path) -> None:
    """WaitGroupOp: two qualifying calls in same function → 2 emissions."""
    source = textwrap.dedent("""
        import asyncio
        import threading

        async def sync_two_ways(tasks, barrier):
            await asyncio.gather(*tasks)
            barrier.wait()
    """)
    path = tmp_path / "multi_wait.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "sync_two_ways")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.WaitGroupOp)
    assert count == 2


# ---------------------------------------------------------------------------
# UnsafeMutation (P4) — ctypes pointer writes
# ---------------------------------------------------------------------------


def test_unsafe_mutation_ptr_subscript() -> None:
    """UnsafeMutation: ptr[0] = ... → detected."""
    targets = FileDetector.detect(FIXTURES / "unsafe_mutation.py", root=ROOT)
    fn = next(t for t in targets if t.function == "write_ptr_subscript")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.UnsafeMutation)
    assert count == 1


def test_unsafe_mutation_buf_subscript() -> None:
    """UnsafeMutation: buf[0] = ... → detected."""
    targets = FileDetector.detect(FIXTURES / "unsafe_mutation.py", root=ROOT)
    fn = next(t for t in targets if t.function == "write_buf_subscript")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.UnsafeMutation)
    assert count == 1


def test_unsafe_mutation_p_name_subscript() -> None:
    """UnsafeMutation: p_data[0] = ... → detected (validates 'p_' in _CTYPES_PTR_NAMES)."""
    targets = FileDetector.detect(FIXTURES / "unsafe_mutation.py", root=ROOT)
    fn = next(t for t in targets if t.function == "write_p_name_subscript")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.UnsafeMutation)
    assert count == 1


def test_unsafe_mutation_contents_attr() -> None:
    """UnsafeMutation: mem.contents = ... → detected."""
    targets = FileDetector.detect(FIXTURES / "unsafe_mutation.py", root=ROOT)
    fn = next(t for t in targets if t.function == "write_contents")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.UnsafeMutation)
    assert count == 1


def test_unsafe_mutation_not_emitted_for_list_write() -> None:
    """UnsafeMutation: items[0] = ... (list) → NOT detected."""
    targets = FileDetector.detect(FIXTURES / "unsafe_mutation.py", root=ROOT)
    fn = next(t for t in targets if t.function == "safe_list_write")
    assert not any(e.type == SideEffectType.UnsafeMutation for e in fn.effects)


def test_unsafe_mutation_both_patterns_independent(tmp_path: Path) -> None:
    """UnsafeMutation: ptr subscript + .contents in same function → 2 emissions."""
    source = textwrap.dedent("""
        import ctypes
        def f(ptr, mem):
            ptr[0] = 0xFF
            mem.contents = ctypes.c_int(0)
    """)
    path = tmp_path / "unsafe_both.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    count = sum(1 for e in fn.effects if e.type == SideEffectType.UnsafeMutation)
    assert count == 2


# ---------------------------------------------------------------------------
# Python-native detection — subprocess GoroutineSpawn
# ---------------------------------------------------------------------------


def test_subprocess_popen_is_goroutine_spawn() -> None:
    """subprocess.Popen → GoroutineSpawn."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "spawn_popen")
    assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


def test_subprocess_run_is_goroutine_spawn() -> None:
    """subprocess.run → GoroutineSpawn."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "spawn_run")
    assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


def test_subprocess_call_is_goroutine_spawn() -> None:
    """subprocess.call → GoroutineSpawn."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "spawn_call")
    assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


def test_subprocess_check_output_is_goroutine_spawn() -> None:
    """subprocess.check_output → GoroutineSpawn."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "spawn_check_output")
    assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


def test_subprocess_check_call_is_goroutine_spawn() -> None:
    """subprocess.check_call → GoroutineSpawn."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "spawn_check_call")
    assert any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


def test_non_subprocess_run_not_goroutine_spawn(tmp_path: Path) -> None:
    """proc.run() where proc is not subprocess → no GoroutineSpawn."""
    source = textwrap.dedent("""
        def f(proc):
            proc.run(["ls"])
    """)
    path = tmp_path / "non_subprocess.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert not any(e.type == SideEffectType.GoroutineSpawn for e in fn.effects)


# ---------------------------------------------------------------------------
# Python-native detection — async with MutexOp / DatabaseTransaction
# ---------------------------------------------------------------------------


def test_async_with_lock_is_mutex_op() -> None:
    """async with lock (param) → MutexOp."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "async_lock")
    assert any(e.type == SideEffectType.MutexOp for e in fn.effects)


def test_async_with_mutex_is_mutex_op() -> None:
    """async with mutex (param) → MutexOp."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "async_mutex")
    assert any(e.type == SideEffectType.MutexOp for e in fn.effects)


def test_async_with_sem_is_mutex_op() -> None:
    """async with sem (param) → MutexOp (not a connection name → MutexOp by default)."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "async_sem")
    assert any(e.type == SideEffectType.MutexOp for e in fn.effects)


def test_async_with_conn_is_database_transaction() -> None:
    """async with conn (param) → DatabaseTransaction."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "async_conn")
    assert any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


def test_async_with_session_is_mutex_op_not_database_transaction() -> None:
    """async with session (param) → MutexOp, NOT DatabaseTransaction.

    'session' is excluded from _is_db_context to avoid false positives on
    session_id (a common HTTP/user session identifier). session → MutexOp by default.
    """
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "async_session")
    assert any(e.type == SideEffectType.MutexOp for e in fn.effects)
    assert not any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


def test_async_with_db_conn_is_database_transaction() -> None:
    """async with db_conn (param, word-part 'db' match) → DatabaseTransaction."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "async_db_conn")
    assert any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


def test_async_with_db_conn_not_mutex_op() -> None:
    """async with db_conn → DatabaseTransaction, NOT MutexOp."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "async_db_conn")
    assert not any(e.type == SideEffectType.MutexOp for e in fn.effects)


def test_sync_with_db_conn_is_database_transaction() -> None:
    """with db_conn (sync) → DatabaseTransaction via _is_db_context (regression)."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "sync_db_conn")
    assert any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects)


def test_sync_with_ctx_is_not_database_transaction() -> None:
    """with ctx (sync) → MutexOp, NOT DatabaseTransaction (ctx excluded from _is_db_context)."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "sync_ctx_not_db")
    assert any(e.type == SideEffectType.MutexOp for e in fn.effects), (
        f"Expected MutexOp for 'with ctx:', got: {[e.type for e in fn.effects]}"
    )
    assert not any(e.type == SideEffectType.DatabaseTransaction for e in fn.effects), (
        "ctx must NOT produce DatabaseTransaction (excluded from _is_db_context)"
    )


def test_async_with_non_param_does_not_emit_mutex(tmp_path: Path) -> None:
    """async with non-param local var → no MutexOp (not a parameter)."""
    source = textwrap.dedent("""
        import asyncio
        async def f():
            lock = asyncio.Lock()
            async with lock:
                pass
    """)
    path = tmp_path / "async_local.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert not any(e.type == SideEffectType.MutexOp for e in fn.effects)


# ---------------------------------------------------------------------------
# Python-native detection — atexit GlobalMutation
# ---------------------------------------------------------------------------


def test_atexit_register_is_global_mutation() -> None:
    """atexit.register → GlobalMutation."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "register_shutdown")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_atexit_register_lambda_is_global_mutation() -> None:
    """atexit.register(lambda) → GlobalMutation."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "register_lambda_shutdown")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_atexit_register_not_finalizer_registration() -> None:
    """atexit.register → NOT FinalizerRegistration."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "register_shutdown")
    assert not any(e.type == SideEffectType.FinalizerRegistration for e in fn.effects)


def test_atexit_register_not_callback_invocation() -> None:
    """atexit.register → NOT CallbackInvocation (registers, does not invoke)."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "register_shutdown")
    assert not any(e.type == SideEffectType.CallbackInvocation for e in fn.effects)


def test_atexit_unregister_not_global_mutation(tmp_path: Path) -> None:
    """atexit.unregister → NOT GlobalMutation (only .register is detected)."""
    source = textwrap.dedent("""
        import atexit
        def cancel_shutdown(cleanup):
            atexit.unregister(cleanup)
    """)
    path = tmp_path / "atexit_unreg.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "cancel_shutdown")
    assert not any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


# ---------------------------------------------------------------------------
# Python-native detection — warnings.warn LogWrite + GlobalMutation
# ---------------------------------------------------------------------------


def test_warnings_warn_emits_log_write() -> None:
    """warnings.warn → LogWrite."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "emit_warning")
    assert any(e.type == SideEffectType.LogWrite for e in fn.effects)


def test_warnings_warn_emits_global_mutation() -> None:
    """warnings.warn → GlobalMutation (__warningregistry__)."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "emit_warning")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_warnings_warn_emits_exactly_one_each_with_distinct_ids() -> None:
    """warnings.warn → exactly one LogWrite AND one GlobalMutation, distinct IDs (EC-003)."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "emit_warning")
    log_effects = [e for e in fn.effects if e.type == SideEffectType.LogWrite]
    mut_effects = [e for e in fn.effects if e.type == SideEffectType.GlobalMutation]
    assert len(log_effects) == 1, f"Expected 1 LogWrite, got {len(log_effects)}"
    assert len(mut_effects) == 1, f"Expected 1 GlobalMutation, got {len(mut_effects)}"
    assert log_effects[0].id != mut_effects[0].id, (
        "Effects from same node must have distinct IDs (EC-003)"
    )


def test_warnings_warn_with_stacklevel_emits_both_effects(tmp_path: Path) -> None:
    """warnings.warn(..., stacklevel=2) → both LogWrite and GlobalMutation."""
    source = textwrap.dedent("""
        import warnings
        def warn_stacklevel():
            warnings.warn("deprecated", stacklevel=2)
    """)
    path = tmp_path / "warn_stacklevel.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "warn_stacklevel")
    assert any(e.type == SideEffectType.LogWrite for e in fn.effects)
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_warnings_warn_not_finalizer_or_callback() -> None:
    """warnings.warn → NOT FinalizerRegistration or CallbackInvocation."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "emit_warning")
    assert not any(e.type == SideEffectType.FinalizerRegistration for e in fn.effects)
    assert not any(e.type == SideEffectType.CallbackInvocation for e in fn.effects)


# ---------------------------------------------------------------------------
# Python-native detection — @lru_cache GlobalMutation
# ---------------------------------------------------------------------------


def test_lru_cache_bare_is_global_mutation() -> None:
    """@lru_cache (bare) → GlobalMutation."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "cached_compute")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_lru_cache_call_form_is_global_mutation() -> None:
    """@lru_cache(maxsize=128) → GlobalMutation."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "cached_fetch")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_cache_decorator_is_global_mutation() -> None:
    """@cache → GlobalMutation."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "cached_memoized")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_uncached_function_not_global_mutation_from_decorator() -> None:
    """Plain function with no cache decorator → no lru_cache GlobalMutation."""
    targets = FileDetector.detect(FIXTURES / "python_native.py", root=ROOT)
    fn = next(t for t in targets if t.function == "not_cached")
    assert not any(e.type == SideEffectType.GlobalMutation for e in fn.effects), (
        f"not_cached has no GlobalMutation sources; got: {[e.type for e in fn.effects]}"
    )


def test_functools_lru_cache_qualified_form(tmp_path: Path) -> None:
    """@functools.lru_cache → GlobalMutation."""
    source = textwrap.dedent("""
        import functools
        @functools.lru_cache
        def f(x: int) -> int:
            return x * x
    """)
    path = tmp_path / "qualified_cache.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_functools_lru_cache_call_form_is_global_mutation(tmp_path: Path) -> None:
    """@functools.lru_cache(maxsize=None) → GlobalMutation."""
    source = textwrap.dedent("""
        import functools
        @functools.lru_cache(maxsize=None)
        def f(x: int) -> int:
            return x * x
    """)
    path = tmp_path / "qualified_cache_call.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_functools_cache_qualified_form_is_global_mutation(tmp_path: Path) -> None:
    """@functools.cache → GlobalMutation."""
    source = textwrap.dedent("""
        import functools
        @functools.cache
        def f(x: int) -> int:
            return x * x
    """)
    path = tmp_path / "qualified_cache_bare.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    fn = next(t for t in targets if t.function == "f")
    assert any(e.type == SideEffectType.GlobalMutation for e in fn.effects)


def test_lru_cache_effect_on_definition_not_call_site(tmp_path: Path) -> None:
    """@lru_cache effect attributed to decorated fn, NOT to its callers."""
    source = textwrap.dedent("""
        from functools import lru_cache
        @lru_cache
        def compute(x: int) -> int:
            return x * x
        def caller_a() -> int:
            return compute(1)
        def caller_b() -> int:
            return compute(2)
        def caller_c() -> int:
            return compute(3)
    """)
    path = tmp_path / "cache_call_site.py"
    path.write_text(source)
    targets = FileDetector.detect(path, root=tmp_path)
    compute_fn = next(t for t in targets if t.function == "compute")
    gm_effects = [e for e in compute_fn.effects if e.type == SideEffectType.GlobalMutation]
    assert len(gm_effects) == 1, (
        f"Expected exactly 1 GlobalMutation on compute, got {len(gm_effects)}"
    )
    assert "lru_cache" in gm_effects[0].description, (
        f"Expected 'lru_cache' in description, got: {gm_effects[0].description!r}"
    )
    for caller in ("caller_a", "caller_b", "caller_c"):
        caller_fn = next(t for t in targets if t.function == caller)
        assert not any(e.type == SideEffectType.GlobalMutation for e in caller_fn.effects), (
            f"{caller} should not have GlobalMutation (callers have no GlobalMutation sources)"
        )


# ---------------------------------------------------------------------------
# _build_signature and _format_annotation error paths (M-8)
# CR-004: tested directly because injecting a malformed ast.FunctionDef
# through the public FileDetector.detect() API is not feasible.
# ---------------------------------------------------------------------------


def test_build_signature_fallback_on_malformed_args() -> None:
    """_build_signature falls back to 'def f(...)' when args node is malformed."""
    import ast

    node = ast.parse("def f(x: int) -> str: pass").body[0]
    assert isinstance(node, ast.FunctionDef)
    # Force an AttributeError inside _build_signature by removing args.
    node.args = None  # type: ignore[assignment]
    result = _build_signature(node, "f")
    assert result == "def f(...)", f"Expected fallback signature, got {result!r}"


def test_build_signature_async_prefix() -> None:
    """_build_signature emits 'async def' for AsyncFunctionDef nodes."""
    import ast

    node = ast.parse("async def fetch(url: str) -> bytes: pass").body[0]
    assert isinstance(node, ast.AsyncFunctionDef)
    result = _build_signature(node, "fetch")
    assert result.startswith("async def "), (
        f"Expected 'async def' prefix for async function, got {result!r}"
    )
    assert "url: str" in result
    assert "-> bytes" in result


def test_format_annotation_returns_empty_string_on_none() -> None:
    """_format_annotation returns '' for None input (no annotation)."""
    result = _format_annotation(None)
    assert result == "", f"Expected '' for None annotation, got {result!r}"


# ---------------------------------------------------------------------------
# EC-001 P2 — DatabaseWrite on locally-constructed connections (G1a)
# ---------------------------------------------------------------------------


def test_database_write_local_connection_detected() -> None:
    """DatabaseWrite (P2): con = sqlite3.connect(); con.execute()/commit().

    Regression for the G1a false negative (docs/audit-2026-07-12.md): the
    parameter-path heuristic missed connections constructed in-function.
    """
    targets = FileDetector.detect(FIXTURES / "db_write_local_conn.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    db_writes = [e for e in all_effects if e.type == SideEffectType.DatabaseWrite]
    assert len(db_writes) == 2, (
        f"Expected 2 DatabaseWrite (execute + commit), got: {[e.type for e in all_effects]}"
    )


def test_database_write_local_cursor_detected() -> None:
    """DatabaseWrite (P2): cursor derived from a tracked connection.

    cur = con.cursor() inherits tracking from con = sqlite3.connect();
    cur.executemany() must emit DatabaseWrite.
    """
    targets = FileDetector.detect(FIXTURES / "db_write_local_cursor.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.DatabaseWrite for e in all_effects), (
        f"Expected DatabaseWrite, got: {[e.type for e in all_effects]}"
    )


# ---------------------------------------------------------------------------
# EC-001 P1 — GlobalMutation via imported-module attribute assignment (G1a)
# ---------------------------------------------------------------------------


def test_module_attr_assignment_is_global_mutation() -> None:
    """GlobalMutation (P1): os.getcwd = fake mutates process-global state.

    Regression for the G1a false negative (docs/audit-2026-07-12.md):
    monkeypatch-style assignment to an imported module attribute emitted
    nothing. The dedicated MonkeyPatch type is G1c; GlobalMutation is the
    correct currently-defined label.
    """
    targets = FileDetector.detect(FIXTURES / "module_attr_mutation.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert any(e.type == SideEffectType.GlobalMutation for e in all_effects), (
        f"Expected GlobalMutation, got: {[e.type for e in all_effects]}"
    )


def test_module_attr_shadowed_by_param_not_global_mutation() -> None:
    """A parameter shadowing a module name suppresses module-attr detection.

    def f(os): os.getcwd = ... mutates the argument, not the module — no
    GlobalMutation may be emitted.
    """
    targets = FileDetector.detect(FIXTURES / "module_attr_shadowed_param.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert not any(e.type == SideEffectType.GlobalMutation for e in all_effects), (
        f"Param-shadowed module name must not emit GlobalMutation, got: "
        f"{[e.type for e in all_effects]}"
    )
