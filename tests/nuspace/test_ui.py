"""nuspace.ui: a cell reading its params and linking planes.

Run the way a cell runs: rooted under the cell by the session env's rewrite,
inside the kernel's ``Here`` frame, with a session that keeps what is sent.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import nu
import nuspace.ui
import nustd.ui
from nuspace import PlaneSpec, ops
from nuspace.ops import Here
from nuspace.ops.utils import atomic
from nuspace.shapes import Space
from nuspace.system.devices.web import CellRoot, Shell
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.session import Session


#: nu's shared query fixtures: one encoding for nustd.ui and the ui-kit.
FIXTURES = Path(__file__).resolve().parents[3] / "nu" / "tests" / "fixtures" / "query.json"


class KeptSession(WsSession):
    """No socket: frames are kept."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)


def _as_cell(term: nu.Nu, plane: str = "p1", cell: str = "c1", run: str = "r1") -> nu.Nu:
    rooted = CellRoot(Shell.viewer, cell)(term)
    return nu.Frame(Here, rooted, plane=plane, cell=cell, run=run, cell_run="cr1")


async def _run(store, term: nu.Nu, session: KeptSession | None = None) -> object:
    value, _ = await nu.arun(term, store.ctx.bind(Session, session or KeptSession()))
    return value


async def test_params_are_this_planes_off_its_tab(store):
    tab = Space.connections["s1"]
    await store.run(
        atomic(
            Space.kernel.runs["r1"].envs.set([["session", "s1"]])
            >> tab.params.set({"movies": {}, "movie": {"id": "42"}})
        )
    )
    got = await _run(store, _as_cell(nuspace.ui.params(), plane="movie"))
    assert got == {"id": "42"}
    assert await _run(store, _as_cell(nuspace.ui.params(), plane="movies")) == {}
    # A plane the tab does not have open, and a run with no tab at all.
    assert await _run(store, _as_cell(nuspace.ui.params(), plane="other")) == {}
    assert await _run(store, _as_cell(nuspace.ui.params(), run="r2")) == {}


async def test_params_move_without_a_rerun_and_on_params_hears_it(store):
    """Params are data: the store moves, a cell listening reads the new ones."""
    tab = Space.connections["s1"]
    await store.run(
        atomic(
            Space.kernel.runs["r1"].envs.set([["session", "s1"]])
            >> tab.params.set({"movie": {"id": "42"}})
        )
    )
    seen = nu.WaitReactive(nuspace.ui.on_params(), nuspace.ui.params() == {"id": "43"})
    waiting = asyncio.create_task(_run(store, _as_cell(seen, plane="movie")))
    await asyncio.sleep(0.05)
    assert not waiting.done()
    await store.run(atomic(tab.params.set({"movie": {"id": "43"}})))
    await asyncio.wait_for(waiting, 3.0)


async def test_href_encodes_ids_and_params(store):
    assert await store.run(nuspace.ui.href("home")) == "/home"
    assert await store.run(nuspace.ui.href("movie", {"id": 42, "q": "a b;c"})) == (
        "/movie?id=42&q=a+b%3Bc"
    )
    assert await store.run(nuspace.ui.href("movie", {"drop": None})) == "/movie"
    assert await store.run(nuspace.ui.href("a b")) == "/a%20b"
    assert await store.run(nuspace.ui.href(nu.Str("a") + ".b")) == "/a.b"


def _encode_cases() -> list[dict]:
    if not FIXTURES.exists():
        return []
    return json.loads(FIXTURES.read_text())["encode"]


@pytest.mark.skipif(not FIXTURES.exists(), reason="no nu checkout beside nuspace")
@pytest.mark.parametrize("case", _encode_cases())
async def test_href_query_is_nus_encoding(store, case):
    got = await store.run(nuspace.ui.href("p", case["query"]))
    assert got == ("/p?" + case["string"] if case["string"] else "/p")


async def test_page_link_draws_a_link_off_the_store(store):
    await store.run(
        ops.create_plane(PlaneSpec("x", "X", backend="async"), name="Movies", plane_id="mv")
    )
    await store.run(ops.set_plane_meta("mv", {"icon": "lucide:film"}))
    session = KeptSession()
    link = nustd.ui.LinkRef("open")
    await _run(store, _as_cell(nuspace.ui.page_link(link, "mv", params={"id": 1})), session)
    (frame,) = session.frames
    assert tuple(frame.ref) == ("viewer", "cells", "c1", "open")
    assert frame.payload["href"] == "/mv?id=1" and frame.payload["label"] == "Movies"


async def test_page_link_fills_a_page_link(store):
    await store.run(
        ops.create_plane(PlaneSpec("x", "X", backend="async"), name="Notes", plane_id="nt")
    )
    await store.run(ops.set_plane_meta("nt", {"icon": "emoji:📝"}))
    session = KeptSession()
    link = nustd.ui.PageLinkRef("open")
    term = nuspace.ui.page_link(link, "nt", params={"tab": "a"}, description="Daily notes")
    await _run(store, _as_cell(term), session)
    (frame,) = session.frames
    assert frame.payload == {
        "href": "/nt?tab=a",
        "title": "Notes",
        "icon": "📝",
        "description": "Daily notes",
    }


async def test_a_cells_refs_land_in_a_column_with_no_gap(store):
    """The cell's own node holds what it draws and adds no spacing of its own."""
    session = KeptSession()
    await _run(store, _as_cell(nustd.ui.TextRef("t").set("hi")), session)
    (frame,) = session.frames
    cell = next(step for step in frame.chain if step[0] == "c1")
    assert cell[1] == "Column"
    assert cell[2] == {"gap": 0}
