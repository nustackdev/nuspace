"""NuspaceSession -- Session over a FastAPI websocket.

Bound on Context for the lifetime of one ws connection. Owns the ws,
the observer registry, and the pending-read futures. Interactions build
Frames and call ``send``; the session does no per-op work.

Concrete implementation of ``nu.ui.core.session.Session`` -- the abstract
transport nu.ui refs target. Nuspace's own host, mirroring nudle's
session shape so the reactive plumbing behaves the same on both.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from nu.ui.core.protocol import (
    OP_ERROR,
    OP_MOUNT,
    OP_NOTIFY,
    OP_READ,
    OP_UNMOUNT,
    Frame,
    decode,
    encode,
)
from nu.ui.core.session import Session


if TYPE_CHECKING:
    from fastapi import WebSocket


__all__ = ["NuspaceSession", "Subscription"]


Callback = Callable[[object], None]


class Subscription:
    """Observer handle returned by ``session.subscribe(path)``."""

    def __init__(self, session: NuspaceSession, path: str) -> None:
        self._session = session
        self._path = path
        # A list, and compared by identity throughout. A callback here is
        # usually a reverse proxy into a worker, and hashing one is a round
        # trip over the wire -- which raises once that worker is gone, so a
        # set could not even drop a dead entry.
        self._callbacks: list[Callback] = []
        self._closed = False

    def bind(self, cb: Callback) -> None:
        """Register ``cb`` to fire on inbound notify frames for this path."""
        if self._closed:
            return
        if not any(cb is bound for bound in self._callbacks):
            self._callbacks.append(cb)

    def unbind(self, cb: Callback) -> None:
        """Drop a previously bound callback (idempotent)."""
        self._callbacks = [bound for bound in self._callbacks if bound is not cb]

    def close(self) -> None:
        """Detach from the session; further ``bind`` calls no-op."""
        if self._closed:
            return
        self._closed = True
        self._callbacks = []
        subs = self._session._subs.get(self._path)
        if subs is not None:
            subs.discard(self)
            if not subs:
                self._session._subs.pop(self._path, None)

    def _fire(self, payload: object) -> None:
        """Hand the payload to every bound callback, dropping the dead ones.

        A callback here is usually a reverse proxy into a pool worker, and a
        page restarting kills the worker without giving it a chance to unbind.
        So a raise means the far end is gone: drop that callback and carry on,
        rather than letting one stale subscriber take the whole ws down.
        """
        dead: list[Callback] = []
        for cb in tuple(self._callbacks):
            try:
                cb(payload)
            except Exception:  # the far end is a dead process
                dead.append(cb)
        if dead:
            self._callbacks = [cb for cb in self._callbacks if not any(cb is gone for gone in dead)]


class NuspaceSession(Session):
    """One ws connection, one mounted page."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws
        self._subs: dict[str, set[Subscription]] = defaultdict(set)
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._stopped = False

    # ---- outbound -----------------------------------------------------------

    async def send(self, frame: Frame) -> None:
        """Encode and ship one Frame on the ws."""
        await self._ws.send_bytes(encode(frame))

    async def mount(
        self,
        name: str,
        fields: list[dict[str, object]],
        pages: list[dict[str, object]] | None = None,
        *,
        sidebar: bool = False,
    ) -> None:
        """Ship a mount frame naming the page and its field list."""
        payload: dict[str, object] = {"name": name, "fields": fields}
        if pages is not None:
            payload["pages"] = pages
        if sidebar:
            payload["sidebar"] = True
        await self.send(Frame(OP_MOUNT, ref="", payload=payload))

    async def aread(self, path: str) -> Any:  # noqa: ANN401 -- payload is opaque
        """Round-trip read: ship a read frame, await the client's reply."""
        rid = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[rid] = fut
        try:
            await self.send(Frame(OP_READ, ref=path, payload=None, id=rid))
            return await fut
        finally:
            self._pending.pop(rid, None)

    def subscribe(self, path: str) -> Subscription:
        """Return a Subscription observing notify frames for ``path``."""
        sub = Subscription(self, path)
        self._subs[path].add(sub)
        return sub

    # ---- intake -------------------------------------------------------------

    async def run_intake(self) -> None:
        """Drive the ws read loop, dispatch client->server frames."""
        from fastapi import WebSocketDisconnect

        try:
            while not self._stopped:
                raw = await self._ws.receive_bytes()
                frame = decode(raw)
                self._dispatch(frame)
        except WebSocketDisconnect:
            pass
        finally:
            self._stopped = True
            self._fail_pending()

    def _dispatch(self, frame: Frame) -> None:
        if frame.op == OP_NOTIFY:
            for sub in tuple(self._subs.get(frame.ref, ())):
                sub._fire(frame.payload)
            return
        if frame.op == OP_READ and frame.id is not None:
            fut = self._pending.get(frame.id)
            if fut is not None and not fut.done():
                fut.set_result(frame.payload)
            return
        if frame.op in (OP_MOUNT, OP_UNMOUNT, OP_ERROR):
            return

    def _fail_pending(self) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(ConnectionError("nuspace session closed"))
        self._pending.clear()
