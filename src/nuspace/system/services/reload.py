"""reload: a cell rewritten during a live plane run runs again in it, on the new prog (D13).

One arm per live plane run. The arm wakes when a cell is rewritten, and
runs again every cell of the run's plane whose newest cell run in it has a
``version`` behind its cell's: ``cell_interrupt >> cell_run`` in one
commit, so the plane run never reads empty in between and never ends for
it. The new cell run is ``by`` reload; the plane run keeps its own ``by``.

Live or over makes no difference: a save reruns its cell. A cell that drew
once and returned is over while the plane run goes on, and an edit to it
has to draw again. The interrupt is a no-op on a cell run that is over.

Every read is a point read of the run's ``latest`` per cell of its plane,
never a walk of its history.
"""

from __future__ import annotations

import nu
from nuspace.ops.kernel import add_cell_run, interrupt, latest
from nuspace.ops.read import cells
from nuspace.ops.utils import MintId, atomic
from nuspace.shapes import Space

from ..utils import Ticking, snap, wake


__all__ = ["BY", "CELL", "PLANE", "SHIM", "behind", "program"]


#: The plane id, fixed (D31).
PLANE = "reload"

#: The one cell on the plane.
CELL = "reload_main"

#: What cell runs reload starts are recorded as ``by``.
BY = "reload"

#: The cell's prog: the code lives here, the store holds this (D20).
SHIM = """\
from nuspace.system.services import reload


def out():
    return reload.program()
"""

_kernel = Space.kernel


def _stale(run_id: nu.StrArg, cell: nu.Str) -> nu.Bool:
    """Whether a cell ran in the plane run and was rewritten since its newest cell run there.

    A cell that never ran in it is not stale: a birth is nav's. A cell gone
    is not stale: removing it interrupted its runs already. An unwritten
    version reads 0.
    """
    cr = latest(run_id, cell)
    ran = _kernel.runs[run_id].cells[cr].version.fallback(0)
    newer = ran < Space.cells[cell].version.fallback(0)
    return (cr != "").and_(Space.cells.contains(cell)).and_(newer)


def behind(run_id: nu.StrArg) -> nu.List:
    """The cells of a plane run's plane rewritten since their newest cell run in it. Bare read."""
    plane = _kernel.runs[run_id].plane.fallback("")
    return cells(plane).iter().filter(lambda at: _stale(run_id, nu.Str(at))).to_list()


def _replace(run_id: nu.StrArg) -> nu.Nu:
    """Every stale cell run again and its newest cell run interrupted, one commit each.

    Read again inside the commit, so a cell another reload already ran
    again is left alone.
    """

    def one(at: nu.Attr) -> nu.Nu:
        cell = nu.Str(at)
        again = nu.let(MintId("cr"), lambda new: add_cell_run(run_id, cell, nu.Str(new), by=BY))
        rerun = interrupt(run_id, latest(run_id, cell)) >> again
        return atomic(nu.IfDo(_stale(run_id, cell), rerun))

    return nu.ForEachDo(snap(behind(run_id)), one)


def _arm(run_id: nu.Str) -> nu.Nu:
    """One live plane run: rerun what is stale, then again on every rewrite of a cell.

    Cells are flat, so the subscription hears every cell's rewrite, and
    :func:`behind` tells the run's own apart.
    """
    edits = Space.cells.on_descendants_change("*", "version")
    return nu.ForeverDo(_replace(run_id) >> wake(edits))


def program() -> nu.Nu:
    """One arm per live plane run, births and deaths included. Never returns."""
    running = _kernel.running
    return nu.ForEachParReactive(
        snap(nu.list(running)),
        Ticking(snap(running.on_children_change())),
        lambda rid: _arm(nu.Str(rid)),
    )
