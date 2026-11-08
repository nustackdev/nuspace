"""The record writes the kernel, reap and close share: the end ops, guarded, and the live sets read.

The end ops raise on a run or worker that ended already: ending twice is a
driver bug. A driver often races another writer to an end that is normal
(a kill and a body finishing at once, every cell run on a dead ``async``
worker reporting the same death, a cancelled arm letting its worker go as
the space closes), so it ends through these: the op when the row is there
and not ended yet, nothing otherwise. Bare terms, the caller brackets them.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, Space


__all__ = [
    "cell_runs_of",
    "end_cell_run",
    "end_live",
    "end_plane_run",
    "end_worker",
    "keys",
    "workers_of",
]


def keys(ids: nu.Nu) -> nu.Nu:
    """The ids in a live set, as a list. ``[]`` when the set is gone: an ended run's is erased."""
    return nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([]))


def cell_runs_of(plane_run: nu.StrArg) -> nu.Nu:
    """A plane run's live cell runs, as a list. A read."""
    return keys(Space.exec.indexes.live.plane_run_to_cell_runs[plane_run].ids)


def workers_of(plane_run: nu.StrArg) -> nu.Nu:
    """A plane run's held workers, as a list. A read."""
    return keys(Space.exec.indexes.live.plane_run_to_workers[plane_run].ids)


def _open(rows: nu.Nu, id: nu.StrArg) -> nu.Bool:
    """Whether ``rows`` has a row ``id`` and it has not ended."""
    return nu.Bool(nu.If(rows.contains(id), rows[id].ended_at.exists().not_(), False))


def end_cell_run(cell_run: nu.StrArg, exit: nu.StrArg, error: nu.StrArg = "") -> nu.Nu:
    """``nuspace.cell_run.end``, unless it ended already or has no row."""
    rows = Space.exec.cell_runs
    return nu.IfDo(_open(rows, cell_run), ops.cell_run.end(cell_run, exit, error))


def end_worker(worker: nu.StrArg, exit: nu.StrArg, error: nu.StrArg = "") -> nu.Nu:
    """``nuspace.worker.end``, unless it ended already or has no row."""
    rows = Space.exec.workers
    return nu.IfDo(_open(rows, worker), ops.worker.end(worker, exit, error))


def end_plane_run(plane_run: nu.StrArg, exit: nu.StrArg, error: nu.StrArg = "") -> nu.Nu:
    """``nuspace.plane_run.end``, unless it ended already or has no row."""
    rows = Space.exec.plane_runs
    return nu.IfDo(_open(rows, plane_run), ops.plane_run.end(plane_run, exit, error))


def _run_exit(plane_run: nu.StrArg, exit: nu.StrArg) -> nu.Nu:
    """The exit a plane run ends with: ``failed`` over ``interrupted`` when a cell's last run failed.

    As the kernel's own end has it. ``plane_run.end`` turns an ``ok`` into
    ``failed`` itself; ``killed`` stays ``killed``. A literal other than
    ``interrupted`` is handed back as is, so the op still checks it at build.
    A read.
    """
    if isinstance(exit, str) and exit != EXIT_INTERRUPTED:
        return exit
    failed_cells = Space.exec.indexes.live.plane_run_to_failed_cells[plane_run].ids
    failed = nu.Bool(nu.If(failed_cells.exists(), nu.Not(failed_cells), True)).not_()
    return nu.If((nu.Str(exit) == EXIT_INTERRUPTED).and_(failed), EXIT_FAILED, exit)


def end_live(exit: nu.StrArg, error: nu.StrArg) -> nu.Nu:
    """Every live cell run, worker and plane run ended ``exit`` with ``error``. Bare.

    Each through its guarded end, so one ended meanwhile is skipped. Cell
    runs first, read off every plane run that still has a live cell run set
    (an ended plane run keeps one until its last cell run ends), then the
    workers, then the plane runs. A plane run ended ``interrupted`` whose
    cell's last run failed ends ``failed``. Walks the live indexes only,
    never history: O(what is live).
    """
    live = Space.exec.indexes.live
    by_run = live.plane_run_to_cell_runs
    cell_runs = nu.ForEachDo(
        keys(by_run),
        lambda r: nu.ForEachDo(
            keys(by_run[nu.Str(r)].ids), lambda cr: end_cell_run(nu.Str(cr), exit, error)
        ),
    )
    workers = nu.ForEachDo(keys(live.workers), lambda w: end_worker(nu.Str(w), exit, error))
    plane_runs = nu.ForEachDo(
        keys(live.plane_runs),
        lambda r: end_plane_run(nu.Str(r), _run_exit(nu.Str(r), exit), error),
    )
    return cell_runs >> workers >> plane_runs
