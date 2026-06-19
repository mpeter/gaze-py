## 1. Branch Setup

- [ ] 1.1 Create branch `opsx/python-native-detection` from `main`

## 2. detector.py — Constants and Helpers

- [ ] 2.1 Extend `_GOROUTINE_SPAWN_CALLS` frozenset with `("subprocess", "Popen")`, `("subprocess", "run")`, `("subprocess", "call")`, `("subprocess", "check_output")`, `("subprocess", "check_call")`
- [ ] 2.2 Add module-level `_is_db_context(name: str) -> bool` helper using word-part split on `_` plus substring check for `conn`/`connection`/`session`/`transaction`
- [ ] 2.3 Add module-level `_is_cache_decorator(node: ast.expr) -> bool` helper matching all six `@lru_cache`/`@cache`/`@functools.*` forms

## 3. detector.py — Detection Logic

- [ ] 3.1 In `visit_With`: replace inline `if ctx.id in {"connection", "conn", "session", "tx", "transaction"}:` with `if _is_db_context(ctx.id):`
- [ ] 3.2 In `_handle_lib_attr_call`: add `atexit.register` → `GlobalMutation` branch (after `weakref.finalize`; `atexit.unregister` must NOT trigger)
- [ ] 3.3 In `_handle_lib_attr_call`: add `warnings.warn` → dual `LogWrite` + `GlobalMutation` branch (two `_add()` calls before `return True`)
- [ ] 3.4 In `visit_AsyncWith`: add second loop over `node.items` for param-based `MutexOp`/`DatabaseTransaction` detection using `_is_db_context` (independent of existing TaskGroup loop)
- [ ] 3.5 In `FileDetector.detect()` per-function loop: after visitor runs, inspect `fn_node.decorator_list` with `_is_cache_decorator`; append `GlobalMutation` effect if matched (one effect per function via `break`)

## 4. Testdata Fixtures

- [ ] 4.1 Create `tests/testdata/analysis/subprocess_spawn.py` — five functions (one per subprocess variant) plus one `proc.run()` negative
- [ ] 4.2 Create `tests/testdata/analysis/async_mutex.py` — four functions: `lock` param (MutexOp), `conn` param (DBTx), `db_conn` param (DBTx via substring), local-var `async with` (no effect)
- [ ] 4.3 Create `tests/testdata/analysis/atexit_register.py` — three functions: `atexit.register(fn)`, `atexit.register(lambda: ...)`, `atexit.unregister(fn)` (negative)
- [ ] 4.4 Create `tests/testdata/analysis/warnings_warn.py` — one function with `warnings.warn("msg")` producing dual effects
- [ ] 4.5 Create `tests/testdata/analysis/lru_cache_mutation.py` — six decorated functions (one per decorator form) plus one `@staticmethod` negative

## 5. Tests — subprocess

- [ ] 5.1 `test_subprocess_popen_goroutine_spawn` — fixture `subprocess_spawn.py`, fn `popen_fn`
- [ ] 5.2 `test_subprocess_run_goroutine_spawn` — fixture, fn `run_fn`
- [ ] 5.3 `test_subprocess_call_goroutine_spawn` — fixture, fn `call_fn`
- [ ] 5.4 `test_subprocess_check_output_goroutine_spawn` — fixture, fn `check_output_fn`
- [ ] 5.5 `test_subprocess_check_call_goroutine_spawn` — fixture, fn `check_call_fn`
- [ ] 5.6 `test_non_subprocess_attr_call_not_goroutine_spawn` — `tmp_path`, `proc.run()` asserts no GoroutineSpawn via this path

## 6. Tests — async with

- [ ] 6.1 `test_async_with_lock_param_mutex_op` — fixture `async_mutex.py`, fn with `lock` param
- [ ] 6.2 `test_async_with_conn_param_database_transaction` — fixture, fn with `conn` param
- [ ] 6.3 `test_async_with_db_conn_param_database_transaction` — fixture, fn with `db_conn` param (substring match)
- [ ] 6.4 `test_async_with_local_var_no_effect` — fixture, fn with local `lock` variable (not a param)
- [ ] 6.5 `test_async_with_conn_not_mutex_op` — fixture, asserts no MutexOp when `conn` produces DatabaseTransaction

## 7. Tests — atexit

- [ ] 7.1 `test_atexit_register_global_mutation` — fixture `atexit_register.py`
- [ ] 7.2 `test_atexit_register_lambda_global_mutation` — fixture
- [ ] 7.3 `test_atexit_unregister_not_global_mutation` — fixture, negative
- [ ] 7.4 `test_atexit_register_not_finalizer_registration` — fixture, negative

## 8. Tests — warnings

- [ ] 8.1 `test_warnings_warn_logwrite` — fixture `warnings_warn.py`
- [ ] 8.2 `test_warnings_warn_global_mutation` — fixture
- [ ] 8.3 `test_warnings_warn_dual_effect` — fixture, asserts both effects present on same function

## 9. Tests — lru_cache

- [ ] 9.1 `test_lru_cache_bare_global_mutation` — fixture `lru_cache_mutation.py`, `@lru_cache`
- [ ] 9.2 `test_lru_cache_with_args_global_mutation` — fixture, `@lru_cache(maxsize=128)`
- [ ] 9.3 `test_cache_bare_global_mutation` — fixture, `@cache`
- [ ] 9.4 `test_functools_lru_cache_global_mutation` — fixture, `@functools.lru_cache`
- [ ] 9.5 `test_functools_lru_cache_with_args_global_mutation` — fixture, `@functools.lru_cache(maxsize=None)`
- [ ] 9.6 `test_functools_cache_global_mutation` — fixture, `@functools.cache`
- [ ] 9.7 `test_lru_cache_effect_on_definition_not_call_site` — `tmp_path`, decorated fn and caller; asserts GlobalMutation on decorated fn, not caller
- [ ] 9.8 `test_unrelated_decorator_no_lru_cache_global_mutation` — fixture, `@staticmethod` asserts no GlobalMutation via decorator path

## 10. Tests — visit_With heuristic regression

- [ ] 10.1 `test_db_context_heuristic_substring_match_sync` — `tmp_path`, `def f(db_conn): with db_conn: pass` asserts `DatabaseTransaction` via sync `with` (confirms `_is_db_context` applied to `visit_With`)

## 11. CI Gate and Cleanup

- [ ] 11.1 Run `ruff check . && ruff format --check .` — fix any issues
- [ ] 11.2 Run `mypy src/` — fix any type errors
- [ ] 11.3 Run `pytest --cov=gaze_py --cov-fail-under=85` — confirm all tests pass, coverage ≥ 85%
- [ ] 11.4 Commit detector changes: `feat(detection): add python-native detection patterns (EC-005)`
- [ ] 11.5 Commit fixtures and tests: `test(detection): add EC-005 python-native pattern tests`
- [ ] 11.6 Archive `return-none-annotation` change: move to `openspec/changes/archive/return-none-annotation/`; commit `chore: archive return-none-annotation (G.1 decision already implemented)`
- [ ] 11.7 Push branch and open PR targeting `main`
