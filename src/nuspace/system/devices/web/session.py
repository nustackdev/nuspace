"""One browser connection, and how a worker reaches it.

A cell never runs in the host, so a cell that draws is always across a
process boundary. Two halves:

- **worker side**: :func:`proxied_session` binds the connection a run draws
  on, taken by id out of :class:`Connections`, a proxy to the host's book.
  :class:`FrameCodec` makes frames cross by value. These are pickled into
  every drawing run, so this module imports no web server at module scope:
  a worker unpickling a body would otherwise load uvicorn and fastapi for a
  server it never runs.
- **host side**: :func:`served_sessions` puts :class:`Sessions`, the lookup
  on the ws server's book, on one socket for the process. One socket rather
  than one per connection, because a bracket's kwargs are plain python and
  cannot be picked per connection inside a term built once.

**Why the relay.** The invisibles async dispatcher awaits a served coroutine
on a loop of its own, on a background thread, while the websocket belongs to
the host's loop. :class:`HostedSession` hands every call back to that loop.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import nu
import nustd.proxy
from nu.core.spans.bracket import _LifecycleBracket
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Coroutine

    from nu.lang.runtime import Context
    from nustd.ui.core.protocol import Frame
    from nustd.ui.core.session import Subscription
    from nustd.ws_server import WebServer


__all__ = [
    "SESSION_ATTR",
    "ConnectedSession",
    "Connections",
    "FrameCodec",
    "HostedSession",
    "Sessions",
    "proxied_session",
    "served_sessions",
]


#: The attr a drawing run's connection id is bound under, in the worker.
SESSION_ATTR = "nuspace.session"


# --- worker side -----------------------------------------------------------------


class FrameCodec:
    """Frames by value on the invisibles wire, for as long as the bracket holds.

    Invisibles boxes a class it was not told about by reference, and the
    encoder cannot msgpack a netref. Registering the frame type pickles it
    across instead, chain and all, which lets a cell in a worker create the
    node it writes to.

    The registry is process wide and a worker hosts many runs at once, so the
    registration is counted: the first run in registers, the last one out
    unregisters. Uncounted, the first run to end took frames away from every
    run still drawing on its worker.
    """

    _held = 0
    _lock = threading.Lock()

    def setup(self, ctx: Context) -> None:
        """Register the frame type, once per process."""
        from invisibles.core.boxing import register_value_type

        from nustd.ui.core.protocol import Frame

        with FrameCodec._lock:
            if FrameCodec._held == 0:
                register_value_type(Frame)
            FrameCodec._held += 1

    def cleanup(self) -> None:
        """Drop the registration when the last run holding it ends."""
        from invisibles.core.boxing import unregister_value_type

        from nustd.ui.core.protocol import Frame

        with FrameCodec._lock:
            FrameCodec._held -= 1
            if FrameCodec._held == 0:
                unregister_value_type(Frame)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: setup is sync work."""
        self.setup(ctx)

    async def acleanup(self) -> None:
        """Async shim: cleanup is sync work."""
        self.cleanup()


class Connections:
    """Every live browser connection, by id. A type to bind the proxy under.

    The book is in the host, which holds the sockets; what a worker holds
    under this name is a proxy to :class:`Sessions`.
    """

    def session(self, sid: str) -> object:
        """The connection ``sid`` names, as something a ui ref draws on.

        Raises:
            LookupError: no such connection. Ordinary: a tab can close
                between a run being dispatched and the worker asking.
        """
        raise NotImplementedError


class ConnectedSession(_LifecycleBracket):
    """Bind the connection named by :data:`SESSION_ATTR` as the session.

    What lands on the context is the remote connection itself, not a wrapper:
    every call on it is a round trip, and a local object in between would
    have to know which of its methods are coroutines on the far side.
    """

    @asynccontextmanager
    async def _aopen(self, ctx: Context) -> AsyncIterator[Context]:
        sid = ctx.attrs.get(SESSION_ATTR)
        if sid is None:
            msg = f"ConnectedSession found no {SESSION_ATTR!r} on the context"
            raise LookupError(msg)
        yield ctx.bind(Session, ctx.get(Connections).session(sid))


def proxied_session(address: str, body: nu.Nu) -> nu.With:
    """``body`` with its connection bound as the session it draws on.

    Needs :data:`SESSION_ATTR` bound around it (the session env does that).

    Args:
        address: ``host:port`` where :func:`served_sessions` listens.
        body: what runs with the connection bound. Pickled into the worker.
    """
    return nu.With(
        nu.Provide(FrameCodec, {}),
        # bg_serve, because the far end calls back: a subscription's callback
        # is a reverse proxy, which is what carries a browser edit into the
        # worker running the cell.
        nustd.proxy.InvisiblesProxy(Connections, address=address, bg_serve=True),
        ConnectedSession(),
        body=body,
    )


# --- host side -------------------------------------------------------------------


class HostedSession(Session):
    """A session callable from off the loop that owns it.

    ``subscribe`` is passed straight through: it only touches the session's
    observer registry, which no loop owns.
    """

    def __init__(self, session: Session, loop: asyncio.AbstractEventLoop) -> None:
        self._session = session
        self._loop = loop

    async def _relay(self, work: Coroutine[Any, Any, Any]) -> Any:  # noqa: ANN401
        """Run ``work`` on the connection's loop and wait for it here."""
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(work, self._loop))

    async def send(self, frame: Frame) -> None:
        """Ship one frame, on the loop that owns the socket."""
        await self._relay(self._session.send(frame))

    async def aread(self, path: tuple[str, ...]) -> Any:  # noqa: ANN401 -- the browser's blob
        """Round trip read, on the loop that owns the pending futures."""
        return await self._relay(self._session.aread(path))

    def subscribe(self, path: tuple[str, ...]) -> Subscription:
        """Observe notify frames for ``path``. The callback arrives as a reverse proxy."""
        return self._session.subscribe(path)


class Sessions(Connections):
    """The lookup on the ws server's book of connections. What the socket serves."""

    def __init__(self) -> None:
        self._server: WebServer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def asetup(self, ctx: Context) -> None:
        """Take the server's book and the loop its connections are on."""
        # Here, not at the top: see the module docstring. The process running
        # this is the one that called ``listen``, so it is loaded already.
        from nustd.ws_server import WebServer

        self._server = ctx.get(WebServer)
        self._loop = asyncio.get_running_loop()

    def session(self, sid: str) -> HostedSession:
        """The connection ``sid`` names, callable from another process.

        Raises:
            LookupError: the connection is gone, or no server was bound.
        """
        if self._server is None or self._loop is None:
            msg = "Sessions was asked for a connection before the server was bound"
            raise LookupError(msg)
        session = self._server.session(sid)
        if session is None:
            msg = f"no live connection for {sid!r}"
            raise LookupError(msg)
        return HostedSession(session, self._loop)


def served_sessions(address: str) -> nu.With:
    """Every live connection on one socket, so a worker can draw on one.

    Goes inside the server bracket: the book it reads is the server's.

    Args:
        address: ``host:port`` to listen on.
    """
    return nu.With(
        nu.Provide(Sessions, {}),
        nu.Provide(
            nustd.proxy.InvisiblesServer,
            {
                "target": Sessions,
                "address": address,
                "transport": "tcp",
                # Threaded: every drawing worker holds a connection here and
                # they do not take turns. Async: send and aread are coroutines.
                "executor": "threaded",
                "dispatcher": "async",
            },
        ),
    )
