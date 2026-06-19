# ruff: noqa
"""Fixture for Python-native detection patterns.

Covers: subprocess GoroutineSpawn, async-with MutexOp/DatabaseTransaction,
atexit GlobalMutation, warnings LogWrite+GlobalMutation,
lru_cache GlobalMutation.
"""
import asyncio
import atexit
import subprocess
import warnings
from functools import lru_cache, cache


# --- GoroutineSpawn: subprocess ---

def spawn_popen() -> None:
    """subprocess.Popen — GoroutineSpawn."""
    subprocess.Popen(["ls", "-la"])


def spawn_run() -> None:
    """subprocess.run — GoroutineSpawn."""
    subprocess.run(["echo", "hello"])


def spawn_call() -> None:
    """subprocess.call — GoroutineSpawn."""
    subprocess.call(["true"])


def spawn_check_output() -> str:
    """subprocess.check_output — GoroutineSpawn."""
    return subprocess.check_output(["date"]).decode()


def spawn_check_call() -> None:
    """subprocess.check_call — GoroutineSpawn."""
    subprocess.check_call(["true"])


# --- MutexOp / DatabaseTransaction: async with param ---

async def async_lock(lock) -> None:
    """async with lock: — MutexOp."""
    async with lock:
        pass


async def async_mutex(mutex) -> None:
    """async with mutex: — MutexOp."""
    async with mutex:
        pass


async def async_sem(sem) -> None:
    """async with sem: — MutexOp (not a connection name → MutexOp by default)."""
    async with sem:
        pass


async def async_conn(conn) -> None:
    """async with conn: — DatabaseTransaction."""
    async with conn:
        pass


async def async_session(session) -> None:
    """async with session: — MutexOp (NOT DatabaseTransaction; 'session' excluded from heuristic)."""
    async with session:
        pass


async def async_db_conn(db_conn) -> None:
    """async with db_conn: — DatabaseTransaction (word-part 'db' match)."""
    async with db_conn:
        pass


def sync_db_conn(db_conn) -> None:
    """with db_conn: — DatabaseTransaction via _is_db_context (regression)."""
    with db_conn:
        pass


def sync_ctx_not_db(ctx) -> None:
    """with ctx: — MutexOp, NOT DatabaseTransaction (ctx excluded from heuristic)."""
    with ctx:
        pass


# --- GlobalMutation: atexit ---

def register_shutdown(cleanup) -> None:
    """atexit.register — GlobalMutation."""
    atexit.register(cleanup)


def register_lambda_shutdown() -> None:
    """atexit.register with lambda — GlobalMutation."""
    atexit.register(lambda: None)


# --- LogWrite + GlobalMutation: warnings ---

def emit_warning() -> None:
    """warnings.warn — LogWrite + GlobalMutation."""
    warnings.warn("this is deprecated", DeprecationWarning)


# --- GlobalMutation: lru_cache decorator ---

@lru_cache
def cached_compute(n: int) -> int:
    """@lru_cache bare — GlobalMutation."""
    return n * n


@lru_cache(maxsize=128)
def cached_fetch(url: str) -> str:
    """@lru_cache call form — GlobalMutation."""
    return url


@cache
def cached_memoized(x: int) -> int:
    """@cache bare — GlobalMutation."""
    return x + 1


def not_cached(n: int) -> int:
    """No decorator — NOT GlobalMutation from lru_cache."""
    return n * n
