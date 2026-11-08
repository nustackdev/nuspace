"""``nuspace.worker``: the ops over ``Space.exec.workers``. Written by the kernel.

The record says a worker should exist; the backend makes it. The kernel
mints the worker id (``add``'s ``into``) and every backend method takes it.
Calling these by hand records a fact the kernel did not see. Every op is a
bare term the caller brackets (see :mod:`nuspace.ops`).
"""

from __future__ import annotations

import nu
import nustd.time
from nuspace.shapes.space import Space
from nuspace.utils import MintId
from nuspace.utils.checks import exit_known, not_ended


__all__ = ["add", "end", "start"]


def add(plane_run: nu.StrArg, backend: nu.StrArg, *, into: nu.Ref | None = None) -> nu.Nu:
    """A worker wanted for a live plane run, on ``backend``. The backend starts it under the id.

    One commit: the row (backend, plane_run, created_at), into the plane
    run's history and the live sets (every live worker, the plane run's
    held workers). Cost: O(1), about 6 keys.

    Args:
        plane_run: The live plane run it serves.
        backend: The backend that runs it, by registered name.
        into: A ref set to the new worker's id in the same commit.

    Raises:
        Missing: No plane run with that id.
        Ended: The plane run ended.
    """
    runs = Space.exec.plane_runs
    indexes = Space.exec.indexes

    def write(minted: nu.ObjectRef) -> nu.Nu:
        w = nu.Str(minted)
        row = Space.exec.workers[w]
        node = indexes.history.plane_to_plane_runs[runs[plane_run].plane].runs[plane_run]
        writes = (
            row.backend.set(backend)
            >> row.plane_run.set(plane_run)
            >> row.created_at.set(nustd.time.time())
            >> node.workers.set_item(w, True)
            >> indexes.live.workers.set_item(w, True)
            >> indexes.live.plane_run_to_workers[plane_run].ids.set_item(w, True)
        )
        return writes if into is None else writes >> into.set(w)

    return not_ended(runs, plane_run, "plane run") >> nu.let(MintId("w"), write)


def start(worker: nu.StrArg, *, handle: dict[str, object] | nu.Nu) -> nu.Nu:
    """Observed, by the backend: the worker is up. Writes ``started_at`` and its ``handle``.

    The handle is the backend's own (pid, container id): nothing else reads
    into it. Cost: O(1), 2 keys.

    Raises:
        Missing: No worker with that id.
        Ended: It already ended.
    """
    rows = Space.exec.workers
    row = rows[worker]
    return (
        not_ended(rows, worker, "worker")
        >> row.started_at.set(nustd.time.time())
        >> row.handle.set(handle)
    )


def end(worker: nu.StrArg, exit: nu.StrArg, error: nu.StrArg = "") -> nu.Nu:
    """Observed: the worker is gone. Writes ``ended_at``, ``exit``, ``error``; out of live.

    Out of every live worker and its plane run's held workers. When that
    was the last one of a plane run that already ended, the plane run's set
    goes too. Cost: O(1), about 7 keys.

    Args:
        worker: The worker.
        exit: How it ended, one of :data:`~nuspace.shapes.exec.EXITS`.
        error: Why it failed, ``""`` for none.

    Raises:
        Missing: No worker with that id.
        Ended: It already ended: ending twice is a driver bug.
        Refused: An exit none of ``EXITS`` (a literal at build).
    """
    rows = Space.exec.workers
    row = rows[worker]
    held = Space.exec.indexes.live
    plane_run = row.plane_run
    workers = held.plane_run_to_workers[plane_run]
    over = Space.exec.plane_runs[plane_run].ended_at.exists().and_(nu.Not(workers.ids))
    return (
        exit_known(exit)
        >> not_ended(rows, worker, "worker")
        >> row.exit.set(exit)
        >> row.error.set(error)
        >> row.ended_at.set(nustd.time.time())
        >> held.workers.del_item(worker)
        >> workers.ids.del_item(worker)
        >> nu.IfDo(over, workers.erase())
    )
