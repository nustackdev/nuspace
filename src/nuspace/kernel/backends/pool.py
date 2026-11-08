"""What the process backends share: workers from ``nustd.mp_pool``, each cell run a blocking request on one.

Both sit on the pool, unchanged: a worker is a pool process, a warm spare
when the pool keeps some (a cold launch when there is none). The two differ
only in placement, so this base holds everything and a subclass names its
placement.

Books: the kernel's worker id to the pool's own id. A handle is the pool's
id with the process's ``pid``, ``pgid`` and ``started_at``, what a reap by
handle would need. A cell run's body runs as a blocking request on its
worker (the pool's teleport), so its arm lives as long as the body does,
and a worker that dies surfaces as ``WorkerGone`` on every request pending
there, with its exit code: every cell run on it. The pool's ``cause`` says
whose end it was: ``stopped`` or ``killed`` is the pool's own doing, so the
backend letting go and no loss; anything else (``crashed``, an outside
signal included) is a loss, reported with the exit code. Letting go is the
pool's ``stop``: the worker tears down within the pool's grace, killed if
it will not.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from nustd.mp_pool import Interrupted, UnknownWorker, WorkerGone, WorkerPool

from .base import Backend


if TYPE_CHECKING:
    import nu
    from nu.lang.runtime import Context


__all__ = ["PoolBackend"]

# Causes the pool records only when it ended the worker itself: a stop, or a
# kill it signalled. Nuspace ends workers only by stopping or killing them
# (directly, or through the pool's close), so these mean the backend let the
# worker go.
_LET_GO = frozenset({"stopped", "killed"})


class PoolBackend(Backend):
    """A backend whose workers are ``nustd.mp_pool`` processes. Subclass for placement.

    Opened inside the pool, so it is there to take from and to stop into,
    and closed before it.
    """

    def __init__(self) -> None:
        self._pool: WorkerPool | None = None
        # The kernel's worker id to the pool's.
        self._workers: dict[str, int] = {}

    # --- lifecycle -------------------------------------------------------

    async def asetup(self, ctx: Context) -> None:
        """Take the pool."""
        try:
            self._pool = ctx.fabrics.get(WorkerPool)
        except LookupError:
            msg = f"{type(self).__name__} needs a WorkerPool bound around it"
            raise RuntimeError(msg) from None

    async def acleanup(self) -> None:
        """Forget every worker: the pool's close, right after, stops them all at once."""
        self._workers = {}

    # --- books -----------------------------------------------------------

    def _require_pool(self) -> WorkerPool:
        if self._pool is None:
            msg = f"{type(self).__name__} was used before its bracket opened"
            raise RuntimeError(msg)
        return self._pool

    async def _gone(self, worker: str, wid: int, exc: WorkerGone | None) -> str:
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
                status = await pool.await_exit(wid, pool.grace)
                cause, code = status.cause, status.exitcode
        if cause in _LET_GO:
            return ""
        self._workers.pop(worker, None)
        return f"Worker exited: {code}"

    def _stopping(self, wid: int) -> bool:
        """Whether the pool is ending the worker, or has: a stop or kill under way, or done."""
        with contextlib.suppress(UnknownWorker):
            return self._require_pool().status(wid).state in ("stopping", "exited")
        return False

    # --- Backend -----------------------------------------------------------

    async def alaunch(self, worker: str) -> dict[str, object]:
        """A pool process for ``worker``: a spare when the pool has one, else a cold launch."""
        pool = self._require_pool()
        wid = await pool.alaunch()
        self._workers[worker] = wid
        status = pool.status(wid)
        return {"wid": wid, "pid": status.pid, "pgid": status.pgid, "started_at": status.started_at}

    async def arun(self, worker: str, cell_run: str, body: nu.Nu) -> str:
        """Run the body on the worker's process, until it ends.

        Cancelled, ``mp_pool`` cancels the body's task in the worker.

        Raises:
            RuntimeError: The worker is not on the books: never launched,
                gone, or let go.
        """
        wid = self._workers.get(worker)
        if wid is None:
            msg = f"Worker {worker} is not up: it died, or was let go, before cell run {cell_run}"
            raise RuntimeError(msg)
        try:
            await self._require_pool().ateleport(wid, body)
        except WorkerGone as exc:
            return await self._gone(worker, wid, exc)
        except UnknownWorker:
            # The pool no longer keeps the worker's record.
            return await self._gone(worker, wid, None)
        except Interrupted:
            # A stop's SIGINT rung reached a body that would not end politely.
            if self._stopping(wid):
                return ""
            raise
        return ""

    async def astop(self, worker: str) -> None:
        """The pool's stop: torn down within its grace, killed if it will not end."""
        wid = self._workers.pop(worker, None)
        if wid is not None:
            with contextlib.suppress(UnknownWorker):
                await self._require_pool().astop(wid)

    async def akill(self, worker: str) -> None:
        """The pool's kill: SIGKILL to the worker's process group, now."""
        wid = self._workers.pop(worker, None)
        if wid is not None:
            with contextlib.suppress(UnknownWorker):
                await self._require_pool().akill(wid)
