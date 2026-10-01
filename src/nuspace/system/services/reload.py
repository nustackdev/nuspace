"""reload: a live cell run whose cell's prog changed is replaced by one of the new prog (D13).

One arm per live plane run. The arm wakes when a cell of its plane is
rewritten, and replaces every live cell run whose ``version`` is behind its
cell's: ``cell_interrupt >> cell_run`` in one commit, so the plane run never
reads empty in between and never ends for it. The new cell run is ``by``
reload; the plane run keeps its own ``by``.

Only live cell runs are replaced: a cell whose run is over stays over.
Every read walks the run's ``cells_running``, never its history.
"""

from __future__ import annotations

import nu
from nuspace.ops.kernel import add_cell_run, interrupt
from nuspace.ops.utils import MintId, atomic
from nuspace.shapes import Space

from ..utils import Ticking, snap, wake


__all__ = ["BY", "CELL", "PLANE", "SHIM", "behind", "program"]


#: The plane id, fixed (D31).
PLANE = "reload"

#: The one cell on the plane.
CELL = "main"

#: What cell runs reload starts are recorded as ``by``.
BY = "reload"

#: The cell's prog: the code lives here, the store holds this (D20).
SHIM = """\
from nuspace.system.services import reload


def out():
    return reload.program()
"""

_kernel = Space.kernel


def behind(run_id: nu.StrArg, plane: nu.StrArg) -> nu.List:
    """The live cell runs of a plane run whose cell was rewritten since. Bare read.

    A cell gone is not behind: removing it interrupted its runs already.
    An unwritten version reads 0.
    """
    row = _kernel.runs[run_id]
    cells = Space.planes[plane].cells

    def stale(at: nu.Attr) -> nu.Bool:
        cr = row.cells[nu.Str(at)]
        cell = cr.cell.fallback("")
        newer = cr.version.fallback(0) < cells[cell].version.fallback(0)
        return cells.contains(cell).and_(newer)

    return nu.list(row.cells_running).iter().filter(stale).to_list()


def _replace(run_id: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """Every stale live cell run interrupted and run anew, one commit each.

    Read again inside the commit, so a cell run another reload already
    replaced is left alone.
    """
    row = _kernel.runs[run_id]

    def one(at: nu.Attr) -> nu.Nu:
        cr = nu.Str(at)
        cell = row.cells[cr].cell.fallback("")
        again = nu.let(MintId("cr"), lambda new: add_cell_run(run_id, cell, nu.Str(new), by=BY))
        return atomic(nu.IfDo(behind(run_id, plane).contains(cr), interrupt(run_id, cr) >> again))

    return nu.ForEachDo(snap(behind(run_id, plane)), one)


def _arm(run_id: nu.Str) -> nu.Nu:
    """One live plane run: replace what is stale, then again on every rewrite of its plane's cells."""

    def watch(held: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(held)
        edits = Space.planes[plane].cells.on_descendants_change("*", "version")
        return nu.ForeverDo(_replace(run_id, plane) >> wake(edits))

    return nu.let(snap(_kernel.runs[run_id].plane.fallback("")), watch)


def program() -> nu.Nu:
    """One arm per live plane run, births and deaths included. Never returns."""
    running = _kernel.running
    return nu.ForEachParReactive(
        snap(nu.list(running)),
        Ticking(snap(running.on_children_change())),
        lambda rid: _arm(nu.Str(rid)),
    )
