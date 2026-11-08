"""``nuspace.cell_run``: the ops over ``Space.exec.cell_runs``. Flat: one id per cell run.

A cell run is one run of a cell inside a plane run. ``add`` and
``interrupt`` ask; ``start`` and ``end`` are the kernel saying what
happened. Every op is a bare term the caller brackets (see
:mod:`nuspace.ops`).
"""

from __future__ import annotations

import nu
import nustd.time
from nuspace.errors import Refused
from nuspace.shapes.exec import EXIT_FAILED
from nuspace.shapes.space import Space
from nuspace.utils import MintId
from nuspace.utils.checks import exit_known, live, not_ended, refuse, row_known


__all__ = ["add", "end", "interrupt", "start"]


def _runs_of(plane_run: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """A cell's cell runs in one plane run, in start order: its history list."""
    plane = Space.exec.plane_runs[plane_run].plane
    node = Space.exec.indexes.history.plane_to_plane_runs[plane].runs[plane_run]
    return node.cell_to_cell_runs[cell].ids


def add(
    plane_run: nu.StrArg,
    cell: nu.StrArg,
    *,
    by: nu.StrArg = "",
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Ask for a run of a cell inside a live plane run: a new cell run record.

    One commit: the row (plane_run, cell, the cell's version now, by,
    created_at, an empty output), into the plane run's history and the live
    sets of its cell and its plane run. The cell drops out of the plane
    run's failed cells: a new run replaces a failed one. The kernel runs it
    on a worker. Cost: O(1), about 12 keys.

    Args:
        plane_run: The live plane run it runs in.
        cell: The cell, on the plane run's plane.
        by: Who asked, eg ``reload``.
        into: A ref set to the new cell run's id in the same commit.

    Raises:
        Missing: No plane run or cell with that id.
        Removed: The cell is removed.
        Ended: The plane run ended.
        Refused: The cell is not on the plane run's plane.
    """
    runs = Space.exec.plane_runs
    held = Space.exec.indexes.live
    on = Space.cells[cell].plane.fallback("")

    def write(minted: nu.ObjectRef) -> nu.Nu:
        cr = nu.Str(minted)
        row = Space.exec.cell_runs[cr]
        writes = (
            row.plane_run.set(plane_run)
            >> row.cell.set(cell)
            >> row.version.set(Space.cells[cell].version)
            >> row.by.set(by)
            >> row.worker.set("")
            >> row.out.set([])
            >> row.created_at.set(nustd.time.time())
            >> _runs_of(plane_run, cell).set_item(cr, True)
            >> held.cell_to_cell_runs[cell].ids.set_item(cr, True)
            >> held.plane_run_to_cell_runs[plane_run].ids.set_item(cr, True)
            >> held.plane_run_to_failed_cells[plane_run].ids.del_item(cell, missing_ok=True)
        )
        return writes if into is None else writes >> into.set(cr)

    return (
        not_ended(runs, plane_run, "plane run")
        >> live(Space.cells, cell, "cell")
        >> refuse(
            on != runs[plane_run].plane,
            Refused,
            "cell ",
            cell,
            " is not on plane run ",
            plane_run,
            "'s plane",
        )
        >> nu.let(MintId("cr"), write)
    )


def start(cell_run: nu.StrArg, *, worker: nu.StrArg) -> nu.Nu:
    """Observed, by the kernel: the cell runs on ``worker``. Writes ``started_at`` once and ``worker``.

    Cost: O(1), 2 keys.

    Raises:
        Missing: No cell run with that id.
        Ended: It already ended.
    """
    rows = Space.exec.cell_runs
    row = rows[cell_run]
    return (
        not_ended(rows, cell_run, "cell run")
        >> row.started_at.init(nustd.time.time())
        >> row.worker.set(worker)
    )


def interrupt(cell_run: nu.StrArg) -> nu.Nu:
    """Ask the kernel to interrupt it on its worker: ``interrupt_at = now``. Cost: O(1), 1 key.

    A no-op on a cell run that ended: a race that harms nothing.

    Raises:
        Missing: No cell run with that id.
    """
    rows = Space.exec.cell_runs
    row = rows[cell_run]
    asked = nu.IfDo(row.ended_at.exists().not_(), row.interrupt_at.set(nustd.time.time()))
    return row_known(rows, cell_run, "cell run") >> asked


def end(cell_run: nu.StrArg, exit: nu.StrArg, error: nu.StrArg = "") -> nu.Nu:
    """Observed, by the kernel: the cell run is over. Writes ``ended_at``, ``exit``, ``error``.

    Out of the live sets of its cell and its plane run. When that was the
    last one of a plane run that already ended, the plane run's set goes
    too. A failed end of the cell's newest run in a live plane run adds the
    cell to the plane run's failed cells, so the plane run ends failed; an
    older run, replaced by reload or a restart, does not count. Cost: O(1),
    about 8 keys.

    Args:
        cell_run: The cell run.
        exit: How it ended, one of :data:`~nuspace.shapes.exec.EXITS`.
        error: Why it failed, ``""`` for none.

    Raises:
        Missing: No cell run with that id.
        Ended: It already ended: ending twice is a driver bug.
        Refused: An exit none of ``EXITS`` (a literal at build).
    """
    rows = Space.exec.cell_runs
    row = rows[cell_run]
    held = Space.exec.indexes.live
    plane_run = row.plane_run
    cells = held.plane_run_to_cell_runs[plane_run]
    ended = Space.exec.plane_runs[plane_run].ended_at.exists()
    newest = _runs_of(plane_run, row.cell).last() == cell_run
    counts = (nu.Str(exit) == EXIT_FAILED).and_(ended.not_()).and_(newest)
    return (
        exit_known(exit)
        >> not_ended(rows, cell_run, "cell run")
        >> row.exit.set(exit)
        >> row.error.set(error)
        >> row.ended_at.set(nustd.time.time())
        >> held.cell_to_cell_runs[row.cell].ids.del_item(cell_run)
        >> cells.ids.del_item(cell_run)
        >> nu.IfDo(counts, held.plane_run_to_failed_cells[plane_run].ids.set_item(row.cell, True))
        >> nu.IfDo(ended.and_(nu.Not(cells.ids)), cells.erase())
    )
