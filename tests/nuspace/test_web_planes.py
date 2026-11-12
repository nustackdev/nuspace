"""The web planes the device ships with: home, settings, search, their cells, and the search op.

A cell's prog is run here the way a program is: its module built, then its
``draw`` (or ``out``) evaluated against the store with a recording session
bound, so what it would draw is read off the frames it sends.
"""

from __future__ import annotations

import asyncio

import pytest
from _support.contents import NoteContent, PlainContent, write
from _support.made import MADE

import nu
import nuspace
import nuspace.web as web
import nustd.kv
from nuspace.places import inside
from nuspace.shapes import Space
from nuspace.shapes.content import CELL, PLANE, SPACE, address
from nuspace.web import home
from nuspace.web.planes import ensure, search, settings
from nustd.ui import Session


NOTE = "testing.Note"
PLAIN = "testing.Plain"


async def do(store, term):
    return await store.run(nuspace.atomic(term))


class _Notify:
    """A browser notify nobody fires: the subscription a cell's arm opens."""

    def __init__(self) -> None:
        self.callbacks: list = []

    def bind(self, cb) -> None:
        self.callbacks.append(cb)

    def unbind(self, cb) -> None:
        self.callbacks = [c for c in self.callbacks if c is not cb]

    def close(self) -> None:
        self.callbacks = []


class _Recording:
    """A session that keeps the frames it is sent, answers reads off ``values`` and subscribes."""

    def __init__(self, values: dict | None = None) -> None:
        self.frames: list = []
        self.values = values or {}
        self.notifies: dict = {}

    async def send(self, frame: object) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        return self.values.get(tuple(path), nu.lang.NULL)

    def subscribe(self, path: tuple[str, ...]) -> _Notify:
        return self.notifies.setdefault(tuple(path), _Notify())

    def last(self, ref: tuple) -> object:
        """The last payload sent to ``ref``, None when none or an erase."""
        for frame in reversed(self.frames):
            if frame.ref == ref:
                return None if frame.op == "remove" else frame.payload
        return None


def _built(source: str) -> dict:
    namespace: dict = {}
    exec(compile(source, "cell", "exec"), namespace)  # noqa: S102
    return namespace


async def _framed(store, term: nu.Nu, values: dict | None = None) -> list[tuple]:
    """One draw, in order: ``(ref path, payload)``, ``None`` for an erase."""
    session = _Recording(values)
    await nu.arun(term, store.ctx.bind(Session, session))
    return [(f.ref, None if f.op == "remove" else f.payload) for f in session.frames]


async def _frames(store, term: nu.Nu, values: dict | None = None) -> dict:
    """One draw: ``{ref path: payload}``, the last write to a path winning."""
    return dict(await _framed(store, term, values))


async def _live(store, term: nu.Nu) -> tuple[_Recording, asyncio.Task]:
    """``term`` running against the store, drawing into a recording session."""
    session = _Recording()
    task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, session)))
    await asyncio.sleep(0)
    return session, task


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def _until(check, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def _quiet(session: _Recording, seconds: float = 1.0) -> int:
    """Frames after ``seconds`` with nothing written."""
    await asyncio.sleep(seconds)
    return len(session.frames)


ALL_CELLS = [*home.CELLS, *settings.CELLS, *search.CELLS]


@pytest.mark.parametrize("cell", ALL_CELLS, ids=lambda c: c[0])
def test_each_cell_builds_and_validates(cell):
    _, source = cell
    out = _built(source)["out"]
    term = inside(out(), plane="home", cell="home_x")
    nu.validate(nu.compile(term))


async def test_settings_draws_the_space_versions_and_nav(store):
    await store.run(ensure())
    await do(store, Space.info.path.set("/tmp/garden") >> Space.info.opened_at.set(1.0))
    drawn = list((await _frames(store, settings.draw())).values())
    assert "garden" in drawn and "/tmp/garden" in drawn
    assert settings.VERSIONS["nuspace"] in drawn
    assert {"ts": 1000.0, "mode": "duration"} in drawn
    links = [p for p in drawn if isinstance(p, dict) and "href" in p]
    assert [p["title"] for p in links if "description" in p] == ["Home", "Search", "Settings"]
    assert {p["href"] for p in links} >= {settings.DOCS, settings.SOURCE}
    assert {"keys": ["mod", ","]} in drawn


async def test_settings_leaves_out_a_role_not_set(store):
    await store.run(ensure())
    await do(store, web.Web.roles.set_item("search", ""))
    frames = await _framed(store, settings.draw())
    links = [p for _, p in frames if isinstance(p, dict) and "description" in p]
    assert {p["title"] for p in links} == {"Home", "Settings"}
    assert any(p is None for _, p in frames)  # the search row erased


async def test_ensure_then_home_is_a_system_web_plane(store):
    await store.run(ensure())
    home_plane = await store.read(web.Web.roles["home"])
    assert await store.read(web.Web.planes[home_plane].editable) is True
    with pytest.raises(nuspace.errors.Refused):
        await do(store, nuspace.plane.remove(home_plane))
    with pytest.raises(nuspace.errors.Refused):
        await do(store, nuspace.plane.add("searches", backend="async"))
    # The role names are no reserved ids any more: a user plane may take one.
    await do(store, nuspace.plane.add("home", backend="async"))


# --- Search ---------------------------------------------------------------------------


async def _garden(store) -> None:
    """Notes in two cells, on a plane and in the space, and plain items beside them."""
    await do(store, nuspace.plane.add("p1", backend="async"))
    for c in ("c1", "c2"):
        await do(store, nuspace.cell.add("p1", "x = 1", id=c, fabrics=[]))
    await store.run(
        write(NoteContent, (CELL, "c1"), "a", body="Tomato needs sun", stars=4.0)
        >> write(NoteContent, (CELL, "c1"), "b", body="Basil", stars=1.0, done=True)
        >> write(NoteContent, (CELL, "c2"), "a", body="Buy TOMATO seeds", stars=2.0)
        >> write(NoteContent, (PLANE, "p1"), "t", body="Tomato plan", stars=5.0, done=True)
        >> write(NoteContent, (SPACE, ""), "r", body="Read me")
        >> write(PlainContent, (CELL, "c1"), "z", body="tomato, plainly")
    )


async def _searched(store, request, **kwargs: object) -> str:
    await store.run(ensure())
    await store.run(search.search(request, into=MADE, **kwargs))
    return await store.run(MADE)


async def _hits(store, pid: str) -> list[tuple]:
    hits = nuspace.at.plane(id=pid).state(search.Search).hits
    got = await store.read(nu.If(hits.exists(), hits.extract(), nu.Literal([])))
    return [(h["kind"], tuple(h["scope"]), h["key"]) for h in got]


async def _run(store, pid: str) -> None:
    """The search's own cell, run to its end on this store, as its run would."""
    (cell,) = await store.read(nu.list(Space.planes[pid].cells.keys()))
    source = await store.read(Space.cells[cell].prog)
    out = _built(source)["out"]
    await store.run(inside(out(), plane=pid, cell=cell))


def test_describe_says_what_was_asked():
    assert search.describe({NOTE: {"text": "tomato", "min_stars": 3.0, "done": True}}) == (
        "Note: tomato, min_stars 3.0, done"
    )
    assert search.describe({NOTE: {}, PLAIN: {}}) == "Note: all; Plain note: all"
    assert search.describe({}) == "Nothing asked"


async def test_search_makes_a_plane_under_searches_its_state_and_its_run(store):
    request = {NOTE: {"text": "tomato"}}
    pid = await _searched(store, request)
    row = await store.read(Space.planes[pid].extract())
    assert row["parent"] == search.SEARCHES and row["name"] == "Note: tomato"
    assert row["backend"] == search.SEARCHES_BACKEND
    assert await store.read(web.Web.planes.contains(pid)) is False
    (cell,) = await store.read(nu.list(Space.planes[pid].cells.keys()))
    assert await store.read(Space.cells[cell].prog) == search.source(request)
    state = nuspace.at.plane(id=pid).state(search.Search)
    assert await store.read(state.request) == request
    assert await store.read(nuspace.plane_run.any_live(pid)) is True


async def test_the_cell_walks_cells_then_planes_then_the_space(store):
    await _garden(store)
    pid = await _searched(store, {NOTE: {"text": "tomato"}})
    await _run(store, pid)
    assert await _hits(store, pid) == [
        (NOTE, (CELL, "c1"), "a"),
        (NOTE, (CELL, "c2"), "a"),
        (NOTE, (PLANE, "p1"), "t"),
    ]
    state = nuspace.at.plane(id=pid).state(search.Search)
    assert await store.read(state.finished_at.exists()) is True


async def test_items_of_a_removed_cell_are_not_found(store):
    await _garden(store)
    await do(store, nuspace.cell.remove("c2"))
    pid = await _searched(store, {NOTE: {"text": "tomato"}})
    await _run(store, pid)
    assert (NOTE, (CELL, "c2"), "a") not in await _hits(store, pid)


async def test_an_unknown_kind_is_passed_by_and_the_search_finishes(store):
    pid = await _searched(store, {"nobody.Kind": {"x": 1}})
    await _run(store, pid)
    assert await _hits(store, pid) == []
    state = nuspace.at.plane(id=pid).state(search.Search)
    assert await store.read(state.finished_at.exists()) is True


async def test_keywords_left_out_stay_unset(store):
    await _garden(store)
    everything = await _searched(store, {NOTE: {}})
    await _run(store, everything)
    assert len(await _hits(store, everything)) == 5
    stars = await _searched(store, {NOTE: {"min_stars": 2.0}})
    await _run(store, stars)
    assert [h[1:] for h in await _hits(store, stars)] == [
        ((CELL, "c1"), "a"),
        ((CELL, "c2"), "a"),
        ((PLANE, "p1"), "t"),
    ]
    both = await _searched(store, {NOTE: {"text": "tomato", "done": True}})
    await _run(store, both)
    assert [h[1:] for h in await _hits(store, both)] == [((PLANE, "p1"), "t")]


async def test_kinds_are_searched_each_on_their_own(store):
    await _garden(store)
    pid = await _searched(store, {PLAIN: {}, NOTE: {"text": "basil"}})
    await _run(store, pid)
    assert await _hits(store, pid) == [(PLAIN, (CELL, "c1"), "z"), (NOTE, (CELL, "c1"), "b")]


# --- The search viewer's cells ------------------------------------------------------------


class _Chosen(nu.Shape):
    """The viewer plane's own state, as its pick and results cells declare it."""

    picked = nustd.kv.StrRef.slot()
    newest = nustd.kv.StrRef.slot()
    shown = nustd.kv.StrRef.slot()


#: The viewer plane these tests run its cells in: its id is minted in a space.
VIEWER = "p_search"

CHOSEN = nuspace.at.plane(id=VIEWER).state(_Chosen)

# Where the viewer's cells draw, as the browser is sent it.
FORM_KIND = ("ask", "0", "0")
FORM_MAIN = ("ask", "0", "1")
FORM_MORE = ("ask", "1")
PICK_SELECT = ("head", "1")
RESULTS_STATE = ("results", "0", "0")
RESULTS_COUNT = ("results", "0", "1")
RESULTS_EMPTY = ("results", "1")
RESULTS_HITS = ("results", "3")


def _viewer(source: str, call: str, *args: object) -> nu.Nu:
    """A viewer cell's ``call``, built from its source and run in the viewer plane."""
    term = _built(source)[call](*args)
    return inside(term, plane=VIEWER, cell=f"{VIEWER}_x")


@pytest.fixture
def ours(monkeypatch):
    """The viewer offers the tests' kinds only, not every other installed one."""
    kept = {name: kind for name, kind in search.kinds().items() if name in (NOTE, PLAIN)}
    monkeypatch.setattr(search, "kinds", lambda: kept)


@pytest.mark.usefixtures("ours")
async def test_the_form_offers_the_kinds_and_the_picked_ones_fields(store):
    await store.run(ensure())
    framed = await _framed(store, _viewer(search.FORM, "draw"))
    got = dict(framed)
    options = next(p for r, p in framed if r == FORM_KIND)
    assert options == {
        "options": [{"value": NOTE, "label": "Note"}, {"value": PLAIN, "label": "Plain note"}]
    }
    assert got[FORM_KIND] == NOTE
    # The note's first text keyword is the bar's own input, the rest are filters under it.
    assert got[(*FORM_MAIN, "0")] == ""
    assert got[(*FORM_MORE, "0", "min_stars", "control")] == ""
    assert got[(*FORM_MORE, "0", "done", "control")] is False
    # A kind that asks nothing says so in the bar.
    assert got[(*FORM_MAIN, "1")] == "Asks nothing: lists every item"


async def test_the_form_says_so_when_no_kind_is_installed(store, monkeypatch):
    monkeypatch.setattr(search, "kinds", dict)
    await store.run(ensure())
    got = await _frames(store, _viewer(search.FORM, "out"))
    # The empty state is drawn as declared, and the bar never is.
    assert ("ask", "2") in got
    assert FORM_KIND not in got


@pytest.mark.usefixtures("ours")
async def test_the_forms_button_makes_a_search_of_what_was_filled_in(store):
    await store.run(ensure())
    values = {
        FORM_KIND: NOTE,
        (*FORM_MAIN, "0"): "  tomato ",
        (*FORM_MORE, "0", "min_stars", "control"): "",
        (*FORM_MORE, "0", "done", "control"): True,
    }
    await _framed(store, _viewer(search.FORM, "go"), values)
    kids = Space.planes[search.SEARCHES].children
    (pid,) = await store.read(nu.list(kids.keys()))
    state = nuspace.at.plane(id=pid).state(search.Search)
    assert await store.read(state.request) == {NOTE: {"text": "tomato", "done": True}}
    assert await store.read(nuspace.plane.title(pid)) == "Note: tomato, done"
    stars = {
        **values,
        (*FORM_MAIN, "0"): "",
        (*FORM_MORE, "0", "min_stars", "control"): "3",
    }
    await _framed(store, _viewer(search.FORM, "go"), stars)
    newest = (await store.read(nu.list(kids.keys())))[-1]
    newest_state = nuspace.at.plane(id=newest).state(search.Search)
    assert await store.read(newest_state.request) == {NOTE: {"min_stars": 3.0, "done": True}}


async def test_pick_lists_searches_newest_first_and_shows_the_newest(store):
    old = await _searched(store, {NOTE: {}}, name="old")
    new = await _searched(store, {NOTE: {}}, name="new")
    framed = await _framed(store, _viewer(search.PICK, "draw"))
    select = [payload for ref, payload in framed if ref == PICK_SELECT]
    assert select == [
        {"options": [{"value": new, "label": "new"}, {"value": old, "label": "old"}]},
        new,
    ]
    assert await store.read(CHOSEN.shown) == new


async def test_pick_lists_nothing_before_any_search(store):
    await store.run(ensure())
    framed = await _framed(store, _viewer(search.PICK, "draw"))
    select = [payload for ref, payload in framed if ref == PICK_SELECT]
    assert select == [{"options": []}, ""]


async def test_pick_follows_a_search_made_while_it_runs(store):
    old = await _searched(store, {NOTE: {}}, name="old")
    session, task = await _live(store, _viewer(search.PICK, "out"))

    def options() -> list:
        sent = [f.payload for f in session.frames if f.ref == PICK_SELECT]
        return [p["options"] for p in sent if isinstance(p, dict)]

    try:
        await _until(lambda: options() and options()[-1] == [{"value": old, "label": "old"}])
        new = await _searched(store, {NOTE: {}}, name="new")
        await _until(lambda: [o["value"] for o in options()[-1]] == [new, old])
        await _until(lambda: session.last(PICK_SELECT) == new)
        assert not task.done()
        assert await store.read(CHOSEN.shown) == new
    finally:
        await _stop(task)


async def test_results_follow_hits_as_they_land_and_end_once_done(store):
    await _garden(store)
    pid = await _searched(store, {NOTE: {"text": "tomato"}})
    session, task = await _live(store, _viewer(search.RESULTS, "shown", nu.Str(pid)))
    state = nuspace.at.plane(id=pid).state(search.Search)
    try:
        await _until(lambda: session.last(RESULTS_COUNT) == "0 hits")
        assert session.last(RESULTS_STATE) == {"label": "Searching", "tone": "info"}
        assert not task.done()
        await do(store, state.hits.append(address(NoteContent, (CELL, "c1"), "a")))
        await _until(lambda: session.last(RESULTS_COUNT) == "1 hit")
        await do(store, state.finished_at.set(1.0))
        await asyncio.wait_for(task, 3.0)
        assert session.last(RESULTS_STATE) == {"label": "Done", "tone": "ok"}
        assert session.last(RESULTS_COUNT) == "1 hit"
        # Row 0 of the hits table: what the kind draws, its kind, where it lives.
        assert session.last((*RESULTS_HITS, "0", "0", "0", "body")) == "Tomato needs sun"
        assert session.last((*RESULTS_HITS, "0", "1")) == {"label": "Note"}
        # The hit links to its cell's plane, titled by its id: p1 has no name.
        link = session.last((*RESULTS_HITS, "0", "2", "0"))
        assert link["href"] == "/p1" and link["title"] == "p1"
        assert session.last((*RESULTS_HITS, "0", "2", "1")) == "cell \u00b7 a"
    finally:
        await _stop(task)


async def test_results_say_when_nothing_was_found_or_searched(store):
    pid = await _searched(store, {NOTE: {"text": "zzz"}})
    await _run(store, pid)
    got = await _frames(store, _viewer(search.RESULTS, "shown", nu.Str(pid)))
    assert got[RESULTS_COUNT] == "0 hits"
    assert got[RESULTS_EMPTY]["label"] == "Nothing found"
    none = await _frames(store, _viewer(search.RESULTS, "none"))
    assert none[RESULTS_EMPTY]["label"] == "No searches yet"
