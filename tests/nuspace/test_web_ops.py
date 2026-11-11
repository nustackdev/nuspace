"""``nuspace.devices.web``: each op's writes, its raises, and the reads a cell on a pane makes.

Every op is a bare term, run here inside ``nuspace.atomic`` as a caller
would.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import nu
import nuspace
import nuspace.devices.web as web
import nustd.ui
from nu.lang import is_null
from nuspace.errors import Exists, Missing, Refused, Removed
from nuspace.places import inside
from nuspace.shapes import ROOT, Space
from nustd.ui import Session


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

tabs = web.Conn.connections


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def plane(store, pid, *, on_web=True, **kw):
    await do(store, nuspace.plane.add(pid, backend="async", **kw))
    if on_web:
        await do(store, web.add(pid))
    return pid


# --- Web planes --------------------------------------------------------------------------


async def test_add_writes_the_web_row_with_its_flags(store):
    await plane(store, "p1", on_web=False)
    await do(store, web.add("p1", editable=True, compact=True))
    row = await store.read(web.Web.planes["p1"].extract())
    assert row == {"editable": True, "full_width": False, "compact": True}


async def test_add_raises_for_a_missing_removed_or_web_plane(store):
    with pytest.raises(Missing):
        await do(store, web.add("nope"))
    await plane(store, "p1")
    with pytest.raises(Exists):
        await do(store, web.add("p1"))
    await plane(store, "p2", on_web=False)
    await do(store, nuspace.plane.remove("p2"))
    with pytest.raises(Removed):
        await do(store, web.add("p2"))


async def test_set_changes_only_the_flags_given(store):
    await plane(store, "p1")
    await do(store, web.set("p1", full_width=True))
    row = await store.read(web.Web.planes["p1"].extract())
    assert row == {"editable": False, "full_width": True, "compact": False}
    with pytest.raises(Missing):
        await do(store, web.set("p9", editable=True))


# --- Recents ------------------------------------------------------------------------------


async def test_visit_moves_to_the_front_and_caps(store):
    for i in range(web.RECENTS_CAP + 2):
        await plane(store, f"p{i}", on_web=False)
        await do(store, web.visit(f"p{i}"))
    await do(store, web.visit("p5"))
    recents = await store.read(nu.list(web.Web.recents))
    assert len(recents) == web.RECENTS_CAP
    assert recents[:2] == ["p5", f"p{web.RECENTS_CAP + 1}"]
    assert "p0" not in recents
    assert recents.count("p5") == 1


async def test_visit_raises_for_missing_or_removed(store):
    with pytest.raises(Missing):
        await do(store, web.visit("nope"))
    await plane(store, "gone")
    await do(store, nuspace.plane.remove("gone"))
    with pytest.raises(Removed):
        await do(store, web.visit("gone"))


# --- Tabs and panes -----------------------------------------------------------------------


async def test_open_and_close_tab(store):
    await do(store, web.open_tab("t1"))
    assert await store.read(tabs["t1"].extract()) == {"order": [], "panes": {}, "expanded": {}}
    with pytest.raises(Exists):
        await do(store, web.open_tab("t1"))
    await do(store, web.close_tab("t1"))
    assert not await store.read(tabs.contains("t1"))
    with pytest.raises(Missing):
        await do(store, web.close_tab("t1"))


async def test_set_panes_adds_new_panes_drops_closed_and_keeps_order(store):
    for p in ("a", "b", "c"):
        await plane(store, p)
    await do(store, web.open_tab("t"))
    await do(store, web.set_panes("t", ["a", "b"]))
    await do(store, web.set_pane_params("t", "a", {"row": "1"}))
    await do(store, web.set_panes("t", ["b", "a", "c"]))
    tab = await store.read(tabs["t"].extract())
    assert tab["order"] == ["b", "a", "c"]
    assert tab["panes"]["a"]["params"] == {"row": "1"}
    assert tab["panes"]["c"] == {"params": {}, "plane_run": "", "restart": ""}
    await do(store, web.set_panes("t", ["c"]))
    tab = await store.read(tabs["t"].extract())
    assert tab["order"] == ["c"]
    assert set(tab["panes"]) == {"c"}


async def test_set_panes_keeps_a_pane_whose_plane_was_removed_since(store):
    await plane(store, "a")
    await plane(store, "b")
    await do(store, web.open_tab("t"))
    await do(store, web.set_panes("t", ["a"]))
    await do(store, nuspace.plane.remove("a"))
    await do(store, web.set_panes("t", ["a", "b"]))
    assert await store.read(nu.list(tabs["t"].order)) == ["a", "b"]


async def test_set_panes_opens_a_plane_missing_or_with_no_view(store):
    await plane(store, "off", on_web=False)
    await do(store, web.open_tab("t"))
    await do(store, web.set_panes("t", ["ghost", "off"]))
    tab = await store.read(tabs["t"].extract())
    assert tab["order"] == ["ghost", "off"]
    assert tab["panes"]["off"] == {"params": {}, "plane_run": "", "restart": ""}


async def test_set_panes_raises(store):
    await plane(store, "a")
    with pytest.raises(Missing):
        await do(store, web.set_panes("nope", ["a"]))
    await do(store, web.open_tab("t"))
    with pytest.raises(Refused):
        await do(store, web.set_panes("t", ["a", "a"]))
    with pytest.raises(Refused):
        await do(store, web.set_panes("t", [""]))
    # Nothing landed: each raise aborted its commit.
    assert await store.read(tabs["t"].extract()) == {"order": [], "panes": {}, "expanded": {}}


async def test_pane_ops_raise_without_the_pane(store):
    await plane(store, "a")
    await do(store, web.open_tab("t"))
    with pytest.raises(Missing):
        await do(store, web.set_pane_params("t", "a", {}))
    with pytest.raises(Missing):
        await do(store, web.restart_pane("t", "a"))


async def test_restart_pane_writes_a_new_token_each_time(store):
    await plane(store, "a")
    await do(store, web.open_tab("t"))
    await do(store, web.set_panes("t", ["a"]))
    token = tabs["t"].panes["a"].restart
    await do(store, web.restart_pane("t", "a"))
    first = await store.read(token)
    await do(store, web.restart_pane("t", "a"))
    assert first != "" and await store.read(token) != first


# --- restart_cell: without a kernel, the run records written by hand -------------------


async def pane_on(
    store, *, run: bool = False, started: bool = False, ended: bool = False, running=("c1", "c2")
):
    """Tab ``t`` with a pane on plane ``a`` (cells ``c1``, ``c2``), its run as asked: its id, or ``""``.

    A started run has a cell run of each cell in ``running``.
    """
    await plane(store, "a")
    for c in ("c1", "c2"):
        await do(store, nuspace.cell.add("a", "x = 1", id=c, fabrics=[]))
    await do(store, web.open_tab("t"))
    await do(store, web.set_panes("t", ["a"]))
    if run:
        made = await store.made(nuspace.atomic(nuspace.plane_run.add("a", into=_made())))
        await do(store, tabs["t"].panes["a"].plane_run.set(made))
        if started:
            await do(store, nuspace.plane_run.start(made))
            for c in running:
                await do(store, nuspace.cell_run.add(made, c))
        if ended:
            await do(store, nuspace.plane_run.end(made, "ok"))
        return made
    return ""


def cell_runs(run: str, cell: str):
    node = Space.exec.indexes.history.plane_to_plane_runs["a"].runs[run]
    ids = node.cell_to_cell_runs[cell].ids
    return nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([]))


async def test_restart_cell_in_a_started_run_adds_a_cell_run(store):
    run = await pane_on(store, run=True, started=True)
    (old,) = await store.read(cell_runs(run, "c1"))
    await store.run(web.restart_cell("t", "c1"))
    old_row = await store.read(Space.exec.cell_runs[old].extract())
    assert old_row.get("interrupt_at") is not None
    first, new = await store.read(cell_runs(run, "c1"))
    assert first == old
    row = await store.read(Space.exec.cell_runs[new].extract())
    assert row["plane_run"] == run and row["by"] == "web"
    # The other cell runs on; the plane run is the same; no restart asked.
    assert len(await store.read(cell_runs(run, "c2"))) == 1
    assert await store.read(tabs["t"].panes["a"].restart) == ""


async def test_restart_cell_with_no_cell_run_yet_adds_one(store):
    run = await pane_on(store, run=True, started=True, running=("c2",))
    (other,) = await store.read(cell_runs(run, "c2"))
    await store.run(web.restart_cell("t", "c1"))
    (new,) = await store.read(cell_runs(run, "c1"))
    row = await store.read(Space.exec.cell_runs[new].extract())
    assert row["plane_run"] == run and row["by"] == "web"
    # Nothing was interrupted, no restart asked.
    assert (await store.read(Space.exec.cell_runs[other].extract())).get("interrupt_at") is None
    assert await store.read(tabs["t"].panes["a"].restart) == ""


async def test_restart_cell_in_a_run_not_started_does_nothing(store):
    run = await pane_on(store, run=True)
    await store.run(web.restart_cell("t", "c1"))
    assert await store.read(cell_runs(run, "c1")) == []
    assert await store.read(tabs["t"].panes["a"].restart) == ""


async def test_restart_cell_with_no_live_run_restarts_the_pane(store):
    await pane_on(store)
    await store.run(web.restart_cell("t", "c1"))
    token = await store.read(tabs["t"].panes["a"].restart)
    assert token != ""
    await store.run(web.restart_cell("t", "c2"))
    assert await store.read(tabs["t"].panes["a"].restart) not in ("", token)


async def test_restart_cell_on_an_ended_run_restarts_the_pane(store):
    run = await pane_on(store, run=True, started=True, ended=True)
    before = await store.read(cell_runs(run, "c1"))
    await store.run(web.restart_cell("t", "c1"))
    assert await store.read(tabs["t"].panes["a"].restart) != ""
    assert await store.read(cell_runs(run, "c1")) == before


async def test_restart_cell_raises(store):
    await pane_on(store)
    await plane(store, "b")
    await do(store, nuspace.cell.add("b", "x = 1", id="cb", fabrics=[]))
    with pytest.raises(Missing):
        await store.run(web.restart_cell("t", "ghost"))
    with pytest.raises(Missing):
        await store.run(web.restart_cell("t", "cb"))
    with pytest.raises(Missing):
        await store.run(web.restart_cell("nope", "c1"))
    await do(store, nuspace.cell.remove("c2"))
    with pytest.raises(Removed):
        await store.run(web.restart_cell("t", "c2"))
    assert await store.read(tabs["t"].panes["a"].restart) == ""


async def test_expand_and_collapse_fold(store):
    await do(store, web.open_tab("t"))
    await do(store, web.expand("t", "a"))
    await do(store, web.expand("t", "a"))
    assert await store.read(tabs["t"].expanded.extract()) == {"a": True}
    await do(store, web.collapse("t", "a"))
    await do(store, web.collapse("t", "a"))
    assert await store.read(tabs["t"].expanded.extract()) == {}
    with pytest.raises(Missing):
        await do(store, web.expand("nope", "a"))


# --- A cell on a pane ---------------------------------------------------------------------


async def test_params_read_the_running_cells_own_pane(store):
    await plane(store, "a")
    await do(store, web.open_tab("t"))
    await do(store, web.set_panes("t", ["a"]))
    await do(store, web.set_pane_params("t", "a", {"id": "42"}))
    run = await store.made(
        nuspace.atomic(nuspace.plane_run.add("a", envs=[["session", "t"]], into=_made()))
    )
    got = await store.run(inside(nuspace.atomic(web.params()), plane="a", plane_run=run))
    assert got == {"id": "42"}


async def test_params_are_empty_for_a_run_on_no_tab(store):
    await plane(store, "a")
    run = await store.made(nuspace.atomic(nuspace.plane_run.add("a", into=_made())))
    got = await store.run(inside(nuspace.atomic(web.params()), plane="a", plane_run=run))
    assert got == {}


async def test_on_params_hears_params_move_without_a_rerun(store):
    """Params are data: the store moves, a cell listening reads the new ones."""
    await plane(store, "a")
    await do(store, web.open_tab("t"))
    await do(store, web.set_panes("t", ["a"]))
    await do(store, web.set_pane_params("t", "a", {"id": "42"}))
    run = await store.made(
        nuspace.atomic(nuspace.plane_run.add("a", envs=[["session", "t"]], into=_made()))
    )
    seen = nu.WaitUntil(
        nuspace.atomic(web.on_params()), nuspace.atomic(web.params() == {"id": "43"})
    )
    waiting = asyncio.create_task(store.run(inside(seen, plane="a", plane_run=run)))
    await asyncio.sleep(0.1)
    assert not waiting.done()
    await do(store, web.set_pane_params("t", "a", {"id": "43"}))
    await asyncio.wait_for(waiting, 3.0)


def _made():
    from _support.made import MADE

    return MADE


async def test_href_encodes_like_the_browser():
    got, _ = await nu.arun(web.href("p 1", {"q": "a b", "gone": None}))
    assert got == "/p%201?q=a+b" or got == "/p%201?q=a%20b"


#: nu's shared query cases, the ones the browser's encoder is checked against too.
FIXTURES = Path(__file__).resolve().parents[3] / "nu" / "tests" / "fixtures" / "query.json"


def _encode_cases() -> list[dict]:
    return json.loads(FIXTURES.read_text())["encode"] if FIXTURES.exists() else []


@pytest.mark.skipif(not FIXTURES.exists(), reason="no nu checkout beside nuspace")
@pytest.mark.parametrize("case", _encode_cases())
async def test_href_query_is_nus_encoding(case):
    got, _ = await nu.arun(web.href("p", case["query"]))
    assert got == ("/p?" + case["string"] if case["string"] else "/p")


class _Recording:
    """A session that keeps the frames it is sent."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


async def _drawn(store, term) -> dict:
    session = _Recording()
    await nu.arun(nuspace.atomic(term), store.ctx.bind(Session, session))
    return {f.ref: f.payload for f in session.frames}


async def test_link_draws_title_and_icon(store):
    await plane(store, "a", name="Movies", icon="emoji:🎬")
    await plane(store, "b")
    got = await _drawn(store, web.link(nustd.ui.PageLinkRef("l"), "a", params={"id": "1"}))
    assert got[("l",)]["href"] == "/a?id=1" and got[("l",)]["title"] == "Movies"
    got = await _drawn(store, web.link(nustd.ui.LinkRef("k"), "b"))
    assert got[("k",)] == {"href": "/b", "label": "b"}
    page = web.link(nustd.ui.PageLinkRef("n"), "a", description="Daily")
    got = await _drawn(store, page)
    assert got[("n",)] == {"href": "/a", "title": "Movies", "icon": "🎬", "description": "Daily"}
    with pytest.raises(TypeError):
        web.link(nustd.ui.TextRef("t"), "a")


async def test_link_to_a_plane_not_there_still_draws(store):
    got = await _drawn(store, web.link(nustd.ui.LinkRef("k"), "nowhere", label="Gone"))
    assert got[("k",)] == {"href": "/nowhere", "label": "Gone"}
    got = await _drawn(store, web.link(nustd.ui.PageLinkRef("l"), "nowhere"))
    assert got[("l",)]["title"] == "nowhere"


async def test_root_is_never_a_pane(store):
    await do(store, web.open_tab("t"))
    with pytest.raises(Missing):
        await do(store, web.set_panes("t", [ROOT]))
    assert is_null(await store.read(Space.planes[ROOT].removed_at))
