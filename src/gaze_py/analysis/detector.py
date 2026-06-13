"""AST-based side-effect detector for Python source files.

Implements a two-phase scan:
1. Module-level pass: detect SentinelError from top-level ClassDef nodes
   with transitive base resolution within the same module.
2. Per-function pass: FunctionVisitor collects all other effect types.

Per EC-003: effect IDs use project-relative paths so they are stable across
machines and working directories.

Per design.md: GazeParseError is raised (not a silent empty list) when
ast.parse() fails with SyntaxError or ValueError.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from gaze_py.analysis.complexity import cyclomatic_complexity
from gaze_py.taxonomy.effects import TIER_MAP, SideEffectType, Tier
from gaze_py.taxonomy.exceptions import GazeParseError
from gaze_py.taxonomy.models import FunctionTarget, SideEffect

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Standard library exception base classes that make a subclass a sentinel.
# Kept as a frozenset for O(1) membership tests.
_STDLIB_EXCEPTIONS: frozenset[str] = frozenset(
    {
        "Exception",
        "BaseException",
        "ValueError",
        "RuntimeError",
        "TypeError",
        "OSError",
        "IOError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "NotImplementedError",
        "StopIteration",
        "LookupError",
        "EnvironmentError",
        "ArithmeticError",
        "PermissionError",
        "FileNotFoundError",
        "IsADirectoryError",
        "TimeoutError",
        "ConnectionError",
        "ImportError",
        "NameError",
        "ZeroDivisionError",
        "OverflowError",
        "MemoryError",
        "RecursionError",
        "SystemError",
        "UnicodeError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "AssertionError",
        "GeneratorExit",
        "StopAsyncIteration",
    }
)

# List method names that indicate SliceMutation (P1)
_SLICE_METHODS: frozenset[str] = frozenset(
    {"append", "extend", "insert", "pop", "remove", "clear", "reverse", "sort"}
)

# Dict method names that indicate MapMutation (P1)
_MAP_METHODS: frozenset[str] = frozenset({"update", "setdefault", "pop", "clear"})

# Logging module/object names that indicate LogWrite (P2)
_LOG_NAMES: frozenset[str] = frozenset({"logging", "logger", "log"})

# File open modes that indicate a write operation
_WRITE_MODES: frozenset[str] = frozenset({"w", "a", "wb", "ab", "w+", "a+", "wb+", "ab+"})

# Qualified names for GoroutineSpawn detection
_GOROUTINE_SPAWN_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("threading", "Thread"),
        ("asyncio", "create_task"),
        ("multiprocessing", "Process"),
    }
)

# Qualified names for ProcessExit detection (function calls only — no overlap with Panic)
_PROCESS_EXIT_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("sys", "exit"),
        ("os", "_exit"),
        ("os", "abort"),
    }
)

# Qualified names for TimeDependency detection
_TIME_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("time", "time"),
        ("time", "monotonic"),
        ("time", "perf_counter"),
        ("datetime", "now"),
        ("datetime", "utcnow"),
    }
)

# Qualified names for FileSystemDelete detection
_FS_DELETE_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("os", "remove"),
        ("os", "unlink"),
        ("shutil", "rmtree"),
    }
)

# Qualified names for FileSystemMeta detection
_FS_META_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("os", "chmod"),
        ("os", "chown"),
        ("os", "utime"),
        ("os", "symlink"),
        ("os", "link"),
    }
)

# Positional argument index for the mode parameter in open() calls.
# open(path, mode) — mode is the second positional argument (index 1).
_OPEN_MODE_ARG_INDEX: int = 1


# ---------------------------------------------------------------------------
# Effect ID computation
# ---------------------------------------------------------------------------


def _effect_id(rel_path: str, fn_name: str, effect_type: str, location: str) -> str:
    """Compute a deterministic 8-character hex effect ID prefixed with 'se-'.

    Per EC-003: uses project-relative path so IDs are stable across machines.

    Args:
        rel_path: Project-relative path to the source file.
        fn_name: Simple function name (or '<module>' for module-level effects).
        effect_type: SideEffectType string value.
        location: Location string in 'file:line:col' format.

    Returns:
        Effect ID string in the format 'se-XXXXXXXX'.
    """
    payload = f"{rel_path}:{fn_name}:{effect_type}:{location}"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    return f"se-{digest}"


def _location(rel_path: str, node: ast.AST) -> str:
    """Format a location string as 'file:line:col'.

    Args:
        rel_path: Project-relative path to the source file.
        node: AST node with lineno and col_offset attributes.

    Returns:
        Location string in 'rel_path:lineno:col_offset' format.
    """
    lineno = getattr(node, "lineno", 0)
    col = getattr(node, "col_offset", 0)
    return f"{rel_path}:{lineno}:{col}"


def _make_effect(
    *,
    rel_path: str,
    fn_name: str,
    effect_type: SideEffectType,
    node: ast.AST,
    description: str,
) -> SideEffect:
    """Construct a SideEffect with a deterministic ID.

    Args:
        rel_path: Project-relative path to the source file.
        fn_name: Simple function name for the containing function.
        effect_type: The SideEffectType enum value.
        node: AST node at the detection site (provides line/col).
        description: Human-readable description of the detected effect.

    Returns:
        A frozen SideEffect dataclass instance.
    """
    loc = _location(rel_path, node)
    tier: Tier = TIER_MAP[effect_type]
    eid = _effect_id(rel_path, fn_name, effect_type.value, loc)
    return SideEffect(
        id=eid,
        type=effect_type,
        tier=tier,
        location=loc,
        description=description,
        target=fn_name,
    )


# ---------------------------------------------------------------------------
# Module-level SentinelError detection
# ---------------------------------------------------------------------------


def _collect_sentinel_classes(module: ast.Module) -> set[str]:
    """Collect names of top-level exception classes in the module.

    A class is a sentinel if any of its bases is in _STDLIB_EXCEPTIONS OR
    is itself a known sentinel class (transitive resolution within the module).

    Only top-level ClassDef nodes are considered — classes defined inside
    function or method bodies are NOT sentinels per design.md.

    Args:
        module: Parsed AST module node.

    Returns:
        Set of class names that are sentinel exception classes.
    """
    # First pass: collect all top-level ClassDef nodes and their base names
    top_level_classes: dict[str, list[str]] = {}
    for node in module.body:
        if isinstance(node, ast.ClassDef):
            base_names: list[str] = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    # e.g., exceptions.ValueError — use the attribute name
                    base_names.append(base.attr)
            top_level_classes[node.name] = base_names

    # Iterative resolution: keep expanding the known sentinel set until stable
    known_sentinels: set[str] = set(_STDLIB_EXCEPTIONS)
    changed = True
    while changed:
        changed = False
        for class_name, bases in top_level_classes.items():
            if class_name not in known_sentinels:
                if any(b in known_sentinels for b in bases):
                    known_sentinels.add(class_name)
                    changed = True

    # Return only the locally-defined sentinel classes (not stdlib names)
    return {name for name in top_level_classes if name in known_sentinels}


def _sentinel_effects(module: ast.Module, rel_path: str) -> list[tuple[ast.ClassDef, SideEffect]]:
    """Detect SentinelError effects from top-level ClassDef nodes.

    Args:
        module: Parsed AST module node.
        rel_path: Project-relative path to the source file.

    Returns:
        List of (ClassDef node, SideEffect) pairs for each sentinel class.
    """
    sentinel_names = _collect_sentinel_classes(module)
    results: list[tuple[ast.ClassDef, SideEffect]] = []
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name in sentinel_names:
            effect = _make_effect(
                rel_path=rel_path,
                fn_name="<module>",
                effect_type=SideEffectType.SentinelError,
                node=node,
                description=(
                    f"Class '{node.name}' is a sentinel exception type "
                    f"(inherits from Exception or a known subclass)"
                ),
            )
            results.append((node, effect))
    return results


# ---------------------------------------------------------------------------
# Per-function visitor
# ---------------------------------------------------------------------------


class _FunctionVisitor(ast.NodeVisitor):
    """AST visitor that collects side effects within a single function body.

    Designed to be instantiated once per function. The visitor is given the
    set of parameter names for the function so it can detect parameter-based
    effects (SliceMutation, PointerArgMutation, etc.).

    Does NOT recurse into nested function definitions — those are handled
    separately by FileDetector.
    """

    def __init__(
        self,
        *,
        rel_path: str,
        fn_name: str,
        params: set[str],
        has_return_annotation: bool,
        annotation_is_none: bool,
    ) -> None:
        """Initialize the visitor for a specific function.

        Args:
            rel_path: Project-relative path to the source file.
            fn_name: Simple function name.
            params: Set of parameter names for this function.
            has_return_annotation: True if the function has a return annotation.
            annotation_is_none: True if the annotation is exactly '-> None'.
        """
        self._rel_path = rel_path
        self._fn_name = fn_name
        self._params = params
        self._has_return_annotation = has_return_annotation
        self._annotation_is_none = annotation_is_none
        self._effects: list[SideEffect] = []
        self._depth = 0  # nesting depth; skip nested FunctionDef when > 0
        # For GlobalMutation: track declared global names
        self._global_names: set[str] = set()
        # For ClosureCaptureMutation: track declared nonlocal names
        self._nonlocal_names: set[str] = set()
        # For DeferredReturnMutation: track finally-assigned names and return names
        self._finally_assigned: set[str] = set()
        self._return_names: set[str] = set()

    @property
    def effects(self) -> list[SideEffect]:
        """All detected effects, in detection order."""
        return self._effects

    def _add(self, effect_type: SideEffectType, node: ast.AST, description: str) -> None:
        """Append a new SideEffect to the collected list.

        Args:
            effect_type: The SideEffectType for this effect.
            node: AST node at the detection site.
            description: Human-readable description.
        """
        self._effects.append(
            _make_effect(
                rel_path=self._rel_path,
                fn_name=self._fn_name,
                effect_type=effect_type,
                node=node,
                description=description,
            )
        )

    # ------------------------------------------------------------------
    # Nesting control — skip nested function definitions
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Skip nested function definitions — they are visited separately."""
        if self._depth > 0:
            return
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Skip nested async function definitions — they are visited separately."""
        if self._depth > 0:
            return
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    # ------------------------------------------------------------------
    # ReturnValue
    # ------------------------------------------------------------------

    def visit_Return(self, node: ast.Return) -> None:  # noqa: N802
        """Detect ReturnValue effects.

        Rules (per design.md ReturnValue heuristic):
        - If the function has a return annotation that is not '-> None',
          ALL return statements (including 'return None') are ReturnValue.
        - Otherwise, only 'return <expr>' where expr is not None literal.
        - Bare 'return' (node.value is None) never produces ReturnValue.
        """
        if node.value is None:
            # Bare 'return' — never a ReturnValue
            self.generic_visit(node)
            return

        is_none_literal = isinstance(node.value, ast.Constant) and node.value.value is None

        if self._has_return_annotation and not self._annotation_is_none:
            # Annotation exception: even 'return None' is a ReturnValue
            self._add(
                SideEffectType.ReturnValue,
                node,
                "Function returns a value (annotation signals None is meaningful)",
            )
        elif not is_none_literal:
            # Non-None return value without annotation exception
            self._add(
                SideEffectType.ReturnValue,
                node,
                "Function returns a non-None value",
            )

        # Track return names for DeferredReturnMutation
        if isinstance(node.value, ast.Name):
            self._return_names.add(node.value.id)

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # ErrorReturn / Panic
    # ------------------------------------------------------------------

    def visit_Raise(self, node: ast.Raise) -> None:  # noqa: N802
        """Detect ErrorReturn and Panic effects.

        Panic: raise SystemExit (bare) or raise SystemExit(...) — ast.Raise node.
        ErrorReturn: all other raise statements.
        Per design.md: no overlap — a single ast.Raise cannot be both.
        """
        if node.exc is not None:
            exc = node.exc
            is_panic = False
            if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                is_panic = True
            elif (
                isinstance(exc, ast.Call)
                and isinstance(exc.func, ast.Name)
                and exc.func.id == "SystemExit"
            ):
                is_panic = True

            if is_panic:
                self._add(
                    SideEffectType.Panic,
                    node,
                    "Function raises SystemExit (terminates the interpreter)",
                )
            else:
                self._add(
                    SideEffectType.ErrorReturn,
                    node,
                    "Function raises an exception as part of its contract",
                )
        else:
            # Bare 're-raise' — still an ErrorReturn
            self._add(
                SideEffectType.ErrorReturn,
                node,
                "Function re-raises an exception",
            )
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # ReceiverMutation
    # ------------------------------------------------------------------

    def _check_receiver_mutation(self, targets: list[ast.expr]) -> bool:
        """Return True if any target is self.<attr> assignment."""
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                return True
        return False

    def _check_pointer_arg_mutation(self, targets: list[ast.expr]) -> bool:
        """Return True if any target is param[key] = val (subscript on a param)."""
        for target in targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id in self._params
            ):
                return True
        return False

    def _check_env_var_mutation(self, targets: list[ast.expr]) -> bool:
        """Return True if any target is os.environ[key] = val."""
        for target in targets:
            if isinstance(target, ast.Subscript):
                val = target.value
                if (
                    isinstance(val, ast.Attribute)
                    and val.attr == "environ"
                    and isinstance(val.value, ast.Name)
                    and val.value.id == "os"
                ):
                    return True
        return False

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        """Detect ReceiverMutation, PointerArgMutation, GlobalMutation, EnvVarMutation."""
        targets = node.targets

        # EnvVarMutation takes priority over PointerArgMutation for os.environ
        if self._check_env_var_mutation(targets):
            self._add(
                SideEffectType.EnvVarMutation,
                node,
                "Function mutates an environment variable via os.environ",
            )
        elif self._check_receiver_mutation(targets):
            self._add(
                SideEffectType.ReceiverMutation,
                node,
                "Method mutates receiver state via self.<attr> assignment",
            )
        elif self._check_pointer_arg_mutation(targets):
            self._add(
                SideEffectType.PointerArgMutation,
                node,
                "Function mutates a parameter via item assignment param[key] = val",
            )

        # GlobalMutation: assignment to a declared global name
        for target in targets:
            if isinstance(target, ast.Name) and target.id in self._global_names:
                self._add(
                    SideEffectType.GlobalMutation,
                    node,
                    f"Function mutates module-level global '{target.id}'",
                )

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        """Detect ReceiverMutation, PointerArgMutation, GlobalMutation via augmented assign."""
        target = node.target

        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ):
            self._add(
                SideEffectType.ReceiverMutation,
                node,
                "Method mutates receiver state via self.<attr> augmented assignment",
            )
        elif (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id in self._params
        ):
            self._add(
                SideEffectType.PointerArgMutation,
                node,
                "Function mutates a parameter via augmented item assignment",
            )
        elif isinstance(target, ast.Name) and target.id in self._global_names:
            self._add(
                SideEffectType.GlobalMutation,
                node,
                f"Function mutates module-level global '{target.id}' via augmented assignment",
            )

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # GlobalMutation — collect global declarations first
    # ------------------------------------------------------------------

    def visit_Global(self, node: ast.Global) -> None:  # noqa: N802
        """Record declared global names for subsequent GlobalMutation detection."""
        self._global_names.update(node.names)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # ClosureCaptureMutation — nonlocal + assignment in inner function
    # (attributed to the inner function; handled by FileDetector recursion)
    # ------------------------------------------------------------------

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:  # noqa: N802
        """Record declared nonlocal names for ClosureCaptureMutation detection."""
        # ClosureCaptureMutation is attributed to the inner function.
        # This visitor runs on the inner function, so we track nonlocal names
        # and detect assignment to them via visit_Assign/visit_AugAssign.
        # Use a separate set to avoid conflating with GlobalMutation.
        self._nonlocal_names.update(node.names)
        self.generic_visit(node)

    def _check_nonlocal_assignment(self, targets: list[ast.expr]) -> str | None:
        """Return the nonlocal name if any target is an assignment to one."""
        for target in targets:
            if isinstance(target, ast.Name) and target.id in self._nonlocal_names:
                return target.id
        return None

    # ------------------------------------------------------------------
    # Call-based effects
    # ------------------------------------------------------------------

    def visit_Call(  # noqa: N802, PLR0911, PLR0912, PLR0915
        self, node: ast.Call
    ) -> None:
        """Detect call-based effects: SliceMutation, MapMutation, WriterOutput,
        HTTPResponseWrite, ChannelSend, ChannelClose, FileSystemWrite,
        FileSystemDelete, FileSystemMeta, DatabaseWrite, DatabaseTransaction,
        GoroutineSpawn, CallbackInvocation, LogWrite, ContextCancellation,
        StdoutWrite, StderrWrite, TimeDependency, ProcessExit,
        ReflectionMutation, CgoCall, FinalizerRegistration.

        This method is a dispatch table for all call-based effect types.
        The high branch/statement count is inherent to the dispatch pattern
        and cannot be reduced without sacrificing readability or correctness.
        """
        func = node.func

        # --- Attribute calls: obj.method(...) ---
        if isinstance(func, ast.Attribute):
            obj = func.value
            method = func.attr

            obj_name: str | None = None
            if isinstance(obj, ast.Name):
                obj_name = obj.id

            # StderrWrite: sys.stderr.write(...)
            if (
                method == "write"
                and isinstance(obj, ast.Attribute)
                and obj.attr == "stderr"
                and isinstance(obj.value, ast.Name)
                and obj.value.id == "sys"
            ):
                self._add(
                    SideEffectType.StderrWrite,
                    node,
                    "Function writes to stderr via sys.stderr.write()",
                )
                self.generic_visit(node)
                return

            # StdoutWrite: sys.stdout.write(...)
            if (
                method == "write"
                and isinstance(obj, ast.Attribute)
                and obj.attr == "stdout"
                and isinstance(obj.value, ast.Name)
                and obj.value.id == "sys"
            ):
                self._add(
                    SideEffectType.StdoutWrite,
                    node,
                    "Function writes to stdout via sys.stdout.write()",
                )
                self.generic_visit(node)
                return

            # LogWrite: logging.info/debug/warning/error/critical/log(...)
            if obj_name in _LOG_NAMES:
                self._add(
                    SideEffectType.LogWrite,
                    node,
                    f"Function writes a log entry via {obj_name}.{method}()",
                )
                self.generic_visit(node)
                return

            # GoroutineSpawn: threading.Thread, asyncio.create_task, etc.
            if obj_name is not None and (obj_name, method) in _GOROUTINE_SPAWN_CALLS:
                self._add(
                    SideEffectType.GoroutineSpawn,
                    node,
                    f"Function spawns a concurrent task via {obj_name}.{method}()",
                )
                self.generic_visit(node)
                return

            # concurrent.futures.*.submit — check for submit on any futures obj
            if method == "submit" and obj_name is not None:
                # Heuristic: if the object is named executor/pool/futures
                if obj_name in {"executor", "pool", "futures", "thread_pool"}:
                    self._add(
                        SideEffectType.GoroutineSpawn,
                        node,
                        "Function submits a task to a thread/process pool",
                    )
                    self.generic_visit(node)
                    return

            # ProcessExit: sys.exit, os._exit, os.abort
            if obj_name is not None and (obj_name, method) in _PROCESS_EXIT_CALLS:
                self._add(
                    SideEffectType.ProcessExit,
                    node,
                    f"Function terminates the process via {obj_name}.{method}()",
                )
                self.generic_visit(node)
                return

            # TimeDependency: time.time, time.monotonic, datetime.now, etc.
            if obj_name is not None and (obj_name, method) in _TIME_CALLS:
                self._add(
                    SideEffectType.TimeDependency,
                    node,
                    f"Function reads the current time via {obj_name}.{method}()",
                )
                self.generic_visit(node)
                return

            # FileSystemDelete: os.remove, os.unlink, shutil.rmtree
            if obj_name is not None and (obj_name, method) in _FS_DELETE_CALLS:
                self._add(
                    SideEffectType.FileSystemDelete,
                    node,
                    f"Function deletes a filesystem entry via {obj_name}.{method}()",
                )
                self.generic_visit(node)
                return

            # FileSystemMeta: os.chmod, os.chown, os.utime, os.symlink, os.link
            if obj_name is not None and (obj_name, method) in _FS_META_CALLS:
                self._add(
                    SideEffectType.FileSystemMeta,
                    node,
                    f"Function modifies filesystem metadata via {obj_name}.{method}()",
                )
                self.generic_visit(node)
                return

            # pathlib.Path.unlink() — FileSystemDelete
            if method == "unlink":
                self._add(
                    SideEffectType.FileSystemDelete,
                    node,
                    "Function deletes a filesystem entry via Path.unlink()",
                )
                self.generic_visit(node)
                return

            # pathlib.Path.chmod() — FileSystemMeta
            if method == "chmod":
                self._add(
                    SideEffectType.FileSystemMeta,
                    node,
                    "Function modifies filesystem permissions via Path.chmod()",
                )
                self.generic_visit(node)
                return

            # pathlib.Path.write_text / write_bytes — FileSystemWrite
            if method in {"write_text", "write_bytes"}:
                self._add(
                    SideEffectType.FileSystemWrite,
                    node,
                    f"Function writes to the filesystem via Path.{method}()",
                )
                self.generic_visit(node)
                return

            # ReflectionMutation: object.__setattr__(...)
            if method == "__setattr__":
                self._add(
                    SideEffectType.ReflectionMutation,
                    node,
                    "Function mutates an object via __setattr__()",
                )
                self.generic_visit(node)
                return

            # FinalizerRegistration: weakref.finalize(...)
            if obj_name == "weakref" and method == "finalize":
                self._add(
                    SideEffectType.FinalizerRegistration,
                    node,
                    "Function registers a finalizer via weakref.finalize()",
                )
                self.generic_visit(node)
                return

            # CgoCall: ctypes.* or cffi.*
            if obj_name in {"ctypes", "cffi"}:
                self._add(
                    SideEffectType.CgoCall,
                    node,
                    f"Function calls native code via {obj_name}.{method}()",
                )
                self.generic_visit(node)
                return

            # Parameter-based effects — obj must be a known parameter
            if obj_name in self._params:
                # HTTPResponseWrite: .write() on response/resp parameter
                if method == "write" and obj_name in {"response", "resp"}:
                    self._add(
                        SideEffectType.HTTPResponseWrite,
                        node,
                        f"Function writes to HTTP response via {obj_name}.write()",
                    )
                    self.generic_visit(node)
                    return

                # WriterOutput: .write() on any other parameter
                if method == "write":
                    self._add(
                        SideEffectType.WriterOutput,
                        node,
                        f"Function writes to injected writer via {obj_name}.write()",
                    )
                    self.generic_visit(node)
                    return

                # SliceMutation: list methods on a parameter
                if method in _SLICE_METHODS:
                    self._add(
                        SideEffectType.SliceMutation,
                        node,
                        f"Function mutates a list parameter via {obj_name}.{method}()",
                    )
                    self.generic_visit(node)
                    return

                # MapMutation: dict methods on a parameter
                if method in _MAP_METHODS:
                    self._add(
                        SideEffectType.MapMutation,
                        node,
                        f"Function mutates a dict parameter via {obj_name}.{method}()",
                    )
                    self.generic_visit(node)
                    return

                # ChannelSend: .put() on a parameter
                if method == "put":
                    self._add(
                        SideEffectType.ChannelSend,
                        node,
                        f"Function sends to a channel/queue via {obj_name}.put()",
                    )
                    self.generic_visit(node)
                    return

                # ChannelClose: .close() on a parameter
                if method == "close":
                    self._add(
                        SideEffectType.ChannelClose,
                        node,
                        f"Function closes a channel/queue via {obj_name}.close()",
                    )
                    self.generic_visit(node)
                    return

                # DatabaseWrite: .execute() or .commit() on a parameter
                if method in {"execute", "commit"}:
                    self._add(
                        SideEffectType.DatabaseWrite,
                        node,
                        f"Function writes to a database via {obj_name}.{method}()",
                    )
                    self.generic_visit(node)
                    return

                # ContextCancellation: .cancel() on any parameter
                if method == "cancel":
                    self._add(
                        SideEffectType.ContextCancellation,
                        node,
                        f"Function cancels a task/future via {obj_name}.cancel()",
                    )
                    self.generic_visit(node)
                    return

                # ContextCancellation: .set() on a parameter (threading.Event)
                if method == "set":
                    self._add(
                        SideEffectType.ContextCancellation,
                        node,
                        f"Function signals cancellation via {obj_name}.set()",
                    )
                    self.generic_visit(node)
                    return

        # --- Simple name calls: func(...) ---
        elif isinstance(func, ast.Name):
            fn = func.id

            # StdoutWrite: print(...)
            if fn == "print":
                self._add(
                    SideEffectType.StdoutWrite,
                    node,
                    "Function writes to stdout via print()",
                )
                self.generic_visit(node)
                return

            # ReflectionMutation: setattr(...)
            if fn == "setattr":
                self._add(
                    SideEffectType.ReflectionMutation,
                    node,
                    "Function mutates an object via setattr()",
                )
                self.generic_visit(node)
                return

            # FileSystemWrite: open(path, mode) with write mode
            if fn == "open":
                mode = _extract_open_mode(node)
                if mode in _WRITE_MODES:
                    self._add(
                        SideEffectType.FileSystemWrite,
                        node,
                        f"Function opens a file for writing with mode '{mode}'",
                    )
                    self.generic_visit(node)
                    return

            # CallbackInvocation: calling a parameter directly
            if fn in self._params:
                self._add(
                    SideEffectType.CallbackInvocation,
                    node,
                    f"Function invokes a callable parameter '{fn}'",
                )
                self.generic_visit(node)
                return

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # With statement — DatabaseTransaction, MutexOp
    # ------------------------------------------------------------------

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        """Detect DatabaseTransaction and MutexOp from 'with param:' patterns."""
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Name) and ctx.id in self._params:
                # MutexOp and DatabaseTransaction both match 'with param:'
                # Use MutexOp for lock-like names, DatabaseTransaction for connection-like names
                # Heuristic: connection/session/tx → DatabaseTransaction; else MutexOp
                if ctx.id in {"connection", "conn", "session", "tx", "transaction"}:
                    self._add(
                        SideEffectType.DatabaseTransaction,
                        node,
                        f"Function uses a database connection as a context manager via {ctx.id}",
                    )
                else:
                    self._add(
                        SideEffectType.MutexOp,
                        node,
                        f"Function acquires a lock/mutex via 'with {ctx.id}:'",
                    )

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Try/Finally — DeferredReturnMutation
    # ------------------------------------------------------------------

    def collect_deferred_return_mutation(
        self, fn_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Detect DeferredReturnMutation by scanning the whole function body.

        Pattern: a finally block assigns to name N, AND the function body
        (outside the finally block) contains 'return N'.

        This must be called after the full visitor pass so that all return
        names collected by visit_Return are available. It scans the function
        body for Try nodes with finally blocks.

        Args:
            fn_node: The function definition AST node to scan.
        """
        # Collect all return names from the function body (excluding finally blocks)
        all_return_names: set[str] = set()
        for stmt in fn_node.body:
            # Collect returns from the function body, but NOT from finally blocks
            all_return_names |= _collect_return_names_excluding_finally([stmt])

        # Now find Try nodes with finally blocks and check for overlap
        for node in ast.walk(ast.Module(body=fn_node.body, type_ignores=[])):
            if not isinstance(node, ast.Try):
                continue
            if not node.finalbody:
                continue

            # Collect names assigned in the finally block
            finally_names: set[str] = set()
            for stmt in node.finalbody:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            finally_names.add(target.id)
                elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                    finally_names.add(stmt.target.id)

            overlap = finally_names & all_return_names
            if overlap:
                self._effects.append(
                    _make_effect(
                        rel_path=self._rel_path,
                        fn_name=self._fn_name,
                        effect_type=SideEffectType.DeferredReturnMutation,
                        node=node,
                        description=(
                            "Function's finally block assigns to a variable "
                            "that is subsequently returned"
                        ),
                    )
                )
                # Only emit once per function even if multiple try/finally blocks match
                return


def _collect_return_names_excluding_finally(stmts: list[ast.stmt]) -> set[str]:
    """Collect return names from statements, skipping finally block contents.

    Used for DeferredReturnMutation detection: we want return names from the
    main function body and try/except/else blocks, but NOT from finally blocks
    (since the return must be OUTSIDE the finally block per design.md).

    Args:
        stmts: List of AST statement nodes to scan.

    Returns:
        Set of variable names that appear as return values outside finally blocks.
    """
    names: set[str] = set()
    for stmt in stmts:
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Name):
            names.add(stmt.value.id)
        elif isinstance(stmt, ast.Try):
            # Recurse into body, handlers, orelse — but NOT finalbody
            names |= _collect_return_names_excluding_finally(stmt.body)
            for handler in stmt.handlers:
                names |= _collect_return_names_excluding_finally(handler.body)
            names |= _collect_return_names_excluding_finally(stmt.orelse)
            # Deliberately skip stmt.finalbody
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Do not recurse into nested functions
            pass
        else:
            # For other compound statements, recurse into their sub-statements
            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, ast.stmt):
                    names |= _collect_return_names_excluding_finally([child])
    return names


def _extract_open_mode(call: ast.Call) -> str:
    """Extract the mode string from an open() call, if present.

    Handles both positional (open(path, 'w')) and keyword (open(path, mode='w'))
    argument styles.

    Args:
        call: The ast.Call node for the open() call.

    Returns:
        The mode string if found and is a string literal, else empty string.
    """
    # Positional: open(path, mode) — mode is the second positional argument (index 1)
    if len(call.args) > _OPEN_MODE_ARG_INDEX:
        mode_arg = call.args[_OPEN_MODE_ARG_INDEX]
        if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
            return mode_arg.value
    # Keyword: open(path, mode='w')
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return ""


def _is_annotation_none(returns: ast.expr | None) -> bool:
    """Return True if the return annotation is exactly '-> None'.

    Args:
        returns: The return annotation AST node, or None if absent.

    Returns:
        True if the annotation is the None constant.
    """
    if returns is None:
        return False
    return isinstance(returns, ast.Constant) and returns.value is None


def _extract_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Extract the set of parameter names from a function definition.

    Includes positional, keyword-only, *args, and **kwargs parameters.
    Excludes 'self' and 'cls' (receiver names).

    Args:
        node: The function definition AST node.

    Returns:
        Set of parameter name strings.
    """
    args = node.args
    params: set[str] = set()
    for arg in args.args + args.posonlyargs + args.kwonlyargs:
        if arg.arg not in {"self", "cls"}:
            params.add(arg.arg)
    if args.vararg:
        params.add(args.vararg.arg)
    if args.kwarg:
        params.add(args.kwarg.arg)
    return params


# ---------------------------------------------------------------------------
# Nested function walker — visits all function defs recursively
# ---------------------------------------------------------------------------


def _walk_functions(
    stmts: list[ast.stmt],
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Walk a statement list and yield all function definitions at any depth.

    Args:
        stmts: Top-level or nested statement list to walk.

    Returns:
        List of all FunctionDef and AsyncFunctionDef nodes found.
    """
    result: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.append(node)
    return result


# ---------------------------------------------------------------------------
# ClosureCaptureMutation visitor — runs on inner functions only
# ---------------------------------------------------------------------------


class _ClosureVisitor(ast.NodeVisitor):
    """Detects ClosureCaptureMutation in inner (nested) functions.

    The effect is attributed to the inner function containing the nonlocal
    statement, not the outer function.

    Call `visit_body(fn_node)` rather than `visit(fn_node)` to avoid the
    top-level function dispatch being skipped by the nesting guard.
    """

    def __init__(self, *, rel_path: str, fn_name: str) -> None:
        self._rel_path = rel_path
        self._fn_name = fn_name
        self._nonlocal_names: set[str] = set()
        self._effects: list[SideEffect] = []
        self._depth = 0  # depth > 0 means we are inside the target function

    @property
    def effects(self) -> list[SideEffect]:
        """All detected ClosureCaptureMutation effects."""
        return self._effects

    def visit_body(self, fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Visit the body of the inner function directly.

        Bypasses the FunctionDef dispatch so the nesting guard does not
        skip the top-level inner function.

        Args:
            fn_node: The inner function definition to scan.
        """
        self._depth += 1
        for stmt in fn_node.body:
            self.visit(stmt)
        self._depth -= 1

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:  # noqa: N802
        """Record nonlocal variable names."""
        self._nonlocal_names.update(node.names)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        """Detect assignment to a nonlocal variable."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in self._nonlocal_names:
                self._effects.append(
                    _make_effect(
                        rel_path=self._rel_path,
                        fn_name=self._fn_name,
                        effect_type=SideEffectType.ClosureCaptureMutation,
                        node=node,
                        description=(
                            f"Inner function mutates captured variable '{target.id}' "
                            f"via nonlocal assignment"
                        ),
                    )
                )
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        """Detect augmented assignment to a nonlocal variable."""
        if isinstance(node.target, ast.Name) and node.target.id in self._nonlocal_names:
            self._effects.append(
                _make_effect(
                    rel_path=self._rel_path,
                    fn_name=self._fn_name,
                    effect_type=SideEffectType.ClosureCaptureMutation,
                    node=node,
                    description=(
                        f"Inner function mutates captured variable '{node.target.id}' "
                        f"via nonlocal augmented assignment"
                    ),
                )
            )
        self.generic_visit(node)

    # Do not recurse into further nested functions
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Skip further nested functions."""

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Skip further nested async functions."""


# ---------------------------------------------------------------------------
# FileDetector — public API
# ---------------------------------------------------------------------------


class FileDetector:
    """Detects side effects in a Python source file using AST-only analysis.

    Uses a two-phase approach:
    1. Module-level pass: detect SentinelError from top-level ClassDef nodes.
    2. Per-function pass: FunctionVisitor collects all other effect types.

    Per design.md: no code is executed, no modules are imported.
    """

    @staticmethod
    def detect(
        path: Path,
        *,
        root: Path,
        callers: dict[str, int] | None = None,
    ) -> list[FunctionTarget]:
        """Detect all side effects in a Python source file.

        Args:
            path: Absolute or relative path to the Python source file.
            root: Project root directory. Used to compute project-relative
                paths for effect IDs and location strings (EC-003).
            callers: Optional mapping of function qualified name → caller
                module count. When provided, sets FunctionTarget.caller_count.
                Defaults to None (caller_count = 0 for all functions).

        Returns:
            List of FunctionTarget objects, one per analyzed function plus
            one synthetic '<module>' target for module-level effects.

        Raises:
            GazeParseError: When ast.parse() fails with SyntaxError or
                ValueError (e.g., null bytes in source). The exception
                carries the file path in its message.
        """
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise GazeParseError(f"Cannot read {path}: {e}") from e

        try:
            module = ast.parse(source, filename=str(path))
        except (SyntaxError, ValueError) as e:
            raise GazeParseError(f"Cannot parse {path}: {e}") from e

        # Compute the project-relative path for stable IDs (EC-003)
        try:
            rel_path = str(path.relative_to(root))
        except ValueError:
            # Path is not under root — use the filename only as a fallback
            rel_path = path.name

        targets: list[FunctionTarget] = []

        # --- Phase 1: Module-level SentinelError detection ---
        sentinel_pairs = _sentinel_effects(module, rel_path)
        if sentinel_pairs:
            module_target = FunctionTarget(
                name="<module>",
                file_path=rel_path,
                line=1,
                complexity=1,
                caller_count=0,
                effects=[effect for _, effect in sentinel_pairs],
            )
            targets.append(module_target)

        # --- Phase 2: Per-function pass ---
        # Walk ALL function definitions at any nesting level
        for fn_node in ast.walk(module):
            if not isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            fn_name = fn_node.name
            params = _extract_params(fn_node)
            has_annotation = fn_node.returns is not None
            annotation_is_none = _is_annotation_none(fn_node.returns)

            # Check if this is an inner (nested) function by looking for nonlocal
            is_inner = _has_nonlocal(fn_node)

            effects: list[SideEffect] = []

            if is_inner:
                # Run ClosureCaptureMutation detection for inner functions.
                # Use visit_body() to bypass the top-level FunctionDef dispatch
                # guard so the inner function body is actually visited.
                closure_visitor = _ClosureVisitor(rel_path=rel_path, fn_name=fn_name)
                closure_visitor.visit_body(fn_node)
                effects.extend(closure_visitor.effects)

            # Run the main function visitor for all other effects
            visitor = _FunctionVisitor(
                rel_path=rel_path,
                fn_name=fn_name,
                params=params,
                has_return_annotation=has_annotation,
                annotation_is_none=annotation_is_none,
            )
            visitor.visit(fn_node)
            # Post-process: DeferredReturnMutation requires whole-function context
            visitor.collect_deferred_return_mutation(fn_node)
            effects.extend(visitor.effects)

            # Compute complexity
            complexity = cyclomatic_complexity(fn_node)

            # Resolve caller count
            caller_count = 0
            if callers is not None:
                caller_count = callers.get(fn_name, 0)

            target = FunctionTarget(
                name=fn_name,
                file_path=rel_path,
                line=fn_node.lineno,
                complexity=complexity,
                caller_count=caller_count,
                effects=effects,
            )
            targets.append(target)

        return targets


def _has_nonlocal(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the function body contains a nonlocal statement.

    Only checks the direct body — does not recurse into nested functions.

    Args:
        fn_node: The function definition AST node.

    Returns:
        True if the function body contains at least one ast.Nonlocal node.
    """
    for stmt in fn_node.body:
        if isinstance(stmt, ast.Nonlocal):
            return True
    return False
