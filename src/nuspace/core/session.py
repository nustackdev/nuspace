"""One connection's ``nu.ui`` Session, reachable from another process.

A section runs in a pool worker and every ``nu.ui`` Ref it builds asks the
context for a ``Session``. The Session is the websocket, so it cannot be
copied into the worker; it is served over invisibles instead, exactly the way
:func:`~nuspace.core.host.served_navigator` serves the store.

Three things stand between the raw session and the wire, and all of them are
here:

- :class:`HostedSession`, because the invisibles async dispatcher runs a loop
  of its own and the websocket belongs to the connection's.
- :class:`FrameCodec`, because invisibles boxes an unknown class by reference
  and a ``Frame`` is meant to travel by value.
- :class:`SessionServer`, because a section restarting closes a client every
  few seconds and ``nu.proxy.InvisiblesServer`` shares one dispatcher across
  all of them.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

from invisibles import AsyncDispatcher, InvisiblesConnection, Protocol
from invisibles.config import AttributeAccessConfig, ConnectionConfig
from invisibles.core.boxing import register_value_type, unregister_value_type
from invisibles.netkit import SyncServer
from invisibles.netkit.executors.threaded import ThreadedExecutor
from invisibles.netkit.framing import LengthPrefixedFraming
from invisibles.netkit.transports import TCPListener

import nu
from nu.ui.core.protocol import Frame
from nu.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Coroutine

    from nu.lang.runtime import Context
    from nu.ui.core.session import Subscription


__all__ = ["FrameCodec", "HostedSession", "SessionServer", "served_session"]


#: One megabyte a frame, the same ceiling nu.proxy serves the Navigator under.
_MAX_FRAME = 1024 * 1024


def _framing(transport: object) -> LengthPrefixedFraming:
    """Length-prefix whatever the listener hands back."""
    return LengthPrefixedFraming(transport, max_frame_size=_MAX_FRAME)


class HostedSession(Session):
    """A Session callable from off the event loop that owns it.

    The invisibles async dispatcher awaits a served coroutine on a loop it
    runs in a background thread, and both the websocket transport and the
    pending-read futures belong to the connection's loop instead. So every
    async call is handed back to that loop rather than run where it landed.

    ``subscribe`` is left alone: it only touches the session's observer dict,
    which no loop owns.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._loop = asyncio.get_running_loop()

    async def _relay(self, work: Coroutine[Any, Any, Any]) -> Any:  # noqa: ANN401
        """Run ``work`` on the connection's loop and wait for it here."""
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(work, self._loop))

    async def send(self, frame: Frame) -> None:
        """Ship one Frame, on the loop that owns the socket."""
        await self._relay(self._session.send(frame))

    async def aread(self, path: str) -> Any:  # noqa: ANN401 -- payload is opaque
        """Round-trip read, on the loop that owns the pending futures."""
        return await self._relay(self._session.aread(path))

    def subscribe(self, path: str) -> Subscription:
        """Observe notify frames for ``path``.

        The handle comes back to the worker as a proxy, and the callback the
        worker binds on it goes the other way as a reverse proxy, which is
        what carries a browser edit into the process running the section.
        """
        return self._session.subscribe(path)


class FrameCodec:
    """Frames by value on the invisibles wire, for as long as the bracket holds.

    A ``Frame`` is plain data, but invisibles boxes any class it has not been
    told about by reference: the worker would hand the server a proxy and
    ``encode`` would try to msgpack a netref. Registering the type makes it
    pickle across instead.
    """

    def setup(self, ctx: Context) -> None:
        """Register the type. Process-wide, which is what the registry is."""
        register_value_type(Frame)

    def cleanup(self) -> None:
        """Drop the registration again."""
        unregister_value_type(Frame)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: setup is sync work."""
        self.setup(ctx)

    async def acleanup(self) -> None:
        """Async shim: cleanup is sync work."""
        self.cleanup()


class SessionServer:
    """The bound :class:`HostedSession`, on a TCP socket, one client per worker.

    Not ``nu.proxy.InvisiblesServer``, and the reason is the dispatcher.
    ``send`` and ``aread`` are coroutines, so the calls have to run on an
    event loop, and invisibles' async dispatcher owns one. ``InvisiblesServer``
    builds a single dispatcher and shares it across every client, while
    invisibles shuts a dispatcher down when *a* connection closes -- and a
    section restarting closes one every few seconds, which would take every
    other section on the page down with it. So a dispatcher is per client
    here, and it dies with the client it belongs to.

    Args:
        address: ``host:port`` to listen on.
    """

    def __init__(self, address: str) -> None:
        self.address = address
        self._server: SyncServer | None = None

    def setup(self, ctx: Context) -> None:
        """Read the hosted session off ctx and start accepting."""
        root = ctx.get(HostedSession)
        config = ConnectionConfig(attrs=AttributeAccessConfig(allow_all_attrs=True))
        server = SyncServer(
            listener_factory=TCPListener,
            framing_factory=_framing,
            # Thread per client, because a page runs as many workers as it
            # has sections and each one holds a connection open.
            executor=ThreadedExecutor(),
        )

        def handle(netkit_conn: object) -> None:
            dispatcher = AsyncDispatcher()
            conn = InvisiblesConnection(netkit_conn, Protocol(config, root, dispatcher=dispatcher))
            try:
                while netkit_conn.is_connected():
                    conn._serve_one(timeout=1.0)
            finally:
                dispatcher.shutdown()

        server.set_handler(handle)
        self._server = server
        host, _, port = self.address.rpartition(":")
        threading.Thread(
            target=lambda: server.start(host or "127.0.0.1", int(port)),
            daemon=True,
            name="nuspace-session-server",
        ).start()

    def cleanup(self) -> None:
        """Stop accepting. The daemon thread exits when ``start`` returns."""
        if self._server is not None:
            self._server.stop(wait=False)
            self._server = None

    async def asetup(self, ctx: Context) -> None:
        """Async shim: setup is sync work."""
        self.setup(ctx)

    async def acleanup(self) -> None:
        """Async shim: cleanup is sync work."""
        self.cleanup()


def served_session(address: str) -> nu.Provide:
    """This connection's Session, on a socket, for its sections to write through."""
    return nu.Provide(SessionServer, {"address": address})
