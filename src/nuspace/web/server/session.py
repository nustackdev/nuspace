"""NuspaceSession -- Session implementation over a FastAPI websocket.

Near-copy of ``nu.ui.nudle.session.NudleSession``; only difference is
``mount(payload)`` which ships the payload opaquely (nuspace has its own
MOUNT shape: ``pages`` / ``active_page.blocks[]``).
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
        self._callbacks: set[Callback] = set()
        self._closed = False

    def bind(self, cb: Callback) -> None:
        if self._closed:
            return
        self._callbacks.add(cb)

    def unbind(self, cb: Callback) -> None:
        self._callbacks.discard(cb)

    def close(self) -> None:
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
    """One ws connection, one mounted space."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws
        self._subs: dict[str, set[Subscription]] = defaultdict(set)
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._stopped = False

    async def send(self, frame: Frame) -> None:
        await self._ws.send_bytes(encode(frame))

    async def mount(self, payload: dict) -> None:
        """Ship a MOUNT frame with an opaque payload."""
        await self.send(Frame(OP_MOUNT, ref="", payload=payload))

    async def aread(self, path: str) -> Any:
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
        sub = Subscription(self, path)
        self._subs[path].add(sub)
        return sub

    async def run_intake(self) -> None:
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
