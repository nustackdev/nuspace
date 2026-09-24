"""Home: the seed, ``Space.state`` (info and recents), and the four cells drawn once."""

from __future__ import annotations

import asyncio
import time

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops import App
from nuspace.ops.utils import atomic
from nuspace.shapes import RECENTS_CAP, Reroot, Space
from nuspace.system import home
from nuspace.system.devices.web.env import session_env
from nuspace.system.devices.web.sidebar import rows
from nuspace.system.kernel.body import Bracketed, Rewrites
from nustd.ui import Session
from nustd.ui.core import OP_NOTIFY, Frame, WsSession


def _page(plane_id=None, name=""):
    return ops.add_plane(plane_id, name=name, ui=True, made_by="page")


APPS = [App("page", "Pages", _page)]


# --- The seed ---------------------------------------------------------------------


async def test_home_is_seeded_once_and_left_alone_after_edits(store):
    await store.run(home.ensure_home())
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == home.PLANE]
    assert row["name"] == "Home"
    assert row["props"] == {"system": True, "ui": True, "made_by": ""}
    assert row["meta"] == {"editable": True, "full_width": False}
    cells = await store.read(ops.cell_rows(home.PLANE))
    assert [(c["id"], c["name"], c["prog"]) for c in cells] == [
        (cell, cell, source) for cell, source in home.CELLS
    ]

    # The owner edits it: a cell gone, one rewritten, the plane renamed.
    await store.run(
        ops.remove_cell(home.PLANE, "start")
        >> ops.set_prog(home.PLANE, "header", "def out():\n    return None\n")
        >> ops.rename_plane(home.PLANE, "Mine")
    )
    await store.run(home.ensure_home())
    cells = await store.read(ops.cell_rows(home.PLANE))
    assert [c["id"] for c in cells] == ["header", "recent", "glance"]
    assert cells[0]["prog"] == "def out():\n    return None\n"
    assert await store.read(Space.planes[home.PLANE].name) == "Mine"
    # System: protected.
    assert await store.run(ops.remove_plane(home.PLANE)) is False


async def test_home_is_under_no_sidebar_section(store):
    await store.run(home.ensure_home() >> _page("p1", "One"))
    got = await store.read(rows(APPS))
    assert [r["id"] for r in got] == ["space", "page", "p1"]


async def test_write_info(store, tmp_path):
    before = time.time()
    await store.run(home.write_info(str(tmp_path)))
    info = await store.read(Space.state.info.extract())
    assert info["path"] == str(tmp_path)
    assert info["opened"] >= before
    assert info["versions"] == home.versions()
    assert "nuspace" in info["versions"]
    await store.run(home.write_info(None))
    assert await store.read(Space.state.info.path) == ""


def test_versions_leaves_out_what_is_not_installed():
    got = home.versions(("nuspace", "no-such-package-here"))
    assert list(got) == ["nuspace"]


# --- Recents ----------------------------------------------------------------------


async def test_remember_dedupes_caps_and_skips(store):
    from nuspace.system.devices.web.device import remember

    await store.run(
        home.ensure_home()
        >> ops.add_plane("svc", system=True)
        >> ops.add_plane("hidden")
        >> _page("a")
        >> _page("b")
    )
    recents = Space.state.recents

    async def push(*ids: str) -> list:
        await store.run(atomic(remember(nu.Literal(list(ids)))))
        return await store.read(recents)

    # Pane order: the last is the newest. Home and services are skipped; a
    # plane not written yet and a plain non ui one are kept.
    assert await push("a", home.PLANE, "svc", "b") == ["b", "a"]
    assert await push("later") == ["later", "b", "a"]
    assert await push("hidden") == ["hidden", "later", "b", "a"]
    # Opened again: moved to the front, never twice.
    assert await push("a") == ["a", "hidden", "later", "b"]
    # Nothing left to push writes nothing.
    assert await push(home.PLANE) == ["a", "hidden", "later", "b"]
    # Capped.
    many = [f"x{i}" for i in range(30)]
    got = await push(*many)
    assert len(got) == RECENTS_CAP
    assert got[:3] == ["x29", "x28", "x27"]


class _FakeSession(WsSession):
    """A session with no socket: frames sent are kept, notifies are fired by hand."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    def notify(self, path: tuple[str, ...], payload: dict) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))


async def _until(store, term: nu.Nu, check, timeout: float = 3.0) -> object:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        value = await store.read(term)
        if check(value):
            return value
        assert asyncio.get_running_loop().time() < deadline, f"timed out, last read {value!r}"
        await asyncio.sleep(0.01)


async def test_pages_open_pushes_recents(store):
    from nuspace.system.devices.web.device import connection

    await store.run(home.ensure_home() >> _page("p1", "One") >> _page("p2", "Two"))
    session = _FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), apps=APPS), ctx))
    recents = Space.state.recents
    routes = Space.connections["s1"].routes

    def opened(*ids: str) -> None:
        session.notify(("viewer", "ops", "pages.open"), {"page_ids": list(ids)})

    try:
        await asyncio.sleep(0.2)
        opened(home.PLANE)
        await _until(store, routes, lambda r: r == [home.PLANE])
        opened(home.PLANE, "p1")
        assert await _until(store, recents, lambda r: r == ["p1"]) == ["p1"]
        # A split: only the newly opened one is pushed.
        opened("p1", "p2")
        assert await _until(store, recents, lambda r: r == ["p2", "p1"]) == ["p2", "p1"]
        # p1 was open all along, so closing p2 pushes nothing.
        opened("p1")
        await _until(store, routes, lambda r: r == ["p1"])
        assert await store.read(recents) == ["p2", "p1"]
        # Opened again: to the front, deduped.
        opened("p2")
        await _until(store, routes, lambda r: r == ["p2"])
        opened("p1")
        assert await _until(store, recents, lambda r: r == ["p1", "p2"]) == ["p1", "p2"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


# --- The cells --------------------------------------------------------------------


@pytest.mark.parametrize("cell", home.CELLS, ids=lambda c: c[0])
async def test_each_cell_loads_through_the_kernel_rewrites(store, cell):
    _, source = cell
    await store.run(ops.add_plane("p") >> ops.add_cell("p", source, cell_id="c"))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("p", "c"), env.rewrite, Bracketed())
    prog = Space.planes["p"].cells["c"].prog
    term = await store.run(
        nustd.kv.auto_flow_atomic(
            prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite), scope=Space
        )
    )
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


class _Recording:
    """A session that keeps the frames it is sent instead of sending them."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


async def _frames(store, source: str) -> dict:
    """One draw of a cell: ``{ref path: payload}``, ``None`` for an erase."""
    namespace: dict = {}
    exec(compile(source, "cell", "exec"), namespace)  # noqa: S102
    session = _Recording()
    await nu.arun(namespace["draw"](), store.ctx.bind(Session, session))
    return {frame.ref: None if frame.op == "remove" else frame.payload for frame in session.frames}


async def test_header_draws_the_space_line(store, tmp_path):
    await store.run(home.write_info(str(tmp_path)))
    info = Space.state.info
    await store.run(atomic(info.opened.set(nu.Float(time.time() - 3725.0))))
    (line,) = (await _frames(store, home.HEADER)).values()
    parts = line.split("  ·  ")
    assert parts[0] == "nuspace"
    assert parts[1] == str(tmp_path)
    assert parts[2].startswith("nuspace ")
    assert parts[3] == "Up 1h 2m"


async def test_header_on_a_store_never_opened(store):
    (line,) = (await _frames(store, home.HEADER)).values()
    assert line == "nuspace  ·  Throwaway store"


async def test_recent_links_the_planes_that_still_exist(store):
    await store.run(
        _page("a", "Alpha")
        >> _page("b", "")
        >> atomic(Space.state.recents.set(nu.Literal(["gone", "b", "a"])))
    )
    got = await _frames(store, home.RECENT)
    assert got[("title",)]["label"] == "Recent"
    assert got[("r0",)] == {"href": "/b", "label": "b"}
    assert got[("r1",)] == {"href": "/a", "label": "Alpha"}
    assert all(got[(f"r{i}",)] is None for i in range(2, home.RECENT_SHOWN))
    assert got[("none",)] is None


async def test_recent_with_nothing_opened(store):
    got = await _frames(store, home.RECENT)
    assert got[("none",)] == "Nothing opened yet."
    assert all(got[(f"r{i}",)] is None for i in range(home.RECENT_SHOWN))


async def test_recent_shows_at_most_eight(store):
    ids = [f"p{i}" for i in range(12)]
    await store.run(
        nu.Sequential(*[_page(pid, pid.upper()) for pid in ids])
        >> atomic(Space.state.recents.set(nu.Literal(ids)))
    )
    got = await _frames(store, home.RECENT)
    links = [got[(f"r{i}",)]["href"] for i in range(home.RECENT_SHOWN)]
    assert links == [f"/{pid}" for pid in ids[: home.RECENT_SHOWN]]


def _seed_kernel() -> nu.Nu:
    """One worker up and one dead, one live run, a run failed now and one failed long ago."""
    k = Space.kernel
    now = time.time()
    return atomic(
        k.workers["w1"].status.set("up")
        >> k.workers["w2"].status.set("dead")
        >> k.runs["r1"].status.set("up")
        >> k.live.set_item("r1", "w1")
        >> k.runs["r2"].status.set("dead")
        >> k.runs["r2"].exit.set("failed")
        >> k.runs["r2"].ended.set(nu.Float(now - 60.0))
        >> k.runs["r3"].status.set("dead")
        >> k.runs["r3"].exit.set("failed")
        >> k.runs["r3"].ended.set(nu.Float(now - 7200.0))
        >> k.runs["r4"].status.set("dead")
        >> k.runs["r4"].exit.set("ok")
        >> k.runs["r4"].ended.set(nu.Float(now - 10.0))
    )


def _tiles(got: dict) -> dict:
    return {ref[-1]: got[ref]["value"] for ref in got if ref[:-1] == ("tiles",)}


async def test_glance_draws_plain_tiles(store):
    await store.run(
        home.ensure_home()
        >> _page("a")
        >> _page("b")
        >> ops.add_plane("svc", system=True)
        >> ops.add_plane("hidden")
        >> _seed_kernel()
    )
    got = await _frames(store, home.GLANCE)
    assert _tiles(got) == {"pages": "2", "live": "1", "workers": "1", "failed": "1"}
    assert [got[("links", name)] for name in ("runs", "workers", "planes")] == [None] * 3


async def test_glance_links_the_live_pages_there_are(store):
    await store.run(
        ops.add_plane("r1", name="R", ui=True, made_by="runs")
        >> ops.add_plane("r2", name="R2", ui=True, made_by="runs")
        >> ops.add_plane("pl", name="P", ui=True, made_by="planes")
    )
    got = await _frames(store, home.GLANCE)
    assert got[("links", "runs")] == {"href": "/r1", "label": "Runs"}
    assert got[("links", "workers")] is None
    assert got[("links", "planes")] == {"href": "/pl", "label": "Planes"}
    assert _tiles(got)["pages"] == "3"


async def test_start_draws_its_text(store):
    (text,) = (await _frames(store, home.START)).values()
    for bit in ("`+`", "`/`", "Cmd/Ctrl-click", "`⋯`", "code button"):
        assert bit in text
