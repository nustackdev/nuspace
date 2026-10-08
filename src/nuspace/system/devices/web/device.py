"""The web device: the ws server, its connections in the store, the feeds.

A device owns an external resource and makes it bindable. It never runs a
cell (D1): which plane runs for a tab is the nav service's call, made from
``connections[sid].routes``, which this device writes and nobody else (D14).

Per connection, one arm:

1. ``connections[sid] = {opened: now, routes: []}``;
2. in parallel: the route arm, and the shell boot followed by the sidebar
   and viewer feeds. The route arm subscribes beside the boot rather than
   after it, so the browser's first ``planes.open`` cannot land before
   anybody listens;
3. on every way out, ``connections[sid]`` is deleted.

The route arm (D15): the viewer's ``planes.open`` carries the full ordered
list of open planes (its panes, left to right). Deduped with order kept and
empty ids dropped, it is written whole as ``routes``. Every plane that left
the list has its cells erased as drawn first. The planes newly in the list
are pushed onto ``Space.state.recents`` in the same commit (:func:`remember`).

What a run needs to draw on a tab is the session env, returned beside the
term for the host to register with the kernel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.time
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import RECENTS_CAP, Space
from nuspace.system.devices.web.env import SESSION_ENV, session_env
from nuspace.system.devices.web.session import served_sessions
from nuspace.system.devices.web.shell import Shell
from nuspace.system.devices.web.sidebar import (
    registered_entries,
    searchable_entries,
    sidebar_feed,
)
from nuspace.system.devices.web.utils import Arms, cell_ui, field_ids
from nuspace.system.devices.web.viewer import on_open, slash_entries, viewer_feed
from nuspace.system.home import PLANE as HOME
from nuspace.system.kernel.space import free_port
from nuspace.system.kernel.utils import snap
from nuspace.system.search import PLANE as SEARCH
from nuspace.system.services.nav import clear_connections
from nuspace.system.settings import PLANE as SETTINGS
from nustd.ui.core import WsSession
from nustd.ws_server import SID_ATTR, listen, run_once, session_for, sessions_fold


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.ops import Plane, Snippet
    from nuspace.system.kernel import EnvFactory
    from nustd.ui.core import Ref


__all__ = [
    "BANNER",
    "clear_connections",
    "close_connection",
    "connection",
    "open_connection",
    "remember",
    "route_arm",
    "serve_web",
]


#: What the server calls itself when it is up.
BANNER = "nuspace"

_arms = Arms("device")
_connections = Space.connections


def open_connection(sid: nu.StrArg) -> nu.Nu:
    """Publish connection ``sid``: opened now, no plane open. One commit."""
    row = _connections[sid]
    return atomic(row.opened.set(nustd.time.time()) >> row.routes.set([]))


def close_connection(sid: nu.StrArg) -> nu.Nu:
    """Drop connection ``sid``. A no-op when it is gone."""
    return atomic(nu.IfDo(_connections.contains(sid), _connections.del_item(sid)))


def _erase(viewer: Ref, plane: nu.Nu) -> nu.Nu:
    """A plane's cells erased as drawn, so nothing of a closed pane stays on screen."""
    ids = nu.If(ops.plane_exists(plane), ops.cells(plane), [])
    return nu.ForEachDo(snap(ids), lambda cell: cell_ui(viewer, nu.Str(cell)).erase())


def _remembered(plane: nu.Nu) -> nu.Bool:
    """Whether an opened plane goes in recents: not home, settings or search, and not a service.

    A plane not written yet counts: a new plane is routed before its create
    lands (D41), and the home cell drops ids that never came to exist.
    """
    props = Space.planes[plane].props
    service = props.system.fallback(False).and_(props.ui.fallback(False).not_())
    return nu.List.of(HOME, SETTINGS, SEARCH).contains(plane).or_(service).not_()


def remember(opened: nu.Nu) -> nu.Nu:
    """Push plane ids onto ``Space.state.recents``, newest first. Unbracketed.

    ``opened`` is a list in pane order, so its last one is the newest. Those
    :func:`_remembered` skips are left out; the list is deduped and capped at
    :data:`~nuspace.shapes.RECENTS_CAP`, and written whole (D24).
    """
    recents = Space.state.recents
    wanted = nu.Reversed(nu.Filter(nu.List(opened), lambda p: _remembered(nu.str(p))))

    def push(held: nu.ObjectRef) -> nu.Nu:
        pushed = nu.List(held)
        kept = recents.fallback([]).iter().filter(lambda p: pushed.contains(p).not_())
        merged = (pushed + kept.to_list())[0:RECENTS_CAP]
        return nu.IfDo(pushed.len() > 0, recents.set(merged))

    return nu.let(nu.List(nu.Collect(wanted)), push)


def route_arm(viewer: Ref, sid: nu.StrArg) -> nu.Nu:
    """Route ``sid`` to the planes the viewer has open (D15). Never ends.

    ``planes.open`` is the full list every time. The cells of every plane
    leaving it are erased as drawn before ``routes`` is written, so nothing
    of a closed pane stays on screen. The planes entering it are pushed onto
    recents in the same commit as ``routes``.
    """
    row = _connections[sid]
    routes = row.routes.fallback([])

    def routed(wanted: nu.ObjectRef) -> nu.Nu:
        kept = nu.List(wanted)
        closed = nu.Filter(snap(routes), lambda p: kept.contains(p).not_())
        # Read inside the commit, so a burst of opens never pushes one twice.
        opened = kept.iter().filter(lambda p: routes.contains(p).not_())
        write = nu.let(opened.to_list(), remember) >> row.routes.set(kept)
        erase = nu.ForEachDo(nu.List(nu.Collect(closed)), lambda p: _erase(viewer, nu.Str(p)))
        return erase >> atomic(nu.IfDo(_connections.contains(sid), write))

    def route(event: nu.Attr) -> nu.Nu:
        ids = nu.Map(field_ids(event, "plane_ids"), lambda p: nu.str(p))
        return nu.let(nu.List(nu.Collect(nu.Unique(nu.Filter(ids, lambda p: p != "")))), routed)

    return _arms.event("route", on_open(viewer), route)


def connection(
    sid: nu.StrArg,
    *,
    planes: Sequence[Plane] = (),
    snippets: Sequence[Snippet] = (),
    shell: type[Shell] = Shell,
) -> nu.Nu:
    """What one browser tab runs, with its session bound. Never ends.

    Args:
        sid: The connection id.
        planes: The registered Planes, what the sidebar can create.
        snippets: The registered snippets, for the viewer's ``/`` menu and
            the sidebar's search.
        shell: The shell every tab holds.
    """
    boot = shell.boot(
        slash_entries(snippets), registered_entries(planes), searchable_entries(snippets)
    )
    feeds = boot >> nu.ParallelAsync(
        sidebar_feed(shell.sidebar, planes, snippets),
        viewer_feed(shell.viewer, sid, snippets),
    )
    return nu.TryCatch(
        open_connection(sid) >> nu.ParallelAsync(route_arm(shell.viewer, sid), feeds),
        finally_=close_connection(sid),
    )


def serve_web(
    *,
    planes: Sequence[Plane] = (),
    snippets: Sequence[Snippet] = (),
    host: str = "127.0.0.1",
    port: int = 8080,
    static: str | None = "nuspace_ui",
    open_browser: bool = True,
    log_level: str = "warning",
    session_address: str | None = None,
) -> tuple[nu.Nu, dict[str, EnvFactory]]:
    """The web device: the term the host runs, and the envs it registers.

    The term opens the server and the socket workers draw through, then
    runs one arm per connection. Connections a previous open left are the
    host's to clear, before init starts (D34). It
    never returns; it goes in a ``body=`` slot, beside the kernel, inside the
    store brackets (``open_kernel``).

    Args:
        planes: The registered Planes, what the sidebar can create.
        snippets: The registered snippets: the viewer's ``/`` menu, and what
            a cell made from each entry stores.
        host: The interface the server binds.
        port: The port the server binds.
        static: The wheel shipping the browser bundle. None serves the socket
            alone, eg for a vite dev server.
        open_browser: Open the URL once the server is up.
        log_level: How much the server says.
        session_address: ``host:port`` for the connection socket. A free port
            by default.

    Returns:
        ``(term, envs)``: ``envs`` maps ``"session"`` to the session env
        factory, ``factory(sid) -> Env``.
    """
    session_address = session_address or f"127.0.0.1:{free_port()}"
    sid = nu.Str(nu.Attr(SID_ATTR))
    term = nu.With(
        listen(
            session_cls=WsSession,
            static=static,
            host=host,
            port=port,
            log_level=log_level,
            banner=BANNER,
            open_browser=open_browser,
        ),
        served_sessions(session_address),
        body=sessions_fold(
            session_for(
                SID_ATTR,
                # Once per connection: the fold respawns ended arms on every
                # connect or disconnect anywhere, and a tab rebooted because
                # somebody else opened one is wiped for no reason.
                run_once(connection(sid, planes=planes, snippets=snippets)),
            )
        ),
    )
    return term, {SESSION_ENV: session_env(session_address)}
