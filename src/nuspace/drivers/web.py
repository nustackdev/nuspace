"""A Space with browsers on it, where navigating to a Plane is what runs it.

The other answer to when and what. :mod:`nuspace.drivers.headless` brings up
the Planes a process opening the Space is enough for; those are the same for
everybody. A ``nav`` Plane is not: it is up because one tab is looking at it
and it goes down when that tab looks elsewhere, so it is per connection and it
belongs to whichever driver holds the connections. That is this one.

Three layers, and each is somebody else's already:

- ``nustd.ws_server`` holds the sockets and gives one live arm per open tab;
- :mod:`nuspace.web` is what a tab holds: the Shell, the sidebar of Planes, the
  Viewer a Plane is drawn on, the connection a worker reaches back through;
- :mod:`nuspace.exec` places a Plane's Cells and keeps them alive.

What is decided here and nowhere else is the join: which Plane a connection
has open, and that having it open means running it. Everything drawing needs
is an argument to the runtime language rather than a thing it knows about, so
the Cell rooting and the connection's address are built here and handed down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace import ops
from nuspace.exec import CELL_ATTR, PLANE_ATTR, park, run_plane
from nuspace.shapes import Space
from nuspace.space import free_port
from nuspace.web.route import PLANE_ID, opened, opens, per_connection
from nuspace.web.session import WsSession, served_sessions
from nuspace.web.shell import Shell
from nuspace.web.sidebar import sidebar_driver
from nuspace.web.utils import Arms, CellRoot, cell_ui, cells_ui, field_str
from nuspace.web.viewer import on_select, viewer_driver
from nustd.ws_server import SID_ATTR, listen, run_once, session_for, sessions_fold


if TYPE_CHECKING:
    from nustd.ui.core import Ref


__all__ = ["BANNER", "connection", "run_opened", "serve_space"]


#: What the server calls itself when it says it is ready.
BANNER = "nuspace"

#: This driver's one arm that belongs to neither region, named for the report
#: it prints and for the event it binds under.
_NAV = "opened_plane"


_arms = Arms("web")


def run_opened(
    viewer: Ref,
    *,
    session_address: str | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Whatever Plane this connection has open, running, and nothing else.

    The whole of "navigation is execution", and it is one arm because the two
    halves are one sentence. A tab that moved says so by selecting a Plane;
    the selection is recorded and the loop re-enters, which cancels whatever
    was running and reads the record again. Cancelling is what takes the old
    Plane down: the runtime kills the worker on every way out of the branch,
    the Plane being left behind included.

    Recorded first and read after, in that order and in one arm, because two
    arms would be the write and the re-entry racing each other. Read from the
    record rather than from the tab, because asking the browser is a round
    trip and a client that stopped answering would hang the arm that runs its
    Planes.

    The Plane id is bound to the attr the runtime reads it off, so it travels
    into the worker with the rest of the Context. A term reading a per
    connection record would resolve against the worker's own and find nothing.

    Args:
        viewer: the ref this connection's Planes are drawn on. Where a
            selection arrives from and where every Cell's refs land.
        session_address: ``host:port`` where this process serves its live
            connections. None draws nothing, which is a tab that navigates and
            gets a Plane running headless behind it.
        root: the Space shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never
        finishes.
    """
    # What the Plane being left behind drew, taken off the screen before the
    # next one starts drawing on it.
    #
    # Here, at the head of the branch that brings a Plane up, rather than where
    # the move is recorded: a Race settles the branch it cancelled before it
    # returns, so by the time this runs the old Plane's worker is already dead
    # and cannot write a node back in behind the erase. Recording the move and
    # clearing the screen in one place would race exactly that.
    #
    # Unconditional, so navigating to something that draws nothing still clears
    # what was there. On the first turn it erases a node nobody has written,
    # which costs one frame the browser ignores.
    cleared = cells_ui(viewer).erase()
    up = cleared >> nu.Let(
        PLANE_ATTR,
        opened(),
        body=nu.IfDo(
            nu.And(
                nu.Ne(nu.StrAttrRef(PLANE_ATTR), nu.Str("")),
                ops.plane_exists(nu.StrAttrRef(PLANE_ATTR), root=root),
            ),
            run_plane(
                nu.StrAttrRef(PLANE_ATTR),
                # Where a Cell's refs land, and what the last turn of that
                # Cell left standing. Both name the Cell the fold is on, and
                # the fold is in the worker, so both travel there as payload.
                rewrite=CellRoot(viewer, nu.StrAttrRef(CELL_ATTR)),
                erase=cell_ui(viewer, nu.StrAttrRef(CELL_ATTR)).erase(),
                session_address=session_address,
                root=root,
            ),
        ),
    )
    moved = nu.React(
        on_select(viewer),
        opens(field_str(_NAV, PLANE_ID)),
        changed_key=_NAV,
    )
    return nustd.kv.auto_flow_atomic(
        # Two guards, the same pair every arm gets. The inner one keeps a
        # Plane that will not start from ending the arm that would start the
        # next one; the outer turns a dead arm into a completed arm rather
        # than a raise that would take the tab's other arms with it.
        _arms.guard(
            nu.ForeverDo(
                nu.Race(
                    _arms.guard(up, f"{_NAV}:run") >> park(),
                    moved,
                )
            ),
            _NAV,
        ),
        scope=root,
    )


def connection(
    shell: type[Shell] = Shell,
    *,
    session_address: str | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """What one browser tab runs, from the frames that seed it onwards.

    The boot batch is sequenced in front, because the browser shows nothing at
    all until something lands under its root. The three halves after it run
    side by side, because none waits on another: the list of Planes, what the
    Viewer draws, and the Plane running behind it.

    Args:
        shell: the Shell this tab holds. Both regions are its own slots and the
            driver reads them off here rather than from a registry, because the
            class body is the one place that says where they hang.
        session_address: ``host:port`` where this process serves its live
            connections, so a worker can draw on this one.
        root: the Space shape class.
    """
    return shell.boot() >> per_connection(
        nu.ParallelAsync(
            sidebar_driver(shell.sidebar, root=root),
            viewer_driver(shell.viewer, shell.route, root=root),
            run_opened(shell.viewer, session_address=session_address, root=root),
        )
    )


def serve_space(
    *,
    shell: type[Shell] = Shell,
    host: str = "127.0.0.1",
    port: int = 8080,
    static: str | None = "nuspace_ui",
    open_browser: bool = True,
    log_level: str = "warning",
    session_address: str | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """The Space on a browser, as the one term a process drives.

    No store bracket and no pool: those come from the Context this runs in,
    which is :func:`nuspace.space.open_space`. What it does open is the server
    and the socket every worker drawing on a tab calls back through, in that
    order, because the book of connections is the server's.

    Goes in a ``body=`` slot and never in a ``nu.With`` spec slot, which would
    discard everything under it. It never returns.

    Args:
        shell: the Shell every tab holds.
        host: the interface the server binds.
        port: the port the server binds.
        static: the wheel shipping the compiled browser app. None serves the
            socket alone, which is what a separate vite dev server wants.
        open_browser: open the bound URL once the server says it is ready.
        log_level: how much the server itself says. The default leaves only
            the line that says it is up.
        session_address: ``host:port`` for the connection socket. A free port
            by default. One for the process: a bracket's kwargs are plain
            python, so an address cannot be picked per connection inside a
            term that is built once.
        root: the Space shape class, which is also the store's tag.
    """
    session_address = session_address or f"127.0.0.1:{free_port()}"
    return nu.With(
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
                # Once per connection and not once per reconcile pass: the
                # fold sweeps arms whose task ended and starts them again on
                # every connect or disconnect anywhere on the server, and a
                # tab rebooted because somebody else opened one is a tab that
                # was wiped and reseeded for no reason.
                run_once(
                    connection(
                        shell,
                        session_address=session_address,
                        root=root,
                    )
                ),
            ),
        ),
    )
