"""nav: what runs for each connection is the planes its routes name (D12, D14).

One arm per connection in ``Space.connections``, which the device writes
and the host empties at open. A connection's arm runs one arm per plane in
its ``routes`` (its panes, left to right): a user plane named there gets a
plane run ``by`` nav, inside the ``session`` env bound to the connection,
for as long as it stays in ``routes``:

    plane opened   run = plane_run(plane, envs=[session:sid]), kept in nav's
                     state (:class:`Panes`) under the connection and plane
    cell added     cell_run(run, cell), unless the run has one of it
    cell removed   nothing here: remove_cell interrupts its cell runs
    run ended      (every cell run over) waits for the plane's cells to
                     change, then runs the plane again
    plane closed   plane_stop(run): interrupt, killed after the grace
    connection     plane_stop for every open plane
      gone

Stopping happens on every way out of a turn (``finally_``), so a plane
closed, a connection going and nav itself stopping all leave nothing
behind. The run ids live in nav's own cell state so the viewer shows each
pane the run nav made for it (:func:`pane_run`).

Every fold subscribes through :class:`~..utils.Ticking`: a connection, a
route or a cell whose write the subscription missed is picked up on the
next tick.

A connection outlives no open: :func:`clear_connections` runs before init
starts nav (D34), so a tab from a previous run never brings a plane up.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import cell_exists, cell_run, cells, plane_exists, plane_run, plane_stop
from nuspace.ops.utils import atomic, atomic_state, flag, fresh, or_else
from nuspace.shapes import CellState, Space, reroot

from ..utils import Ticking, park, snap, until, wake


__all__ = [
    "BY",
    "CELL",
    "PLANE",
    "SESSION",
    "SHIM",
    "Panes",
    "clear_connections",
    "pane_key",
    "pane_run",
    "panes",
    "program",
    "routable",
]


#: The plane id, fixed (D31).
PLANE = "nav"

#: The one cell on the plane.
CELL = "main"

#: What plane and cell runs nav starts are recorded as ``by``.
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

_kernel = Space.kernel

_SID = "nuspace.nav.connection"
_ROUTE = "nuspace.nav.route"
_CELL = "nuspace.nav.cell"
_RUN = "nuspace.nav.run"
_SEEN = "nuspace.nav.seen"


class Panes(CellState):
    """nav's state: the plane run of each open pane, keyed ``"<connection>/<plane>"``."""

    runs = nustd.kv.DictRef.slot(str)


def _here(term: nu.Nu) -> nu.Nu:
    """``term`` with :class:`Panes` landing at nav's own cell, for callers anywhere."""
    return reroot(term, PLANE, CELL)


def pane_key(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """A pane's key in :class:`Panes`: ``"<connection>/<plane>"``."""

    def part(x: nu.StrArg) -> nu.Nu:
        return nu.Str(x) if isinstance(x, str) else x

    return part(sid) + nu.Str("/") + part(plane)


def panes() -> nu.Nu:
    """The :class:`Panes` dict, from anywhere: pane key to plane run id."""
    return _here(Panes.runs)


def pane_run(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """The plane run nav keeps for a connection's pane, ``""`` when none. Bare read, from anywhere."""
    runs = panes()
    key = pane_key(sid, plane)
    return nu.If(runs.contains(key), nu.ToStr(runs[key]), nu.Str(""))


def clear_connections() -> nu.Nu:
    """Drop every connection: what a previous open left behind. One commit."""
    connections = Space.connections
    item = fresh("nav_stale")
    at = nu.StrRef(item)
    return atomic(nu.ForEachDo(nu.list(connections.keys()), connections.del_item(at), item=item))


def routable(route: nu.Nu) -> nu.Nu:
    """Whether a route names a plane nav brings up: one that exists and is drawn (``props.ui``).

    ``system`` is not asked: it only means protected, so a system ui plane
    (home) comes up, and a service (``ui`` unset) never does. The viewer
    tells a pane why it is left empty off the same answer.
    """
    return nu.And(
        nu.Ne(route, nu.Str("")),
        plane_exists(route),
        flag(Space.planes[route].props.ui, False),
    )


def _has_cell_run(run_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Whether the plane run ever had a cell run of the cell. A point read of its ``latest``."""
    return _kernel.runs[run_id].latest.contains(cell_id)


def _cell_arm(route: nu.StrRef, run_id: nu.StrRef) -> nu.Nu:
    """One cell of the routed plane: run in the pane's run if it never was, then parked."""
    cell = nu.StrRef(_CELL)
    new = nu.And(cell_exists(route, cell), nu.Not(_has_cell_run(run_id, cell)))
    return nu.IfDo(snap(new), cell_run(run_id, cell, by=BY)) >> park()


def _cells_fold(route: nu.StrRef, run_id: nu.StrRef) -> nu.Nu:
    """:func:`_cell_arm` per cell of the routed plane, births included. Never returns.

    The subscription is length exact: an edited cell is not a birth. The cell
    container is made real first, a subscription over one that is not there
    never fires. A plane gone parks: nothing to follow until the route moves.
    """
    plane_cells = Space.planes[route].cells
    ids = nu.If(plane_exists(route), nu.list(plane_cells.keys()), nu.Literal([]))
    return atomic(nu.IfDo(plane_exists(route), plane_cells.init(nu.Dict.create()))) >> nu.IfDo(
        snap(plane_exists(route)),
        nu.ForEachParReactive(
            snap(ids),
            Ticking(snap(plane_cells.on_children_change())),
            _cell_arm(route, run_id),
            _CELL,
        ),
        park(),
    )


def _cells_seen(route: nu.StrRef) -> nu.Nu:
    """The plane's cells and their versions, as one str to tell a change by. Bare read."""
    item = fresh("nav_seen")
    at = nu.StrRef(item)
    version = Space.planes[route].cells[at].version
    each = at + nu.Str(":") + nu.If(version.exists(), nu.ToStr(version), nu.Str("0"))
    return nu.Str(",").join(nu.Collect(nu.Map(cells(route), each, key=item)))


def _changed(route: nu.StrRef) -> nu.Nu:
    """Wait until a cell of the plane is added, removed or rewritten."""
    seen = nu.StrRef(_SEEN)
    edits = Space.planes[route].cells.on_descendants_change("*", "version")
    return nu.Let(
        _SEEN,
        snap(_cells_seen(route)),
        nu.WhileDo(nu.Eq(snap(_cells_seen(route)), seen), wake(edits)),
    )


def _turn(sid: nu.StrRef, route: nu.StrRef) -> nu.Nu:
    """One plane run of the pane: made, followed cell by cell until it ends, stopped on the way out.

    Waits for the plane first when the route names one not there yet. Once
    the run is over by itself, waits for the plane's cells to change, and
    the next turn runs it again.
    """
    run_id = nu.StrRef(_RUN)
    envs = nu.List.of(nu.List.of(nu.Str(SESSION), sid))
    ended = until(nu.Not(_kernel.running.contains(run_id)), _kernel.running.on_children_change())
    live = snap(_kernel.running.contains(run_id))
    followed = nu.TryCatch(
        nu.Race(_cells_fold(route, run_id), ended), finally_=nu.IfDo(live, plane_stop(run_id))
    )
    remember = atomic_state(_here(Panes.runs.set_item(pane_key(sid, route), run_id)))
    # A route can name a plane before the plane is written: the browser mints
    # a new plane's id and opens it while its create is still in flight. So
    # wait for the plane rather than giving up on the route; the routes will
    # not change again to retry.
    shown = nu.WhileDo(nu.Not(snap(routable(route))), wake(Space.planes.on_children_change()))
    ran = nu.Let(_RUN, plane_run(route, by=BY, envs=envs), remember >> followed >> _changed(route))
    return shown >> ran


def _open(sid: nu.StrRef, route: nu.StrRef) -> nu.Nu:
    """One open plane, run and run again for as long as it is open. Forgotten on the way out."""
    runs = panes()
    key = pane_key(sid, route)
    forget = atomic_state(nu.IfDo(runs.contains(key), runs.del_item(key)))
    return nu.TryCatch(nu.ForeverDo(_turn(sid, route)), finally_=forget)


def _routes(sid: nu.StrRef) -> nu.Nu:
    """A connection's open plane ids, ``[]`` before any are written. Unbracketed."""
    return nu.List(or_else(Space.connections[sid].routes, []))


def _arm(sid: nu.StrRef) -> nu.Nu:
    """One connection: :func:`_open` per plane in its routes, opens and closes included.

    A plane leaving ``routes`` cancels its arm, which stops its run. A
    connection gone parks rather than subscribing to a row that is not there,
    and waits for the fold over connections to cancel it.
    """
    routes = Space.connections[sid].routes
    return nu.IfDo(
        snap(Space.connections.contains(sid)),
        nu.ForEachParReactive(
            snap(_routes(sid)),
            Ticking(snap(routes.on_change())),
            _open(sid, nu.StrRef(_ROUTE)),
            _ROUTE,
        ),
        park(),
    )


def program() -> nu.Nu:
    """One arm per connection, births and deaths included. Never returns.

    What a previous open left in :class:`Panes` is dropped first: its runs
    were ended by reconcile.
    """
    connections = Space.connections
    fresh_state = atomic(connections.init(nu.Dict.create())) >> atomic_state(
        _here(Panes.runs.set(nu.Literal({})))
    )
    return fresh_state >> nu.ForEachParReactive(
        snap(nu.list(connections.keys())),
        Ticking(snap(connections.on_children_change())),
        _arm(nu.StrRef(_SID)),
        _SID,
    )
