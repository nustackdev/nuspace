"""What the process backends share: workers from the pool, each cell run a blocking request on one.

Both sit on ``nustd.mp_pool``, unchanged: a worker is a pool process, a
warm spare when the pool keeps some (a cold launch when there is none), its
``handle`` the pool's id as a str. The two differ only in how many workers
a plane run gets and when one is let go, so this base keeps the books and a
subclass decides placement.

Books, per plane run: its living workers, and per worker the cell runs
placed on it. A cell run's body runs as a blocking request on its worker
(``mp_pool``'s exec), so its arm lives as long as the body does, and a
worker that dies surfaces as ``WorkerGone`` on every request pending there,
with its exit code: all of the run's cells with ``async``, the one with
``mp``. The pool's ``cause`` says whose end it was: ``stopped`` or
``killed`` is the pool's own doing, so the backend letting go and no loss;
anything else (``crashed``, an outside signal included) is a loss, reported
with the exit code. Letting go is the pool's ``stop``: the worker tears down
within the pool's grace, killed if it will not.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from nuspace.ops.utils import mint_ordered_id
from nustd.mp_pool import Interrupted, UnknownWorker, WorkerGone, WorkerPool

from .base import Backend


if TYPE_CHECKING:
    import nu
    from nu.lang.runtime import Context


__all__ = ["PoolBackend", "PoolWorker"]

# Causes the pool records only when it ended the worker itself: a stop, or a
# kill it signalled. Nuspace ends workers only by stopping them (directly, or
# through the pool's close), so these mean the backend let the worker go.
_LET_GO = frozenset({"stopped", "killed"})


class PoolWorker:
    """One pool process a plane run holds: its ids and the cell runs placed on it."""

    __slots__ = ("cells", "id", "wid")

    def __init__(self, worker_id: str, wid: int) -> None:
        self.id = worker_id
        self.wid = wid
        self.cells: set[str] = set()


class PoolBackend(Backend):
    """A backend whose workers are ``nustd.mp_pool`` processes. Subclass for placement.

    Opened inside the pool, so it is there to take from and to stop into,
    and closed before it.
    """

    def __init__(self) -> None:
        self._pool: WorkerPool | None = None
        # Per plane run, its living workers by id.
        self._runs: dict[str, dict[str, PoolWorker]] = {}

    # --- lifecycle -------------------------------------------------------

    async def asetup(self, ctx: Context) -> None:
        """Take the pool."""
        try:
            self._pool = ctx.fabrics.get(WorkerPool)
        except LookupError:
            msg = f"{type(self).__name__} needs a WorkerPool bound around it"
            raise RuntimeError(msg) from None

    async def acleanup(self) -> None:
        """Let go of every worker still held: the pool's close, right after, stops them all at once."""
        self._runs = {}

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
        """A worker for the run: a spare when the pool has one, else a cold launch."""
        wid = await self._require_pool().alaunch()
        worker = PoolWorker(mint_ordered_id("w"), wid)
        self._books(run_id)[worker.id] = worker
        return worker

    async def _gone(self, run_id: str, worker: PoolWorker, exc: WorkerGone | None) -> str:
        """A worker gone: nothing when the pool ended it, else off the books and why.

        ``exc`` is what the request raised, None when the pool no longer keeps
        the worker's record. Its cause and code are None only when the pipe
        closed before the process was reaped; then the exit is awaited,
        bounded by the pool's grace.
        """
        cause, code = (exc.cause, exc.exitcode) if exc is not None else (None, None)
        if exc is not None and cause is None:
            pool = self._require_pool()
            with contextlib.suppress(UnknownWorker):
                status = await pool.await_exit(worker.wid, pool.grace)
                cause, code = status.cause, status.exitcode
        if cause in _LET_GO:
            return ""
        self._runs.get(run_id, {}).pop(worker.id, None)
        return f"Worker exited: {code}"

    def _stopping(self, worker: PoolWorker) -> bool:
        """Whether the pool is ending the worker, or has: a stop or kill under way, or done."""
        with contextlib.suppress(UnknownWorker):
            return self._require_pool().status(worker.wid).state in ("stopping", "exited")
        return False

    async def _let_go(self, run_id: str, worker: PoolWorker) -> None:
        """Stop a worker on purpose, so the requests it fails report no loss.

        The pool's ``stop``: the worker tears down within the pool's grace,
        and is killed if it will not. Either way its cause is the pool's own.
        """
        books = self._runs.get(run_id)
        if books is not None:
            books.pop(worker.id, None)
        with contextlib.suppress(UnknownWorker):
            await self._require_pool().astop(worker.wid)

    # --- Backend -----------------------------------------------------------

    async def arun(self, run_id: str, cell_run_id: str, body: nu.Nu) -> str:
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
            await self._require_pool().ateleport(worker.wid, body)
        except WorkerGone as exc:
            return await self._gone(run_id, worker, exc)
        except UnknownWorker:
            # The pool no longer keeps the worker's record.
            return await self._gone(run_id, worker, None)
        except Interrupted:
            # A stop's SIGINT rung reached a body that would not end politely.
            if self._stopping(worker):
                return ""
            raise
        return ""

    async def akill(self, run_id: str) -> list[str]:
        """Let go of every worker the run holds, and forget the run."""
        books = self._runs.pop(run_id, None)
        if books is None:
            return []
        gone = list(books.values())
        # Shielded: a stop cancelled halfway still ends every process.
        await asyncio.shield(asyncio.gather(*(self._let_go(run_id, w) for w in gone)))
        return [worker.id for worker in gone]
