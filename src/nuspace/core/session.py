"""One connection's ``nu.ui`` Session, reachable from another process.

A section runs in a pool worker and every ``nu.ui`` Ref it builds asks the
context for a ``Session``. The Session is the websocket, so it cannot be
copied into the worker; it is served over invisibles instead, exactly the way
:func:`~nuspace.core.host.served_navigator` serves the store.

Two things stand between the raw session and the wire, and both of them are
here:

- :class:`HostedSession`, because the invisibles async dispatcher runs a loop
  of its own and the websocket belongs to the connection's.
- :class:`FrameCodec`, because invisibles boxes an unknown class by reference
  and a ``Frame`` is meant to travel by value.

The server itself is plain ``nu.proxy.InvisiblesServer``. It builds a
dispatcher per connection and drops it on close, which is what a page needs:
a section restarting closes a client every few seconds and must not take the
other clients' loops with it.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from invisibles.core.boxing import register_value_type, unregister_value_type

import nu
import nu.proxy
from nu.ui.core.protocol import Frame
from nu.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Coroutine

    from nu.lang.runtime import Context
    from nu.ui.core.session import Subscription


__all__ = ["FrameCodec", "HostedSession", "served_session"]


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

    async def aread(self, path: tuple[str, ...]) -> Any:  # noqa: ANN401 -- payload is opaque
        """Round-trip read, on the loop that owns the pending futures."""
        return await self._relay(self._session.aread(path))

    def subscribe(self, path: tuple[str, ...]) -> Subscription:
        """Observe notify frames for ``path``.

        The handle comes back to the worker as a proxy, and the callback the
        worker binds on it goes the other way as a reverse proxy, which is
        what carries a browser edit into the process running the section.
        """
        return self._session.subscribe(path)


class FrameCodec:
    """Frames by value on the invisibles wire, for as long as the bracket holds.

    A ``Frame`` is plain data -- a path, a payload, and the chain of types and
    props the write walks down -- but invisibles boxes any class it has not
    been told about by reference: the worker would hand the server a proxy and
    ``encode`` would try to msgpack a netref. Registering the type makes it
    pickle across instead, chain and all, which is what lets a section running
    in a worker create the node it writes to.
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


def served_session(address: str) -> nu.Provide:
    """This connection's Session, on a socket, for its sections to write through.

    Threaded executor because a page holds a connection open per worker, and
    the async dispatcher because ``send`` and ``aread`` are coroutines and want
    a loop to run on.
    """
    return nu.Provide(
        nu.proxy.InvisiblesServer,
        {
            "target": HostedSession,
            "address": address,
            "transport": "tcp",
            "executor": "threaded",
            "dispatcher": "async",
        },
    )
