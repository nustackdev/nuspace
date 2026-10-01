"""Search: the op, the search's own cell, the viewer's two cells, and one search run on a worker."""

from __future__ import annotations

import asyncio

import pytest
from _support import search as notes
from _support.kernel import ended, opened

import nu
import nustd.kv
from nuspace import Snippet, ops
from nuspace.shapes import PlaneState, Reroot, Space, States
from nuspace.system import search
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Bracketed, Rewrites
from nustd.ui import Session
from nustd.ui.core import OP_NOTIFY, Frame, WsSession


S = search.Search

#: What a space with the test snippets registered can search.
SEARCHERS = search.searchable([notes.NOTE, notes.SLOW_NOTE, notes.PLAIN])


def _drawn(plane_id: str, name: str) -> nu.Nu:
    return ops.add_plane(plane_id, name=name, ui=True, made_by="plain", backend="async")


def _note(plane_id: str, cell_id: str, body: str, snippet: Snippet = notes.NOTE) -> nu.Nu:
    return ops.insert_snippet(plane_id, snippet, cell_id=cell_id) >> notes.write(
        plane_id, cell_id, body
    )


def _state(plane_id: str, term: nu.Nu) -> nu.Nu:
    return ops.plane_state(plane_id, term)


async def _hits(store, plane_id: str) -> list[dict]:
    hits = _state(plane_id, S.hits)
    return await store.read(nu.If(hits.exists(), hits.extract(), nu.Literal([])))


async def _finished(store, plane_id: str) -> bool:
    return await store.read(_state(plane_id, S.finished_at).exists())


async def _searched(store, *args: object, **kwargs: object) -> str:
    """Search through ``store``. The new search is the newest child of ``SEARCHES``."""
    await store.run(search.search(*args, **kwargs))
    return (await store.read(ops.children(search.SEARCHES)))[-1]


def _loaded(plane: str, cell: str) -> nu.Nu:
    """A cell's prog loaded as the kernel loads it: rerooted under it, bracketed."""
    rewrite = Rewrites(Reroot(plane, cell), Bracketed())
    prog = Space.planes[plane].cells[cell].prog
    return nustd.kv.auto_flow_atomic(
        prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite), scope=Space
    )


async def _run_search(store, plane_id: str) -> None:
    """The search's own cell, run to its end on this store."""
    term = await store.run(_loaded(plane_id, search.CELL))
    await store.run(term)


async def _garden(store) -> None:
    """Two drawn planes of notes, one plain cell, one plane nobody draws."""
    await store.run(
        _drawn("p1", "Garden")
        >> _note("p1", "c1", "Tomatoes need\nsun and water")
        >> _note("p1", "c2", "Nothing to see")
        >> ops.insert_snippet("p1", notes.PLAIN, cell_id="c3")
        >> _drawn("p2", "Tomato plan")
        >> _note("p2", "c4", "Buy TOMATO seeds")
        >> ops.add_plane("hidden", name="tomato hideout", backend="async")
        >> _note("hidden", "c5", "tomato")
    )


# --- The op -----------------------------------------------------------------------------


async def test_search_makes_a_plane_under_searches_and_starts_its_run(store):
    pid = await _searched(store, "tomato", ["note"], True, searchers=SEARCHERS)
    assert pid
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    parent = rows[search.SEARCHES]
    assert parent["name"] == "Searches"
    assert parent["props"]["system"] is True and parent["props"]["ui"] is False
    assert rows[pid]["name"] == "tomato"
    assert rows[pid]["props"]["ui"] is False and rows[pid]["parent"] == search.SEARCHES
    assert (parent["props"]["backend"], rows[pid]["props"]["backend"]) == ("mp", "mp")
    assert await store.read(ops.children(search.SEARCHES)) == [pid]

    (cell,) = await store.read(ops.cell_rows(pid))
    assert cell["id"] == search.CELL
    assert cell["prog"] == search.source(SEARCHERS)
    assert cell["props"] == {"made_by": "", "has_ui": False}

    state = await store.read(States.planes[pid].state.extract())
    assert state["query"] == "tomato"
    assert state["snippets"] == ["note"]
    assert state["titles"] is True
    assert state["started_at"] > 0
    assert "finished_at" not in state

    (run,) = await store.read(ops.runs(pid))
    assert run["by"] == search.BY

    # A second search: the parent is kept, the new one listed after.
    again = await _searched(store, "sun", [], False, searchers=SEARCHERS)
    assert await store.read(ops.children(search.SEARCHES)) == [pid, again]


def test_the_prog_names_only_snippets_with_a_search():
    assert SEARCHERS == {"note": "_support.search:search", "slow": "_support.search:slow"}
    assert search.load_searcher(SEARCHERS["slow"]) is notes.slow


def test_a_search_that_is_not_module_level_is_refused():
    with pytest.raises(ValueError, match="module level"):
        Snippet("x", "X", "", search=lambda q, p, c: nu.List.of())


async def test_insert_snippet_records_its_snippet_as_a_prop(store):
    await store.run(_drawn("p", "P") >> ops.insert_snippet("p", notes.NOTE, cell_id="c"))
    (cell,) = await store.read(ops.cell_rows("p"))
    assert cell["props"]["made_by"] == "note"


# --- The search's cell --------------------------------------------------------------------


async def test_the_cell_finds_notes_and_titles_in_drawn_planes(store):
    await _garden(store)
    pid = await _searched(store, "tomato", ["note"], True, searchers=SEARCHERS)
    await _run_search(store, pid)
    hits = await _hits(store, pid)
    assert hits == [
        {
            "plane": "p1",
            "cell": "c1",
            "title": "Garden",
            "excerpt": "Tomatoes need sun and water",
            "by": "note",
        },
        {
            "plane": "p2",
            "cell": "",
            "title": "Tomato plan",
            "excerpt": "Tomato plan",
            "by": "title",
        },
        {
            "plane": "p2",
            "cell": "c4",
            "title": "Tomato plan",
            "excerpt": "Buy TOMATO seeds",
            "by": "note",
        },
    ]
    assert await _finished(store, pid)


async def test_unpicked_snippets_and_titles_are_left_out(store):
    await _garden(store)
    titles = await _searched(store, "tomato", [], True, searchers=SEARCHERS)
    await _run_search(store, titles)
    assert [(h["plane"], h["by"]) for h in await _hits(store, titles)] == [("p2", "title")]

    notes_only = await _searched(store, "tomato", ["note"], False, searchers=SEARCHERS)
    await _run_search(store, notes_only)
    assert [(h["cell"], h["by"]) for h in await _hits(store, notes_only)] == [
        ("c1", "note"),
        ("c4", "note"),
    ]

    # Picked, but the space it was made in could not search it.
    unknown = await _searched(store, "tomato", ["plain", "gone"], False, searchers=SEARCHERS)
    await _run_search(store, unknown)
    assert await _hits(store, unknown) == []
    assert await _finished(store, unknown)


async def test_an_empty_query_finds_nothing_and_finishes(store):
    await _garden(store)
    pid = await _searched(store, "  ", ["note"], True, searchers=SEARCHERS)
    await _run_search(store, pid)
    assert await _hits(store, pid) == []
    assert await _finished(store, pid)


def test_excerpt_cuts_around_the_match():
    long = "x" * 60 + " the Needle is here " + "y" * 60
    got, _ = nu.run(search.excerpt(nu.Str(long), nu.Str("needle")))
    assert got.startswith("…") and got.endswith("…")
    assert "the Needle is here" in got
    assert len(got) <= 2 * search.EXCERPT_WIDTH + len("needle") + 2
    short, _ = nu.run(search.excerpt(nu.Str("a needle"), nu.Str("NEEDLE")))
    assert short == "a needle"
    assert nu.run(search.matches(nu.Str("Haystack"), nu.Str("STACK")))[0] is True
    assert nu.run(search.matches(nu.Str("Haystack"), nu.Str("")))[0] is False


# --- The viewer ------------------------------------------------------------------------------


class _Recording:
    """A session that keeps the frames it is sent instead of sending them."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


async def _frames(store, source: str, cell: str, build) -> list[tuple]:
    """``build(namespace)`` from a viewer cell's source, run as the kernel would run it there.

    Yields ``(ref path, payload)`` in order, ``None`` for an erase.
    """
    namespace: dict = {}
    exec(compile(source, cell, "exec"), namespace)  # noqa: S102
    term = Rewrites(Reroot(search.PLANE, cell), Bracketed())(build(namespace))
    session = _Recording()
    await nu.arun(term, store.ctx.bind(Session, session))
    return [
        (frame.ref, None if frame.op == "remove" else frame.payload) for frame in session.frames
    ]


async def _draw(store, source: str, cell: str, build) -> dict:
    """:func:`_frames` as ``{ref path: payload}``, the last write to a path winning."""
    return dict(await _frames(store, source, cell, build))


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
    assert [c["id"] for c in await store.read(ops.cell_rows(search.PLANE))] == ["pick", "results"]
    assert search.PLANE not in await store.read(ops.pinned())


@pytest.mark.parametrize("cell", search.CELLS, ids=lambda c: c[0])
async def test_each_viewer_cell_loads_through_the_kernel_rewrites(store, cell):
    name, source = cell
    await store.run(ops.add_plane("v", backend="async") >> ops.add_cell("v", source, cell_id=name))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("v", name), env.rewrite, Bracketed())
    prog = Space.planes["v"].cells[name].prog
    term = await store.run(
        nustd.kv.auto_flow_atomic(
            prog.load(scope={"plane": "v", "cell": name}, rewrite=rewrite), scope=Space
        )
    )
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


async def test_pick_lists_searches_newest_first_and_shows_the_newest(store):
    await store.run(search.ensure_search())
    old = await _searched(store, "old", [], True, searchers=SEARCHERS)
    new = await _searched(store, "new", [], True, searchers=SEARCHERS)
    got = await _frames(
        store, search.PICK, "pick", lambda ns: nu.Frame(ns["Seen"], ns["draw"](), ids=[])
    )
    select = [payload for ref, payload in got if ref == ("pick", "search")]
    assert select == [
        {"options": [{"value": new, "label": "new"}, {"value": old, "label": "old"}]},
        new,
    ]
    assert await store.read(ops.plane_state(search.PLANE, _Chosen.shown)) == new


async def test_a_picked_search_holds_until_a_newer_one_is_made(store):
    await store.run(search.ensure_search())
    old = await _searched(store, "old", [], True, searchers=SEARCHERS)
    new = await _searched(store, "new", [], True, searchers=SEARCHERS)
    chosen = ops.plane_state(search.PLANE, _Chosen.picked.set(old) >> _Chosen.newest.set(new))
    await store.run(ops.utils.atomic_state(chosen))

    def draw(ns):
        return nu.Frame(ns["Seen"], ns["draw"](), ids=[])

    shown = ops.plane_state(search.PLANE, _Chosen.shown)
    await _frames(store, search.PICK, "pick", draw)
    assert await store.read(shown) == old
    newer = await _searched(store, "newer", [], True, searchers=SEARCHERS)
    got = await _draw(store, search.PICK, "pick", draw)
    assert got[("pick", "search")] == newer
    assert await store.read(shown) == newer


async def test_results_draw_the_shown_search(store):
    await _garden(store)
    pid = await _searched(store, "tomato", ["note"], True, searchers=SEARCHERS)
    await _run_search(store, pid)
    got = await _draw(store, search.RESULTS, "results", lambda ns: ns["shown"](nu.Str(pid)))
    assert got[("title",)]["label"] == "Results for “tomato”"
    assert got[("status",)] == "Done: 3 hits"
    assert got[("hits", "h0", "head", "link")] == {"href": "/p1", "label": "Garden"}
    assert got[("hits", "h0", "head", "by")]["label"] == "note"
    assert got[("hits", "h0", "excerpt")] == "Tomatoes need sun and water"
    assert got[("hits", "h1", "head", "by")]["label"] == "title"
    assert ("hits", "h1", "excerpt") not in got
    assert got[("hits", "h2", "head", "link")] == {"href": "/p2", "label": "Tomato plan"}
    assert got[("empty",)] is None


async def test_results_say_when_nothing_was_found_or_searched(store):
    pid = await _searched(store, "zzz", ["note"], True, searchers=SEARCHERS)
    await _run_search(store, pid)
    got = await _draw(store, search.RESULTS, "results", lambda ns: ns["shown"](nu.Str(pid)))
    assert got[("status",)] == "Done: 0 hits"
    assert got[("empty",)]["label"] == "Nothing found"
    none = await _draw(store, search.RESULTS, "results", lambda ns: ns["none"]())
    assert none[("empty",)]["label"] == "No searches yet"


# --- The sidebar ------------------------------------------------------------------------------


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


async def test_the_sidebar_offers_searchable_snippets_and_runs_a_search(store):
    from nuspace.system.devices.web.device import connection

    await store.run(_drawn("p1", "Tomato plan"))
    session = _FakeSession()
    snippets = [notes.PLAIN, notes.NOTE]
    task = asyncio.create_task(
        nu.arun(connection(nu.Str("s1"), snippets=snippets), store.ctx.bind(Session, session))
    )
    kids = ops.children(search.SEARCHES)
    try:
        # Booted and the tree shipped: every arm is listening.
        deadline = asyncio.get_running_loop().time() + 3.0
        while not any(
            isinstance(f.payload, dict) and f.payload.get("op") == "set_tree"
            for f in session.frames
        ):
            assert asyncio.get_running_loop().time() < deadline, "never booted"
            await asyncio.sleep(0.01)
        sidebar = next(f for f in session.frames if f.ref == ("sidebar",))
        assert sidebar.chain[0][2]["searchable"] == [{"name": "note", "label": "Note"}]

        run = ("sidebar", "ops", "search.run")
        session.notify(run, {"query": "  ", "snippets": ["note"], "titles": True})
        await asyncio.sleep(0.2)
        assert await store.read(kids) == []
        session.notify(run, {"query": "tomato", "snippets": ["note"], "titles": False})
        (pid,) = await _until(store, kids, lambda k: len(k) == 1)
        state = await store.read(States.planes[pid].state.extract())
        assert (state["query"], state["snippets"], state["titles"]) == ("tomato", ["note"], False)
        (cell,) = await store.read(ops.cell_rows(pid))
        # The prog names what the space registered with a search, and nothing else.
        assert cell["prog"] == search.source({"note": "_support.search:search"})
        assert [r["by"] for r in await store.read(ops.runs(pid))] == [search.BY]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


# --- On a worker ---------------------------------------------------------------------------


async def test_a_search_runs_on_a_worker_and_its_run_ends():
    space = await opened(spares=1)
    try:
        await space.run(_drawn("p", "Tomato plan") >> _note("p", "c", "ripe tomato"))
        pid = await _searched(space, "tomato", ["note"], True, searchers=SEARCHERS)
        (run,) = await space.read(ops.runs(pid))
        row = await space.run_row(run["id"], ended, 20.0)
        assert row["exit"] == "ok", row
        hits = ops.plane_state(pid, S.hits.extract())
        assert [(h["cell"], h["by"]) for h in await space.read(hits)] == [
            ("", "title"),
            ("c", "note"),
        ]
        assert await space.read(ops.plane_state(pid, S.finished_at).exists())
    finally:
        await space.close()


async def test_hits_land_one_cell_at_a_time():
    """On a worker, so this loop reads while the slow searcher works there."""
    space = await opened(spares=1)
    try:
        await space.run(
            _drawn("p", "Slow")
            >> _note("p", "a", "apple one", notes.SLOW_NOTE)
            >> _note("p", "b", "apple two", notes.SLOW_NOTE)
            >> _note("p", "c", "apple three", notes.SLOW_NOTE)
        )
        pid = await _searched(space, "apple", ["slow"], False, searchers=SEARCHERS)
        seen: set[int] = set()

        async def watch() -> None:
            while not await _finished(space, pid):
                seen.add(len(await _hits(space, pid)))
                await asyncio.sleep(0.05)

        await asyncio.wait_for(watch(), 20.0)
        assert {1, 2} <= seen
        assert [h["cell"] for h in await _hits(space, pid)] == ["a", "b", "c"]
    finally:
        await space.close()
