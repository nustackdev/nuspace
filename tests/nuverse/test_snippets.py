"""nuverse's snippets, loaded the way the kernel loads them and run on a real store."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session
from nuverse.snippets import SNIPPETS, cell_lens, plane_lens, prose, table


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
    rewrite = Rewrites(Reroot(plane, cell), env.rewrite)
    prog = Space.cells[cell].prog
    load = prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite)
    term, _ = await nu.arun(nustd.kv.Snapshot(load, scope=Space), ctx)
    return term


def _keys(columns: dict) -> dict:
    """``{key: preview}`` of a lens frame's first column."""
    return {e["key"]: e["preview"] for e in columns["columns"][0]["entries"]}


async def _running(ctx: nu.Context, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell's program run as the kernel runs it: inside its ``Here`` frame."""
    term = nu.Frame(ops.Here, await _load(ctx, plane, cell), plane=plane, cell=cell)
    return asyncio.create_task(nu.arun(term, ctx.bind(Session, browser)))


async def test_plane_lens_browses_its_own_plane(ctx):
    await nu.arun(
        ops.add_plane("p", name="Home", backend="async")
        >> ops.add_cell("p", plane_lens.SNIPPET.source, cell_id="me"),
        ctx,
    )
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        shown = _keys(browser.last("lens"))
        assert shown["name"] == "Home"
        assert {"props", "meta", "cells"} <= set(shown)
        # State is in the other store: a lens on the plane does not see it.
        assert "state" not in shown
    finally:
        task.cancel()


async def test_cell_lens_follows_the_select(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async")
        >> ops.add_cell("p", cell_lens.SNIPPET.source, cell_id="me", name="lens")
        >> ops.add_cell("p", "one", cell_id="c1")
        >> ops.add_cell("p", "two", cell_id="c2", name="second")
        >> ops.set_cell_meta("c2", {"marker": 1}),
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
    await nu.arun(
        ops.add_plane("p", backend="async")
        >> ops.add_cell("p", cell_lens.SNIPPET.source, cell_id="me"),
        ctx,
    )
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        assert browser.selected == "me"
        assert cell_lens.SNIPPET.source.startswith(_keys(browser.last("lens"))["prog"][:20])
    finally:
        task.cancel()


# --- every snippet: a shim in the cell, the code in the package ---------------------


@pytest.mark.parametrize("snippet", SNIPPETS, ids=lambda s: s.name)
async def test_every_snippet_runs_from_its_shim(ctx, snippet):
    """The cell stores the shim and nothing else; loaded, it is the snippet's whole program."""
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", snippet, cell_id="c"),
        ctx,
    )
    stored, _ = await nu.arun(ops.snapshot(ops.prog("c")), ctx)
    assert stored == snippet.source
    nu.validate(nu.compile(await _load(ctx, "p", "c")))


async def _read(ctx: nu.Context, term: nu.Nu) -> object:
    value, _ = await nu.arun(ops.snapshot(term), ctx)
    return value


def _shown(browser: _Browser, text: str) -> Callable[[], bool]:
    """Whether the editor was handed ``text``."""
    return lambda: any(f.ref[-1] == "text" and f.payload == text for f in browser.frames)


async def test_set_text_reaches_a_running_editor(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", prose.SNIPPET, cell_id="c"),
        ctx,
    )
    browser = _Browser()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(_shown(browser, ""))
        await nu.arun(prose.set_text("c", "Water the basil"), ctx)
        await _until(_shown(browser, "Water the basil"))
        assert await _read(ctx, prose.text_of("c")) == "Water the basil"
    finally:
        task.cancel()


async def test_set_text_on_a_missing_cell_writes_nothing(ctx):
    await nu.arun(ops.add_plane("p", backend="async") >> prose.set_text("gone", "x"), ctx)
    assert await _read(ctx, prose.text_of("gone")) == ""
    assert await _read(ctx, ops.cell_exists("gone")) is False


async def test_insert_snippet_hands_the_new_cell_to_its_ops(ctx):
    """The id is minted when the term runs; ``into`` holds it for the ops after."""
    made = nu.let(
        "",
        lambda cell: (
            ops.insert_snippet("p", prose.SNIPPET, into=cell)
            >> prose.set_text(cell, "Basil likes sun")
        ),
    )
    await nu.arun(ops.add_plane("p", backend="async") >> made >> made, ctx)
    rows = await _read(ctx, ops.cell_rows("p"))
    assert [row["props"]["made_by"] for row in rows] == ["text", "text"]
    first, second = (row["id"] for row in rows)
    assert first != second
    assert await _read(ctx, prose.text_of(first)) == "Basil likes sun"
    assert await _read(ctx, prose.text_of(second)) == "Basil likes sun"


async def _settles(ctx: nu.Context, term: nu.Nu, check: Callable[[object], bool]) -> object:
    """``term`` read until ``check`` holds for it, then that value."""
    deadline = asyncio.get_running_loop().time() + 3.0
    while not check(value := await _read(ctx, term)):
        assert asyncio.get_running_loop().time() < deadline, f"timed out on {value!r}"
        await asyncio.sleep(0.01)
    return value


async def test_table_seeds_once_and_stores_what_the_browser_asks(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", table.SNIPPET, cell_id="c"),
        ctx,
    )
    sheet = table.snippet.Sheet
    order = ops.cell_state("c", nu.ToList(sheet.order))
    name = ops.cell_state("c", sheet.rows["r2"].cells["name"])
    browser = _Browser()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "table" for f in browser.frames))
        assert await _read(ctx, order) == ["r1", "r2", "r3"]

        # An edit is stored as asked and shipped back.
        browser.notify(
            browser.path("table"),
            {"event": "edit", "key": "r2", "row_index": 1, "column": "name", "value": "Basil"},
        )
        await _settles(ctx, name, lambda v: v == "Basil")
        await _until(lambda: "Basil" in str(browser.last("table")))

        # A row added lands where asked under a fresh key; a delete takes it out again.
        browser.notify(browser.path("table"), {"event": "add", "index": 0})
        added = (await _settles(ctx, order, lambda v: len(v) == 4))[0]
        assert added not in ("r1", "r2", "r3")
        browser.notify(
            browser.path("table"), {"event": "delete", "keys": [added], "row_indexes": [0]}
        )
        await _settles(ctx, order, lambda v: v == ["r1", "r2", "r3"])
    finally:
        task.cancel()

    # A second run finds it seeded and leaves the rows alone.
    browser = _Browser()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "table" for f in browser.frames))
        assert await _read(ctx, name) == "Basil"
        assert await _read(ctx, order) == ["r1", "r2", "r3"]
    finally:
        task.cancel()
