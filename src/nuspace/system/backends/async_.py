"""The ``async`` backend: one worker per plane run, every cell run a task in it.

The default. ``start`` takes a spare for the run, every cell run is
run in it (``mp_pool`` runs each request as its own asyncio task there),
and the run's end lets it go. The cells share one process: cheap, and one
cell crashing the process takes its siblings with it.
"""

from __future__ import annotations

from .pool import PoolBackend


__all__ = ["NAME", "AsyncBackend"]


#: The name it is registered under.
NAME = "async"


class AsyncBackend(PoolBackend):
    """One pool worker per plane run, shared by all of its cell runs."""

    async def astart(self, run_id: str) -> list[list[str]]:
        """Take the run's one worker."""
        worker = await self._take(run_id)
        return [[worker.id, str(worker.wid)]]

    async def aplace(self, run_id: str, cell_run_id: str) -> list:
        """The run's worker, brought up by ``start``.

        Raises:
            RuntimeError: The run holds no worker: it died, or was let go.
        """
        books = self._runs.get(run_id)
        worker = next(iter(books.values()), None) if books is not None else None
        if worker is None:
            msg = f"Plane run {run_id} has no worker: it died, or the run is over"
            raise RuntimeError(msg)
        worker.cells.add(cell_run_id)
        return [worker.id, []]

    async def aend_cell(self, run_id: str, cell_run_id: str) -> list[str]:
        """Off its worker's books. The worker stays for the run's other cells."""
        worker = self._holding(run_id, cell_run_id)
        if worker is not None:
            worker.cells.discard(cell_run_id)
        return []
