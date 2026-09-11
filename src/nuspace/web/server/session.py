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
import logging
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

log = logging.getLogger("nuspace.server")


class Subscription:
    """Observer handle returned by ``session.subscribe(path)``."""

    def __init__(self, session: NuspaceSession, path: str) -> None:
        self._session = session
        self._path = path
        self._callbacks: set[Callback] = set()
        self._closed = False

    def bind(self, cb: Callback) -> None:
        """Register ``cb`` to fire on inbound notify frames for this path."""
        if self._closed:
            return
        self._callbacks.add(cb)

    def unbind(self, cb: Callback) -> None:
        """Drop a previously bound callback (idempotent)."""
        self._callbacks.discard(cb)

    def close(self) -> None:
        """Detach from the session; further ``bind`` calls no-op."""
        if self._closed:
            return
        self._closed = True
        self._callbacks.clear()
        subs = self._session._subs.get(self._path)
        if subs is not None:
            subs.discard(self)
            if not subs:
                self._session._subs.pop(self._path, None)

    def _fire(self, payload: object) -> None:
        for cb in tuple(self._callbacks):
            cb(payload)


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
            subs = tuple(self._subs.get(frame.ref, ()))
            if not subs:
                # Routing is unchanged: nobody subscribed, nothing runs.
                # But a notify to `<surface>.ops.typpo` used to vanish
                # without a trace, and a mistyped op path is the one bug
                # the one-ref-per-op dispatch cannot catch for you.
                log.warning("notify to %r matched no subscription", frame.ref)
            for sub in subs:
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
