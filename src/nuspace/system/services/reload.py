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
from nuspace.ops.utils import MintId, atomic, fresh, text
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

_RUN = "nuspace.reload.run"
_PLANE = "nuspace.reload.plane"


def _version(plane: nu.StrArg, cell: nu.Nu) -> nu.Nu:
    ref = Space.planes[plane].cells[cell].version
    return nu.If(ref.exists(), nu.ToInt(ref), nu.Int(0))


def behind(run_id: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """The live cell runs of a plane run whose cell was rewritten since. Bare read.

    A cell gone is not behind: removing it interrupted its runs already.
    """
    row = _kernel.runs[run_id]
    item = fresh("reload_behind")
    cr = row.cells[nu.StrAttrRef(item)]
    cell = text(cr.cell)
    ran = nu.If(cr.version.exists(), nu.ToInt(cr.version), nu.Int(0))
    stale = nu.And(Space.planes[plane].cells.contains(cell), nu.Lt(ran, _version(plane, cell)))
    return nu.List(nu.Collect(nu.Filter(nu.list(row.cells_running), stale, key=item)))


def _replace(run_id: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """Every stale live cell run interrupted and run anew, one commit each.

    Read again inside the commit, so a cell run another reload already
    replaced is left alone.
    """
    row = _kernel.runs[run_id]
    item, new = fresh("reload_one"), fresh("reload_new")
    cr = nu.StrAttrRef(item)
    again = add_cell_run(run_id, text(row.cells[cr].cell), nu.StrAttrRef(new), by=BY)
    one = atomic(
        nu.IfDo(
            behind(run_id, plane).contains(cr),
            interrupt(run_id, cr) >> nu.Let(new, MintId("cr"), again),
        )
    )
    return nu.ForEachDo(snap(behind(run_id, plane)), one, item=item)


def _arm(run_id: nu.StrAttrRef) -> nu.Nu:
    """One live plane run: replace what is stale, then again on every rewrite of its plane's cells."""
    plane = nu.StrAttrRef(_PLANE)
    edits = Space.planes[plane].cells.on_descendants_change("*", "version")
    look = _replace(run_id, plane) >> wake(edits)
    return nu.Let(
        _PLANE,
        snap(text(_kernel.runs[run_id].plane)),
        nu.ForeverDo(look),
    )


def program() -> nu.Nu:
    """One arm per live plane run, births and deaths included. Never returns."""
    running = _kernel.running
    return nu.ForEachParReactive(
        snap(nu.list(running)),
        Ticking(snap(running.on_children_change())),
        _arm(nu.StrAttrRef(_RUN)),
        _RUN,
    )
