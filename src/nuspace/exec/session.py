"""``WorkerSession`` -- the nu.ui Session a worker binds on its Context.

``nu.ui.core.Session`` is three methods (``send`` / ``aread`` /
``subscribe``) and every use site is ``rt.ctx.get(Session)``, so putting
a section in another process costs exactly one implementation of this
class. Frames go up the worker channel; the supervisor routes them to
whatever host owns the browser connection, and browser notifies come
back down the same pipe.

Subscriptions are worker-local. Each worker owns its own session, so
process death *is* subscription teardown -- the per-section handle
registry that a single shared session would need does not exist here.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from nu.ui.core.session import Session

from .protocol import (
    MSG_READ,
    MSG_SEND,
    MSG_SUBSCRIBE,
    MSG_UNSUBSCRIBE,
)


if TYPE_CHECKING:
    from nu.ui.core.protocol import Frame

    from .protocol import Channel


__all__ = ["WorkerSession", "WorkerSubscription"]


Callback = Callable[[object], None]


class WorkerSubscription:
    """Observer handle for one path inside one worker."""

    def __init__(self, session: WorkerSession, path: str) -> None:
        self._session = session
        self._path = path
        self._callbacks: set[Callback] = set()
        self._closed = False

    def bind(self, cb: Callback) -> None:
        """Register ``cb`` for inbound notifies on this path."""
        if not self._closed:
            self._callbacks.add(cb)

    def unbind(self, cb: Callback) -> None:
        """Drop a callback (idempotent)."""
        self._callbacks.discard(cb)

    def close(self) -> None:
        """Detach from the session and tell the supervisor to stop routing."""
        if self._closed:
            return
        self._closed = True
        self._callbacks.clear()
        self._session._drop(self)

    def _fire(self, payload: object) -> None:
        for cb in tuple(self._callbacks):
            cb(payload)


class WorkerSession(Session):
    """Session over the worker's IPC channel."""

    def __init__(self, channel: Channel) -> None:
        self._channel = channel
        self._subs: dict[str, set[WorkerSubscription]] = defaultdict(set)
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._closed = False

    # -- Session ------------------------------------------------------------

    async def send(self, frame: Frame) -> None:
        """Ship one Frame up to the supervisor."""
        await self._channel.send({"t": MSG_SEND, "frame": frame.to_dict()})

    async def aread(self, path: str) -> Any:  # noqa: ANN401 -- payload is opaque
        """Round-trip a read through the supervisor to the browser."""
        rid = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[rid] = fut
        try:
            await self._channel.send({"t": MSG_READ, "id": rid, "path": path})
            return await fut
        finally:
            self._pending.pop(rid, None)

    def subscribe(self, path: str) -> WorkerSubscription:
        """Register interest in notifies for ``path``."""
        sub = WorkerSubscription(self, path)
        first = not self._subs[path]
        self._subs[path].add(sub)
        if first:
            self._announce(MSG_SUBSCRIBE, path)
        return sub

    # -- Inbound ------------------------------------------------------------

    def on_notify(self, path: str, payload: object) -> None:
        """Fire every callback bound to ``path``."""
        for sub in tuple(self._subs.get(path, ())):
            sub._fire(payload)

    def on_read_reply(self, rid: str, payload: Any, error: str | None = None) -> None:  # noqa: ANN401
        """Resolve a pending ``aread``."""
        fut = self._pending.get(rid)
        if fut is None or fut.done():
            return
        if error is not None:
            fut.set_exception(ConnectionError(error))
        else:
            fut.set_result(payload)

    def close(self) -> None:
        """Fail every pending read; the worker is going away."""
        if self._closed:
            return
        self._closed = True
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(ConnectionError("worker session closed"))
        self._pending.clear()
        self._subs.clear()

    # -- internals ----------------------------------------------------------

    def _drop(self, sub: WorkerSubscription) -> None:
        subs = self._subs.get(sub._path)
        if subs is None:
            return
        subs.discard(sub)
        if not subs:
            self._subs.pop(sub._path, None)
            self._announce(MSG_UNSUBSCRIBE, sub._path)

    def _announce(self, kind: str, path: str) -> None:
        """Tell the supervisor about a routing change, fire and forget.

        ``subscribe`` is sync (the ABC says so) so this cannot await.
        """
        if self._closed:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._channel.send({"t": kind, "path": path}))  # noqa: RUF006
