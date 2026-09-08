"""Wire protocol between the supervisor and a section worker.

One duplex ``AF_UNIX`` socketpair per worker, length-prefixed msgpack in
both directions. Four bytes big-endian length, then the packed dict.

Everything that crosses is plain data. **A compiled Nu tree never
crosses.** The worker that compiles a section is the worker that runs
it, so the only things travelling back up are mount fields (dicts),
status transitions, and ui frames.

Message kinds, supervisor -> worker::

    {"t": "run",     "section_id", "prefix", "source", "store": {...}}
    {"t": "start"}                                 compile is shipped, go
    {"t": "stop"}                                  graceful stop request
    {"t": "notify",  "path", "payload"}            browser -> section
    {"t": "read_ok", "id", "payload"}              reply to a worker read
    {"t": "read_err","id", "error"}

Worker -> supervisor::

    {"t": "ready"}                                 warm, awaiting a run
    {"t": "compiled",  "fields": [MountField]}
    {"t": "invalid",   "error"}                    source never compiled
    {"t": "running",   "started_at"}
    {"t": "stopped"}                               tree finished / stopped
    {"t": "failed",    "error"}                    tree raised
    {"t": "send",      "frame": {...}}             ui frame outbound
    {"t": "read",      "id", "path"}               ui round-trip read
    {"t": "subscribe", "path"}                     routing hint
    {"t": "unsubscribe", "path"}

``invalid`` and ``failed`` stay distinct on purpose: one never ran, one
ran and died.
"""

from __future__ import annotations

import asyncio
import socket
import struct
from typing import TYPE_CHECKING, Any

import msgpack


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = [
    "MSG_COMPILED",
    "MSG_FAILED",
    "MSG_INVALID",
    "MSG_NOTIFY",
    "MSG_READ",
    "MSG_READY",
    "MSG_READ_ERR",
    "MSG_READ_OK",
    "MSG_RUN",
    "MSG_RUNNING",
    "MSG_SEND",
    "MSG_START",
    "MSG_STOP",
    "MSG_STOPPED",
    "MSG_SUBSCRIBE",
    "MSG_UNSUBSCRIBE",
    "Channel",
    "connect_channel",
]


MSG_RUN = "run"
MSG_START = "start"
MSG_STOP = "stop"
MSG_NOTIFY = "notify"
MSG_READ_OK = "read_ok"
MSG_READ_ERR = "read_err"

MSG_READY = "ready"
MSG_COMPILED = "compiled"
MSG_INVALID = "invalid"
MSG_RUNNING = "running"
MSG_STOPPED = "stopped"
MSG_FAILED = "failed"
MSG_SEND = "send"
MSG_READ = "read"
MSG_SUBSCRIBE = "subscribe"
MSG_UNSUBSCRIBE = "unsubscribe"


_HEADER = struct.Struct("!I")
_MAX_FRAME = 64 * 1024 * 1024


class Channel:
    """Length-prefixed msgpack duplex over an asyncio stream pair.

    Both ends of the socketpair use this. ``recv`` returns ``None`` at
    EOF, which is how each side notices the other one died.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._send_lock = asyncio.Lock()
        self._closed = False

    async def send(self, msg: Mapping[str, Any]) -> None:
        """Pack and ship one message. Silent no-op once the pipe is gone."""
        if self._closed:
            return
        body = msgpack.packb(dict(msg), use_bin_type=True, default=_fallback)
        async with self._send_lock:
            try:
                self._writer.write(_HEADER.pack(len(body)) + body)
                await self._writer.drain()
            except (ConnectionError, BrokenPipeError, RuntimeError):
                self._closed = True

    async def recv(self) -> dict[str, Any] | None:
        """Read one message, or ``None`` when the peer is gone."""
        try:
            header = await self._reader.readexactly(_HEADER.size)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None
        (size,) = _HEADER.unpack(header)
        if size > _MAX_FRAME:
            return None
        try:
            body = await self._reader.readexactly(size)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None
        decoded = msgpack.unpackb(body, raw=False)
        return decoded if isinstance(decoded, dict) else None

    async def aclose(self) -> None:
        """Close the writer half; idempotent."""
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except (ConnectionError, RuntimeError, OSError):
            pass


def _fallback(obj: object) -> object:
    """Msgpack default hook: anything exotic degrades to its repr."""
    return repr(obj)


async def connect_channel(sock: socket.socket) -> Channel:
    """Wrap an already-connected socket in a :class:`Channel`."""
    reader, writer = await asyncio.open_connection(sock=sock)
    return Channel(reader, writer)


def socketpair() -> tuple[socket.socket, socket.socket]:
    """A duplex ``AF_UNIX`` pair: (supervisor end, worker end)."""
    return socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
