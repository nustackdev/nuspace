"""Pre-warmed worker pool.

Interpreter start plus ``import nu`` is roughly half a second. Paying
that N times on every navigation would make page open feel broken, so
workers are started ahead of time and parked on their channel waiting
for a ``run``.

Workers are **single use**. A worker that has run user code is never
handed back: user code can leave threads, altered globals, signal
handlers and C state behind, and the only honest way to reclaim that is
to let the process die. So the pool is a refill queue, not a recycler --
acquiring schedules a replacement in the background.
"""

from __future__ import annotations

import asyncio

from .handle import Timeouts, WorkerHandle


__all__ = ["WarmPool"]


class WarmPool:
    """Keeps ``size`` workers warm and hands them out one at a time."""

    def __init__(self, size: int = 8, *, timeouts: Timeouts | None = None) -> None:
        self._size = max(0, size)
        self._timeouts = timeouts or Timeouts()
        self._idle: list[WorkerHandle] = []
        self._spawning: set[asyncio.Task] = set()
        self._closed = False

    @property
    def idle_count(self) -> int:
        """Workers currently parked and ready."""
        return len(self._idle)

    async def astart(self) -> None:
        """Fill the pool and wait for every worker to report ready."""
        if self._closed or not self._size:
            return
        handles = await asyncio.gather(
            *(WorkerHandle.spawn(timeouts=self._timeouts) for _ in range(self._size)),
        )
        self._idle.extend(handles)

    async def acquire(self) -> WorkerHandle:
        """Take a warm worker, or pay a cold start if the pool is dry."""
        if self._closed:
            raise RuntimeError("pool is closed")
        while self._idle:
            handle = self._idle.pop()
            if handle.alive:
                self._refill()
                return handle
            await handle.stop(self._timeouts)
        self._refill()
        return await WorkerHandle.spawn(timeouts=self._timeouts)

    def _refill(self) -> None:
        """Top the pool back up off the navigation path."""
        if self._closed:
            return
        deficit = self._size - len(self._idle) - len(self._spawning)
        for _ in range(max(0, deficit)):
            task = asyncio.create_task(self._spawn_one())
            self._spawning.add(task)
            task.add_done_callback(self._spawning.discard)

    async def _spawn_one(self) -> None:
        try:
            handle = await WorkerHandle.spawn(timeouts=self._timeouts)
        except Exception:
            return
        if self._closed or len(self._idle) >= self._size:
            await handle.stop(self._timeouts)
            return
        self._idle.append(handle)

    async def aclose(self) -> None:
        """Stop refilling and kill every parked worker.

        In-flight spawns are awaited rather than cancelled. Cancelling a
        spawn between ``create_subprocess_exec`` and the ready handshake
        would drop the handle on the floor and orphan a live process,
        which is exactly the thing this package exists to prevent;
        ``_spawn_one`` sees ``_closed`` and reaps its own worker.
        """
        self._closed = True
        if self._spawning:
            await asyncio.gather(*tuple(self._spawning), return_exceptions=True)
        self._spawning.clear()
        idle, self._idle = self._idle, []
        if idle:
            await asyncio.gather(
                *(h.stop(self._timeouts) for h in idle),
                return_exceptions=True,
            )
