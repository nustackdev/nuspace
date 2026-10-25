"""Search: the op, the search's own cell, the viewer's three cells, and one search run on a worker."""

from __future__ import annotations

import pytest
from _support.contents import NoteContent, PlainContent, write
from _support.kernel import ended, opened

import nu
import nustd.kv
from nuspace import ops
from nuspace.content import CELL, PLANE, SPACE
from nuspace.shapes import PlaneState, Reroot, Space, States
from nuspace.system import search
from nuspace.system.devices.web.env import session_env
from nuspace.system.home import seed, seeded_id
from nuspace.system.kernel.body import Rewrites
from nustd.ui import Session


S = search.Search

NOTE = "testing.Note"
PLAIN = "testing.Plain"


def _state(plane_id: str, term: nu.Nu) -> nu.Nu:
    return ops.plane_state(plane_id, term)


async def _hits(store, plane_id: str) -> list[dict]:
    hits = _state(plane_id, S.hits)
    return await store.read(nu.If(hits.exists(), hits.extract(), nu.Literal([])))


async def _addresses(store, plane_id: str) -> list[tuple]:
    return [(h["kind"], tuple(h["scope"]), h["id"]) for h in await _hits(store, plane_id)]


async def _finished(store, plane_id: str) -> bool:
    return await store.read(_state(plane_id, S.finished_at).exists())


async def _searched(store, request, **kwargs: object) -> str:
    """Search through ``store``. The new search is the newest child of ``SEARCHES``."""
    await store.run(search.search(request, **kwargs))
    return (await store.read(ops.children(search.SEARCHES)))[-1]


def _loaded(plane: str, cell: str) -> nu.Nu:
    """A cell's prog loaded as the kernel loads it: read in a snapshot, rerooted under it."""
    rewrite = Rewrites(Reroot(plane, cell))
    prog = Space.cells[cell].prog
    return nustd.kv.Snapshot(
        prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite), scope=Space
    )


async def _run_search(store, plane_id: str) -> None:
    """The search's own cell, run to its end on this store."""
    (cell,) = await store.read(ops.cells(plane_id))
    term = await store.run(_loaded(plane_id, cell))
    await store.run(term)


async def _garden(store) -> None:
    """Notes in two cells, on a plane and in the space, and plain items beside them."""
    await store.run(
        write(NoteContent, (CELL, "c1"), "a", body="Tomato needs sun", stars=4.0)
        >> write(NoteContent, (CELL, "c1"), "b", body="Basil", stars=1.0, done=True)
        >> write(NoteContent, (CELL, "c2"), "a", body="Buy TOMATO seeds", stars=2.0)
        >> write(NoteContent, (PLANE, "p1"), "t", body="Tomato plan", stars=5.0, done=True)
        >> write(NoteContent, (SPACE, ""), "r", body="Read me")
        >> write(PlainContent, (CELL, "c1"), "z", body="tomato, plainly")
    )


# --- The op -----------------------------------------------------------------------------


async def test_search_makes_a_plane_under_searches_and_starts_its_run(store):
    request = {NOTE: {"text": "tomato"}}
    pid = await _searched(store, request)
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    parent = rows[search.SEARCHES]
    assert parent["name"] == "Searches"
    assert parent["props"]["system"] is True and parent["props"]["ui"] is False
    assert rows[pid]["name"] == "Note: tomato"
    assert rows[pid]["props"]["ui"] is False and rows[pid]["parent"] == search.SEARCHES
    assert (parent["props"]["backend"], rows[pid]["props"]["backend"]) == ("mp", "mp")

    (cell,) = await store.read(ops.cell_rows(pid))
    assert cell["name"] == search.CELL
    assert cell["prog"] == search.source(request)
    assert cell["props"] == {"made_by": "", "has_ui": False}

    state = await store.read(States.planes[pid].state.extract())
    assert state["request"] == request
    assert state["started_at"] > 0
    assert "finished_at" not in state

    (run,) = await store.read(ops.runs(pid))
    assert run["by"] == search.BY

    # A second search, its request a term: the parent is kept, the new one listed after.
    again = await _searched(store, nu.Literal({PLAIN: {}}))
    assert await store.read(ops.children(search.SEARCHES)) == [pid, again]
    (cell,) = await store.read(ops.cell_rows(again))
    assert cell["prog"] == search.source({PLAIN: {}})
    assert await store.read(ops.plane_title(again)) == "Plain note: all"


def test_describe_says_what_was_asked():
    assert search.describe({NOTE: {"text": "tomato", "min_stars": 3.0, "done": True}}) == (
        "Note: tomato, min_stars 3.0, done"
    )
    assert search.describe({NOTE: {}, PLAIN: {}}) == "Note: all; Plain note: all"
    assert search.describe({}) == "Nothing asked"


# --- The search's cell --------------------------------------------------------------------


async def test_the_cell_walks_cells_then_planes_then_the_space(store):
    await _garden(store)
    pid = await _searched(store, {NOTE: {"text": "tomato"}})
    await _run_search(store, pid)
    assert await _addresses(store, pid) == [
        (NOTE, (CELL, "c1"), "a"),
        (NOTE, (CELL, "c2"), "a"),
        (NOTE, (PLANE, "p1"), "t"),
    ]
    assert await _finished(store, pid)


async def test_keywords_left_out_stay_unset(store):
    await _garden(store)
    everything = await _searched(store, {NOTE: {}})
    await _run_search(store, everything)
    assert len(await _hits(store, everything)) == 5

    stars = await _searched(store, {NOTE: {"min_stars": 2.0}})
    await _run_search(store, stars)
    assert [a[1:] for a in await _addresses(store, stars)] == [
        ((CELL, "c1"), "a"),
        ((CELL, "c2"), "a"),
        ((PLANE, "p1"), "t"),
    ]

    both = await _searched(store, {NOTE: {"text": "tomato", "done": True}})
    await _run_search(store, both)
    assert [a[1:] for a in await _addresses(store, both)] == [((PLANE, "p1"), "t")]


async def test_kinds_are_searched_each_on_their_own(store):
    await _garden(store)
    pid = await _searched(store, {PLAIN: {}, NOTE: {"text": "basil"}})
    await _run_search(store, pid)
    assert await _addresses(store, pid) == [
        (PLAIN, (CELL, "c1"), "z"),
        (NOTE, (CELL, "c1"), "b"),
    ]


async def test_an_unknown_kind_or_keyword_is_passed_by_and_the_search_finishes(store):
    await _garden(store)
    pid = await _searched(store, {"nowhere.Gone": {}, NOTE: {"text": "basil", "colour": "red"}})
    await _run_search(store, pid)
    assert await _addresses(store, pid) == [(NOTE, (CELL, "c1"), "b")]
    assert await _finished(store, pid)


async def test_items_of_a_removed_cell_are_no_longer_found(store):
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", "", cell_id="c1"))
    await _garden(store)
    await store.run(ops.remove_cell("c1"))
    pid = await _searched(store, {NOTE: {"text": "tomato"}})
    await _run_search(store, pid)
    assert [a[1] for a in await _addresses(store, pid)] == [(CELL, "c2"), (PLANE, "p1")]


# --- The viewer ------------------------------------------------------------------------------


class _Recording:
    """A session that keeps the frames it is sent instead of sending them, and answers reads."""

    def __init__(self, values: dict | None = None) -> None:
        self.frames: list = []
        self.values = values or {}

    async def send(self, frame: object) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        return self.values.get(tuple(path), nu.lang.EMPTY)


async def _frames(store, source: str, cell: str, build, values: dict | None = None) -> list[tuple]:
    """``build(namespace)`` from a viewer cell's source, run as the kernel would run it there.

    Yields ``(ref path, payload)`` in order, ``None`` for an erase.
    """
    namespace: dict = {}
    exec(compile(source, cell, "exec"), namespace)  # noqa: S102
    term = Rewrites(Reroot(search.PLANE, seeded_id(search.PLANE, cell)))(build(namespace))
    session = _Recording(values)
    await nu.arun(term, store.ctx.bind(Session, session))
    return [
        (frame.ref, None if frame.op == "remove" else frame.payload) for frame in session.frames
    ]


async def _draw(store, source: str, cell: str, build, values: dict | None = None) -> dict:
    """:func:`_frames` as ``{ref path: payload}``, the last write to a path winning."""
    return dict(await _frames(store, source, cell, build, values))


class _Chosen(PlaneState):
    """The viewer's own state, as its cells declare it."""

    picked = nustd.kv.StrRef.slot()
    newest = nustd.kv.StrRef.slot()
    shown = nustd.kv.StrRef.slot()


async def test_the_viewer_is_seeded_once_unpinned(store):
    await store.run(search.ensure_search() >> search.ensure_search())
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == search.PLANE]
    assert row["name"] == "Search"
    assert row["props"]["system"] is True and row["props"]["ui"] is True
    assert row["props"]["backend"] == "async"
    cells = await store.read(ops.cell_rows(search.PLANE))
    assert [c["name"] for c in cells] == ["form", "pick", "results"]
    assert all(c["props"]["has_ui"] for c in cells)
    assert search.PLANE not in await store.read(ops.pinned())


async def test_a_viewer_seeded_before_content_gets_its_form_and_new_results(store):
    old = (("pick", search.PICK), ("results", "def out():\n    return None\n"))
    await store.run(seed(search.PLANE, search.NAME, search.ICON, old, backend="async", pin=False))
    await store.run(search.ensure_search())
    cells = await store.read(ops.cell_rows(search.PLANE))
    assert [c["name"] for c in cells] == ["form", "pick", "results"]
    assert cells[0]["prog"] == search.FORM and cells[2]["prog"] == search.RESULTS

    # Once it has a form, the owner's edits stay.
    await store.run(ops.set_prog(seeded_id(search.PLANE, "results"), "edited"))
    await store.run(search.ensure_search())
    assert await store.read(ops.prog(seeded_id(search.PLANE, "results"))) == "edited"


@pytest.mark.parametrize("cell", search.CELLS, ids=lambda c: c[0])
async def test_each_viewer_cell_loads_through_the_kernel_rewrites(store, cell):
    name, source = cell
    await store.run(ops.add_plane("v", backend="async") >> ops.add_cell("v", source, cell_id=name))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("v", name), env.rewrite)
    prog = Space.cells[name].prog
    term = await store.run(
        nustd.kv.Snapshot(
            prog.load(scope={"plane": "v", "cell": name}, rewrite=rewrite), scope=Space
        )
    )
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


def test_the_viewer_reads_every_installed_kind_off_the_registry():
    kinds = search.kinds()
    assert kinds[PLAIN] == {"label": "Plain note", "fields": []}
    assert kinds[NOTE] == {
        "label": "Note",
        "fields": [
            {"name": "text", "input": "text", "label": "Text"},
            {"name": "min_stars", "input": "number", "label": "Min stars"},
            {"name": "done", "input": "switch", "label": "Done"},
        ],
    }


@pytest.fixture
def ours(monkeypatch):
    """The viewer offers the tests' kinds only, not every other installed one."""
    every = search.kinds()
    kept = {name: kind for name, kind in every.items() if name in (NOTE, PLAIN)}
    monkeypatch.setattr(search, "kinds", lambda: kept)


@pytest.mark.usefixtures("ours")
async def test_the_form_offers_the_installed_kinds_and_the_picked_ones_fields(store):
    frames = await _frames(store, search.FORM, "form", lambda ns: ns["draw"]())
    got = dict(frames)
    assert got[("head", "kind")] == NOTE
    options = next(p for r, p in frames if r == ("head", "kind"))
    assert options == {
        "options": [{"value": NOTE, "label": "Note"}, {"value": PLAIN, "label": "Plain note"}]
    }
    assert got[("fields", "f_text", "label")] == "Text"
    assert got[("fields", "f_text", "text")] == ""
    assert got[("fields", "f_min_stars", "label")] == "Min stars"
    assert got[("fields", "f_min_stars", "number")] == ""
    assert got[("fields", "f_done", "switch")] is False
    assert ("fields", "f_done", "text") not in got


async def test_the_forms_button_makes_a_search_of_what_was_filled_in(store):
    values = {
        ("head", "kind"): NOTE,
        ("fields", "f_text", "text"): "  tomato ",
        ("fields", "f_min_stars", "number"): "",
        ("fields", "f_done", "switch"): True,
    }
    await _frames(store, search.FORM, "form", lambda ns: ns["go"](), values)
    (pid,) = await store.read(ops.children(search.SEARCHES))
    assert await store.read(_state(pid, S.request)) == {NOTE: {"text": "tomato", "done": True}}
    assert await store.read(ops.plane_title(pid)) == "Note: tomato, done"

    stars = {**values, ("fields", "f_text", "text"): "", ("fields", "f_min_stars", "number"): "3"}
    await _frames(store, search.FORM, "form", lambda ns: ns["go"](), stars)
    newest = (await store.read(ops.children(search.SEARCHES)))[-1]
    assert await store.read(_state(newest, S.request)) == {NOTE: {"min_stars": 3.0, "done": True}}


async def test_pick_lists_searches_newest_first_and_shows_the_newest(store):
    await store.run(search.ensure_search())
    old = await _searched(store, {NOTE: {}}, name="old")
    new = await _searched(store, {NOTE: {}}, name="new")
    got = await _frames(
        store, search.PICK, "pick", lambda ns: nu.Frame(ns["Seen"], ns["draw"](), ids=[])
    )
    select = [payload for ref, payload in got if ref == ("pick", "search")]
    assert select == [
        {"options": [{"value": new, "label": "new"}, {"value": old, "label": "old"}]},
        new,
    ]
    assert await store.read(ops.plane_state(search.PLANE, _Chosen.shown)) == new


async def test_results_draw_each_hit_with_its_kinds_render_hit(store):
    await store.run(
        ops.add_plane("p1", name="Garden", ui=True, backend="async")
        >> ops.add_cell("p1", "", cell_id="c1")
        >> ops.add_cell("p1", "", cell_id="c2")
    )
    await _garden(store)
    pid = await _searched(store, {NOTE: {"text": "tomato"}, PLAIN: {}})
    await _run_search(store, pid)
    got = await _draw(store, search.RESULTS, "results", lambda ns: ns["shown"](nu.Str(pid)))
    assert got[("title",)]["label"] == "Results for “Note: tomato; Plain note: all”"
    assert got[("status",)] == "Done: 4 hits"
    # A cell's item opens its cell's plane, a plane's its plane.
    assert got[("hits", "h0", "head", "link")] == {"href": "/p1", "label": "Garden"}
    assert got[("hits", "h0", "head", "kind")]["label"] == "Note"
    assert got[("hits", "h0", "item", "body")] == "Tomato needs sun"
    assert got[("hits", "h1", "head", "link")] == {"href": "/p1", "label": "Garden"}
    assert got[("hits", "h1", "item", "body")] == "Buy TOMATO seeds"
    assert got[("hits", "h2", "head", "link")] == {"href": "/p1", "label": "Garden"}
    # A kind that draws nothing draws nothing, under its head.
    assert got[("hits", "h3", "head", "kind")]["label"] == "Plain note"
    assert ("hits", "h3", "item", "body") not in got
    assert got[("empty",)] is None


async def test_results_say_when_nothing_was_found_or_searched(store):
    pid = await _searched(store, {NOTE: {"text": "zzz"}})
    await _run_search(store, pid)
    got = await _draw(store, search.RESULTS, "results", lambda ns: ns["shown"](nu.Str(pid)))
    assert got[("status",)] == "Done: 0 hits"
    assert got[("empty",)]["label"] == "Nothing found"
    none = await _draw(store, search.RESULTS, "results", lambda ns: ns["none"]())
    assert none[("empty",)]["label"] == "No searches yet"


# --- On a worker ---------------------------------------------------------------------------


async def test_a_search_runs_on_a_worker_and_its_run_ends():
    space = await opened(spares=1)
    try:
        await space.run(write(NoteContent, (CELL, "c"), "x", body="ripe tomato"))
        pid = await _searched(space, {NOTE: {"text": "tomato"}})
        (run,) = await space.read(ops.runs(pid))
        row = await space.run_row(run["id"], ended, 20.0)
        assert row["exit"] == "ok", row
        assert await _addresses(space, pid) == [(NOTE, (CELL, "c"), "x")]
        assert await _finished(space, pid)
    finally:
        await space.close()
