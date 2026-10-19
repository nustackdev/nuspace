"""nav: what runs for each connection is the planes its routes name (D12, D14).

One arm per connection in ``Space.connections``, which the device writes
and the host empties at open. A connection's arm runs one arm per plane in
its ``routes`` (its panes, left to right): a user plane named there gets a
plane run ``by`` nav, inside the ``session`` env bound to the connection,
for as long as it stays in ``routes``:

    plane opened   plane_run(plane, envs=[session:sid], into=run), run kept
                     in nav's state (:class:`Panes`) under the connection
                     and plane
    cell added     cell_run(run, cell), unless the run has one of it
    cell removed   nothing here: remove_cell interrupts its cell runs
    run ended      (every cell run over) waits for the plane's cells to
                     change, then runs the plane again
    plane closed   plane_stop(run): interrupt, killed after the grace
    restart asked  plane_stop(run), then the plane runs again at once
                     (:func:`restart`); a cell alone runs again in the
                     live run (:func:`restart_cell`)
    connection     plane_stop for every open plane
      gone

Stopping happens on every way out of a turn (``finally_``), so a plane
closed, a connection going and nav itself stopping all leave nothing
behind. The run ids live in nav's own cell state so the viewer shows each
pane the run nav made for it (:func:`pane_run`).

Every fold and wait is a level one: a connection, a route or a cell whose
write its subscription missed is picked up on the next re-check.

A connection outlives no open: :func:`clear_connections` runs before init
starts nav (D34), so a tab from a previous run never brings a plane up.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import cell_plane, cell_run, cells, plane_exists, plane_run, plane_stop
from nuspace.ops.kernel import add_cell_run, interrupt, latest
from nuspace.ops.utils import MintId, atomic, atomic_state
from nuspace.shapes import CellState, Space, reroot

from ..utils import moved, park, snap


__all__ = [
    "BY",
    "CELL",
    "PLANE",
    "RESTART_BY",
    "SESSION",
    "SHIM",
    "Panes",
    "clear_connections",
    "pane_key",
    "pane_run",
    "panes",
    "program",
    "restart",
    "restart_cell",
    "routable",
]


#: The plane id, fixed (D31).
PLANE = "nav"

#: The one cell on the plane.
CELL = "nav_main"

#: What plane and cell runs nav starts are recorded as ``by``.
BY = "nav"

#: What cell runs a restart starts are recorded as ``by``.
RESTART_BY = "restart"

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


class Panes(CellState):
    """nav's state per open pane, keyed ``"<connection>/<plane>"``.

    ``runs`` is the pane's plane run. ``restarts`` is a fresh token each time
    a restart is asked for: a turn that sees it move stops its run and the
    next turn starts at once.
    """

    runs = nustd.kv.DictRef.slot(str)
    restarts = nustd.kv.DictRef.slot(str)


def _here(term: nu.Nu) -> nu.Nu:
    """``term`` with :class:`Panes` landing at nav's own cell, for callers anywhere."""
    return reroot(term, PLANE, CELL)


def pane_key(sid: nu.StrArg, plane: nu.StrArg) -> nu.Str:
    """A pane's key in :class:`Panes`: ``"<connection>/<plane>"``."""
    return nu.Str(sid) + "/" + plane


def panes() -> nu.Nu:
    """The :class:`Panes` dict, from anywhere: pane key to plane run id."""
    return _here(Panes.runs)


def pane_run(sid: nu.StrArg, plane: nu.StrArg) -> nu.Str:
    """The plane run nav keeps for a connection's pane, ``""`` when none. Bare read, from anywhere."""
    return panes().get_item(pane_key(sid, plane), "")


def _asked(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """A pane's restart token in :class:`Panes`, from anywhere."""
    return _here(Panes.restarts)[pane_key(sid, plane)]


def restart(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """Run a connection's pane again: nav stops its plane run and makes a new one. One commit.

    A no-op for a plane the connection does not have open: no turn hears it.
    """
    key = pane_key(sid, plane)
    return atomic_state(
        nu.let(MintId("rs"), lambda token: _here(Panes.restarts.set_item(key, nu.Str(token))))
    )


def restart_cell(sid: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """Run one cell of a connection's pane again, in the pane's live run. One commit.

    Its newest cell run interrupted and a new one made, the way a reload
    does. A pane whose run is over has nothing to run it in, so the whole
    pane runs again (:func:`restart`).
    """
    plane = cell_plane(cell)

    def knowing(held: nu.ObjectRef) -> nu.Nu:
        run_id = nu.Str(held)
        again = nu.let(
            MintId("cr"), lambda new: add_cell_run(run_id, cell, nu.Str(new), RESTART_BY)
        )
        rerun = atomic(interrupt(run_id, latest(run_id, cell)) >> again)
        live = (run_id != "").and_(_kernel.running.contains(run_id))
        return nu.IfDo(snap(live), rerun, restart(sid, plane))

    return nu.let(snap(pane_run(sid, plane)), knowing)


def clear_connections() -> nu.Nu:
    """Drop every connection: what a previous open left behind. One commit."""
    connections = Space.connections
    return atomic(
        nu.ForEachDo(nu.list(connections.keys()), lambda c: connections.del_item(nu.Str(c)))
    )


def routable(route: nu.Nu) -> nu.Nu:
    """Whether a route names a plane nav brings up: one that exists and is drawn (``props.ui``).

    ``system`` is not asked: it only means protected, so a system ui plane
    (home) comes up, and a service (``ui`` unset) never does. The viewer
    tells a pane why it is left empty off the same answer.
    """
    return nu.And(
        nu.Str(route) != "",
        plane_exists(route),
        Space.planes[route].props.ui.fallback(False),
    )


def _cell_arm(route: nu.Str, run_id: nu.Str, cell: nu.Str) -> nu.Nu:
    """One cell of the routed plane: run in the pane's run if it never was, then parked.

    Whether it ever was is a point read of the run's ``latest``.
    """
    new = (cell_plane(cell) == route).and_(_kernel.runs[run_id].latest.contains(cell).not_())
    return nu.IfDo(snap(new), cell_run(run_id, cell, by=BY)) >> park()


def _cells_fold(route: nu.Str, run_id: nu.Str) -> nu.Nu:
    """:func:`_cell_arm` per cell of the routed plane, births included. Never returns.

    The subscription is on the plane's list of cells: an edited cell is not
    a birth. A plane gone parks: nothing to follow until the route moves.
    """
    return nu.IfDo(
        snap(plane_exists(route)),
        nu.ForEachParReactive(
            snap(cells(route)),
            snap(Space.planes[route].cells.on_children_change()),
            lambda cell: _cell_arm(route, run_id, nu.Str(cell)),
        ),
        park(),
    )


def _cells_seen(route: nu.Str) -> nu.Str:
    """The plane's cells and their versions, as one str to tell a change by. Bare read."""

    def seen(at: nu.Attr) -> nu.Str:
        cell = nu.Str(at)
        return cell + ":" + nu.str(Space.cells[cell].version.fallback(0))

    return nu.Str(",").join(cells(route).iter().map(seen).to_list())


def _changed(route: nu.Str) -> nu.Nu:
    """Wait until a cell of the plane is added, removed or rewritten.

    The plane's ``version`` counts every write to its cells, so the
    subscription hears this plane only; reading them again tells a change
    that matters here from a rename.
    """
    edits = Space.planes[route].version.on_change()
    return nu.let(
        snap(_cells_seen(route)),
        lambda seen: nu.WaitReactive(snap(edits), nu.Not(seen == snap(_cells_seen(route)))),
    )


def _turn(sid: nu.Str, route: nu.Str) -> nu.Nu:
    """One plane run of the pane: made, followed cell by cell until it ends, stopped on the way out.

    Waits for the plane first when the route names one not there yet. Once
    the run is over by itself, waits for the plane's cells to change, and
    the next turn runs it again. A restart asked for (:func:`restart`) ends
    either wait: the run is stopped and the next turn starts at once.
    """
    envs = nu.List.of(nu.List.of(SESSION, sid))
    token = _asked(sid, route)

    def follow(made: nu.ObjectRef, seen: nu.Str) -> nu.Nu:
        run_id = nu.Str(made)
        running = _kernel.running
        # The run leaves the plane's live runs in the commit that ends it.
        live = _kernel.planes_running[route].runs.on_children_change()
        ended = nu.WaitReactive(snap(live), snap(running.contains(run_id).not_()))
        asked = moved(token, seen)
        followed = nu.TryCatch(
            nu.Race(_cells_fold(route, run_id), ended, asked),
            finally_=nu.IfDo(snap(running.contains(run_id)), plane_stop(run_id)),
        )
        remember = atomic_state(_here(Panes.runs.set_item(pane_key(sid, route), run_id)))
        start = plane_run(route, by=BY, envs=envs, into=made)
        return start >> remember >> followed >> nu.Race(_changed(route), asked)

    def turn(held: nu.ObjectRef) -> nu.Nu:
        return nu.let("", lambda made: follow(made, nu.Str(held)))

    # A route can name a plane before the plane is written: the browser mints
    # a new plane's id and opens it while its create is still in flight. So
    # wait for the plane rather than giving up on the route; the routes will
    # not change again to retry.
    shown = nu.WaitReactive(snap(Space.planes[route].on_change()), snap(routable(route)))
    return shown >> nu.let(snap(nu.str(token).fallback("")), turn)


def _open(sid: nu.Str, route: nu.Str) -> nu.Nu:
    """One open plane, run and run again for as long as it is open. Forgotten on the way out."""
    runs, restarts = panes(), _here(Panes.restarts)
    key = pane_key(sid, route)
    forget = atomic_state(
        nu.IfDo(runs.contains(key), runs.del_item(key))
        >> nu.IfDo(restarts.contains(key), restarts.del_item(key))
    )
    return nu.TryCatch(nu.ForeverDo(_turn(sid, route)), finally_=forget)


def _arm(sid: nu.Str) -> nu.Nu:
    """One connection: :func:`_open` per plane in its routes, opens and closes included.

    A plane leaving ``routes`` cancels its arm, which stops its run. A
    connection gone parks rather than subscribing to a row that is not there,
    and waits for the fold over connections to cancel it. ``routes`` reads
    ``[]`` before any are written.
    """
    routes = Space.connections[sid].routes
    return nu.IfDo(
        snap(Space.connections.contains(sid)),
        nu.ForEachParReactive(
            snap(routes.fallback([])),
            snap(routes.on_change()),
            lambda route: _open(sid, nu.Str(route)),
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
        _here(Panes.runs.set({}) >> Panes.restarts.set({}))
    )
    return fresh_state >> nu.ForEachParReactive(
        snap(nu.list(connections.keys())),
        snap(connections.on_children_change()),
        lambda sid: _arm(nu.Str(sid)),
    )
