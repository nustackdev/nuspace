"""The frame pipe between a worker and the host's connections.

The host end runs on the test's loop, as it runs on uvicorn's; the worker end
runs on a loop of its own in another thread, as it runs in a pool process.
Sessions are fakes with no socket: frames sent are kept, notifies are fired
by hand on the host loop, the way a browser edit lands.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

import pytest

from nuspace.system.devices.web.session import PipeSession, SessionPipe, _Pipe
from nustd.ui.core import OP_NOTIFY, Frame, WsSession


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class FakeSession(WsSession):
    """A session with no socket: frames sent are kept, reads answer from a dict."""

    def __init__(self, reads: dict[tuple[str, ...], Any] | None = None) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []
        self.reads = reads or {}

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> Any:
        return self.reads[path]

    def notify(self, path: tuple[str, ...], payload: dict) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))


class FakeBook:
    """The ws server's book: live sessions by sid."""

    def __init__(self, **sessions: FakeSession) -> None:
        self.sessions = sessions

    def session(self, sid: str) -> FakeSession | None:
        return self.sessions.get(sid)


@pytest.fixture
async def host():
    """A ``SessionPipe`` on this loop, over a book with one live tab ``s1``."""
    tab = FakeSession(reads={("form", "name"): "Ada"})
    pipe = SessionPipe("127.0.0.1:0")
    pipe._web = FakeBook(s1=tab)
    pipe._server = await asyncio.start_server(pipe._serve, "127.0.0.1", 0)
    port = pipe._server.sockets[0].getsockname()[1]
    yield pipe, tab, f"127.0.0.1:{port}"
    await pipe.acleanup()


async def in_worker(work: Callable[[], Awaitable[Any]]) -> Any:
    """Run ``work`` on a fresh loop in another thread, await its result here."""
    done: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    loop = asyncio.get_running_loop()

    def main() -> None:
        try:
            result = asyncio.run(work())
        except BaseException as exc:
            loop.call_soon_threadsafe(done.set_exception, exc)
        else:
            loop.call_soon_threadsafe(done.set_result, result)

    threading.Thread(target=main, daemon=True).start()
    return await asyncio.wait_for(done, timeout=10)


async def _until(check: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def test_open_answers_whether_the_tab_is_live(host):
    _, _, address = host

    async def work() -> tuple[bool, bool]:
        pipe = await _Pipe.acquire(address)
        try:
            return await pipe.request("open", "s1"), await pipe.request("open", "gone")
        finally:
            await pipe.release()

    assert await in_worker(work) == (True, False)


async def test_frames_land_in_order(host):
    _, tab, address = host

    async def work() -> None:
        pipe = await _Pipe.acquire(address)
        try:
            session = PipeSession(pipe, "s1")
            for i in range(50):
                await session.send(Frame("write", ref=("rows", str(i)), payload={"n": i}))
            # A read after the writes comes back only once they have landed.
            await session.aread(("form", "name"))
        finally:
            await pipe.release()

    await in_worker(work)
    assert [f.payload["n"] for f in tab.frames] == list(range(50))
    assert tab.frames[0].ref == ("rows", "0")


async def test_read_round_trips_and_a_missing_tab_raises(host):
    _, _, address = host

    async def work() -> tuple[Any, str]:
        pipe = await _Pipe.acquire(address)
        try:
            value = await PipeSession(pipe, "s1").aread(("form", "name"))
            try:
                await PipeSession(pipe, "gone").aread(("form", "name"))
            except ConnectionError as exc:
                return value, str(exc)
            return value, ""
        finally:
            await pipe.release()

    value, error = await in_worker(work)
    assert value == "Ada"
    assert "gone" in error


async def test_notify_reaches_the_worker_and_its_redraw_lands(host):
    """The hang: a browser edit wakes the worker, which draws in answer.

    Many edits fired back to back on the host loop, each answered by a send.
    Over the proxy this held the host loop on the first one; here every edit
    is one message out, every redraw one message in.
    """
    _, tab, address = host
    edits = 40
    subscribed = threading.Event()

    async def work() -> int:
        pipe = await _Pipe.acquire(address)
        try:
            session = PipeSession(pipe, "s1")
            seen: asyncio.Queue[object] = asyncio.Queue()
            loop = asyncio.get_running_loop()
            sub = session.subscribe(("table", "cell"))
            sub.bind(lambda payload: loop.call_soon_threadsafe(seen.put_nowait, payload))
            await session.aread(("form", "name"))  # the sub is in place on the host
            subscribed.set()
            for _ in range(edits):
                payload = await asyncio.wait_for(seen.get(), timeout=5)
                await session.send(Frame("write", ref=("table", "view"), payload=payload))
            sub.close()
            return edits
        finally:
            await pipe.release()

    worker = asyncio.ensure_future(in_worker(work))
    await _until(subscribed.is_set)
    for i in range(edits):
        tab.notify(("table", "cell"), {"value": i})
    assert await worker == edits
    await _until(lambda: len(tab.frames) == edits)
    assert [f.payload["value"] for f in tab.frames] == list(range(edits))


async def test_a_closed_subscription_stops_forwarding(host):
    _, tab, address = host
    closed = threading.Event()

    async def work() -> None:
        pipe = await _Pipe.acquire(address)
        try:
            sub = PipeSession(pipe, "s1").subscribe(("x",))
            sub.bind(lambda payload: None)
            sub.close()
            await pipe.request("open", "s1")  # the unsub is through
            closed.set()
        finally:
            await pipe.release()

    await in_worker(work)
    assert closed.is_set()
    assert not tab._subs.get(("x",))


async def test_a_worker_going_away_drops_its_subscriptions(host):
    _, tab, address = host

    async def work() -> None:
        pipe = await _Pipe.acquire(address)
        PipeSession(pipe, "s1").subscribe(("y",)).bind(lambda payload: None)
        await pipe.request("open", "s1")
        await pipe.release()

    await in_worker(work)
    await _until(lambda: not tab._subs.get(("y",)))


async def test_runs_on_one_loop_share_one_stream(host):
    pipe_host, _, address = host

    async def work() -> bool:
        a = await _Pipe.acquire(address)
        b = await _Pipe.acquire(address)
        try:
            return a is b
        finally:
            await a.release()
            await b.release()

    assert await in_worker(work)
    await _until(lambda: not pipe_host._workers)
