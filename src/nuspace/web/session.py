"""One browser connection, and how a worker reaches it.

The wire half needs no class of nuspace's own: the browser speaks the same
Frame codec every ws host speaks, so :class:`~nustd.ui.core.WsSession` is the
session handed to ``listen`` and it is re-exported here, because this is the
module that answers what a connection is.

The rest is the out of process half, and it is the interesting one. A Cell
never runs in this process, so a Cell that draws is always across a process
boundary: it holds a proxy, and on this end is the socket in :func:`served_sessions`.

**Why one socket for the process rather than one per connection.** A bracket's
kwargs are plain python, never terms, so an address cannot be picked per
connection inside an arm term that is built once and merely re-entered. So
there is one socket, and what it serves is :class:`Sessions`, which turns a
session id back into a connection. The id is the one thing a worker already
has: a connection's arm runs with it on the Context and a dispatch carries the
Context's attrs into the worker.

**Why the relay.** The invisibles async dispatcher awaits a served coroutine
on a loop of its own, on a background thread, while the websocket and the
pending read futures belong to the loop this process runs on. So every async
call is handed back to that loop rather than run where it landed, which is all
:class:`HostedSession` is.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import nu
import nustd.proxy
from nuspace.space import Connections
from nustd.ui.core import WsSession
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Coroutine

    from nu.lang.runtime import Context
    from nustd.ui.core.protocol import Frame
    from nustd.ui.core.session import Subscription
    from nustd.ws_server import WebServer


__all__ = ["HostedSession", "Sessions", "WsSession", "served_sessions"]


class HostedSession(Session):
    """A Session callable from off the event loop that owns it.

    ``subscribe`` is left alone: it only touches the session's observer
    registry, which no loop owns.
    """

    def __init__(self, session: Session, loop: asyncio.AbstractEventLoop) -> None:
        self._session = session
        self._loop = loop

    async def _relay(self, work: Coroutine[Any, Any, Any]) -> Any:  # noqa: ANN401
        """Run ``work`` on the connection's loop and wait for it here."""
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(work, self._loop))

    async def send(self, frame: Frame) -> None:
        """Ship one Frame, on the loop that owns the socket."""
        await self._relay(self._session.send(frame))

    async def aread(self, path: tuple[str, ...]) -> Any:  # noqa: ANN401 -- the browser's blob
        """Round trip read, on the loop that owns the pending futures."""
        return await self._relay(self._session.aread(path))

    def subscribe(self, path: tuple[str, ...]) -> Subscription:
        """Observe notify frames for ``path``.

        The handle reaches a worker as a proxy and the callback it binds goes
        the other way as a reverse proxy, which is what carries a browser edit
        into the process running the Cell.
        """
        return self._session.subscribe(path)


class Sessions(Connections):
    """Every live connection, by session id. What the socket serves.

    The book itself belongs to the server, which is holding the sockets; this
    is the lookup on it, plus the relay onto the loop the connections live on.
    That loop is captured once, here, because it is the loop this process runs
    on and every connection's transport is on it.

    The other end of it is :class:`~nuspace.space.Connections`, which is what
    a worker binds the proxy under.
    """

    def __init__(self) -> None:
        self._server: WebServer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def asetup(self, ctx: Context) -> None:
        """Take the server's book and the loop its connections are on."""
        # Imported here rather than at the top, because the top of this module
        # is reached by every worker that draws: a Cell's dispatched body holds
        # refs from this package, so unpickling it imports ``nuspace.web``, and
        # a module level import would hand each of them uvicorn and fastapi for
        # a server they will never run. The process this runs in is the one
        # that called ``listen``, so here it is already loaded.
        from nustd.ws_server import WebServer

        self._server = ctx.get(WebServer)
        self._loop = asyncio.get_running_loop()

    def session(self, sid: str) -> HostedSession:
        """The connection ``sid`` names, ready to be called from another process.

        Raises:
            LookupError: the connection is gone. Reachable in the ordinary
                course of things, since a browser can close between a Cell
                being dispatched and the worker asking for the tab it draws
                on.
        """
        if self._server is None or self._loop is None:
            msg = "Sessions was asked for a connection before the server was bound"
            raise LookupError(msg)
        session = self._server.session(sid)
        if session is None:
            msg = f"no live connection for {sid!r}"
            raise LookupError(msg)
        # Fresh per call rather than kept: a worker asks once, when the body
        # it came up with opens its brackets, and nothing here should outlive
        # the connection it wraps.
        return HostedSession(session, self._loop)


def served_sessions(address: str) -> nu.With:
    """Every live connection on a socket, so a worker can draw on one.

    Goes inside the server bracket, because the book it reads is the server's.

    Args:
        address: ``host:port`` to listen on, one for the process.

    Returns:
        A bracket with no body, for a ``nu.With`` spec slot.
    """
    return nu.With(
        nu.Provide(Sessions, {}),
        nu.Provide(
            nustd.proxy.InvisiblesServer,
            {
                "target": Sessions,
                "address": address,
                "transport": "tcp",
                # Threaded, because every worker drawing on a tab holds a
                # connection here and they do not take turns. Async, because
                # send and aread are coroutines and want a loop to run on.
                "executor": "threaded",
                "dispatcher": "async",
            },
        ),
    )
