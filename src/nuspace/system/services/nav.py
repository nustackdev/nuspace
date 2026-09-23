"""nav: what runs for each connection is the plane its route names (D12, D14).

One arm per connection in ``Space.connections``, which the device writes
and the host empties at open. An arm follows its connection's ``route``: a user plane named there
comes up on a worker of its own, inside the ``session`` env bound to the
connection, and stays following the plane's cells while the route holds:

    route set     w = worker(); one arm per cell of the plane:
                    up(route, [cell], worker=w, envs=[session:sid]), held
    cell added    its arm ups it on w
    cell removed  its arm is cancelled, its run downed (if the removal
                    did not already stop it)
    route moved   kill_worker(w), then the same for the new route
    connection    kill_worker(w)
      gone

Killing happens on every way out of the turn (``finally_``), so a route
change, a connection going and nav itself stopping all leave nothing
behind. An arm downs its run only when its cell is gone: when the turn
ends the kill takes every run, and a down racing it is what to avoid
(see :func:`_cell_arm`).

Idle GC (D9) takes a worker that had runs and has none, so a plane whose
last run ended (its cells removed or all finished) loses its worker. The
turn then waits for a cell that has not run yet, and only then takes a new
one: a plane with no cells never has a run, so its worker idles rather than
churns, and cells that already ran to an end are not run again because a
sibling was added. A cell counts as run once its run came up on the worker:
one upped on a worker already going (the orphan sweep fails it unstarted),
or added after the worker went, runs on the next.

A connection outlives no open: :func:`clear_connections` runs before init
starts nav (D34), so a tab from a previous run never brings a plane up.
"""

from __future__ import annotations

import nu
from nuspace.ops import cell_exists, kill_worker, plane_exists, up, worker
from nuspace.ops.utils import atomic, flag, fresh, text
from nuspace.shapes import STATUS_DEAD, STATUS_STARTING, STATUS_STOPPING, STATUS_UP, Space

from ..kernel.body import until
from ..utils import follows, park, snap, wake


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
_DONE = "nuspace.nav.done"
_RUNS = "nuspace.nav.runs"


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
        nu.Not(flag(Space.planes[route].system, False)),
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


def _cell_arm(route: nu.StrAttrRef, envs: nu.Nu) -> nu.Nu:
    """One cell: up on the turn's worker, held, its run downed once the cell is gone.

    The ops that take a cell away stop its runs in the same commit, so the
    down here is for a cell gone some other way. Cancelled with its cell
    still on the plane means the whole turn is ending, and the worker kill
    after it takes the run. Downing it then as well would race that kill: a
    run killed while writing its own end leaves the kernel's reap of its
    worker waiting on the store.

    A cell in ``_DONE`` came up on an earlier worker, so it already ran
    and is not run again. The run id goes on the turn's ``_RUNS``, one list
    every arm shares, so the turn can tell which cells came up.
    """
    cell = nu.StrAttrRef(_CELL)
    run = up(route, nu.List.of(cell), worker=nu.StrAttrRef(_WORKER), envs=envs, by=BY)
    gone = nu.Not(snap(cell_exists(route, cell)))
    held = nu.Let(
        _RUN,
        run,
        nu.ListAttrRef(_RUNS).extend(nu.ListAttrRef(_RUN))
        >> nu.TryCatch(park(), finally_=nu.IfDo(gone, _down_running(nu.ListAttrRef(_RUN)))),
    )
    return nu.IfDo(nu.Not(nu.ListAttrRef(_DONE).contains(cell)), held, park())


def _cells_fold(route: nu.StrAttrRef, envs: nu.Nu) -> nu.Nu:
    """:func:`_cell_arm` per cell of the routed plane, births and deaths included.

    The subscription is length exact: an edited cell is not a birth. The cell
    container is made real first, a subscription over one that is not there
    never fires.
    """
    cells = Space.planes[route].cells
    return atomic(nu.IfDo(plane_exists(route), cells.init(nu.Dict.create()))) >> nu.IfDo(
        snap(plane_exists(route)),
        nu.ForEachParReactive(
            snap(_cell_ids(route)),
            snap(cells.on_children_change()),
            _cell_arm(route, envs),
            _CELL,
        ),
        park(),
    )


def _ran(route: nu.StrAttrRef) -> nu.Nu:
    """The routed plane's cells in ``_DONE`` or with a run in ``_RUNS`` that came up. Unbracketed.

    Came up is ``started`` written: the body writes it with ``up``, a run the
    orphan sweep failed never has it.
    """
    item = fresh("nav_ran")
    rid = fresh("nav_rid")
    cell = nu.StrAttrRef(item)
    row = Space.kernel.runs[nu.StrAttrRef(rid)]
    came_up = nu.Filter(
        nu.ListAttrRef(_RUNS),
        nu.And(nu.Eq(text(row.cell), cell), row.started.exists()),
        key=rid,
    )
    ran = nu.Or(
        nu.ListAttrRef(_DONE).contains(cell),
        nu.Gt(nu.List(nu.Collect(came_up)).len(), nu.Int(0)),
    )
    return nu.List(nu.Collect(nu.Filter(_cell_ids(route), ran, key=item)))


def _new_cell(route: nu.StrAttrRef) -> nu.Nu:
    """Whether the routed plane is there and has a cell not in ``_DONE``."""
    item = fresh("nav_new")
    new = nu.Filter(
        _cell_ids(route),
        nu.Not(nu.ListAttrRef(_DONE).contains(nu.StrAttrRef(item))),
        key=item,
    )
    return nu.And(plane_exists(route), nu.Gt(nu.List(nu.Collect(new)).len(), nu.Int(0)))


def _open(sid: nu.StrAttrRef, route: nu.StrAttrRef) -> nu.Nu:
    """The route's plane followed cell by cell on a worker, held until cancelled.

    Each pass takes a worker and runs the cells fold on it until the worker
    is dead (idle GC, a crash), killing it on every way out. Then it waits
    for a cell that has not come up yet before taking the next worker.
    """
    w = nu.StrAttrRef(_WORKER)
    done = nu.ListAttrRef(_DONE)
    envs = nu.List.of(nu.List.of(nu.Str(SESSION), sid))
    held = nu.Race(_cells_fold(route, envs), until(Space.kernel.workers[w].status, STATUS_DEAD))
    pass_ = nu.Let(_WORKER, worker(), nu.TryCatch(held, finally_=kill_worker(w)))
    turn = nu.Let(_RUNS, nu.List.of(), pass_ >> nu.SetCmd(done, snap(_ran(route)))) >> nu.WhileDo(
        nu.Not(snap(_new_cell(route))),
        # A plane gone parks: nothing to wait on until the route moves.
        nu.IfDo(
            snap(plane_exists(route)),
            wake(Space.planes[route].cells.on_children_change()),
            park(),
        ),
    )
    return nu.IfDo(snap(_shown(route)), nu.Let(_DONE, nu.List.of(), nu.ForeverDo(turn)))


def _arm(sid: nu.StrAttrRef) -> nu.Nu:
    """One connection: its route followed, the plane behind it kept up."""
    route = nu.StrAttrRef(_ROUTE)
    connections = Space.connections
    return follows(
        connections[sid].route, _ROUTE, _open(sid, route), alive=connections.contains(sid)
    )


def program() -> nu.Nu:
    """One arm per connection, births and deaths included. Never returns."""
    connections = Space.connections
    return atomic(connections.init(nu.Dict.create())) >> nu.ForEachParReactive(
        snap(nu.list(connections.keys())),
        snap(connections.on_children_change()),
        _arm(nu.StrAttrRef(_SID)),
        _SID,
    )
