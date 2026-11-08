"""The ``mp`` backend: one worker per cell run, ending with it.

``start`` takes nothing. Every cell run is placed on a spare of its own and
run in it, and the worker is let go once the cell run is over. A
crash ends only that cell run: its siblings are other processes, and the
plane run goes on while any of them runs.
"""

from __future__ import annotations

from .pool import PoolBackend


__all__ = ["NAME", "MpBackend"]


#: The name it is registered under.
NAME = "mp"


class MpBackend(PoolBackend):
    """One pool worker per cell run."""

    async def astart(self, run_id: str) -> list[list[str]]:
        """Nothing to bring up: cells bring their own."""
        self._books(run_id)
        return []

    async def aplace(self, run_id: str, cell_run_id: str) -> list:
        """A fresh worker for the cell run."""
        worker = await self._take(run_id)
        worker.cells.add(cell_run_id)
        return [worker.id, [[worker.id, str(worker.wid)]]]

    async def aend_cell(self, run_id: str, cell_run_id: str) -> list[str]:
        """Let the cell run's worker go with it."""
        worker = self._holding(run_id, cell_run_id)
        if worker is None:
            return []
        await self._let_go(run_id, worker)
        return [worker.id]
