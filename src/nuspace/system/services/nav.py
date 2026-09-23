"""nav: what runs for each connection is the plane its route names (D12, D14).

One arm per connection in ``Space.connections``, which the device writes
and the host empties at open. An arm follows its connection's ``route``: a user plane named there
comes up on a worker of its own, inside the ``session`` env bound to the
connection. The worker is the whole handle, so moving on is killing it:

    route set     w = worker(); up_plane(route, worker=w, envs=[session:sid])
    route moved   kill_worker(w), then the same for the new route
    connection    kill_worker(w)
      gone

Killing happens on every way out of the arm (``finally_``), so a route
change, a connection going and nav itself stopping all leave nothing behind.

A connection outlives no open: :func:`clear_connections` runs before init
starts nav (D34), so a tab from a previous run never brings a plane up.
"""

from __future__ import annotations

import nu
from nuspace.ops import kill_worker, plane_exists, up_plane, worker
from nuspace.ops.utils import atomic, flag, fresh
from nuspace.shapes import Space

from ..utils import follows, park, snap


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


def _open(sid: nu.StrAttrRef, route: nu.StrAttrRef) -> nu.Nu:
    """The route's plane up on a fresh worker, held until cancelled, the worker killed then."""
    w = nu.StrAttrRef(_WORKER)
    envs = nu.List.of(nu.List.of(nu.Str(SESSION), sid))
    held = up_plane(route, worker=w, envs=envs, by=BY) >> park()
    return nu.IfDo(
        snap(_shown(route)),
        nu.Let(_WORKER, worker(), nu.TryCatch(held, finally_=kill_worker(w))),
    )


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
