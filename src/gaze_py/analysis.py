"""AST-based side-effect detection engine for gaze-py.

This module implements the core analysis pipeline:

1. ``GazeParseError`` — domain exception for unparseable source.
2. ``FunctionEffectVisitor`` — ``ast.NodeVisitor`` that detects side effects
   in a single function body without recursing into nested functions.
3. ``analyze_function`` — entry point for one function node.
4. ``analyze_module`` — parse source and analyse all top-level functions and
   class methods.
5. ``analyze_path`` — walk a file or directory and analyse all Python files.

Design decisions:
- Deduplication by ``SideEffectType`` is enforced inside
  ``FunctionEffectVisitor``: a set tracks which types have already been
  emitted so that, e.g., two ``return`` statements produce exactly one
  ``ReturnValue`` effect (SOLID Single Responsibility — the visitor owns
  deduplication, callers do not need to filter).
- Nested function bodies are skipped by overriding ``visit_FunctionDef`` /
  ``visit_AsyncFunctionDef`` to be no-ops, preventing false positives from
  inner closures.
- Path validation uses ``Path.resolve()`` to canonicalise before comparing
  against the declared root (SC-003, SC-004 from the Python convention pack).
"""

from __future__ import annotations

import ast
import datetime
import hashlib
import sys
from pathlib import Path

import gaze_py
from gaze_py.taxonomy import (
    TIER_MAP,
    AnalysisResult,
    FunctionTarget,
    Metadata,
    SideEffect,
    SideEffectType,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Method names on mutable containers that constitute a PointerArgMutation.
_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "update",
        "append",
        "extend",
        "pop",
        "clear",
        "add",
        "discard",
        "remove",
        "insert",
        "setdefault",
        "__setitem__",
    }
)

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class GazeParseError(Exception):
    """Raised when a source file cannot be parsed by the AST module.

    Attributes:
        path: Path to the file that failed to parse.
        line: Line number of the error, or ``None`` if unavailable.
        msg: Human-readable description of the parse failure.
        code: Short error code string (default ``"PARSE_ERROR"``).
    """

    def __init__(
        self,
        path: str,
        line: int | None,
        msg: str,
        code: str = "PARSE_ERROR",
    ) -> None:
        """Initialise the exception with location and message.

        Args:
            path: Path to the file that failed to parse.
            line: Line number of the error, or ``None`` if unavailable.
            msg: Human-readable description of the parse failure.
            code: Short error code string.
        """
        super().__init__(f"{code}: cannot parse {path}:{line}: {msg}")
        self.path = path
        self.line = line
        self.msg = msg
        self.code = code


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def _make_effect_id(
    module: str,
    func: str,
    effect_type: SideEffectType,
    location: str,
) -> str:
    """Generate a stable, content-addressed side-effect ID.

    The ID is derived from a SHA-256 hash of the concatenated key fields
    so that the same effect in the same location always produces the same
    ID across runs (deterministic output for JSON schema parity with Go
    gaze).

    Args:
        module: Module path (e.g. the file path used as module identifier).
        func: Function name.
        effect_type: The ``SideEffectType`` being recorded.
        location: Location string in ``file:line`` format.

    Returns:
        An 8-hex-char ID prefixed with ``"se-"``.
    """
    raw = f"{module}:{func}:{effect_type}:{location}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"se-{digest}"


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------


class FunctionEffectVisitor(ast.NodeVisitor):
    """Detect side effects in a single function body.

    The visitor is initialised with the function's argument names and
    global declarations, then ``generic_visit`` is called on the function
    body.  Nested ``FunctionDef`` / ``AsyncFunctionDef`` nodes are NOT
    recursed into, preventing false positives from inner closures.

    Deduplication is enforced via ``_emitted``: once a ``SideEffectType``
    has been added to ``effects``, it is added to ``_emitted`` and will
    not be added again.

    Attributes:
        effects: Accumulated list of detected ``SideEffect`` instances.
    """

    def __init__(
        self,
        module_path: str,
        func_name: str,
        arg_names: list[str],
        source_lines: list[str],
    ) -> None:
        """Initialise the visitor for one function.

        Args:
            module_path: Module path used for ID generation and location strings.
            func_name: Name of the function being analysed.
            arg_names: Parameter names of the function (excluding ``self``/``cls``).
            source_lines: Source lines of the module (1-indexed via ``lineno``).
        """
        super().__init__()
        self._module = module_path
        self._func = func_name
        self._arg_names: set[str] = set(arg_names)
        self._source_lines = source_lines
        self._globals: set[str] = set()
        self._emitted: set[SideEffectType] = set()
        self.effects: list[SideEffect] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _location(self, node: ast.AST) -> str:
        """Return a ``file:line`` location string for *node*.

        Args:
            node: An AST node with ``lineno`` attribute.

        Returns:
            Location string in ``<module_path>:<lineno>`` format.
        """
        lineno = getattr(node, "lineno", 0)
        return f"{self._module}:{lineno}"

    def _emit(
        self,
        effect_type: SideEffectType,
        node: ast.AST,
        description: str,
    ) -> None:
        """Emit a side effect if it has not already been emitted.

        Deduplication is by ``SideEffectType``: only the first occurrence
        of each type is recorded, regardless of how many AST nodes trigger
        the same type.

        Args:
            effect_type: The type of side effect to record.
            node: The AST node that triggered the detection.
            description: Human-readable description of the effect.
        """
        if effect_type in self._emitted:
            return
        self._emitted.add(effect_type)
        location = self._location(node)
        effect_id = _make_effect_id(self._module, self._func, effect_type, location)
        self.effects.append(
            SideEffect(
                id=effect_id,
                type=effect_type,
                tier=TIER_MAP[effect_type],
                location=location,
                description=description,
            )
        )

    # ------------------------------------------------------------------
    # Scoping: do NOT recurse into nested functions
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Skip nested function definitions entirely.

        Overriding this method (and its async counterpart) without calling
        ``generic_visit`` prevents the visitor from descending into inner
        closures or nested functions, which would produce false positives.

        Args:
            node: The nested ``FunctionDef`` node (ignored).
        """
        # Intentionally do not call generic_visit — skip nested functions.

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Skip nested async function definitions entirely.

        Args:
            node: The nested ``AsyncFunctionDef`` node (ignored).
        """
        # Intentionally do not call generic_visit — skip nested functions.

    # ------------------------------------------------------------------
    # Global tracking
    # ------------------------------------------------------------------

    def visit_Global(self, node: ast.Global) -> None:
        """Record names declared with the ``global`` keyword.

        Args:
            node: The ``Global`` AST node.
        """
        for name in node.names:
            self._globals.add(name)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Return / raise detection
    # ------------------------------------------------------------------

    def visit_Return(self, node: ast.Return) -> None:
        """Detect ``ReturnValue`` when the return carries a non-None value.

        An implicit ``return`` (no value) or ``return None`` is NOT a
        ``ReturnValue`` side effect — only returns that produce observable
        data are recorded.

        Args:
            node: The ``Return`` AST node.
        """
        if node.value is not None:
            self._emit(
                SideEffectType.ReturnValue,
                node,
                f"Function '{self._func}' returns a value",
            )
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        """Detect ``ErrorReturn`` on any ``raise`` statement.

        Args:
            node: The ``Raise`` AST node.
        """
        self._emit(
            SideEffectType.ErrorReturn,
            node,
            f"Function '{self._func}' raises an exception",
        )
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Assignment-based detection
    # ------------------------------------------------------------------

    def _check_assign_targets(self, targets: list[ast.expr], node: ast.AST) -> None:
        """Inspect assignment targets for GlobalMutation, ReceiverMutation, and PointerArgMutation.

        Called from both ``visit_Assign`` and ``visit_AugAssign``.

        Args:
            targets: List of assignment target nodes.
            node: The parent assignment node (for location).
        """
        for target in targets:
            if isinstance(target, ast.Name):
                # GlobalMutation: name is in the declared globals set
                if target.id in self._globals:
                    self._emit(
                        SideEffectType.GlobalMutation,
                        node,
                        f"Function '{self._func}' mutates global '{target.id}'",
                    )

            elif isinstance(target, ast.Attribute):
                # ReceiverMutation: self.attr = ...
                if isinstance(target.value, ast.Name) and target.value.id == "self":
                    self._emit(
                        SideEffectType.ReceiverMutation,
                        node,
                        f"Function '{self._func}' mutates receiver attribute '{target.attr}'",
                    )

            elif isinstance(target, ast.Subscript):
                # Could be PointerArgMutation (arg[key] = val)
                # or EnvVarMutation (os.environ[key] = val)
                obj = target.value
                if self._is_os_environ(obj):
                    self._emit(
                        SideEffectType.EnvVarMutation,
                        node,
                        f"Function '{self._func}' mutates os.environ via subscript",
                    )
                elif isinstance(obj, ast.Name) and obj.id in self._arg_names:
                    self._emit(
                        SideEffectType.PointerArgMutation,
                        node,
                        f"Function '{self._func}' mutates argument '{obj.id}' via subscript",
                    )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Detect mutations via simple assignment.

        Args:
            node: The ``Assign`` AST node.
        """
        self._check_assign_targets(node.targets, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Detect mutations via augmented assignment (``+=``, etc.).

        Args:
            node: The ``AugAssign`` AST node.
        """
        # AugAssign has a single target, not a list
        self._check_assign_targets([node.target], node)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Call-based detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_os_environ(node: ast.expr) -> bool:
        """Return True if *node* is the expression ``os.environ``.

        Args:
            node: An AST expression node.

        Returns:
            ``True`` when the node represents ``os.environ``.
        """
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "environ"
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        )

    def visit_Call(self, node: ast.Call) -> None:
        """Detect call-based side effects.

        Handles:
        - ``print(...)`` → ``StdoutWrite``
        - ``sys.stdout.write(...)`` → ``StdoutWrite``
        - ``sys.stderr.write(...)`` → ``StderrWrite``
        - ``os.environ.update(...)`` / ``os.environ.__setitem__(...)`` → ``EnvVarMutation``
        - ``arg.mutating_method(...)`` → ``PointerArgMutation``

        Args:
            node: The ``Call`` AST node.
        """
        func = node.func

        # print(...) → StdoutWrite
        if isinstance(func, ast.Name) and func.id == "print":
            self._emit(
                SideEffectType.StdoutWrite,
                node,
                f"Function '{self._func}' writes to stdout via print()",
            )

        elif isinstance(func, ast.Attribute):
            obj = func.value
            method = func.attr

            # sys.stdout.write(...) → StdoutWrite
            if (
                method == "write"
                and isinstance(obj, ast.Attribute)
                and obj.attr == "stdout"
                and isinstance(obj.value, ast.Name)
                and obj.value.id == "sys"
            ):
                self._emit(
                    SideEffectType.StdoutWrite,
                    node,
                    f"Function '{self._func}' writes to sys.stdout",
                )

            # sys.stderr.write(...) → StderrWrite
            elif (
                method == "write"
                and isinstance(obj, ast.Attribute)
                and obj.attr == "stderr"
                and isinstance(obj.value, ast.Name)
                and obj.value.id == "sys"
            ):
                self._emit(
                    SideEffectType.StderrWrite,
                    node,
                    f"Function '{self._func}' writes to sys.stderr",
                )

            # os.environ.update(...) or os.environ.__setitem__(...) → EnvVarMutation
            elif self._is_os_environ(obj) and method in {"update", "__setitem__"}:
                self._emit(
                    SideEffectType.EnvVarMutation,
                    node,
                    f"Function '{self._func}' mutates os.environ via .{method}()",
                )

            # arg.mutating_method(...) → PointerArgMutation
            elif method in _MUTATING_METHODS and isinstance(obj, ast.Name) and obj.id in self._arg_names:
                self._emit(
                    SideEffectType.PointerArgMutation,
                    node,
                    f"Function '{self._func}' mutates argument '{obj.id}' via .{method}()",
                )

        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Argument extraction helper
# ---------------------------------------------------------------------------


def _extract_arg_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    is_method: bool,
) -> list[str]:
    """Extract parameter names from a function node, excluding self/cls.

    Args:
        node: The function definition AST node.
        is_method: Whether the function is a class method (first arg is
            ``self`` or ``cls`` and should be excluded from the arg list
            used for ``PointerArgMutation`` detection).

    Returns:
        List of parameter name strings, with ``self``/``cls`` excluded
        when *is_method* is ``True``.
    """
    args = node.args
    all_args = [a.arg for a in args.args]
    if is_method and all_args:
        # Exclude the first argument (self / cls) from mutation detection
        return all_args[1:]
    return all_args


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    module_path: str,
    source_lines: list[str],
    is_method: bool = False,
) -> list[SideEffect]:
    """Detect side effects in one function node.

    Runs ``FunctionEffectVisitor`` over the function body and returns a
    deduplicated list of ``SideEffect`` instances (at most one per
    ``SideEffectType``).

    Args:
        node: The ``FunctionDef`` or ``AsyncFunctionDef`` AST node to analyse.
        module_path: Module path string used for ID generation and location
            strings.
        source_lines: Source lines of the module (used for location context).
        is_method: Whether the function is a class method.  When ``True``,
            the first parameter (``self``/``cls``) is excluded from the
            ``PointerArgMutation`` detection set.

    Returns:
        Deduplicated list of ``SideEffect`` instances detected in the
        function body.
    """
    arg_names = _extract_arg_names(node, is_method=is_method)
    visitor = FunctionEffectVisitor(
        module_path=module_path,
        func_name=node.name,
        arg_names=arg_names,
        source_lines=source_lines,
    )
    visitor.generic_visit(node)
    return visitor.effects


def analyze_module(source: str, module_path: str) -> list[AnalysisResult]:
    """Parse *source* and analyse all top-level functions and class methods.

    Walks the module-level AST for:
    - Top-level ``FunctionDef`` / ``AsyncFunctionDef`` nodes.
    - ``ClassDef`` nodes, analysing each method within them and setting
      ``FunctionTarget.receiver`` to the class name.

    Args:
        source: Python source code as a string.
        module_path: Path to the source file (used as the module identifier
            in ``FunctionTarget.package`` and location strings).

    Returns:
        List of ``AnalysisResult`` instances, one per function/method.

    Raises:
        GazeParseError: When *source* cannot be parsed by ``ast.parse()``.
    """
    try:
        tree = ast.parse(source, filename=module_path)
    except SyntaxError as exc:
        raise GazeParseError(
            path=module_path,
            line=exc.lineno,
            msg=str(exc.msg),
        ) from exc

    source_lines = source.splitlines()
    results: list[AnalysisResult] = []
    now = datetime.datetime.now(tz=datetime.UTC).isoformat()
    version = gaze_py.__version__
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _make_result(
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        receiver: str | None,
        is_method: bool,
    ) -> AnalysisResult:
        """Build one ``AnalysisResult`` for *func_node*.

        Args:
            func_node: The function/method AST node.
            receiver: Class name when *func_node* is a method, else ``None``.
            is_method: Whether the function is a class method.

        Returns:
            Populated ``AnalysisResult``.
        """
        effects = analyze_function(
            func_node,
            module_path=module_path,
            source_lines=source_lines,
            is_method=is_method,
        )
        target = FunctionTarget(
            package=module_path,
            function=func_node.name,
            receiver=receiver,
            location=f"{module_path}:{func_node.lineno}",
        )
        metadata = Metadata(
            gaze_version=version,
            python_version=python_ver,
            duration_ms=0,
            timestamp=now,
            warnings=[],
        )
        return AnalysisResult(
            target=target,
            side_effects=effects,
            metadata=metadata,
        )

    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            results.append(_make_result(stmt, receiver=None, is_method=False))

        elif isinstance(stmt, ast.ClassDef):
            class_name = stmt.name
            for item in stmt.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    results.append(_make_result(item, receiver=class_name, is_method=True))

    return results


def analyze_path(path: Path, root: Path | None = None) -> list[AnalysisResult]:
    """Walk *path* (file or directory) and analyse all Python files.

    Security: validates that the resolved *path* is within *root* to
    prevent directory traversal attacks (SC-003, SC-004 from the Python
    convention pack).

    Excludes:
    - Hidden directories (names starting with ``.``).
    - ``__pycache__`` directories.

    Args:
        path: File or directory to analyse.
        root: Declared project root.  Defaults to the current working
            directory.  The resolved *path* MUST be within the resolved
            *root*.

    Returns:
        List of ``AnalysisResult`` instances from all analysed files.

    Raises:
        ValueError: When the resolved *path* escapes *root*.
        GazeParseError: When a file cannot be read (encoding error) or
            parsed (syntax error).
    """
    if root is None:
        root = Path.cwd()

    resolved_root = root.resolve()
    resolved_path = path.resolve()

    # Security: ensure path is within root (prevent .. traversal)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Path '{resolved_path}' escapes declared root '{resolved_root}'") from exc

    results: list[AnalysisResult] = []

    if resolved_path.is_file():
        results.extend(_analyze_file(resolved_path))
    elif resolved_path.is_dir():
        results.extend(_analyze_directory(resolved_path))

    return results


def _analyze_directory(directory: Path) -> list[AnalysisResult]:
    """Recursively analyse all Python files in *directory*.

    Skips hidden directories (names starting with ``.``) and
    ``__pycache__`` directories.

    Args:
        directory: Directory to walk.

    Returns:
        Accumulated list of ``AnalysisResult`` instances.
    """
    results: list[AnalysisResult] = []
    for entry in sorted(directory.iterdir()):
        if entry.is_dir():
            # Skip hidden directories and __pycache__
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            results.extend(_analyze_directory(entry))
        elif entry.is_file() and entry.suffix == ".py":
            results.extend(_analyze_file(entry))
    return results


def _analyze_file(file_path: Path) -> list[AnalysisResult]:
    """Analyse a single Python file.

    Args:
        file_path: Path to the ``.py`` file to analyse.

    Returns:
        List of ``AnalysisResult`` instances from the file.

    Raises:
        GazeParseError: When the file cannot be read (encoding error) or
            parsed (syntax error).
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise GazeParseError(
            path=str(file_path),
            line=None,
            msg=f"encoding error: {exc}",
            code="ENCODING_ERROR",
        ) from exc

    return analyze_module(source, str(file_path))
