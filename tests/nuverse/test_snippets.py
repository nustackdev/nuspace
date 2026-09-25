"""nuverse's lens snippets, loaded the way the kernel loads them and run on a real store."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest_asyncio

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Bracketed, Rewrites
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session
from nuverse.snippets import cell_lens, plane_lens


if TYPE_CHECKING:
    from collections.abc import Callable


class _Hold(ScalarQuery):
    """Hands the ctx it runs in to ``opened``, then waits for ``done``."""

    def __init__(self, opened: asyncio.Future, done: asyncio.Event) -> None:
        super().__init__()
        self._payload = {"opened": opened, "done": done}

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        opened, done = self._payload["opened"], self._payload["done"]

        async def athunk(rt: object) -> object:
            opened.set_result(rt.ctx)
            await done.wait()

        return athunk


@pytest_asyncio.fixture
async def ctx():
    """An in memory store bound untagged, the way a worker binds its proxy."""
    loop = asyncio.get_running_loop()
    opened, done = loop.create_future(), asyncio.Event()
    held = asyncio.create_task(
        nu.arun(nu.With(nustd.kv.memory_navigator(), body=_Hold(opened, done)))
    )
    yield await opened
    done.set()
    await held


class _Browser(WsSession):
    """A session with no socket. Keeps frames, and plays the select's part."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []
        self.selected = ""

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)
        if frame.ref[-1] == "cell" and isinstance(frame.payload, str):
            self.selected = frame.payload

    async def aread(self, path: tuple[str, ...]) -> object:
        assert path[-1] == "cell"
        return self.selected

    def notify(self, path: tuple[str, ...], payload: object) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))

    def pick(self, cell_id: str) -> None:
        """What the dropdown does: select locally, notify with no payload."""
        self.selected = cell_id
        self.notify(self.path("cell"), None)

    def path(self, name: str) -> tuple[str, ...]:
        return next(f.ref for f in self.frames if f.ref[-1] == name)

    def last(self, name: str) -> object:
        return next(f.payload for f in reversed(self.frames) if f.ref[-1] == name)

    def options(self) -> list:
        """The dropdown's latest list."""
        writes = [f.payload for f in self.frames if f.ref[-1] == "cell"]
        return next(w["options"] for w in reversed(writes) if isinstance(w, dict))


async def _until(check: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def _load(ctx: nu.Context, plane: str, cell: str) -> nu.Nu:
    """The cell's program, loaded through the kernel's rewrites."""
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot(plane, cell), env.rewrite, Bracketed())
    prog = Space.planes[plane].cells[cell].prog
    load = prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite)
    term, _ = await nu.arun(nustd.kv.auto_flow_atomic(load, scope=Space), ctx)
    return term


def _keys(columns: dict) -> dict:
    """``{key: preview}`` of a lens frame's first column."""
    return {e["key"]: e["preview"] for e in columns["columns"][0]["entries"]}


async def _running(ctx: nu.Context, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    term = await _load(ctx, plane, cell)
    return asyncio.create_task(nu.arun(term, ctx.bind(Session, browser)))


async def test_plane_lens_browses_its_own_plane(ctx):
    await nu.arun(
        ops.add_plane("p", name="Home") >> ops.add_cell("p", plane_lens.SOURCE, cell_id="me"), ctx
    )
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        shown = _keys(browser.last("lens"))
        assert shown["name"] == "Home"
        assert {"props", "meta", "state", "cells", "order"} <= set(shown)
    finally:
        task.cancel()


async def test_cell_lens_follows_the_select(ctx):
    await nu.arun(
        ops.add_plane("p")
        >> ops.add_cell("p", cell_lens.SOURCE, cell_id="me", name="lens")
        >> ops.add_cell("p", "one", cell_id="c1")
        >> ops.add_cell("p", "two", cell_id="c2", name="second")
        >> ops.set_cell_meta("p", "c2", {"marker": 1}),
        ctx,
    )
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        # Every cell listed in order, named or by id. The first other cell picked.
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        assert browser.last("cell") == "c1"
        assert browser.options() == [
            {"value": "me", "label": "lens"},
            {"value": "c1", "label": "c1"},
            {"value": "c2", "label": "second"},
        ]
        assert _keys(browser.last("lens"))["prog"] == "one"

        # A pick restarts the lens on the other cell.
        before = len(browser.frames)
        browser.pick("c2")
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames[before:]))
        assert _keys(browser.last("lens"))["prog"] == "two"

        # Moving the cursor reads the picked cell, not the first one.
        before = len(browser.frames)
        browser.notify(browser.path("lens"), ["meta"])
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames[before:]))
        meta = browser.last("lens")["columns"][1]["entries"]
        assert [(e["key"], e["preview"]) for e in meta] == [("marker", "1")]

        # A cell added shows up in the list.
        await nu.arun(ops.add_cell("p", "three", cell_id="c3"), ctx)
        await _until(lambda: browser.options()[-1] == {"value": "c3", "label": "c3"})
    finally:
        task.cancel()


async def test_cell_lens_alone_on_its_plane_browses_itself(ctx):
    await nu.arun(ops.add_plane("p") >> ops.add_cell("p", cell_lens.SOURCE, cell_id="me"), ctx)
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        assert browser.selected == "me"
        assert _keys(browser.last("lens"))["prog"].startswith("import nu")
    finally:
        task.cancel()
