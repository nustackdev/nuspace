"""One browser connection, and how a worker reaches it.

A cell never runs in the host, so a cell that draws is always across a
process boundary. The two ends talk over a frame pipe: one TCP stream per
worker process, length-prefixed msgpack messages, every live connection
multiplexed over it by sid.

- **worker side**: :func:`piped_session` binds a :class:`PipeSession` for
  connection ``sid``, a local :class:`Session` whose every call is a message
  on the worker's one pipe. This module imports no web server at module
  scope: a worker unpickling a body would otherwise load uvicorn and fastapi
  for a server it never runs.
- **host side**: :func:`served_sessions` puts :class:`SessionPipe` on one
  socket, a router on the host's loop between the pipe and the ws server's
  book of connections.

**Why a pipe and not a proxy.** Both ends are asyncio loops, and the host's
is the one every browser socket lives on. A proxy is a blocking call: a
browser edit firing a reverse proxy into the worker blocked the host loop,
and the worker drawing in answer needed that same loop, so the host hung.
Here nothing blocks and nothing calls back: the host only reads and writes
messages, the worker owns its subscriptions, and a notify is one message.

Messages, each a msgpack array whose first item is the kind:

- worker -> host: ``open(rid, sid)``, ``send(sid, frame)``,
  ``read(rid, sid, path)``, ``sub(id, sid, path)``, ``unsub(id)``
- host -> worker: ``reply(rid, ok, value)``, ``notify(id, payload)``

``frame`` is a frame already encoded the way the browser reads it.
"""

from __future__ import annotations

import asyncio
import itertools
import struct
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, ClassVar

import msgpack

import nu
from nu.core.spans.bracket import _LifecycleBracket
from nustd.ui.core.protocol import decode, encode
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nu.lang.runtime import Context
    from nustd.ui.core.protocol import Frame
    from nustd.ui.core.session import Subscription
    from nustd.ws_server import WebServer


__all__ = [
    "ConnectedSession",
    "PipeSession",
    "SessionPipe",
    "piped_session",
    "served_sessions",
]


_OPEN = "open"
_SEND = "send"
_READ = "read"
_SUB = "sub"
_UNSUB = "unsub"
_REPLY = "reply"
_NOTIFY = "notify"

_HEADER = struct.Struct("!I")
_MAX_MESSAGE = 16 * 1024 * 1024


def _split(address: str) -> tuple[str, int]:
    host, _, port = address.rpartition(":")
    return host or "127.0.0.1", int(port)


def _pack(message: list[Any]) -> bytes:
    body = msgpack.packb(message, use_bin_type=True)
    return _HEADER.pack(len(body)) + body


async def _receive(reader: asyncio.StreamReader) -> list[Any]:
    """The next message, or ``IncompleteReadError`` once the stream ends."""
    (size,) = _HEADER.unpack(await reader.readexactly(_HEADER.size))
    if size > _MAX_MESSAGE:
        msg = f"pipe message of {size} bytes is over the {_MAX_MESSAGE} limit"
        raise ConnectionError(msg)
    return msgpack.unpackb(await reader.readexactly(size), raw=False)


# --- Worker side -----------------------------------------------------------------


class _Pipe:
    """The worker's one stream to the host, shared by every run drawing on it.

    Per process and loop, and counted: the first run in opens it, the last
    one out closes it. Replies are matched by request id, notifies by
    subscription id; both are read on the loop by one reader task.
    """

    _open: ClassVar[dict[tuple[str, asyncio.AbstractEventLoop], _Pipe]] = {}
    _opening: ClassVar[dict[tuple[str, asyncio.AbstractEventLoop], asyncio.Lock]] = {}

    def __init__(self, key: tuple[str, asyncio.AbstractEventLoop]) -> None:
        self._key = key
        self._held = 0
        self._ids = itertools.count(1)
        self._replies: dict[int, asyncio.Future[Any]] = {}
        self._subs: dict[int, PipeSubscription] = {}
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None
        self._closed = False

    @classmethod
    async def acquire(cls, address: str) -> _Pipe:
        """The pipe to ``address`` for this loop, opened on first use."""
        key = (address, asyncio.get_running_loop())
        lock = cls._opening.setdefault(key, asyncio.Lock())
        async with lock:
            pipe = cls._open.get(key)
            if pipe is None or pipe._closed:
                pipe = cls(key)
                await pipe._connect(address)
                cls._open[key] = pipe
            pipe._held += 1
            return pipe

    async def release(self) -> None:
        """Let go of the pipe; the last holder closes it."""
        self._held -= 1
        if self._held > 0:
            return
        if _Pipe._open.get(self._key) is self:
            del _Pipe._open[self._key]
        await self._close()

    async def _connect(self, address: str) -> None:
        host, port = _split(address)
        reader, self._writer = await asyncio.open_connection(host, port)
        self._task = asyncio.get_running_loop().create_task(self._read_loop(reader))

    async def _close(self) -> None:
        self._shut(ConnectionError("session pipe closed"))
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._task
        if self._writer is not None:
            self._writer.close()
            with suppress(Exception):
                await self._writer.wait_closed()

    def _shut(self, error: Exception) -> None:
        self._closed = True
        for fut in self._replies.values():
            if not fut.done():
                fut.set_exception(error)
        self._replies.clear()
        self._subs.clear()

    # ---- outbound -----------------------------------------------------------

    def post(self, message: list[Any]) -> asyncio.StreamWriter:
        """Queue one message on the stream. Never waits."""
        writer = self._writer
        if self._closed or writer is None or writer.is_closing():
            msg = "session pipe closed"
            raise ConnectionError(msg)
        writer.write(_pack(message))
        return writer

    async def apost(self, message: list[Any]) -> None:
        """Queue one message and wait for the stream to drain."""
        await self.post(message).drain()

    async def request(self, kind: str, *args: Any) -> Any:  # noqa: ANN401 -- the host's answer
        """Send ``kind(rid, *args)`` and wait for its reply."""
        rid = next(self._ids)
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._replies[rid] = fut
        try:
            await self.apost([kind, rid, *args])
            return await fut
        finally:
            self._replies.pop(rid, None)

    def subscribe(self, sid: str, path: tuple[str, ...]) -> PipeSubscription:
        """Ask the host for ``path``'s notifies on ``sid``."""
        sub = PipeSubscription(self, next(self._ids))
        self._subs[sub.id] = sub
        self.post([_SUB, sub.id, sid, list(path)])
        return sub

    def unsubscribe(self, sub: PipeSubscription) -> None:
        if self._subs.pop(sub.id, None) is None:
            return
        with suppress(ConnectionError):
            self.post([_UNSUB, sub.id])

    # ---- inbound ------------------------------------------------------------

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        error: Exception = ConnectionError("session pipe closed by the host")
        try:
            while True:
                message = await _receive(reader)
                kind = message[0]
                if kind == _NOTIFY:
                    sub = self._subs.get(message[1])
                    if sub is not None:
                        sub._fire(message[2])
                elif kind == _REPLY:
                    fut = self._replies.get(message[1])
                    if fut is not None and not fut.done():
                        if message[2]:
                            fut.set_result(message[3])
                        else:
                            fut.set_exception(ConnectionError(message[3]))
        except (asyncio.IncompleteReadError, ConnectionError, OSError) as exc:
            error = ConnectionError(f"session pipe lost: {exc}")
        finally:
            self._shut(error)


class PipeSubscription:
    """A subscription living in the worker; the host only forwards its notifies.

    Callbacks are held in a list and matched by identity, and one that raises
    is dropped, the same contract as the host's own subscription.
    """

    def __init__(self, pipe: _Pipe, sub_id: int) -> None:
        self.id = sub_id
        self._pipe = pipe
        self._callbacks: list[Callable[[object], None]] = []
        self._closed = False

    def bind(self, cb: Callable[[object], None]) -> None:
        """Register ``cb`` to fire on every notify for this path."""
        if self._closed:
            return
        if not any(cb is bound for bound in self._callbacks):
            self._callbacks.append(cb)

    def unbind(self, cb: Callable[[object], None]) -> None:
        """Drop a previously bound callback (idempotent)."""
        self._callbacks = [bound for bound in self._callbacks if bound is not cb]

    def close(self) -> None:
        """Stop the host forwarding; further ``bind`` calls no-op."""
        if self._closed:
            return
        self._closed = True
        self._callbacks = []
        self._pipe.unsubscribe(self)

    def _fire(self, payload: object) -> None:
        dead: list[Callable[[object], None]] = []
        for cb in tuple(self._callbacks):
            try:
                cb(payload)
            except Exception:
                dead.append(cb)
        if dead:
            self._callbacks = [cb for cb in self._callbacks if not any(cb is gone for gone in dead)]


class PipeSession(Session):
    """Connection ``sid``, reached over the worker's pipe to the host."""

    def __init__(self, pipe: _Pipe, sid: str) -> None:
        self._pipe = pipe
        self._sid = sid

    async def send(self, frame: Frame) -> None:
        """Ship one frame. Lands on the socket in the order it was sent."""
        await self._pipe.apost([_SEND, self._sid, encode(frame)])

    async def aread(self, path: tuple[str, ...]) -> Any:  # noqa: ANN401 -- the browser's blob
        """Round trip read through the host to the browser."""
        return await self._pipe.request(_READ, self._sid, list(path))

    def subscribe(self, path: tuple[str, ...]) -> Subscription:
        """Observe notify frames for ``path``."""
        return self._pipe.subscribe(self._sid, tuple(path))


class ConnectedSession(_LifecycleBracket):
    """Bind connection ``sid`` as the session, over the pipe at ``address``.

    Opening asks the host whether the connection is live, so a run for a tab
    that closed between dispatch and now fails here rather than drawing into
    nothing.

    Args:
        address: ``host:port`` where :func:`served_sessions` listens.
        sid: The connection id, fixed when the run's env is built.
    """

    def __init__(self, address: str, sid: str) -> None:
        super().__init__()
        self._payload["address"] = address
        self._payload["sid"] = sid

    @asynccontextmanager
    async def _aopen(self, ctx: Context) -> AsyncIterator[None]:
        sid = self._payload["sid"]
        pipe = await _Pipe.acquire(self._payload["address"])
        try:
            if not await pipe.request(_OPEN, sid):
                msg = f"No live connection for {sid!r}"
                raise LookupError(msg)
            with ctx.fabrics.bind(Session, PipeSession(pipe, sid)):
                yield
        finally:
            await pipe.release()


def piped_session(address: str, sid: str, body: nu.Nu) -> nu.With:
    """``body`` with connection ``sid`` bound as the session it draws on.

    Args:
        address: ``host:port`` where :func:`served_sessions` listens.
        sid: The connection id.
        body: What runs with the connection bound. Pickled into the worker.
    """
    return nu.With(ConnectedSession(address, sid), body=body)


# --- Host side -------------------------------------------------------------------


class _Worker:
    """One worker's stream, as the host sees it: its subscriptions by id."""

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self.writer = writer
        self.subs: dict[int, tuple[Subscription, Callable[[object], None]]] = {}

    def post(self, message: list[Any]) -> None:
        """Queue one message to the worker. Never waits, never blocks the loop."""
        if self.writer.is_closing():
            msg = "worker pipe closed"
            raise ConnectionError(msg)
        self.writer.write(_pack(message))

    def drop(self) -> None:
        for sub, cb in self.subs.values():
            sub.unbind(cb)
            sub.close()
        self.subs.clear()


class SessionPipe:
    """The host end: routes every worker's messages to the ws server's book.

    Runs on the loop the browser sockets live on and only ever reads and
    writes messages there, so a worker can never hold that loop up.

    Args:
        address: ``host:port`` to listen on.
    """

    def __init__(self, address: str) -> None:
        self.address = address
        self._web: WebServer | None = None
        self._server: asyncio.Server | None = None
        self._workers: set[asyncio.Task[None]] = set()

    async def asetup(self, ctx: Context) -> None:
        """Take the server's book and start listening."""
        # Here, not at the top: see the module docstring. The process running
        # this is the one that called ``listen``, so it is loaded already.
        from nustd.ws_server import WebServer

        self._web = ctx.fabrics.get(WebServer)
        host, port = _split(self.address)
        self._server = await asyncio.start_server(self._serve, host, port)

    async def acleanup(self) -> None:
        """Stop listening and drop every worker's stream."""
        if self._server is not None:
            self._server.close()
            self._server = None
        for task in tuple(self._workers):
            task.cancel()
        for task in tuple(self._workers):
            with suppress(asyncio.CancelledError, Exception):
                await task

    def _session(self, sid: str) -> Session | None:
        return None if self._web is None else self._web.session(sid)

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._workers.add(task)
        worker = _Worker(writer)
        try:
            while True:
                await self._handle(worker, await _receive(reader))
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass  # the worker went away
        finally:
            if task is not None:
                self._workers.discard(task)
            worker.drop()
            writer.close()

    async def _handle(self, worker: _Worker, message: list[Any]) -> None:
        kind = message[0]
        if kind == _SEND:
            # Awaited in line: frames from one worker reach the socket in the
            # order they were sent, and a slow tab slows only its writers.
            session = self._session(message[1])
            if session is not None:
                with suppress(Exception):  # the tab closed mid write
                    await session.send(decode(message[2]))
        elif kind == _SUB:
            self._subscribe(worker, message[1], message[2], tuple(message[3]))
        elif kind == _UNSUB:
            entry = worker.subs.pop(message[1], None)
            if entry is not None:
                sub, cb = entry
                sub.unbind(cb)
                sub.close()
        elif kind == _READ:
            # Its own task: a read waits on the browser, and the stream does
            # not stop for it.
            asyncio.get_running_loop().create_task(
                self._read(worker, message[1], message[2], tuple(message[3]))
            )
        elif kind == _OPEN:
            with suppress(ConnectionError):
                worker.post([_REPLY, message[1], True, self._session(message[2]) is not None])

    def _subscribe(self, worker: _Worker, sub_id: int, sid: str, path: tuple[str, ...]) -> None:
        session = self._session(sid)
        if session is None:
            return  # the tab is gone; nothing will ever notify
        sub = session.subscribe(path)

        def forward(payload: object) -> None:
            worker.post([_NOTIFY, sub_id, payload])

        sub.bind(forward)
        worker.subs[sub_id] = (sub, forward)

    async def _read(self, worker: _Worker, rid: int, sid: str, path: tuple[str, ...]) -> None:
        session = self._session(sid)
        if session is None:
            reply = [_REPLY, rid, False, f"No live connection for {sid!r}"]
        else:
            try:
                reply = [_REPLY, rid, True, await session.aread(path)]
            except Exception as exc:
                reply = [_REPLY, rid, False, f"{type(exc).__name__}: {exc}"]
        with suppress(ConnectionError):
            worker.post(reply)


def served_sessions(address: str) -> nu.With:
    """Every live connection on one socket, so a worker can draw on one.

    Goes inside the server bracket: the book it reads is the server's.

    Args:
        address: ``host:port`` to listen on.
    """
    return nu.With(nu.Provide(SessionPipe, {"address": address}))
