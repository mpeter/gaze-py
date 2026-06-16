## ADDED Requirements

### Requirement: Pathlib FileSystemDelete detection via Path.unlink()
Tests MUST verify that calling `.unlink()` on any object (regardless of variable name) produces a `FileSystemDelete` effect.

#### Scenario: path.unlink() produces FileSystemDelete
- **WHEN** a function calls `.unlink()` on any object
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `FileSystemDelete` effect

### Requirement: Pathlib FileSystemMeta detection via Path.chmod()
Tests MUST verify that calling `.chmod()` on any object produces a `FileSystemMeta` effect.

#### Scenario: path.chmod() produces FileSystemMeta
- **WHEN** a function calls `.chmod(mode)` on any object
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `FileSystemMeta` effect

### Requirement: Pathlib FileSystemWrite detection via Path.write_text() and Path.write_bytes()
Tests MUST verify that both `.write_text()` and `.write_bytes()` produce `FileSystemWrite` effects.

#### Scenario: path.write_text() produces FileSystemWrite
- **WHEN** a function calls `.write_text(content)` on any object
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `FileSystemWrite` effect

#### Scenario: path.write_bytes() produces FileSystemWrite
- **WHEN** a function calls `.write_bytes(data)` on any object
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `FileSystemWrite` effect

### Requirement: ReflectionMutation detection via bare setattr() call
Tests MUST verify that a bare `setattr(obj, name, value)` call produces a `ReflectionMutation` effect.

#### Scenario: setattr() produces ReflectionMutation
- **WHEN** a function calls `setattr(obj, "attr", value)`
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `ReflectionMutation` effect

### Requirement: ReflectionMutation detection via obj.__setattr__() method call
Tests MUST verify that `obj.__setattr__(name, value)` produces a `ReflectionMutation` effect.

#### Scenario: obj.__setattr__() produces ReflectionMutation
- **WHEN** a function calls `obj.__setattr__("attr", value)`
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `ReflectionMutation` effect

### Requirement: GoroutineSpawn detection via executor.submit()
Tests MUST verify that `executor.submit(fn)` (where `executor` is the object variable name) produces a `GoroutineSpawn` effect.

#### Scenario: executor.submit() produces GoroutineSpawn
- **WHEN** a function calls `executor.submit(fn)` where `executor` is a variable name in the heuristic set
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `GoroutineSpawn` effect

### Requirement: FinalizerRegistration detection via weakref.finalize()
Tests MUST verify that `weakref.finalize(obj, fn)` produces a `FinalizerRegistration` effect.

#### Scenario: weakref.finalize() produces FinalizerRegistration
- **WHEN** a function calls `weakref.finalize(obj, callback)`
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `FinalizerRegistration` effect

### Requirement: CgoCall detection via ctypes.*
Tests MUST verify that any method call on the `ctypes` object produces a `CgoCall` effect.

#### Scenario: ctypes.cdll.LoadLibrary() produces CgoCall
- **WHEN** a function calls `ctypes.something()` for any method name
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `CgoCall` effect

### Requirement: StdoutWrite detection via sys.stdout.write()
Tests MUST verify that `sys.stdout.write(s)` produces a `StdoutWrite` effect (distinct from the `print()` path already tested).

#### Scenario: sys.stdout.write() produces StdoutWrite
- **WHEN** a function calls `sys.stdout.write(s)`
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `StdoutWrite` effect

### Requirement: ContextCancellation detection via event.set() on a parameter
Tests MUST verify that `.set()` called on a parameter variable produces a `ContextCancellation` effect.

#### Scenario: event.set() produces ContextCancellation
- **WHEN** a function calls `event.set()` where `event` is a function parameter
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `ContextCancellation` effect

### Requirement: open() keyword-argument mode detection
Tests MUST verify that `open(path, mode="w")` (mode as keyword argument) is detected as `FileSystemWrite`.

#### Scenario: open() with keyword mode="w" produces FileSystemWrite
- **WHEN** a function calls `open(path, mode="w")`
- **THEN** `FileDetector.detect()` returns a `FunctionTarget` containing a `FileSystemWrite` effect

### Requirement: _extract_params captures *args and **kwargs
Tests MUST verify that variadic positional (`*args`) and keyword (`**kwargs`) parameters are included in the detected parameter set.

#### Scenario: *args parameter is captured
- **WHEN** a function is defined with `def f(*args)`
- **THEN** `"args"` is in the set of parameter names used for effect detection

#### Scenario: **kwargs parameter is captured
- **WHEN** a function is defined with `def f(**kwargs)`
- **THEN** `"kwargs"` is in the set of parameter names used for effect detection

### Requirement: detect() raises GazeParseError on OSError
Tests MUST verify that when the source file cannot be read (e.g. permissions), `FileDetector.detect()` raises `GazeParseError`.

#### Scenario: Unreadable file raises GazeParseError
- **WHEN** the source file exists but cannot be read (OSError)
- **THEN** `FileDetector.detect()` raises `GazeParseError`
- **NOTE** Skip this test when running as root (root bypasses chmod)

### Requirement: detect() uses filename-only fallback when file is not under root
Tests MUST verify that when the analyzed file is not a descendant of the provided root, the `file_path` in effects uses only the filename (not a full or relative path).

#### Scenario: File outside root uses filename as file_path
- **WHEN** `FileDetector.detect(path, root=some_other_path)` is called and `path` is not under `some_other_path`
- **THEN** the resulting `FunctionTarget.file_path` equals `path.name` (filename only)

### Requirement: DeferredReturnMutation — try block with no finally is skipped
Tests MUST verify that a `try/except` block with no `finally` clause does not produce a `DeferredReturnMutation` effect.

#### Scenario: try/except without finally produces no DeferredReturnMutation
- **WHEN** a function contains `try: return x  except: pass` with no `finally`
- **THEN** `FileDetector.detect()` does NOT return a `DeferredReturnMutation` effect

### Requirement: DeferredReturnMutation — finally with augmented assignment
Tests MUST verify that a `finally` block containing `x += 1` where `x` is also in the return names produces a `DeferredReturnMutation` effect.

#### Scenario: finally with augmented assignment to returned name produces DeferredReturnMutation
- **WHEN** a function contains `try: return x  finally: x += 1`
- **THEN** `FileDetector.detect()` returns a `DeferredReturnMutation` effect

### Requirement: _collect_return_names recurses into except handler bodies
Tests MUST verify that return statements inside `except` handler bodies are included in the collected return names.

#### Scenario: return inside except handler is collected
- **WHEN** a function contains `try: ... except Exception as e: return e`
- **THEN** the name `e` is included in the set of collected return names

### Requirement: ClosureCaptureMutation via augmented assignment to nonlocal
Tests MUST verify that `nonlocal x; x += 1` inside an inner function produces a `ClosureCaptureMutation` effect.

#### Scenario: nonlocal augmented assignment produces ClosureCaptureMutation
- **WHEN** an inner function uses `nonlocal x` and then does `x += 1`
- **THEN** `FileDetector.detect()` returns a `ClosureCaptureMutation` effect

### Requirement: GlobalMutation via augmented assignment
Tests MUST verify that `global x; x += 1` produces a `GlobalMutation` effect (augmented-assignment path, distinct from the simple-assignment path already tested).

#### Scenario: global augmented assignment produces GlobalMutation
- **WHEN** a function uses `global x` and then does `x += 1`
- **THEN** `FileDetector.detect()` returns a `GlobalMutation` effect

### Requirement: caller_count is populated from callers map
Tests MUST verify that when a non-None callers dict is passed to `FileDetector.detect()`, the resulting `FunctionTarget.caller_count` reflects the value from the dict for the function name.

#### Scenario: callers map populates caller_count
- **WHEN** `FileDetector.detect(path, root, callers={"my_func": 3})` is called
- **THEN** the `FunctionTarget` for `my_func` has `caller_count == 3`

### Requirement: chmod 000 test MUST restore permissions in try/finally
The `test_detect_raises_gaze_parse_error_on_unreadable_file` test MUST wrap the chmod and detection in a `try/finally` block that restores `path.chmod(0o644)` before exiting, so that pytest's `tmp_path` cleanup (via `shutil.rmtree`) can delete the directory regardless of test outcome.

#### Scenario: Permissions restored even if test fails
- **WHEN** `path.chmod(0o000)` is called and `FileDetector.detect()` is called
- **THEN** `path.chmod(0o644)` is called in a `finally` block before the test exits
- **AND** pytest's `tmp_path` cleanup succeeds (no session-level `PermissionError`)
