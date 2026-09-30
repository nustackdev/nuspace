"""What the process backends share: workers from the pool, each cell run a blocking request on one.

Both sit on ``nustd.mp_pool`` and its shelf of spares, unchanged: a worker
is a pool process taken off the shelf (a cold launch when it is empty), its
``handle`` the pool's id as a str. The two differ only in how many workers
a plane run gets and when one is let go, so this base keeps the books and a
subclass decides placement.

Books, per plane run: its living workers, and per worker the cell runs
placed on it. A cell run's body runs as a blocking request on its worker
(``mp_pool``'s exec), so its arm lives as long as the body does, and a
worker that dies surfaces as ``WorkerGone`` on every request pending there:
all of the run's cells with ``async``, the one with ``mp``. A death
while nobody was letting the worker go is a loss, reported with the exit
code; one the backend caused on purpose is not.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from nuspace.ops.utils import mint_ordered_id
from nustd.mp_pool import UnknownWorker, WorkerGone, WorkerPool
from nustd.mp_pool.presets import Spares

from .base import Backend


if TYPE_CHECKING:
    import nu
    from nu.lang.runtime import Context


__all__ = ["PoolBackend", "PoolWorker"]


class PoolWorker:
    """One pool process a plane run holds: its ids and the cell runs placed on it."""

    __slots__ = ("cells", "gone", "id", "letting_go", "wid")

    def __init__(self, worker_id: str, wid: int) -> None:
        self.id = worker_id
        self.wid = wid
        self.cells: set[str] = set()
        self.letting_go = False
        # Why it died by itself, once a cell run on it found out.
        self.gone: str | None = None


class PoolBackend(Backend):
    """A backend whose workers are ``nustd.mp_pool`` processes. Subclass for placement.

    Opened inside the pool and its shelf, so both are there to take from and
    to kill into, and closed before them.
    """

    def __init__(self) -> None:
        self._pool: WorkerPool | None = None
        self._spares: Spares | None = None
        # Per plane run, its living workers by id.
        self._runs: dict[str, dict[str, PoolWorker]] = {}

    # --- lifecycle -------------------------------------------------------

    async def asetup(self, ctx: Context) -> None:
        """Take the pool, and the shelf when one is bound."""
        try:
            self._pool = ctx.fabrics.get(WorkerPool)
        except LookupError:
            msg = f"{type(self).__name__} needs a WorkerPool bound around it"
            raise RuntimeError(msg) from None
        self._spares = ctx.fabrics.get(Spares) if ctx.fabrics.has(Spares) else None

    async def acleanup(self) -> None:
        """Kill every worker still held. No await points, like the pool's own close."""
        pool, runs, self._runs = self._pool, self._runs, {}
        for workers in runs.values():
            for worker in workers.values():
                worker.letting_go = True
                if pool is not None:
                    pool.kill(worker.wid)

    # --- books -----------------------------------------------------------

    def _books(self, run_id: str) -> dict[str, PoolWorker]:
        books = self._runs.get(run_id)
        if books is None:
            books = self._runs[run_id] = {}
        return books

    def _holding(self, run_id: str, cell_run_id: str) -> PoolWorker | None:
        """The worker a cell run was placed on, None when there is none."""
        books = self._runs.get(run_id)
        if books is None:
            return None
        return next((w for w in books.values() if cell_run_id in w.cells), None)

    def _require_pool(self) -> WorkerPool:
        if self._pool is None:
            msg = f"{type(self).__name__} was used before its bracket opened"
            raise RuntimeError(msg)
        return self._pool

    async def _take(self, run_id: str) -> PoolWorker:
        """A worker for the run, off the shelf when it has one."""
        pool = self._require_pool()
        wid = await (self._spares.atake() if self._spares is not None else pool.alaunch())
        worker = PoolWorker(mint_ordered_id("w"), wid)
        self._books(run_id)[worker.id] = worker
        return worker

    async def _lost(self, run_id: str, worker: PoolWorker) -> str:
        """A worker gone with nobody letting it go: off the books, and why."""
        if worker.gone is None:
            pool = self._require_pool()
            code = await pool.await_exit(worker.wid)
            if worker.gone is None:
                worker.gone = f"Worker exited: {code}"
                # Drop the pool's handle: the process is gone, the id is not reused.
                pool.kill(worker.wid)
                self._runs.get(run_id, {}).pop(worker.id, None)
        return worker.gone

    async def _let_go(self, run_id: str, worker: PoolWorker) -> None:
        """Kill a worker on purpose, so the requests it fails report no loss."""
        worker.letting_go = True
        books = self._runs.get(run_id)
        if books is not None:
            books.pop(worker.id, None)
        await self._require_pool().akill(worker.wid)

    # --- Backend -----------------------------------------------------------

    async def arun(self, run_id: str, cell_run_id: str, body: nu.Nu, attrs: dict[str, str]) -> str:
        """Run the body on the worker the cell run was placed on, until it ends.

        Cancelled, ``mp_pool`` cancels the body's task in the worker.
        """
        worker = self._holding(run_id, cell_run_id)
        if worker is None:
            msg = (
                f"Cell run {cell_run_id} has no worker: it was never placed, or its worker is gone"
            )
            raise RuntimeError(msg)
        try:
            await self._require_pool().ateleport(worker.wid, body, attrs=attrs)
        except (WorkerGone, UnknownWorker):
            # Unknown: a sibling found the death first and dropped the handle.
            if worker.letting_go:
                return ""
            return await self._lost(run_id, worker)
        return ""

    async def akill(self, run_id: str) -> list[str]:
        """Let go of every worker the run holds, and forget the run."""
        books = self._runs.pop(run_id, None)
        if books is None:
            return []
        gone = list(books.values())
        # Shielded: a kill cancelled halfway still reaps every process.
        await asyncio.shield(asyncio.gather(*(self._let_go(run_id, w) for w in gone)))
        return [worker.id for worker in gone]
