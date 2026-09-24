"""nav: what runs for each connection is the planes its routes name (D12, D14).

One arm per connection in ``Space.connections``, which the device writes
and the host empties at open. A connection's arm runs one arm per plane in
its ``routes`` (its panes, left to right): a user plane named there comes up
on a worker of its own, inside the ``session`` env bound to the connection,
and stays following the plane's cells while it stays in ``routes``:

    plane opened   w = worker(held=True); one arm per cell of the plane:
                     up(plane, [cell], worker=w, envs=[session:sid]), parked
    cell added     its arm ups it on w
    cell removed   its arm is cancelled, its run downed (if the removal
                     did not already stop it)
    plane closed   kill_worker(w); the other panes' workers are untouched
    connection     kill_worker(w) for every open plane
      gone

The worker is held (D40): idle GC never takes it, so a plane whose runs all
ended (its last cell removed, or every cell finished) keeps its worker, and
a cell added after runs on it. Killing happens on every way out of the turn
(``finally_``), so a plane closed, a connection going and nav itself
stopping all leave nothing behind. An arm downs its run only when its cell
is gone: when the turn ends the kill takes every run, and a down racing it
is what to avoid (see :func:`_cell_arm`).

Every fold subscribes through :class:`~..utils.Ticking`: a connection, a
route or a cell whose write the subscription missed is picked up on the
next tick.

A connection outlives no open: :func:`clear_connections` runs before init
starts nav (D34), so a tab from a previous run never brings a plane up.
"""

from __future__ import annotations

import nu
from nuspace.ops import cell_exists, kill_worker, plane_exists, up, worker
from nuspace.ops.utils import atomic, flag, fresh, or_else, text
from nuspace.shapes import STATUS_DEAD, STATUS_STARTING, STATUS_STOPPING, STATUS_UP, Space

from ..kernel.body import until
from ..utils import Ticking, park, snap, wake


__all__ = ["BY", "CELL", "PLANE", "SESSION", "SHIM", "clear_connections", "program"]


#: The plane id, fixed (D31).
PLANE = "nav"

#: The one cell on the plane.
CELL = "main"

#: What runs nav starts are recorded as ``by``.
BY = "nav"

#: The env a connection's runs execute inside, registered by the host as
#: ``session(connection_id)``.
SESSION = "session"

#: The cell's prog: the code lives here, the store holds this (D20).
SHIM = """\
from nuspace.system.services import nav


def out():
    return nav.program()
"""

_SID = "nuspace.nav.connection"
_ROUTE = "nuspace.nav.route"
_WORKER = "nuspace.nav.worker"
_CELL = "nuspace.nav.cell"
_RUN = "nuspace.nav.run"


def clear_connections() -> nu.Nu:
    """Drop every connection: what a previous open left behind. One commit."""
    connections = Space.connections
    item = fresh("nav_stale")
    at = nu.StrAttrRef(item)
    return atomic(nu.ForEachDo(nu.list(connections.keys()), connections.del_item(at), item=item))


def _shown(route: nu.StrAttrRef) -> nu.Nu:
    """Whether a route names a plane nav brings up: one that exists and is not a system plane."""
    return nu.And(
        nu.Ne(route, nu.Str("")),
        plane_exists(route),
        nu.Not(flag(Space.planes[route].props.system, False)),
    )


def _cell_ids(route: nu.StrAttrRef) -> nu.Nu:
    """The routed plane's cell ids, ``[]`` once the plane is gone. Unbracketed.

    ``nu.list`` is load bearing: a lazy keys view outlives its snapshot.
    """
    cells = Space.planes[route].cells
    return nu.If(plane_exists(route), nu.list(cells.keys()), nu.Literal([]))


def _down_running(run_ids: nu.Nu) -> nu.Nu:
    """Ask runs still starting or up to stop. One commit.

    Not ``ops.down``: it checks ``live`` and ``status`` apart, so a run
    ending between the two reads (the removal already stopped it) gets
    ``stopping`` written over its ``dead``. A run starting or up has not
    ended, whatever ``live`` reads.
    """
    item = fresh("nav_down")
    status = Space.kernel.runs[nu.StrAttrRef(item)].status
    running = nu.Or(
        nu.Eq(text(status), nu.Str(STATUS_STARTING)), nu.Eq(text(status), nu.Str(STATUS_UP))
    )
    return atomic(
        nu.ForEachDo(nu.List(run_ids), nu.IfDo(running, status.set(STATUS_STOPPING)), item=item)
    )


def _cell_arm(route: nu.StrAttrRef, worker_id: nu.StrAttrRef, envs: nu.Nu) -> nu.Nu:
    """One cell: up on the turn's worker, parked, its run downed once the cell is gone.

    The ops that take a cell away stop its runs in the same commit, so the
    down here is for a cell gone some other way. Cancelled with its cell
    still on the plane means the whole turn is ending, and the worker kill
    after it takes the run. Downing it then as well would race that kill: a
    run killed while writing its own end leaves the kernel's reap of its
    worker waiting on the store.
    """
    cell = nu.StrAttrRef(_CELL)
    run = up(route, nu.List.of(cell), worker=worker_id, envs=envs, by=BY)
    gone = nu.Not(snap(cell_exists(route, cell)))
    return nu.Let(
        _RUN, run, nu.TryCatch(park(), finally_=nu.IfDo(gone, _down_running(nu.ListAttrRef(_RUN))))
    )


def _cells_fold(route: nu.StrAttrRef, worker_id: nu.StrAttrRef, envs: nu.Nu) -> nu.Nu:
    """:func:`_cell_arm` per cell of the routed plane, births and deaths included. Never returns.

    The subscription is length exact: an edited cell is not a birth. The cell
    container is made real first, a subscription over one that is not there
    never fires. A plane gone parks: nothing to follow until the route moves.
    """
    cells = Space.planes[route].cells
    return atomic(nu.IfDo(plane_exists(route), cells.init(nu.Dict.create()))) >> nu.IfDo(
        snap(plane_exists(route)),
        nu.ForEachParReactive(
            snap(_cell_ids(route)),
            Ticking(snap(cells.on_children_change())),
            _cell_arm(route, worker_id, envs),
            _CELL,
        ),
        park(),
    )


def _open(sid: nu.StrAttrRef, route: nu.StrAttrRef) -> nu.Nu:
    """One open plane followed cell by cell on a held worker, killed on every way out.

    Waits for the plane first when the route names one not there yet.

    A worker that crashes ends the turn and the arm parks: the plane stays
    down until it is closed and opened again (renavigation brings it back).
    """
    w = nu.StrAttrRef(_WORKER)
    envs = nu.List.of(nu.List.of(nu.Str(SESSION), sid))
    followed = nu.Race(
        _cells_fold(route, w, envs), until(Space.kernel.workers[w].status, STATUS_DEAD)
    )
    turn = nu.Let(_WORKER, worker(held=True), nu.TryCatch(followed, finally_=kill_worker(w)))
    # A route can name a plane before the plane is written: the browser mints
    # a new page's id and opens it while its create is still in flight. So
    # wait for the plane rather than giving up on the route; the routes will
    # not change again to retry.
    shown = nu.WhileDo(nu.Not(snap(_shown(route))), wake(Space.planes.on_children_change()))
    return shown >> turn >> park()


def _routes(sid: nu.StrAttrRef) -> nu.Nu:
    """A connection's open plane ids, ``[]`` before any are written. Unbracketed."""
    return nu.List(or_else(Space.connections[sid].routes, []))


def _arm(sid: nu.StrAttrRef) -> nu.Nu:
    """One connection: :func:`_open` per plane in its routes, opens and closes included.

    A plane leaving ``routes`` cancels its arm, which kills its worker. A
    connection gone parks rather than subscribing to a row that is not there,
    and waits for the fold over connections to cancel it.
    """
    routes = Space.connections[sid].routes
    return nu.IfDo(
        snap(Space.connections.contains(sid)),
        nu.ForEachParReactive(
            snap(_routes(sid)),
            Ticking(snap(routes.on_change())),
            _open(sid, nu.StrAttrRef(_ROUTE)),
            _ROUTE,
        ),
        park(),
    )


def program() -> nu.Nu:
    """One arm per connection, births and deaths included. Never returns."""
    connections = Space.connections
    return atomic(connections.init(nu.Dict.create())) >> nu.ForEachParReactive(
        snap(nu.list(connections.keys())),
        Ticking(snap(connections.on_children_change())),
        _arm(nu.StrAttrRef(_SID)),
        _SID,
    )
