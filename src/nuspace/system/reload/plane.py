"""The reload plane: keeps running plane runs on the latest code. No ops of its own.

One cell, :data:`CELL`, runs :func:`driver`: one arm per live plane run,
births and deaths included. An arm wakes when a cell of its plane is
written (``Plane.version``) and, per cell of the plane:

    a newest cell run in this plane run older than the prog   interrupted, and a new one added
    no cell run in this plane run (a new cell, a moved one)   a first one added

both ``by`` reload, in one commit per cell, so the plane run never reads
empty in between. Live or over makes no difference: a cell that drew and
returned runs again on its new prog. A cell run's version is the
``Cell.version`` it was added at, so a newer prog is one compare.

A plane run the kernel has not started yet is left alone: the kernel adds
its first cell runs in the commit that starts it, so reload never adds one
beside the kernel's. An ended one is left alone too.

An arm is a level flow with the standard re-checks: a missed notification
is a late reload, never a lost one. An arm that raises is reported and
runs again after a short delay (``restarting``). Cost: per live plane run,
O(its plane's cells) a pass, a few point reads each.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space
from nuspace.utils.policies import restarting


__all__ = ["BACKEND", "BY", "CELL", "PLANE", "PROG", "driver"]


#: The plane's id, fixed.
PLANE = "reload"

#: Its one cell's id, fixed.
CELL = "reload_main"

#: What its runs execute on.
BACKEND = "mp"

#: What the cell runs reload asks for are recorded as ``by``.
BY = "reload"

#: The cell's prog: the driver lives here, the store holds this.
PROG = """\
from nuspace.system.reload import plane


def out():
    return plane.driver()
"""

_RECHECK = {"after": nu.RECHECK_AFTER, "every": nu.RECHECK_EVERY}


def _cell(plane_run: nu.Str, plane: nu.Str, cell: nu.Str) -> nu.Nu:
    """One cell brought up to date in the plane run, check and writes in one commit. Bare.

    A cell rewritten since its newest cell run here gets that run
    interrupted (a no-op on one that ended) and a new one; a cell with no
    cell run here gets its first. A removed cell, or a plane run not
    started or ended, gets nothing.
    """
    row = Space.exec.plane_runs[plane_run]
    node = Space.exec.indexes.history.plane_to_plane_runs[plane].runs[plane_run]
    ids = node.cell_to_cell_runs[cell].ids
    newest = ids.last()
    version = Space.cells[cell].version.fallback(0)
    stale = nu.Bool(nu.If(ids.exists(), Space.exec.cell_runs[newest].version < version, False))
    going = row.started_at.exists().and_(row.ended_at.exists().not_())
    kept = Space.cells[cell].removed_at.exists().not_().and_(Space.cells[cell].plane == plane)
    add = ops.cell_run.add(plane_run, cell, by=BY)
    again = ops.cell_run.interrupt(newest) >> add
    return nu.IfDo(
        going.and_(kept),
        nu.IfDo(ids.exists().not_(), add, nu.IfDo(stale, again)),
    )


def _pass(plane_run: nu.Str, plane: nu.Str) -> nu.Nu:
    """Every cell of the plane brought up to date in the plane run, one commit each."""
    cells = Space.planes[plane].cells
    return nu.ForEachDo(
        atomic(nu.list(cells.keys())), lambda c: atomic(_cell(plane_run, plane, nu.Str(c)))
    )


def _arm(plane_run: nu.Str) -> nu.Nu:
    """One live plane run: kept on the latest code, on every write to its plane's cells.

    Also wakes once the kernel starts it, the first moment reload acts.
    """
    row = Space.exec.plane_runs[plane_run]

    def watching(held: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(held)
        changes = nu.OnAny(
            atomic(Space.planes[plane].version.on_change()),
            atomic(row.started_at.on_change()),
        )
        return nu.Reconcile(changes, _pass(plane_run, plane), **_RECHECK)

    return restarting(nu.let(atomic(row.plane.fallback("")), watching), PLANE, plane_run)


def driver() -> nu.Nu:
    """The reload driver: :func:`_arm` per live plane run, births and deaths included. Never returns.

    A raise outside an arm (reading the live runs) is reported and the
    driver runs again (``restarting``).
    """
    plane_runs = Space.exec.indexes.live.plane_runs
    arms = nu.ReconcileLatestEach(
        atomic(nu.list(plane_runs.keys())),
        atomic(plane_runs.on_children_change()),
        lambda r: _arm(nu.Str(r)),
        **_RECHECK,
    )
    return restarting(arms, PLANE)
