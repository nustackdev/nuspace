"""nuverse's snippets, loaded the way the kernel loads them and run on a real store."""

from __future__ import annotations

import asyncio
import datetime
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
from nuverse.snippets import (
    SNIPPETS,
    cell_lens,
    converter,
    date,
    number,
    password,
    plane_lens,
    prose,
    select,
    slider,
    switch,
    table,
    text_input,
)


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


# --- inputs: user input, stored, shown back -----------------------------------------


class _Inputs(_Browser):
    """A session whose inputs hold what was typed, by ref name, and answer reads with it."""

    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, object] = {}

    async def aread(self, path: tuple[str, ...]) -> object:
        return self.values[path[-1]]

    def type(self, *names: str, value: object) -> None:
        """What an input does: hold the value locally, notify with no payload."""
        self.values[names[-1]] = value
        self.notify(next(f.ref for f in self.frames if f.ref[-len(names) :] == names), None)

    def shown(self, *names: str) -> list:
        """Every payload written to the ref ending in ``names``, oldest first."""
        return [f.payload for f in self.frames if f.ref[-len(names) :] == names]


async def test_number_stores_what_is_typed_and_shows_what_is_set(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", number.SNIPPET, cell_id="c"),
        ctx,
    )
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: browser.shown("entry", "input"))
        # Labelled with the cell's name, bounded 0 to 100, a step of 1.
        assert {"label": "number"} in browser.shown("entry")
        assert {"min": 0.0} in browser.shown("entry", "input")
        assert {"max": 100.0} in browser.shown("entry", "input")
        assert {"step": 1.0} in browser.shown("entry", "input")

        browser.type("entry", "input", value=42)
        await _settles(ctx, number.value_of("c"), lambda v: v == 42.0)

        # Set from outside: the running cell shows it.
        await nu.arun(number.set_value("c", 7.5), ctx)
        await _until(lambda: {"value": 7.5} in browser.shown("entry", "input"))

        # Config: a bound typed is stored and applied.
        browser.type("settings", "min", value=-3)
        await _until(lambda: {"min": -3.0} in browser.shown("entry", "input"))

        # Renamed under Config: the cell is renamed, and findable by it.
        browser.type("settings", "name", value="budget")
        await _until(lambda: {"label": "budget"} in browser.shown("entry"))
        assert await _read(ctx, ops.cell_named("p", "budget")) == "c"
    finally:
        task.cancel()


async def _input(ctx: nu.Context, kind: object) -> tuple[_Inputs, asyncio.Task]:
    """A cell of ``kind`` made as ``c`` on ``p``, running, its first paint done."""
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", kind.SNIPPET, cell_id="c"),
        ctx,
    )
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    await _until(lambda: browser.shown("entry") and browser.shown("entry", "input"))
    return browser, task


@pytest.mark.parametrize(
    ("kind", "typed", "stored", "set_to", "shown"),
    [
        (text_input, "Basil", "Basil", "Thyme", "Thyme"),
        (switch, True, True, False, False),
        (select, "Two", "Two", "Three", "Three"),
        (date, "2026-10-06", datetime.date(2026, 10, 6), "2027-01-01", "2027-01-01"),
        (slider, 30, 30.0, 55.0, {"value": 55.0}),
    ],
    ids=lambda v: getattr(v, "__name__", None),
)
async def test_an_input_stores_what_is_typed_and_shows_what_is_set(
    ctx, kind, typed, stored, set_to, shown
):
    browser, task = await _input(ctx, kind)
    try:
        browser.type("entry", "input", value=typed)
        await _settles(ctx, kind.value_of("c"), lambda v: v == stored)
        await nu.arun(kind.set_value("c", set_to), ctx)
        await _until(lambda: browser.shown("entry", "input")[-1] == shown)
        # Labelled by the cell's name, renamed from Config.
        browser.type("settings", "name", value="mine")
        await _until(lambda: {"label": "mine"} in browser.shown("entry"))
        assert await _read(ctx, ops.cell_named("p", "mine")) == "c"
    finally:
        task.cancel()


async def test_a_cleared_date_is_gone(ctx):
    browser, task = await _input(ctx, date)
    try:
        assert browser.shown("entry", "input")[0] == ""
        browser.type("entry", "input", value="2026-10-06")
        await _settles(ctx, date.value_of("c"), lambda v: v == datetime.date(2026, 10, 6))
        browser.type("entry", "input", value="")
        await _settles(ctx, ops.cell_state("c", date.snippet.Day.value.exists()), lambda v: not v)
    finally:
        task.cancel()


async def test_select_options_come_from_config(ctx):
    browser, task = await _input(ctx, select)
    try:
        assert {"options": select.snippet.OPTIONS} in browser.shown("entry", "input")
        browser.type("settings", "options", value=["Red", "Blue"])
        await _until(lambda: browser.shown("entry", "input")[-1] == {"options": ["Red", "Blue"]})
        assert browser.shown("settings", "options")[-1] == ["Red", "Blue"]
    finally:
        task.cancel()


async def test_slider_range_comes_from_config(ctx):
    browser, task = await _input(ctx, slider)
    try:
        assert {"max": 100.0} in browser.shown("entry", "input")
        browser.type("settings", "max", value=10)
        await _until(lambda: {"max": 10.0} in browser.shown("entry", "input"))
        assert {"value": 10.0} in browser.shown("settings", "max")
    finally:
        task.cancel()


# --- examples ------------------------------------------------------------------------


async def _example(
    ctx: nu.Context, kind: object, first: tuple[str, ...]
) -> tuple[_Inputs, asyncio.Task]:
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", kind.SNIPPET, cell_id="c"),
        ctx,
    )
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    await _until(lambda: browser.shown(*first))
    return browser, task


async def test_password_draws_again_when_an_option_changes(ctx):
    browser, task = await _example(ctx, password, ("options", "symbols"))
    try:
        first = browser.shown("password")[-1]
        assert len(first) == 20
        browser.type("length", value=12)
        await _until(lambda: len(browser.shown("password")[-1]) == 12)
        browser.type("digits", value=False)
        browser.type("symbols", value=False)
        browser.type("upper", value=False)
        await _until(lambda: browser.shown("password")[-1].isalpha())
        # Generate draws a new one with the same options.
        last = browser.shown("password")[-1]
        # Never written, so no frame names it: its address is its sibling's.
        browser.notify((*browser.path("upper")[:-1], "generate"), None)
        await _until(lambda: browser.shown("password")[-1] != last)
        assert browser.shown("password")[-1].islower()
    finally:
        task.cancel()


async def test_converter_follows_either_side(ctx):
    browser, task = await _example(ctx, converter, ("right", "amount"))
    try:
        # 1 m on the left, in km on the right.
        assert browser.shown("left", "amount")[-1] == {"value": 1.0}
        assert browser.shown("right", "amount")[-1] == {"value": 0.001}
        browser.type("right", "amount", value=2)
        await _until(lambda: browser.shown("left", "amount")[-1] == {"value": 2000.0})

        # Temperature: 100 °C is 212 °F, and back.
        browser.type("kind", value="Temperature")
        await _until(lambda: browser.shown("right", "unit")[-1] == "°F")
        browser.type("left", "amount", value=100)
        await _until(lambda: browser.shown("right", "amount")[-1] == {"value": 212.0})
        browser.type("right", "amount", value=32)
        await _until(lambda: browser.shown("left", "amount")[-1] == {"value": 0.0})
    finally:
        task.cancel()
