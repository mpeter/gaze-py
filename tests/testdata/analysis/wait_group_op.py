# ruff: noqa
"""Fixture for WaitGroupOp detection.

Uses 'import concurrent.futures as futures' to make futures.wait()
valid Python (required for the obj_name=="futures" heuristic).
"""
import asyncio
import concurrent.futures as futures
import threading


async def gather_tasks(coros: list) -> list:
    """asyncio.gather — WaitGroupOp."""
    return await asyncio.gather(*coros)


async def wait_tasks(tasks: set) -> tuple:
    """asyncio.wait — WaitGroupOp."""
    done, pending = await asyncio.wait(tasks)
    return done, pending


async def task_group_sync() -> None:
    """asyncio.TaskGroup — WaitGroupOp."""
    async def some_coro() -> None:
        pass

    async with asyncio.TaskGroup() as tg:
        tg.create_task(some_coro())


def futures_wait(fs: set) -> None:
    """concurrent.futures.wait via alias import — WaitGroupOp."""
    futures.wait(fs)


def barrier_sync(barrier: threading.Barrier) -> None:
    """threading.Barrier.wait — WaitGroupOp."""
    barrier.wait()
