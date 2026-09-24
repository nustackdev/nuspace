"""The web device: the ws server, its connections in the store, the feeds.

A device owns an external resource and makes it bindable. It never runs a
cell (D1): which plane runs for a tab is the nav service's call, made from
``connections[sid].routes``, which this device writes and nobody else (D14).

Per connection, one arm:

1. ``connections[sid] = {opened: now, routes: []}``;
2. in parallel: the route arm, and the shell boot followed by the sidebar
   and viewer feeds. The route arm subscribes beside the boot rather than
   after it, so the browser's first ``pages.open`` cannot land before
   anybody listens;
3. on every way out, ``connections[sid]`` is deleted.

The route arm (D15): the viewer's ``pages.open`` carries the full ordered
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
from nuspace import ops
from nuspace.ops.utils import atomic, flag, fresh, or_else
from nuspace.shapes import RECENTS_CAP, Space
from nuspace.system.devices.web.env import SESSION_ENV, session_env
from nuspace.system.devices.web.session import served_sessions
from nuspace.system.devices.web.shell import Shell
from nuspace.system.devices.web.sidebar import sidebar_feed
from nuspace.system.devices.web.utils import Arms, cell_ui, field_ids
from nuspace.system.devices.web.viewer import on_open, slash_entries, viewer_feed
from nuspace.system.home import PLANE as HOME
from nuspace.system.kernel.space import free_port
from nuspace.system.kernel.utils import Now, snap
from nuspace.system.services.nav import clear_connections
from nustd.ui.core import WsSession
from nustd.ws_server import SID_ATTR, listen, run_once, session_for, sessions_fold


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.ops import App, Snippet
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
_ROUTE = "nuspace.web.route"
_connections = Space.connections


def open_connection(sid: nu.StrArg) -> nu.Nu:
    """Publish connection ``sid``: opened now, no plane open. One commit."""
    row = _connections[sid]
    return atomic(row.opened.set(Now()) >> row.routes.set(nu.Literal([])))


def close_connection(sid: nu.StrArg) -> nu.Nu:
    """Drop connection ``sid``. A no-op when it is gone."""
    return atomic(nu.IfDo(_connections.contains(sid), _connections.del_item(sid)))


def _erase(viewer: Ref, plane: nu.Nu) -> nu.Nu:
    """A plane's cells erased as drawn, so nothing of a closed pane stays on screen."""
    cell = fresh("web_erase_cell")
    ids = nu.If(ops.plane_exists(plane), ops.cells(plane), nu.List.of())
    return nu.ForEachDo(snap(ids), cell_ui(viewer, nu.StrAttrRef(cell)).erase(), item=cell)


def _remembered(plane: nu.Nu) -> nu.Nu:
    """Whether an opened plane goes in recents: not home, and not a system plane that is not ui.

    A plane not written yet counts: a new page is routed before its create
    lands (D41), and the home cell drops ids that never came to exist.
    """
    props = Space.planes[plane].props
    return nu.And(
        nu.Ne(plane, nu.Str(HOME)),
        nu.Not(nu.And(flag(props.system, False), nu.Not(flag(props.ui, False)))),
    )


def remember(opened: nu.Nu) -> nu.Nu:
    """Push plane ids onto ``Space.state.recents``, newest first. Unbracketed.

    ``opened`` is a list in pane order, so its last one is the newest. Those
    :func:`_remembered` skips are left out; the list is deduped and capped at
    :data:`~nuspace.shapes.RECENTS_CAP`, and written whole (D24).
    """
    recents = Space.state.recents
    item, new = fresh("web_recent"), fresh("web_recent_new")
    at = nu.AnyAttrRef(item)
    fresh_ids = nu.ListAttrRef(new)
    kept = nu.Filter(nu.List(or_else(recents, [])), nu.Not(fresh_ids.contains(at)), key=item)
    wanted = nu.List(
        nu.Collect(nu.Reversed(nu.Filter(nu.List(opened), _remembered(nu.ToStr(at)), key=item)))
    )
    merged = nu.List(fresh_ids + nu.List(nu.Collect(kept)))[0:RECENTS_CAP]
    return nu.Let(new, wanted, nu.IfDo(nu.Gt(fresh_ids.len(), nu.Int(0)), recents.set(merged)))


def route_arm(viewer: Ref, sid: nu.StrArg) -> nu.Nu:
    """Route ``sid`` to the planes the viewer has open (D15). Never ends.

    ``pages.open`` is the full list every time. The cells of every plane
    leaving it are erased as drawn before ``routes`` is written, so nothing
    of a closed pane stays on screen. The planes entering it are pushed onto
    recents in the same commit as ``routes``.
    """
    row = _connections[sid]
    item, wanted, left = fresh("web_open"), fresh("web_open_ids"), fresh("web_closed")
    was, entered = fresh("web_was"), fresh("web_entered")
    at = nu.AnyAttrRef(item)
    ids = nu.List(
        nu.Collect(
            nu.Unique(
                nu.Filter(
                    nu.Map(field_ids(_ROUTE, "page_ids"), nu.ToStr(at), key=item),
                    nu.Ne(at, nu.Str("")),
                    key=item,
                )
            )
        )
    )
    kept = nu.ListAttrRef(wanted)
    closed = nu.Filter(
        nu.List(snap(or_else(row.routes, []))), nu.Not(kept.contains(nu.AnyAttrRef(left))), key=left
    )
    # Read inside the commit, so a burst of opens never pushes one twice.
    opened = nu.Filter(
        kept, nu.Not(nu.List(or_else(row.routes, [])).contains(nu.AnyAttrRef(entered))), key=entered
    )
    write = nu.Let(
        was, nu.List(nu.Collect(opened)), remember(nu.ListAttrRef(was))
    ) >> row.routes.set(kept)
    body = nu.Let(
        wanted,
        ids,
        nu.ForEachDo(nu.List(nu.Collect(closed)), _erase(viewer, nu.StrAttrRef(left)), item=left)
        >> atomic(nu.IfDo(_connections.contains(sid), write)),
    )
    return _arms.event(_ROUTE, on_open(viewer), body)


def connection(
    sid: nu.StrArg,
    *,
    apps: Sequence[App] = (),
    snippets: Sequence[Snippet] = (),
    shell: type[Shell] = Shell,
) -> nu.Nu:
    """What one browser tab runs, with its session bound. Never ends.

    Args:
        sid: The connection id.
        apps: The registered apps, for the sidebar's sections.
        snippets: The registered snippets, for the viewer's ``/`` menu.
        shell: The shell every tab holds.
    """
    feeds = shell.boot(slash_entries(snippets)) >> nu.ParallelAsync(
        sidebar_feed(shell.sidebar, apps),
        viewer_feed(shell.viewer, sid, snippets),
    )
    return nu.TryCatch(
        open_connection(sid) >> nu.ParallelAsync(route_arm(shell.viewer, sid), feeds),
        finally_=close_connection(sid),
    )


def serve_web(
    *,
    apps: Sequence[App] = (),
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
        apps: The registered apps. Those with ``section=True`` are sidebar
            sections.
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
    sid = nu.StrAttrRef(SID_ATTR)
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
                run_once(connection(sid, apps=apps, snippets=snippets)),
            )
        ),
    )
    return term, {SESSION_ENV: session_env(session_address)}
