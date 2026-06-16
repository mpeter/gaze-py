"""Tests for the AST detector — EC-002, EC-003, EC-004, EC-005.

All tests run against static testdata fixtures in tests/testdata/analysis/.
The detector is imported from gaze_py.analysis.detector.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gaze_py.analysis.detector import FileDetector
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


# ---------------------------------------------------------------------------
# EC-005: No-op coverage — WaitGroupOp, AtomicOp, RecoverBehavior,
#         UnsafeMutation, SyncPoolOp never detected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "noop_type",
    ["WaitGroupOp", "AtomicOp", "RecoverBehavior", "UnsafeMutation", "SyncPoolOp"],
)
def test_noop_types_not_detected(noop_type: str) -> None:
    """EC-005: No-op types are never detected (even on pure_function.py)."""
    targets = FileDetector.detect(FIXTURES / "pure_function.py", root=ROOT)
    all_effects = [e for t in targets for e in t.effects]
    assert not any(e.type == SideEffectType(noop_type) for e in all_effects), (
        f"No-op type {noop_type} should never be detected"
    )


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
        "def f():\n"
        "    x = 1\n"
        "    try:\n"
        "        return x\n"
        "    except Exception:\n"
        "        pass\n"
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
        "def f():\n"
        "    x = 1\n"
        "    try:\n"
        "        return x\n"
        "    finally:\n"
        "        x += 1\n"
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
        f"Unexpected DeferredReturnMutation (z not in return names): {[e.type for e in all_effects]}"
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
    matched = [t for t in targets if t.name == "pure"]
    assert matched, f"pure not found in targets: {[t.name for t in targets]}"
    assert matched[0].caller_count == 5, (  # noqa: PLR2004
        f"Expected caller_count=5, got {matched[0].caller_count}"
    )
