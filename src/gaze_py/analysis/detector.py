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

# Qualified names for GoroutineSpawn — subprocess module (separate from
# _GOROUTINE_SPAWN_CALLS to keep OS-process spawning semantically distinct
# from thread/coroutine spawning). concurrent.futures executor constructors
# are deferred — they require chained-attribute obj_name handling.
_SUBPROCESS_SPAWN_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("subprocess", "Popen"),
        ("subprocess", "run"),
        ("subprocess", "call"),
        ("subprocess", "check_output"),
        ("subprocess", "check_call"),
    }
)

# DBAPI module names whose .connect() return value is a database connection.
# Used to track connections bound to local variables so DatabaseWrite fires
# for in-function constructions (con = sqlite3.connect(...); con.execute(...)),
# not only for connections received as parameters. Explicit allowlist keeps
# false positives at zero: socket.connect()/smtplib connect patterns are calls
# on instances, not on these module names.
_DBAPI_MODULES: frozenset[str] = frozenset(
    {"sqlite3", "psycopg", "psycopg2", "pymysql", "MySQLdb", "cx_Oracle", "duckdb", "mariadb"}
)

# Write methods on a tracked DB connection/cursor local. The parameter path in
# _handle_param_attr_call keeps its narrower {execute, commit} set (any-param
# heuristic); locals tracked from a known DBAPI construction are unambiguous,
# so the executemany/executescript siblings are safe to include here.
_DB_WRITE_METHODS: frozenset[str] = frozenset({"execute", "executemany", "executescript", "commit"})

# Decorator names (bare and qualified) that indicate lru_cache/cache decoration
_LRU_CACHE_DECORATORS: frozenset[str] = frozenset({"lru_cache", "cache"})

# Qualified names for WaitGroupOp detection (asyncio module only).
# concurrent.futures.wait is detected via name heuristic below
# (obj_name == "futures") when imported as: import concurrent.futures as futures.
# threading.Barrier.wait is detected via name heuristic (obj_name in {"barrier",...}).
_WAIT_GROUP_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("asyncio", "gather"),
        ("asyncio", "wait"),
    }
)

# ctypes pointer variable name substrings/prefixes for UnsafeMutation detection.
# Substring match: "ptr" matches "ptrdiff", "ptr_buf"; "buf" matches "buffer",
# "bufio"; "mem" matches "membuffer"; "raw" matches "rawdata".
# "p_" matches ctypes naming convention: p_value, p_buf, p_data.
# False-positive risk is acceptable for P4 ("may detect") per EC-001.
_CTYPES_PTR_NAMES: frozenset[str] = frozenset({"ptr", "buf", "mem", "raw", "p_"})

# AtomicOp (P3) and SyncPoolOp (P4) are permanently closed — no Python equivalent.
# See taxonomy/effects.py for rationale. EC-001/EC-005.

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
        module_names: set[str] | None = None,
    ) -> None:
        """Initialize the visitor for a specific function.

        Args:
            rel_path: Project-relative path to the source file.
            fn_name: Simple function name.
            params: Set of parameter names for this function.
            has_return_annotation: True if the function has a return annotation.
            annotation_is_none: True if the annotation is exactly '-> None'.
            module_names: Names bound to imported modules at module level
                (from _collect_module_names). Used to detect GlobalMutation
                via module-attribute assignment (os.getcwd = ...).
                Default: None (no module-attr detection).
        """
        self._rel_path = rel_path
        self._fn_name = fn_name
        self._params = params
        self._has_return_annotation = has_return_annotation
        self._annotation_is_none = annotation_is_none
        self._module_names = module_names or set()
        self._effects: list[SideEffect] = []
        self._depth = 0  # nesting depth; skip nested FunctionDef when > 0
        # For GlobalMutation: track declared global names
        self._global_names: set[str] = set()
        # For DatabaseWrite: locals bound from a known DBAPI construction
        # (con = sqlite3.connect(...)) or a cursor derived from one.
        self._db_locals: set[str] = set()
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

        # EC-005/G.1: unannotated `return None` is idiomatically equivalent to
        # bare `return` in Python — it does not signal that None is a meaningful
        # return value. Treating it as ReturnValue would produce false positives
        # on a large class of void functions. Documented in:
        # openspec/changes/archive/return-none-annotation/
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

        # Track DB connection locals (con = sqlite3.connect(...)) for the
        # DatabaseWrite local-call path. Tracking only — emits nothing.
        self._track_db_local(node)

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
        elif (mod_attr := self._module_attr_target(targets)) is not None:
            # GlobalMutation: assignment to an attribute of an imported module
            # (os.getcwd = fake) — module objects are process-global state.
            self._add(
                SideEffectType.GlobalMutation,
                node,
                f"Function mutates imported module attribute '{mod_attr}'",
            )

        # GlobalMutation: assignment to a declared global name
        for target in targets:
            if isinstance(target, ast.Name) and target.id in self._global_names:
                self._add(
                    SideEffectType.GlobalMutation,
                    node,
                    f"Function mutates module-level global '{target.id}'",
                )

        # UnsafeMutation: ctypes pointer subscript assignment (ptr[0] = ...)
        # Two independent checks — subscript and .contents are not mutually exclusive.
        for target in targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and any(p in target.value.id for p in _CTYPES_PTR_NAMES)
            ):
                self._add(
                    SideEffectType.UnsafeMutation,
                    node,
                    f"Function writes to raw memory via {target.value.id}[...] = ...",
                )
                break

        # UnsafeMutation: ctypes .contents attribute assignment (ptr.contents = ...)
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "contents"
                and isinstance(target.value, ast.Name)
            ):
                self._add(
                    SideEffectType.UnsafeMutation,
                    node,
                    f"Function writes to raw memory via {target.value.id}.contents",
                )
                break

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
        elif (mod_attr := self._module_attr_target([target])) is not None:
            self._add(
                SideEffectType.GlobalMutation,
                node,
                f"Function mutates imported module attribute '{mod_attr}' via augmented assignment",
            )

        self.generic_visit(node)

    def _module_attr_target(self, targets: list[ast.expr]) -> str | None:
        """Return 'module.attr' when a target assigns to an imported module attribute.

        Detects monkeypatch-style global mutation: `os.getcwd = fake`. Module
        objects are process-global state, so attribute assignment on a name
        bound by a module-level `import` is a GlobalMutation (the Go reference
        implements GlobalMutation; the dedicated MonkeyPatch type is not yet
        in the port's taxonomy — see docs/audit-2026-07-12.md G1b/G1c).

        Parameters shadow module names: a param named `os` suppresses the
        check for that name (assignment then mutates the argument, not the
        module — PointerArgMutation territory, and attribute-assignment on
        params is deliberately not claimed here).

        Args:
            targets: Assignment target expressions.

        Returns:
            'module.attr' for the first matching target, or None.
        """
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in self._module_names
                and target.value.id not in self._params
            ):
                return f"{target.value.id}.{target.attr}"
        return None

    def _track_db_local(self, node: ast.Assign) -> None:
        """Record locals bound from a known DBAPI construction.

        Two forms are tracked (emission happens in _handle_db_local_call):
        - con = sqlite3.connect(...)        (module in _DBAPI_MODULES)
        - cur = con.cursor()                (receiver already tracked, or a
                                             _is_db_context() name like 'conn')

        Args:
            node: The assignment statement being visited.
        """
        value = node.value
        if not isinstance(value, ast.Call):
            return
        func = value.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return
        owner = func.value.id
        is_connect = func.attr == "connect" and owner in _DBAPI_MODULES
        is_cursor = func.attr == "cursor" and (owner in self._db_locals or _is_db_context(owner))
        if is_connect or is_cursor:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._db_locals.add(target.id)

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

    def _handle_stream_writes(self, obj: ast.expr, method: str, node: ast.Call) -> bool:
        """Detect StderrWrite and StdoutWrite from sys.stderr/stdout.write().

        Args:
            obj: The object expression (left side of the attribute call).
            method: The method name being called.
            node: The full ast.Call node.

        Returns:
            True when a stream write effect was detected and added.
        """
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
            return True

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
            return True

        return False

    def _handle_pathlib_attr_call(self, method: str, node: ast.Call) -> bool:
        """Detect pathlib.Path filesystem effects from method name alone.

        Checks match on method name only (independent of obj_name), so this
        helper is safe to call before _handle_lib_attr_call which requires
        obj_name to be in a specific set.

        Args:
            method: The method name being called.
            node: The full ast.Call node.

        Returns:
            True when a pathlib filesystem effect was detected and added.
        """
        # pathlib.Path.unlink() — FileSystemDelete
        if method == "unlink":
            self._add(
                SideEffectType.FileSystemDelete,
                node,
                "Function deletes a filesystem entry via Path.unlink()",
            )
            self.generic_visit(node)
            return True

        # pathlib.Path.chmod() — FileSystemMeta
        if method == "chmod":
            self._add(
                SideEffectType.FileSystemMeta,
                node,
                "Function modifies filesystem permissions via Path.chmod()",
            )
            self.generic_visit(node)
            return True

        # pathlib.Path.write_text / write_bytes — FileSystemWrite
        if method in {"write_text", "write_bytes"}:
            self._add(
                SideEffectType.FileSystemWrite,
                node,
                f"Function writes to the filesystem via Path.{method}()",
            )
            self.generic_visit(node)
            return True

        return False

    def _handle_goroutine_process_time(  # noqa: PLR0911
        self, obj_name: str | None, method: str, node: ast.Call
    ) -> bool:
        """Detect goroutine spawn, process exit, and time dependency effects.

        Extracted from ``_handle_lib_attr_call`` to reduce its cyclomatic
        complexity.  Handles the four compound-condition branches that each
        require an ``obj_name is not None`` guard before a set-membership test.

        Args:
            obj_name: The object name if the receiver is a simple Name, else None.
            method: The method name being called.
            node: The full ast.Call node.

        Returns:
            True when an effect was detected and added.
        """
        # GoroutineSpawn: threading.Thread, asyncio.create_task, etc.
        if obj_name is not None and (obj_name, method) in _GOROUTINE_SPAWN_CALLS:
            self._add(
                SideEffectType.GoroutineSpawn,
                node,
                f"Function spawns a concurrent task via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # GoroutineSpawn: subprocess.Popen/run/call/check_output/check_call
        if obj_name is not None and (obj_name, method) in _SUBPROCESS_SPAWN_CALLS:
            self._add(
                SideEffectType.GoroutineSpawn,
                node,
                f"Function spawns a child process via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

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
                return True

        # WaitGroupOp: asyncio.gather, asyncio.wait
        if obj_name is not None and (obj_name, method) in _WAIT_GROUP_CALLS:
            self._add(
                SideEffectType.WaitGroupOp,
                node,
                f"Function synchronizes on a group of tasks via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # WaitGroupOp: threading.Barrier.wait (name heuristic)
        if method == "wait" and obj_name in {"barrier", "barriers"}:
            self._add(
                SideEffectType.WaitGroupOp,
                node,
                f"Function waits on a threading.Barrier via {obj_name}.wait()",
            )
            self.generic_visit(node)
            return True

        # WaitGroupOp: concurrent.futures.wait (requires alias import:
        #   import concurrent.futures as futures)
        if method == "wait" and obj_name == "futures":
            self._add(
                SideEffectType.WaitGroupOp,
                node,
                "Function waits on a concurrent.futures result set via futures.wait()",
            )
            self.generic_visit(node)
            return True

        # ProcessExit: sys.exit, os._exit, os.abort
        if obj_name is not None and (obj_name, method) in _PROCESS_EXIT_CALLS:
            self._add(
                SideEffectType.ProcessExit,
                node,
                f"Function terminates the process via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # TimeDependency: time.time, time.monotonic, datetime.now, etc.
        if obj_name is not None and (obj_name, method) in _TIME_CALLS:
            self._add(
                SideEffectType.TimeDependency,
                node,
                f"Function reads the current time via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        return False

    def _handle_lib_attr_call(  # noqa: PLR0911
        self, obj_name: str | None, method: str, node: ast.Call
    ) -> bool:
        """Detect library attribute call effects (logging, threading, os, etc.).

        All obj_name guards remain inside this helper per spec requirement.
        Goroutine spawn, process exit, and time dependency detection are
        delegated to ``_handle_goroutine_process_time`` to keep CC ≤ 10.

        Args:
            obj_name: The object name if the receiver is a simple Name, else None.
            method: The method name being called.
            node: The full ast.Call node.

        Returns:
            True when a library attribute effect was detected and added.
        """
        # LogWrite: logging.info/debug/warning/error/critical/log(...)
        if obj_name in _LOG_NAMES:
            self._add(
                SideEffectType.LogWrite,
                node,
                f"Function writes a log entry via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # warnings.warn() — two effects:
        # (1) LogWrite: structured, filterable developer-facing warning emission
        # (2) GlobalMutation: typically writes to __warningregistry__ in the calling
        #     module's globals for deduplication (filter-configuration dependent)
        if obj_name == "warnings" and method == "warn":
            self._add(
                SideEffectType.LogWrite,
                node,
                "Function emits a warning via warnings.warn()"
                " (structured developer-facing output;"
                " may go to stderr, logging, or be suppressed)",
            )
            self._add(
                SideEffectType.GlobalMutation,
                node,
                "Function typically mutates __warningregistry__ in the calling module"
                " via warnings.warn() (deduplication state; filter-configuration dependent)",
            )
            self.generic_visit(node)
            return True

        # Delegate goroutine/process/time detection to reduce CC.
        if self._handle_goroutine_process_time(obj_name, method, node):
            return True

        # FileSystemDelete: os.remove, os.unlink, shutil.rmtree
        if obj_name is not None and (obj_name, method) in _FS_DELETE_CALLS:
            self._add(
                SideEffectType.FileSystemDelete,
                node,
                f"Function deletes a filesystem entry via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # FileSystemMeta: os.chmod, os.chown, os.utime, os.symlink, os.link
        if obj_name is not None and (obj_name, method) in _FS_META_CALLS:
            self._add(
                SideEffectType.FileSystemMeta,
                node,
                f"Function modifies filesystem metadata via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # ReflectionMutation: object.__setattr__(...)
        if method == "__setattr__":
            self._add(
                SideEffectType.ReflectionMutation,
                node,
                "Function mutates an object via __setattr__()",
            )
            self.generic_visit(node)
            return True

        # FinalizerRegistration: weakref.finalize(...)
        if obj_name == "weakref" and method == "finalize":
            self._add(
                SideEffectType.FinalizerRegistration,
                node,
                "Function registers a finalizer via weakref.finalize()",
            )
            self.generic_visit(node)
            return True

        # GlobalMutation: atexit.register() — mutates interpreter shutdown handler list
        if obj_name == "atexit" and method == "register":
            self._add(
                SideEffectType.GlobalMutation,
                node,
                "Function registers a shutdown callback via atexit.register()"
                " (mutates interpreter-global atexit handler list)",
            )
            self.generic_visit(node)
            return True

        # CgoCall: ctypes.* or cffi.*
        if obj_name in {"ctypes", "cffi"}:
            self._add(
                SideEffectType.CgoCall,
                node,
                f"Function calls native code via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        return False

    def _handle_param_attr_call(  # noqa: PLR0911
        self, obj_name: str | None, method: str, node: ast.Call
    ) -> bool:
        """Detect parameter-based attribute call effects.

        All obj_name in self._params guards remain inside this helper.

        Args:
            obj_name: The object name if the receiver is a simple Name, else None.
            method: The method name being called.
            node: The full ast.Call node.

        Returns:
            True when a parameter attribute effect was detected and added.
        """
        if obj_name not in self._params:
            return False

        # HTTPResponseWrite: .write() on response/resp parameter
        if method == "write" and obj_name in {"response", "resp"}:
            self._add(
                SideEffectType.HTTPResponseWrite,
                node,
                f"Function writes to HTTP response via {obj_name}.write()",
            )
            self.generic_visit(node)
            return True

        # WriterOutput: .write() on any other parameter
        if method == "write":
            self._add(
                SideEffectType.WriterOutput,
                node,
                f"Function writes to injected writer via {obj_name}.write()",
            )
            self.generic_visit(node)
            return True

        # SliceMutation: list methods on a parameter
        if method in _SLICE_METHODS:
            self._add(
                SideEffectType.SliceMutation,
                node,
                f"Function mutates a list parameter via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # MapMutation: dict methods on a parameter
        if method in _MAP_METHODS:
            self._add(
                SideEffectType.MapMutation,
                node,
                f"Function mutates a dict parameter via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # ChannelSend: .put() on a parameter
        if method == "put":
            self._add(
                SideEffectType.ChannelSend,
                node,
                f"Function sends to a channel/queue via {obj_name}.put()",
            )
            self.generic_visit(node)
            return True

        # ChannelClose: .close() on a parameter
        if method == "close":
            self._add(
                SideEffectType.ChannelClose,
                node,
                f"Function closes a channel/queue via {obj_name}.close()",
            )
            self.generic_visit(node)
            return True

        # DatabaseWrite: .execute() or .commit() on a parameter
        if method in {"execute", "commit"}:
            self._add(
                SideEffectType.DatabaseWrite,
                node,
                f"Function writes to a database via {obj_name}.{method}()",
            )
            self.generic_visit(node)
            return True

        # ContextCancellation: .cancel() on any parameter
        if method == "cancel":
            self._add(
                SideEffectType.ContextCancellation,
                node,
                f"Function cancels a task/future via {obj_name}.cancel()",
            )
            self.generic_visit(node)
            return True

        # ContextCancellation: .set() on a parameter (threading.Event)
        if method == "set":
            self._add(
                SideEffectType.ContextCancellation,
                node,
                f"Function signals cancellation via {obj_name}.set()",
            )
            self.generic_visit(node)
            return True

        return False

    def _handle_db_local_call(self, obj_name: str | None, method: str, node: ast.Call) -> bool:
        """Detect DatabaseWrite on a tracked DB connection/cursor local.

        Fires only for names recorded by _track_db_local (constructed from a
        known DBAPI module inside this function), so it carries none of the
        any-parameter heuristic risk of _handle_param_attr_call.

        Args:
            obj_name: Receiver name of the attribute call, or None.
            method: The method being called.
            node: The full ast.Call node.

        Returns:
            True when a DatabaseWrite effect was detected and added.
        """
        if obj_name is None or obj_name not in self._db_locals:
            return False
        if method in _DB_WRITE_METHODS:
            self._add(
                SideEffectType.DatabaseWrite,
                node,
                f"Function writes to a database via {obj_name}.{method}() "
                "on a connection constructed in-function",
            )
            self.generic_visit(node)
            return True
        return False

    def _handle_name_call(self, fn: str, node: ast.Call) -> bool:
        """Detect simple name call effects (print, setattr, open, callbacks).

        Args:
            fn: The function name being called.
            node: The full ast.Call node.

        Returns:
            True when a name call effect was detected and added.
        """
        # StdoutWrite: print(...)
        if fn == "print":
            self._add(
                SideEffectType.StdoutWrite,
                node,
                "Function writes to stdout via print()",
            )
            self.generic_visit(node)
            return True

        # ReflectionMutation: setattr(...)
        if fn == "setattr":
            self._add(
                SideEffectType.ReflectionMutation,
                node,
                "Function mutates an object via setattr()",
            )
            self.generic_visit(node)
            return True

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
                return True

        # CallbackInvocation: calling a parameter directly
        if fn in self._params:
            self._add(
                SideEffectType.CallbackInvocation,
                node,
                f"Function invokes a callable parameter '{fn}'",
            )
            self.generic_visit(node)
            return True

        return False

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Detect call-based effects: SliceMutation, MapMutation, WriterOutput,
        HTTPResponseWrite, ChannelSend, ChannelClose, FileSystemWrite,
        FileSystemDelete, FileSystemMeta, DatabaseWrite, DatabaseTransaction,
        GoroutineSpawn, CallbackInvocation, LogWrite, ContextCancellation,
        StdoutWrite, StderrWrite, TimeDependency, ProcessExit,
        ReflectionMutation, CgoCall, FinalizerRegistration.

        Thin dispatcher: delegates to focused helper methods and short-circuits
        after the first match. Falls through to generic_visit when no handler
        matches.
        """
        func = node.func
        if isinstance(func, ast.Attribute):
            obj = func.value
            method = func.attr
            obj_name: str | None = None
            if isinstance(obj, ast.Name):
                obj_name = obj.id
            if self._handle_stream_writes(obj, method, node):
                return
            if self._handle_pathlib_attr_call(method, node):
                return
            if self._handle_lib_attr_call(obj_name, method, node):
                return
            if self._handle_db_local_call(obj_name, method, node):
                return
            if self._handle_param_attr_call(obj_name, method, node):
                return
        elif isinstance(func, ast.Name):
            fn = func.id
            if self._handle_name_call(fn, node):
                return
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # With statement — DatabaseTransaction, MutexOp
    # ------------------------------------------------------------------

    def _handle_with_param(self, ctx_name: str, node: ast.AST, *, is_async: bool) -> None:
        """Emit MutexOp or DatabaseTransaction for a parameter-based context manager.

        Used by both visit_With (is_async=False) and visit_AsyncWith (is_async=True).
        The effect type is determined by _is_db_context(ctx_name).

        Args:
            ctx_name: The parameter name used as the context manager.
            node: The with/async-with AST node (for location tracking).
            is_async: True when called from visit_AsyncWith, False from visit_With.
        """
        prefix = "async " if is_async else ""
        if _is_db_context(ctx_name):
            async_infix = "async " if is_async else ""
            self._add(
                SideEffectType.DatabaseTransaction,
                node,
                f"Function uses a database connection as an {async_infix}"
                f"context manager via {ctx_name}",
            )
        else:
            self._add(
                SideEffectType.MutexOp,
                node,
                f"Function acquires a lock/mutex via '{prefix}with {ctx_name}:'",
            )

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        """Detect DatabaseTransaction and MutexOp from 'with param:' patterns.

        Uses _is_db_context() heuristic — see its docstring for word-part rules.
        """
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Name) and ctx.id in self._params:
                self._handle_with_param(ctx.id, node, is_async=False)

        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802
        """Detect WaitGroupOp and MutexOp/DatabaseTransaction from async with patterns.

        Param-based patterns (async with lock:, async with conn:):
            Uses _is_db_context() heuristic — conn/connection/tx/db names
            → DatabaseTransaction; all others → MutexOp. Param-only: local
            variables do not trigger these effects.

        TaskGroup pattern:
            async with asyncio.TaskGroup() as tg: → WaitGroupOp.

        The two branches use `elif` because a single context manager expression
        cannot be both an ast.Name (param-based) and an ast.Call (TaskGroup) —
        they are mutually exclusive by AST node type. `break` exits the item
        loop after the first TaskGroup match (only one TaskGroup is expected per
        async with). Known limitation: items after a TaskGroup in the same
        async with statement are not inspected (see design.md Risks).

        Alias limitation: only detects asyncio.TaskGroup(), not aio.TaskGroup().
        """
        for item in node.items:
            ctx = item.context_expr
            # Param-based async context managers — same heuristic as visit_With
            if isinstance(ctx, ast.Name) and ctx.id in self._params:
                self._handle_with_param(ctx.id, node, is_async=True)
            # TaskGroup pattern — WaitGroupOp
            elif (
                isinstance(ctx, ast.Call)
                and isinstance(ctx.func, ast.Attribute)
                and isinstance(ctx.func.value, ast.Name)
                and ctx.func.value.id == "asyncio"
                and ctx.func.attr == "TaskGroup"
            ):
                self._add(
                    SideEffectType.WaitGroupOp,
                    node,
                    "Function synchronizes tasks via async with asyncio.TaskGroup()",
                )
                break
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Try/Except and Try/Except* — RecoverBehavior
    # ------------------------------------------------------------------

    def _handle_try_node(self, node: ast.Try | ast.TryStar) -> None:
        """Shared RecoverBehavior detection for try/except and except* nodes.

        Emits at most one RecoverBehavior per function (checks self._effects).
        Calls generic_visit(node) so visit_Raise fires on re-raise statements
        inside handlers — RecoverBehavior and ErrorReturn are not mutually
        exclusive.

        Only top-level statements in each handler body are inspected for
        transform-and-re-raise exclusion (not nested inside if/for/with).

        Args:
            node: An ast.Try or ast.TryStar node to inspect.
        """
        # self._effects is bounded by distinct effect types per function (≤38);
        # O(n) scan is safe. Do not replace with a flag — see design.md D1.
        if not any(e.type == SideEffectType.RecoverBehavior for e in self._effects):
            for handler in node.handlers:
                if self._is_recovery_handler(handler):
                    self._add(
                        SideEffectType.RecoverBehavior,
                        handler,
                        self._recover_description(handler),
                    )
                    break
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        """Detect RecoverBehavior from try/except blocks."""
        self._handle_try_node(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:  # noqa: N802
        """Detect RecoverBehavior from except* (Python 3.11+) blocks."""
        self._handle_try_node(node)

    def _is_recovery_handler(self, handler: ast.ExceptHandler) -> bool:
        """Return True if this except clause performs recovery, not re-raise.

        Rules (checked in order):
        1. Empty body → False (defensive; Python disallows empty except bodies)
        2. Single bare raise (no args) → False (pure re-raise)
        3. Any top-level statement in body is raise with non-None exc → False
           (unconditional transform-and-re-raise).
           NOTE: only inspects handler.body directly (not nested blocks),
           so a guarded `if debug: raise RuntimeError()` does NOT trigger
           this rule — the guarded raise is inside an ast.If, not top-level.
        4. Body contains ast.Return, ast.Assign, ast.AugAssign, or ast.Pass
           → True (recovery action present)
        5. Otherwise → False

        Args:
            handler: The ast.ExceptHandler node to inspect.

        Returns:
            True if the handler body contains a recovery action. False if it
            re-raises unconditionally.
        """
        body = handler.body
        if not body:
            return False  # defensive; unreachable in valid Python
        # Rule 2: single bare raise (re-raise)
        if len(body) == 1 and isinstance(body[0], ast.Raise) and body[0].exc is None:
            return False
        # Rule 3: unconditional transform-and-re-raise (top-level only)
        for stmt in body:
            if isinstance(stmt, ast.Raise) and stmt.exc is not None:
                return False
        # Rule 4: recovery action
        for stmt in body:
            if isinstance(stmt, (ast.Return, ast.Assign, ast.AugAssign, ast.Pass)):
                return True
        return False

    def _recover_description(self, handler: ast.ExceptHandler) -> str:
        """Return a description string for RecoverBehavior.

        Distinguishes bare-pass suppression from active recovery.

        Args:
            handler: The qualifying ast.ExceptHandler node.

        Returns:
            Human-readable description of the recovery pattern.
        """
        if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
            return "Function silently suppresses an exception (bare except: pass)"
        return "Function catches an exception and returns a fallback or assigns a default value"

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


def _collect_module_names(module: ast.Module) -> set[str]:
    """Collect names bound to imported modules at module level.

    `import x` → x; `import x.y` → x; `import x.y as z` → z. Module-level
    try/except import blocks are included (the common fallback-import
    pattern). `from x import y` is deliberately excluded: y is usually a
    function or class, and attribute assignment on those is MonkeyPatch
    territory — a type not yet in the port's taxonomy (G1c).

    Args:
        module: Parsed module AST.

    Returns:
        Set of module alias names visible at module scope.
    """
    stmts: list[ast.stmt] = list(module.body)
    for stmt in module.body:
        if isinstance(stmt, ast.Try):
            stmts.extend(stmt.body)
            for handler in stmt.handlers:
                stmts.extend(handler.body)
    names: set[str] = set()
    for stmt in stmts:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _is_db_context(name: str) -> bool:
    """Return True if the parameter name suggests a database connection context.

    Uses word-part split on underscores plus substring check for compound words.
    Avoids the ctx→tx false positive (ctx → parts ["ctx"] → no match).

    `session` is excluded from the word-part set: `session_id` is a common
    HTTP/user session identifier (a string), not a DB connection — including it
    would produce DatabaseTransaction false positives in web framework code.
    `session` alone (bare name) also returns False — use `conn` or `connection`.
    `db` is word-part only (not substring) to avoid matching `debug`.
    `conn` is word-part only (not substring) to avoid matching `reconnect`,
    `connector`, `disconnect`. Only `connection` and `transaction` are in the
    substring list (both long enough to avoid false matches).
    `dbConn` (camelCase, no underscore) → False — accepted limitation.

    Examples:
        _is_db_context("conn")        → True   (word part "conn")
        _is_db_context("db_conn")     → True   (word parts: "db" and "conn")
        _is_db_context("my_db")       → True   (word part "db")
        _is_db_context("connection")  → True   (word part AND substring)
        _is_db_context("session")     → False  ("session" not in word-part set)
        _is_db_context("session_id")  → False  ("session" not in word-part set)
        _is_db_context("reconnect")   → False  ("conn" not in substring list)
        _is_db_context("connector")   → False  ("conn" not in substring list)
        _is_db_context("ctx")         → False  ("ctx" not in set)
        _is_db_context("lock")        → False
        _is_db_context("dbConn")      → False  (camelCase — accepted gap)

    Args:
        name: Parameter name to check.

    Returns:
        True if the name suggests a database connection context.
    """
    parts = set(name.lower().split("_"))
    if parts & {"conn", "connection", "tx", "transaction", "db"}:
        return True
    # Substring check for camelCase compound words only — use long keywords
    # to avoid false positives: "conn" is excluded (matches "reconnect",
    # "connector"); "connection" and "transaction" are safe.
    for kw in ("connection", "transaction"):
        if kw in name.lower():
            return True
    return False


def _matches_cache_decorator(dec: ast.expr) -> bool:
    """Return True if a single decorator node matches @lru_cache or @cache.

    Handles four decorator forms:
    - @lru_cache or @cache              (bare ast.Name)
    - @lru_cache(...) or @cache(...)    (ast.Call wrapping ast.Name)
    - @functools.lru_cache or @functools.cache   (ast.Attribute)
    - @functools.lru_cache(...) or @functools.cache(...)  (ast.Call wrapping ast.Attribute)

    Note: @functools.cache() with arguments is NOT valid Python at runtime
    (functools.cache is not a decorator factory). The AST pattern is handled
    for completeness but will not appear in correctly-functioning Python source
    (the decorator call raises TypeError at decoration time).

    Args:
        dec: A single decorator expression node from fn_node.decorator_list.

    Returns:
        True if the decorator matches any lru_cache/cache form.
    """
    # Bare name: @lru_cache or @cache
    if isinstance(dec, ast.Name) and dec.id in _LRU_CACHE_DECORATORS:
        return True
    # Call form: @lru_cache(...) or @cache()
    if (
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Name)
        and dec.func.id in _LRU_CACHE_DECORATORS
    ):
        return True
    # Qualified: @functools.lru_cache or @functools.cache
    if (
        isinstance(dec, ast.Attribute)
        and isinstance(dec.value, ast.Name)
        and dec.value.id == "functools"
        and dec.attr in _LRU_CACHE_DECORATORS
    ):
        return True
    # Qualified call: @functools.lru_cache(...) or @functools.cache(...)
    if (
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Attribute)
        and isinstance(dec.func.value, ast.Name)
        and dec.func.value.id == "functools"
        and dec.func.attr in _LRU_CACHE_DECORATORS
    ):
        return True
    return False


def _has_lru_cache_decorator(
    fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Return True if the function has an @lru_cache or @cache decorator.

    Delegates per-decorator matching to _matches_cache_decorator, which
    handles all four AST forms (bare name, call, qualified attribute,
    qualified attribute call).

    Args:
        fn_node: The function definition AST node to inspect.

    Returns:
        True if any decorator matches the lru_cache/cache pattern.
    """
    return any(_matches_cache_decorator(d) for d in fn_node.decorator_list)


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


def _build_class_method_map(module: ast.Module) -> dict[int, str]:
    """Build a map from function node id → enclosing class name.

    Walks the module AST once to record which function definitions are direct
    methods of a ClassDef (appear in the class body at depth 1). Used to
    populate FunctionTarget.receiver during detection.

    Args:
        module: Parsed AST module node.

    Returns:
        Dict mapping id(fn_node) → class_name for all direct class methods.
        Module-level functions are not included (they have no enclosing class).
    """
    fn_to_class: dict[int, str] = {}
    for class_node in ast.walk(module):
        if not isinstance(class_node, ast.ClassDef):
            continue
        for stmt in class_node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_to_class[id(stmt)] = class_node.name
    return fn_to_class


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
                function="<module>",
                file_path=rel_path,
                line=1,
                complexity=1,
                package=rel_path,
                receiver=None,
                # sentinel value matching the 'function' field convention;
                # no valid Python syntax exists for module-level scope.
                signature="<module>",
                caller_count=0,
                effects=[effect for _, effect in sentinel_pairs],
            )
            targets.append(module_target)

        # --- Phase 2: Per-function pass ---
        # Build a map from function node id → enclosing class name for receiver.
        _fn_to_class = _build_class_method_map(module)

        # Module alias names for module-attribute GlobalMutation detection.
        module_names = _collect_module_names(module)

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
                module_names=module_names,
            )
            visitor.visit(fn_node)
            # Post-process: DeferredReturnMutation requires whole-function context
            visitor.collect_deferred_return_mutation(fn_node)
            effects.extend(visitor.effects)

            # GlobalMutation: @lru_cache / @functools.cache decorator
            # The cache dict is attached to the function object at decoration time
            # and persists across all callers (functionally global mutable state).
            if _has_lru_cache_decorator(fn_node):
                effects.append(
                    _make_effect(
                        rel_path=rel_path,
                        fn_name=fn_name,
                        effect_type=SideEffectType.GlobalMutation,
                        node=fn_node,
                        description=(
                            "Function is decorated with @lru_cache/@cache —"
                            " memoization cache is persistent global mutable state"
                            " shared across all callers"
                        ),
                    )
                )

            # Compute complexity
            complexity = cyclomatic_complexity(fn_node)

            # Resolve caller count
            caller_count = 0
            if callers is not None:
                caller_count = callers.get(fn_name, 0)

            # Resolve receiver (class name for methods, None for module-level).
            receiver: str | None = _fn_to_class.get(id(fn_node))

            # Reconstruct signature from AST arguments.
            signature = _build_signature(fn_node, fn_name)

            target = FunctionTarget(
                function=fn_name,
                file_path=rel_path,
                line=fn_node.lineno,
                complexity=complexity,
                package=rel_path,
                receiver=receiver,
                signature=signature,
                caller_count=caller_count,
                effects=effects,
            )
            targets.append(target)

        return targets


def _format_annotation(node: ast.expr | None) -> str:
    """Format an AST annotation node as a string. Returns '' on failure.

    Args:
        node: An AST expression node representing a type annotation, or None.

    Returns:
        String representation of the annotation, or empty string when absent
        or when ast.unparse() raises.
    """
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return ""


def _build_signature(fn_node: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> str:
    """Reconstruct function signature from AST arguments node.

    Produces a human-readable signature string in the form:
        def name(param: Type = ...) -> ReturnType

    Handles positional-only, regular, *args, keyword-only, and **kwargs
    parameters. Default values are represented as '...' (the actual value
    is not available from the AST without evaluating it).

    Args:
        fn_node: The function definition AST node.
        name: The simple function name (used in the 'def name(...)' prefix).

    Returns:
        Signature string. Falls back to 'def name(...)' on any error.
    """
    try:
        args = fn_node.args
        parts: list[str] = []

        # positional-only params (before /)
        for arg in args.posonlyargs:
            anno = _format_annotation(arg.annotation)
            parts.append(f"{arg.arg}: {anno}" if anno else arg.arg)
        if args.posonlyargs:
            parts.append("/")

        # regular args
        n_defaults = len(args.defaults)
        n_args = len(args.args)
        for i, arg in enumerate(args.args):
            default_offset = i - (n_args - n_defaults)
            anno = _format_annotation(arg.annotation)
            s = f"{arg.arg}: {anno}" if anno else arg.arg
            if default_offset >= 0:
                s += " = ..."
            parts.append(s)

        # *args
        if args.vararg:
            anno = _format_annotation(args.vararg.annotation)
            parts.append(f"*{args.vararg.arg}: {anno}" if anno else f"*{args.vararg.arg}")
        elif args.kwonlyargs:
            parts.append("*")

        # keyword-only args
        for i, arg in enumerate(args.kwonlyargs):
            default = args.kw_defaults[i]
            anno = _format_annotation(arg.annotation)
            s = f"{arg.arg}: {anno}" if anno else arg.arg
            if default is not None:
                s += " = ..."
            parts.append(s)

        # **kwargs
        if args.kwarg:
            anno = _format_annotation(args.kwarg.annotation)
            parts.append(f"**{args.kwarg.arg}: {anno}" if anno else f"**{args.kwarg.arg}")

        # return annotation
        ret = _format_annotation(fn_node.returns)
        params = ", ".join(parts)
        prefix = "async def" if isinstance(fn_node, ast.AsyncFunctionDef) else "def"
        if ret:
            return f"{prefix} {name}({params}) -> {ret}"
        return f"{prefix} {name}({params})"
    except Exception:  # noqa: BLE001
        prefix = "async def" if isinstance(fn_node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {name}(...)"


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
