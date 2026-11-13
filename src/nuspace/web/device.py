"""The web device: the server, one arm per browser tab, nav, and the web planes it ships with.

A device is a way into the space with its own store: it calls ops like
anyone. Per tab, one arm:

1. ``web.open_tab(sid)``: the tab's ``Conn.connections[sid]`` row;
2. in parallel: the pane arm, and the shell boot followed by the sidebar,
   viewer and desks feeds. The pane arm subscribes beside the boot rather than
   after it, so the browser's first ``planes.open`` cannot land before
   anybody listens;
3. on every way out, ``web.close_tab(sid)``: nav stops its panes' runs.

**The pane arm.** The viewer's ``planes.open`` carries the full ordered
list of open panes, left to right, and each pane's params. It becomes
``web.set_panes`` (the order whole: a new plane gets its pane, nav runs it),
then ``web.set_pane_params`` for each pane whose params moved, and
``web.reveal`` for each plane newly open, all in one Conn commit, then
``web.visit`` for each plane newly open (not a plane a role names, nor one
missing or headless). The reveal opens the sidebar branches above a new
pane's plane for this tab, so the tree reships with its row in reach: the
browser never climbs a tree that holds only open branches.
The cells of every plane leaving the list are erased as drawn first, so
nothing of a closed pane stays on screen. The browser mints a new plane's
id and opens it while its create is in flight, so the arm waits a moment
for a plane new to the list before it asks.

**A failed interaction toasts.** Every browser event, ``planes.open``
included, runs under one guard: its error's type and message show on the
tab (:meth:`~nuspace.web.utils.Arms.event`).

**The device term** (:func:`serve_web`): the web planes made where missing
(:func:`~nuspace.web.planes.ensure`), then the server and nav side
by side. nav runs here, in the host, beside the tabs it serves.

Beside the socket the server answers one plain route,
``POST /api/telemetry/space-loaded``: the browser saying a page loaded,
queued as ``space_loaded`` (see :mod:`nuspace._telemetry`), so the browser
never talks to PostHog and follows the same opt out.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

from starlette.responses import Response
from starlette.routing import Route

import nu
import nuspace
from nuspace import _telemetry
from nuspace.ops.brackets import atomic
from nuspace.specs import space_registry
from nuspace.utils import keys_of
from nustd.ui.core import WsSession
from nustd.ws_server import SID_ATTR, listen, run_once, session_for, sessions_fold

from . import ops as web
from .desks import pruner
from .desks.feed import desks_feed
from .env import SESSION_ENV, session_env
from .home import indexer
from .nav import nav
from .planes import ensure
from .session import served_sessions
from .shapes import Conn, Web
from .shell import Shell
from .sidebar import registered_entries, sidebar_feed
from .utils import Arms, cell_ui, field_dict, field_ids
from .viewer import on_open, slash_entries, viewer_feed


if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request

    from nuspace.kernel import EnvFactory
    from nuspace.specs import Registry
    from nustd.ui.core import Ref


__all__ = [
    "BANNER",
    "OPEN_WAIT",
    "ROUTES",
    "WEB_WAIT",
    "connection",
    "pane_arm",
    "serve_web",
    "space_loaded",
]


#: What the server calls itself when it is up.
BANNER = "nuspace"

#: How long the pane arm waits for a plane new to the list to land, in seconds:
#: the browser opens a plane it creates while the create is in flight.
OPEN_WAIT = 2.0

#: How long it then waits for a plane in the space to be on the web, in
#: seconds: a create commits its web row right after its Space row, so a
#: plane still without one is headless and is not waited on longer.
WEB_WAIT = 0.3


def _erase(viewer: Ref, plane: nu.Str) -> nu.Nu:
    """A plane's cells erased as drawn, so nothing of a closed pane stays on screen."""
    ids = keys_of(nuspace.Space.planes[plane].cells)
    return nu.ForEachDo(atomic(ids), lambda cell: cell_ui(viewer, nu.Str(cell)).erase())


def _landed(planes: nu.List) -> nu.Nu:
    """Wait for every plane to be in the space, then on the web, each wait capped.

    A plane made in the same breath lands in two commits, its Space row then
    its web row, so the wait hears both. Up to :data:`OPEN_WAIT` for the
    Space rows, since a create may still be in flight; then up to
    :data:`WEB_WAIT` for the web rows, which follow at once, so a headless
    plane is not waited on for long. What never lands opens anyway: the
    viewer says it is missing or headless.
    """
    landing = nu.OnAny(
        nuspace.Space.planes.on_children_change(), web.Web.planes.on_children_change()
    )

    def wait(left: Callable[[nu.Str], nu.Bool], cap: float) -> nu.Nu:
        ready = nu.Int(nu.Count(planes.iter().filter(lambda p: left(nu.Str(p))))) == 0
        waited = nu.WaitUntil(atomic(landing), atomic(ready), after=(0.05, 0.2, 0.5))
        return nu.Timeout(cap, waited, on_timeout=nu.Noop())

    def absent(p: nu.Str) -> nu.Bool:
        return nuspace.plane.exists(p).not_()

    def off_web(p: nu.Str) -> nu.Bool:
        return nuspace.plane.exists(p).and_(web.Web.planes.contains(p).not_())

    return wait(absent, OPEN_WAIT) >> wait(off_web, WEB_WAIT)


def pane_arm(viewer: Ref, sid: nu.StrArg, arms: Arms) -> nu.Nu:
    """The tab's panes, as the viewer has them open. Never ends.

    Per ``planes.open``: erase what closed, wait for planes new to the
    list, then ``set_panes``, the params that moved and the sidebar path
    to each plane newly open, then a visit for each plane newly open. Each
    step is its own commit, Conn then Web.
    """
    tab = Conn.connections[sid]

    def route(event: nu.Attr) -> nu.Nu:
        wanted = field_ids(event, "plane_ids")
        given = field_dict(event, "params")

        def opened(held: nu.ObjectRef) -> nu.Nu:
            before = nu.List(held)
            fresh = wanted.iter().filter(lambda p: before.contains(p).not_()).to_list()
            gone = before.iter().filter(lambda p: wanted.contains(p).not_()).to_list()

            def params(at: nu.Attr) -> nu.Nu:
                plane = nu.Str(at)
                pairs = nu.Dict(given.get_item(plane, nu.Dict.create()))
                moved = tab.panes[plane].params.fallback({}) != pairs
                return nu.IfDo(moved, web.set_pane_params(sid, plane, pairs))

            def visited(at: nu.Attr) -> nu.Nu:
                # A plane a role names lives in the sidebar's nav section: no visit.
                plane = nu.Str(at)
                skip = nu.list(Web.roles.values()).contains(plane)
                # A pane told it is missing or headless is no visit.
                shown = nuspace.plane.exists(plane).and_(Web.planes.contains(plane))
                return atomic(nu.IfDo(skip.not_().and_(shown), web.visit(plane)))

            return (
                nu.ForEachDo(gone, lambda p: _erase(viewer, nu.Str(p)))
                >> _landed(fresh)
                >> atomic(
                    web.set_panes(sid, wanted)
                    >> nu.ForEachDo(wanted, params)
                    >> nu.ForEachDo(fresh, lambda p: web.reveal(sid, nu.Str(p)))
                )
                >> nu.ForEachDo(fresh, visited)
            )

        listed = nu.If(tab.order.exists(), nu.list(tab.order), nu.Literal([]))
        return nu.let(atomic(listed), opened)

    return arms.event("open", on_open(viewer), route)


def connection(sid: nu.StrArg, *, registry: Registry | None = None) -> nu.Nu:
    """What one browser tab runs, with its session bound. Never ends.

    Args:
        sid: The tab id.
        registry: What the space registered: its PlaneSpecs, what the
            sidebar can create, and its CellSpecs, for the viewer's ``/``
            menu. None is every installed package's.
    """
    reg = space_registry() if registry is None else registry
    planes, cells = list(reg.planes.values()), list(reg.cells.values())
    arms = Arms("device", Shell.toast)
    boot = Shell.boot(slash_entries(cells), registered_entries(planes))
    feeds = boot >> nu.ParallelAsync(
        sidebar_feed(Shell.sidebar, sid, planes, Shell.toast),
        viewer_feed(Shell.viewer, sid, cells, Shell.toast),
        desks_feed(Shell.desks, Shell.toast),
    )
    gone = atomic(nu.IfDo(Conn.connections.contains(sid), web.close_tab(sid)))
    return nu.TryCatch(
        atomic(web.open_tab(sid)) >> nu.ParallelAsync(pane_arm(Shell.viewer, sid, arms), feeds),
        finally_=gone,
    )


async def space_loaded(request: Request) -> Response:
    """``POST /api/telemetry/space-loaded``: a page loaded. Queued, answered at once."""
    del request
    _telemetry.track("space_loaded")
    return Response(status_code=204)


#: The plain routes the server answers beside the socket.
ROUTES = (Route("/api/telemetry/space-loaded", space_loaded, methods=["POST"]),)


def _free_port() -> int:
    """A port nothing listens on now, on the loopback."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def serve_web(
    *,
    registry: Registry | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    static: str | None = "nuspace_ui",
    open_browser: bool = True,
    log_level: str = "warning",
    session_address: str | None = None,
) -> tuple[nu.Nu, dict[str, EnvFactory]]:
    """The web device: the term the host runs, and the envs it registers.

    The term makes the web planes where missing, asks for one home indexer
    run (:func:`~.home.indexer.wake`) and one desk pruner run
    (:func:`~.desks.pruner.wake`), then runs the server (one arm per tab)
    and nav side by side. It never returns; it goes beside the
    kernel, inside the stores (Space, State, Web, Conn) with ``conn.db``
    fresh, so no tab of a previous open is left.

    Args:
        registry: What the space registered: its PlaneSpecs, what the
            sidebar can create, and its CellSpecs, the viewer's ``/`` menu.
            None is every installed package's.
        host: The interface the server binds.
        port: The port the server binds.
        static: The wheel shipping the browser bundle. None serves the socket
            alone, eg for a vite dev server.
        open_browser: Open the URL once the server is up.
        log_level: How much the server says.
        session_address: ``host:port`` for the tab socket. A free port by
            default.

    Returns:
        ``(term, envs)``: ``envs`` maps ``"session"`` to the session env
        factory, ``factory(sid) -> Env``.
    """
    session_address = session_address or f"127.0.0.1:{_free_port()}"
    registry = space_registry() if registry is None else registry
    sid = nu.Str(nu.Attr(SID_ATTR))
    server = nu.With(
        listen(
            session_cls=WsSession,
            static=static,
            host=host,
            port=port,
            log_level=log_level,
            banner=BANNER,
            open_browser=open_browser,
            routes=ROUTES,
        ),
        served_sessions(session_address),
        body=sessions_fold(
            session_for(
                SID_ATTR,
                # Once per tab: the fold respawns ended arms on every connect
                # or disconnect anywhere, and a tab rebooted because somebody
                # else opened one is wiped for no reason.
                run_once(connection(sid, registry=registry)),
            )
        ),
    )
    term = ensure() >> indexer.wake() >> pruner.wake() >> nu.ParallelAsync(server, nav())
    return term, {SESSION_ENV: session_env(session_address)}
