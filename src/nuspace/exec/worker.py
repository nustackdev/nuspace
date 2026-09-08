"""Section worker. One process, one section, one Nu tree.

Boots, does the expensive imports, reports ``ready``, and parks on its
channel. That parked state is what the warm pool holds, so opening a
page costs a message round trip and not an interpreter start.

When a ``run`` arrives it compiles the source **here** -- arbitrary user
python never runs in the server -- reports mount fields, binds a
:class:`~nuspace.exec.session.WorkerSession` on a fresh Context, and
drives the tree with ``nu.arun``.

The process is single-use. Once it has run user code it is never handed
back to the pool: user code can leave threads, signal handlers, open
handles and imported C state behind, and the only honest way to reclaim
that is to let the process die.

Exit is ``os._exit`` on purpose. A section that spawned a non-daemon
thread would otherwise hang interpreter shutdown, and the whole point of
being a process is that teardown is bounded.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import socket
import sys
import time
import traceback
from typing import TYPE_CHECKING, Any

import nu
import nu.ui
from nu.lang.runtime import Context
from nu.ui.core import Session

from .compile import SectionCompileError, compile_section
from .protocol import (
    MSG_COMPILED,
    MSG_FAILED,
    MSG_INVALID,
    MSG_NOTIFY,
    MSG_READ_ERR,
    MSG_READ_OK,
    MSG_READY,
    MSG_RUN,
    MSG_RUNNING,
    MSG_START,
    MSG_STOP,
    MSG_STOPPED,
    connect_channel,
)
from .session import WorkerSession


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nu.lang import Nu

    from .protocol import Channel


__all__ = ["main"]


# How long the worker gives its own tree to unwind after a graceful stop
# before it stops caring and exits anyway. The supervisor's ladder is the
# real guarantee; this just makes the common case clean.
SELF_CANCEL_GRACE = 0.25


def main(argv: list[str] | None = None) -> None:
    """Entry point: ``python -m nuspace.exec.worker --fd N``."""
    parser = argparse.ArgumentParser(prog="nuspace-section-worker")
    parser.add_argument("--fd", type=int, required=True)
    args = parser.parse_args(argv)
    sock = socket.socket(fileno=args.fd)
    try:
        asyncio.run(_amain(sock))
    except (KeyboardInterrupt, ConnectionError):
        pass
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
    os._exit(0)


async def _amain(sock: socket.socket) -> None:
    channel = await connect_channel(sock)
    await channel.send({"t": MSG_READY})
    msg = await channel.recv()
    if msg is None or msg.get("t") != MSG_RUN:
        return
    await _run_section(channel, msg)


async def _run_section(channel: Channel, msg: Mapping[str, Any]) -> None:
    """Compile, then drive, one section."""
    prefix = str(msg.get("prefix") or f"sections.{msg.get('section_id')}")
    source = str(msg.get("source") or "")
    store = msg.get("store") if isinstance(msg.get("store"), dict) else {}

    session = WorkerSession(channel)
    stop = asyncio.Event()
    start = asyncio.Event()
    inbox = asyncio.create_task(_inbound(channel, session, stop, start))

    try:
        term, fields = compile_section(source, prefix)
    except SectionCompileError as exc:
        await channel.send({"t": MSG_INVALID, "error": exc.diagnostic()})
        return
    except BaseException as exc:
        await channel.send({"t": MSG_INVALID, "error": f"{type(exc).__name__}: {exc}"})
        return
    await channel.send({"t": MSG_COMPILED, "fields": fields})

    # Park between compile and run. The supervisor ships mount fields to
    # the browser first, so a section can never write to a slice the
    # browser has not registered yet.
    if not start.is_set():
        waiters = (asyncio.create_task(start.wait()), asyncio.create_task(stop.wait()))
        await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        for waiter in waiters:
            waiter.cancel()
    if stop.is_set() or not start.is_set():
        await channel.send({"t": MSG_STOPPED})
        return

    ctx = Context().bind(Session, session)
    program = _wrap(term, store)
    await channel.send({"t": MSG_RUNNING, "started_at": time.time()})

    run = asyncio.create_task(nu.arun(program, ctx))  # type: ignore[arg-type]
    halt = asyncio.create_task(stop.wait())
    done, _ = await asyncio.wait({run, halt}, return_when=asyncio.FIRST_COMPLETED)
    halt.cancel()

    if run in done:
        exc = run.exception()
        if exc is None:
            await channel.send({"t": MSG_STOPPED})
        else:
            await channel.send({"t": MSG_FAILED, "error": _format_error(exc, prefix)})
    else:
        run.cancel()
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(asyncio.shield(run), timeout=SELF_CANCEL_GRACE)
        await channel.send({"t": MSG_STOPPED})

    session.close()
    inbox.cancel()


async def _inbound(
    channel: Channel,
    session: WorkerSession,
    stop: asyncio.Event,
    start: asyncio.Event,
) -> None:
    """Drain the channel: start, notifies, read replies, stop requests."""
    while True:
        msg = await channel.recv()
        if msg is None:
            # Supervisor gone. Nothing left to serve.
            stop.set()
            return
        kind = msg.get("t")
        if kind == MSG_START:
            start.set()
        elif kind == MSG_NOTIFY:
            session.on_notify(str(msg.get("path") or ""), msg.get("payload"))
        elif kind == MSG_READ_OK:
            session.on_read_reply(str(msg.get("id") or ""), msg.get("payload"))
        elif kind == MSG_READ_ERR:
            session.on_read_reply(
                str(msg.get("id") or ""),
                None,
                error=str(msg.get("error") or "read failed"),
            )
        elif kind == MSG_STOP:
            stop.set()
            return


def _wrap(term: Nu, store: Mapping[str, Any]) -> Nu:
    """Bracket the term in its kv navigator, when it has one.

    ``kind`` is one of ``none`` (ui-only sections), ``memory`` (per-worker
    scratch) or ``rocksdb``.

    Note that RocksDB takes an exclusive lock on its directory, so N
    workers cannot all open the same store as writers. ``read_only`` and
    ``secondary_path`` are passed through for the reader case; the shared
    writer case wants a kv proxy back through the supervisor, the same
    way ui frames already travel.
    """
    kind = str(store.get("kind") or "none")
    if kind == "none":
        return term

    from nu.kv.tree import auto_flow_atomic

    scope = _scope()
    tags = (scope,) if scope is not None else ()
    if kind == "memory":
        navigator = nu.kv.memory_navigator(tags=tags)
    elif kind == "rocksdb":
        navigator = nu.kv.rocksdb_navigator(
            str(store.get("path") or ".nuspace-db"),
            tags=tags,
            read_only=bool(store.get("read_only", False)),
            secondary_path=store.get("secondary_path"),
        )
    else:
        raise ValueError(f"unknown store kind {kind!r}")
    return nu.With(navigator, body=auto_flow_atomic(term, scope=scope))


def _scope() -> type | None:
    try:
        from nuspace.core.shapes import Space
    except Exception:
        return None
    return Space


def _format_error(exc: BaseException, prefix: str) -> str:
    """A usable runtime error: the exception, plus the section's own frames."""
    head = f"{type(exc).__name__}: {exc}"
    filename = f"<section {prefix}>"
    lines = [
        f"  line {frame.lineno}: {frame.line or ''}".rstrip()
        for frame in traceback.extract_tb(exc.__traceback__)
        if frame.filename == filename
    ]
    return head if not lines else head + "\n" + "\n".join(lines)


if __name__ == "__main__":
    main()
