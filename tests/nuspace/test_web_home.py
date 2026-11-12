"""Home: its cells' reads stay bounded and honest, and each draws again only on a change.

A cell's read runs here against the store; its draw with a recording
session bound, so what it would draw is read off the frames it sends. The
live tests run a cell's ``out`` and write to the store under it.
"""

from __future__ import annotations

import asyncio

import pytest
from _support.made import MADE

import nu
import nuspace
import nuspace.web as web
from nuspace.places import inside
from nuspace.shapes import Space
from nuspace.web import home
from nuspace.web.home import history, indexer, now, runs, space
from nustd.ui import Session


STATE = indexer.index()
LIVE = Space.exec.indexes.live


async def do(store, term):
    return await store.run(nuspace.atomic(term))


class _Notify:
    def __init__(self) -> None:
        self.callbacks: list = []

    def bind(self, cb) -> None:
        self.callbacks.append(cb)

    def unbind(self, cb) -> None:
        self.callbacks = [c for c in self.callbacks if c is not cb]

    def close(self) -> None:
        self.callbacks = []


class _Recording:
    """A session that keeps the frames it is sent."""

    def __init__(self) -> None:
        self.frames: list = []
        self.notifies: dict = {}

    async def send(self, frame: object) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        return nu.lang.NULL

    def subscribe(self, path: tuple[str, ...]) -> _Notify:
        return self.notifies.setdefault(tuple(path), _Notify())

    def last(self, ref: tuple) -> object:
        """The last payload sent to ``ref``, None when none or an erase."""
        for frame in reversed(self.frames):
            if frame.ref == ref:
                return None if frame.op == "remove" else frame.payload
        return None

    def chained(self, ref: tuple) -> dict:
        """The props the last frame through ``ref`` carried for it on its chain, ``{}`` when none."""
        for frame in reversed(self.frames):
            for i, (_, _, props) in enumerate(frame.chain):
                if frame.ref[: i + 1] == ref:
                    return props
        return {}

    def drawn(self) -> dict:
        """Every ref's last payload, erased ones left out."""
        out: dict = {}
        for frame in self.frames:
            if frame.op == "remove":
                out = {k: v for k, v in out.items() if k[: len(frame.ref)] != frame.ref}
            else:
                out[frame.ref] = frame.payload
        return out


async def _draw(store, term: nu.Nu) -> _Recording:
    session = _Recording()
    await nu.arun(term, store.ctx.bind(Session, session))
    return session


async def _live(store, term: nu.Nu) -> tuple[_Recording, asyncio.Task]:
    session = _Recording()
    task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, session)))
    await asyncio.sleep(0)
    return session, task


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def _until(check, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.02)


async def _quiet(session: _Recording, seconds: float = 1.0) -> int:
    await asyncio.sleep(seconds)
    return len(session.frames)


async def plane(store, **kwargs) -> str:
    kwargs.setdefault("backend", "async")
    return await store.made(nuspace.atomic(nuspace.plane.add(into=MADE, **kwargs)))


async def cell(store, p: str) -> str:
    return await store.made(nuspace.atomic(nuspace.cell.add(p, "x = 1", into=MADE, fabrics=[])))


async def run(store, p: str, **kwargs) -> str:
    return await store.made(nuspace.atomic(nuspace.plane_run.add(p, into=MADE, **kwargs)))


# --- The cells ----------------------------------------------------------------------------


def test_the_cells_are_shims_in_draw_order():
    assert [name for name, _ in home.CELLS] == ["space", "history", "now"]
    for name, prog in home.CELLS:
        assert prog == f"from nuspace.web.home.{name} import out\n"


async def test_an_older_homes_runs_cell_draws_nothing(store):
    """Recent sits under Execution in the ``now`` cell: an older home's ``runs`` cell keeps quiet."""
    await run(store, await plane(store, name="P"))
    assert (await _draw(store, runs.out())).frames == []


@pytest.mark.parametrize("module", [space, history, now, runs], ids=lambda m: m.__name__)
def test_each_cell_builds_and_validates(module):
    term = inside(module.out(), plane="home", cell="home_x")
    nu.validate(nu.compile(term))


# --- Space --------------------------------------------------------------------------------


#: The counts card's stats and its footer line, on the board's first place.
STATS = ("space", "board", "0,0", "stats")
FROM_SPECS = ("space", "board", "0,0", "footer", "0")


async def test_space_on_a_space_never_indexed_reads_counting(store):
    await do(store, Space.info.path.set("/tmp/garden") >> Space.info.opened_at.set(1000.0))
    got = await store.read(space.read())
    assert got["counting"] is True
    assert got["days"] == []
    drawn = (await _draw(store, space.draw())).drawn()
    assert drawn[(*STATS, "planes")]["value"] == "…"
    assert drawn[FROM_SPECS] == "counting"
    assert drawn[("space",)]["description"] == "/tmp/garden"
    # Each run but the last ends in its dot: a wrapped line never starts with one.
    assert drawn[("space", "info", "name")] == "garden ·"
    assert drawn[("space", "info", "versions")].endswith(" ·")
    assert drawn[("space", "info", "uptime")]["ts"] == 1_000_000


async def test_space_reads_the_indexer_totals_and_calendar(store):
    for _ in range(3):
        await cell(store, await plane(store))
    await store.run(indexer.catch_up(specs=4))
    got = await store.read(space.read())
    assert got["counting"] is False
    assert (got["planes"], got["cells"], got["specs"], got["from_specs"]) == (3, 3, 4, 0)
    drawn = (await _draw(store, space.draw())).drawn()
    values = drawn[("space", "board", "0,1", "calendar")]["values"]
    assert sum(v.get("planes", 0) for v in values.values()) == 3
    assert drawn[FROM_SPECS] == "0 planes from specs"


async def test_space_counts_go_compact_past_ten_thousand(store):
    await do(store, STATE.totals.cells.set(1_184_220) >> STATE.cursor.cell.set("c_x"))
    drawn = (await _draw(store, space.draw())).drawn()
    assert drawn[(*STATS, "cells")]["value"] == "1.2M"


async def test_space_calendar_reads_only_the_window(store):
    old, new = "2001-01-01", nu.run(space.Since())[0]
    for day in (old, new, "2999-01-01"):
        await do(store, STATE.calendar[day].planes.set(1))
    got = await store.read(space.read())
    assert [d[0] for d in got["days"]] == ["2999-01-01"]


async def test_space_draws_again_on_totals_and_not_while_idle(store):
    session, task = await _live(store, space.out())
    try:
        planes = (*STATS, "planes")
        await _until(lambda: (session.last(planes) or {}).get("value") == "…")
        idle = await _quiet(session, 0.5)
        assert await _quiet(session, 0.5) == idle
        await do(store, STATE.totals.planes.set(7) >> STATE.cursor.cell.set("c_x"))
        await _until(lambda: (session.last(planes) or {}).get("value") == "7")
        seen = await _quiet(session, 0.5)
        # Runs and other writes wake nothing here.
        p = await plane(store)
        await run(store, p)
        assert await _quiet(session, 0.5) == seen
    finally:
        await _stop(task)


# --- History ------------------------------------------------------------------------------


def _tiles(drawn: dict) -> list:
    """The tiles drawn, in the order they were written: the order the grid draws them."""
    return [v for k, v in drawn.items() if k[:2] == ("history", "tiles") and len(k) == 3]


def _tile(plane: str) -> tuple:
    return ("history", "tiles", plane)


async def test_history_on_an_empty_space(store):
    drawn = (await _draw(store, history.draw())).drawn()
    assert _tiles(drawn) == []
    assert drawn[("history", "empty")]["label"] == "Nothing opened yet"


async def test_history_shows_recents(store):
    p = await plane(store, name="Seen")
    await do(store, web.add(p) >> web.visit(p))
    drawn = (await _draw(store, history.draw())).drawn()
    assert [t["title"] for t in _tiles(drawn)] == ["Seen"]
    assert ("history", "empty") not in drawn


async def test_history_recent_shows_the_newest_eight_still_there_icon_and_title_only(store):
    ids = [await plane(store, name=f"R{i}", icon="lucide:rocket") for i in range(12)]
    for p in ids:
        await do(store, web.visit(p))
    await do(store, nuspace.plane.remove(ids[-1]))
    tiles = _tiles((await _draw(store, history.draw())).drawn())
    assert [t["title"] for t in tiles] == [f"R{i}" for i in range(10, 2, -1)]
    assert set(tiles[0]) == {"href", "title", "icon"}
    assert tiles[0]["icon"] == "rocket"


async def test_history_redraws_on_a_visit_and_a_shown_rename_only(store):
    a, b, c = [await plane(store, name=n) for n in ("Alpha", "Beta", "Gamma")]
    await do(store, web.visit(a))
    session, task = await _live(store, history.out())

    def titles() -> list:
        return [t["title"] for t in _tiles(session.drawn())]

    try:
        await _until(lambda: (session.last(_tile(a)) or {}).get("title") == "Alpha")
        idle = await _quiet(session, 0.5)
        assert await _quiet(session, 0.5) == idle
        # A plane it does not show, renamed: nothing drawn.
        await do(store, nuspace.plane.rename(c, "Gee"))
        assert await _quiet(session, 0.5) == idle
        # A shown one, renamed: its own tile again, keyed by the plane.
        await do(store, nuspace.plane.rename(a, "Ay"))
        await _until(lambda: (session.last(_tile(a)) or {}).get("title") == "Ay")
        # A visit: the tiles again, newest first.
        await do(store, web.visit(b))
        await _until(lambda: titles() == ["Beta", "Ay"])
        # A shown plane removed: its tile goes.
        await do(store, nuspace.plane.remove(b))
        await _until(lambda: titles() == ["Ay"])
        assert _tile(b) not in session.drawn()
    finally:
        await _stop(task)


# --- Now ----------------------------------------------------------------------------------


async def test_headings_nest_under_the_page_title(store):
    """The page title is the h1: Space, History and Execution are section titles (h2), Now and Recent h3 under Execution."""
    sections = {}
    for cell_ in (space.draw(), history.draw(), now.draw()):
        session = await _draw(store, cell_)
        for name in ("space", "history", "execution"):
            if title := session.chained((name,)).get("title"):
                sections[name] = title
    assert sections == {"space": "Space", "history": "History", "execution": "Execution"}
    first = (await _draw(store, now.first())).drawn()
    heads = {k[1]: (v["label"], v["level"]) for k, v in first.items() if k[2:] == ("head", "title")}
    assert heads == {"now": ("Now", 3), "recent": ("Recent", 3)}
    # One switch, on the section's head, for both.
    assert first[SWITCH] is False


#: Where Now and Recent draw, under Execution, and the one switch.
NOW = ("execution", "now")
RECENT = ("execution", "recent")
SWITCH = ("execution", "actions")


def _table(session: _Recording) -> list:
    """The rows last shipped to Now's table, ``[]`` when none."""
    for frame in reversed(session.frames):
        if (
            frame.ref == (*NOW, "table")
            and isinstance(frame.payload, dict)
            and "rows" in frame.payload
        ):
            return frame.payload["rows"]
    return []


def _rows(session: _Recording) -> list:
    """The titles of the planes in Now's table, in row order."""
    return [row["plane"]["title"] for row in _table(session)]


async def test_now_on_an_empty_space(store):
    session = await _draw(store, now.draw())
    drawn = session.drawn()
    assert _rows(session) == []
    assert drawn[(*NOW, "empty")]["label"] == "Nothing running"
    assert (*NOW, "more") not in drawn


async def test_now_draws_ten_rows_then_an_honest_more(store):
    for i in range(13):
        p = await plane(store, name=f"N{i}")
        await cell(store, p)
        await run(store, p, by="supervisor")
    session = await _draw(store, now.draw())
    drawn = session.drawn()
    assert _rows(session) == [f"N{i}" for i in range(now.ROWS)]
    assert drawn[(*NOW, "more")] == "+3 more running"
    assert drawn[(*NOW, "head", "count")] == "13 plane runs"
    row = _table(session)[0]
    assert row["by"] == "supervisor"
    assert row["backend"] == "async, 0 workers"
    # Keyed by run: a run that ends takes its row with it, no erase of its own.
    assert len({r["run"] for r in _table(session)}) == now.ROWS


async def test_now_squares_count_every_cell_and_put_failures_first(store):
    p = await plane(store, name="Big")
    cells = [await cell(store, p) for _ in range(30)]
    r = await run(store, p)
    for c in cells[:5]:
        await do(store, nuspace.cell_run.add(r, c))
    # A failure past the first cells still draws first: it is counted, not sampled.
    await do(store, LIVE.plane_run_to_failed_cells[r].ids[cells[-1]].set(True))
    (row,) = _table(await _draw(store, now.draw()))
    counts = row["cells"]["counts"]
    assert counts == {"danger": 1, "info": 5, "ok": 0, "empty": 24}
    assert sum(counts.values()) == 30
    assert row["failed"] == "1"


@pytest.mark.parametrize(
    ("asked", "system", "said"),
    [("", "", "you"), ("nav", "", "tab"), ("c_1", "reactions", "reactions"), ("init", "", "init")],
)
def test_now_says_who_asked(asked, system, said):
    assert now.by(asked, system) == said


async def test_now_names_a_cell_on_any_system_plane_by_that_plane(store):
    """No plane id is known by heart: a cell on a system plane asks as that plane's title."""
    mine = await plane(store, name="mine")
    await do(store, nuspace.plane.add("watchers", name="Watchers", backend="async", system=True))
    asker = await cell(store, "watchers")
    other = await cell(store, mine)
    await run(store, mine, by=asker)
    await run(store, mine, by=other)
    rows = _table(await _draw(store, now.draw()))
    assert [r["by"] for r in rows] == ["Watchers", other]


class _Switched(_Recording):
    """A session whose system runs switch reads ``on``."""

    def __init__(self, on: bool) -> None:
        super().__init__()
        self.on = on

    async def aread(self, path: tuple[str, ...]) -> object:
        return self.on if tuple(path)[-2:] == SWITCH else nu.lang.NULL


async def _system_space(store) -> None:
    for i in range(3):
        await run(store, await plane(store, name=f"mine{i}"))
    for i in range(12):
        p = f"sys{i}"
        await do(store, nuspace.plane.add(p, name=p, backend="async", system=True))
        await run(store, p)


async def test_now_switch_off_leaves_system_runs_out_on_counts_them_honestly(store):
    await _system_space(store)
    session = await _draw(store, now.draw())
    off = session.drawn()
    assert off[(*NOW, "head", "count")] == "3 plane runs"
    assert _rows(session) == ["mine0", "mine1", "mine2"]
    assert (*NOW, "more") not in off
    session = _Switched(True)
    await nu.arun(now.draw(), store.ctx.bind(Session, session))
    on = session.drawn()
    assert on[(*NOW, "head", "count")] == "15 plane runs"
    assert len(_rows(session)) == now.ROWS
    assert on[(*NOW, "more")] == "+5 more running"


async def test_now_read_takes_the_switch(store):
    await _system_space(store)
    assert (await store.read(now.read(False)))["total"] == 3
    assert (await store.read(now.read(True)))["total"] == 15


async def test_now_flipping_the_switch_redraws_and_a_redraw_never_flips_it_back(store):
    await _system_space(store)
    session = _Switched(False)
    task = asyncio.create_task(nu.arun(now.out(), store.ctx.bind(Session, session)))
    await asyncio.sleep(0)
    count = (*NOW, "head", "count")
    try:
        await _until(lambda: session.last(count) == "3 plane runs")
        assert session.last(SWITCH) is False
        session.on = True
        for cb in list(session.notifies[SWITCH].callbacks):
            cb({"value": True})
        await _until(lambda: session.last(count) == "15 plane runs")
        # The switch was written once, off, at the start: never again.
        assert [f.payload for f in session.frames if f.ref == SWITCH] == [False]
    finally:
        await _stop(task)


async def test_now_redraws_on_a_live_change_and_not_while_idle(store):
    p = await plane(store, name="P")
    c = await cell(store, p)
    session, task = await _live(store, now.out())
    try:
        await _until(
            lambda: (session.last((*NOW, "empty")) or {}).get("label") == "Nothing running"
        )
        idle = await _quiet(session, 2.5)
        assert await _quiet(session, 1.0) == idle
        r = await run(store, p)
        await _until(lambda: session.last((*NOW, "head", "count")) == "1 plane run")
        await do(store, nuspace.cell_run.add(r, c))

        def starting() -> int:
            rows = _table(session)
            return rows[0]["cells"]["counts"].get("info", 0) if rows else 0

        await _until(lambda: starting() == 1)
        seen = await _quiet(session, 2.5)
        # A write it does not show wakes nothing.
        await do(store, Space.info.path.set("/elsewhere"))
        assert await _quiet(session, 1.0) == seen
    finally:
        await _stop(task)


# --- Recent runs --------------------------------------------------------------------------


async def collected(store, **kwargs) -> dict:
    return await store.made(
        nu.let(None, lambda s: nuspace.atomic(runs.collect(s, **kwargs)) >> MADE.set(s))
    )


async def ended(store, p: str, exit_: str = "ok") -> str:
    r = await run(store, p)
    row = Space.exec.plane_runs[r]
    await do(store, row.started_at.set(100.0) >> row.ended_at.set(200.0) >> row.exit.set(exit_))
    return r


async def test_runs_on_an_empty_space(store):
    got = await collected(store)
    assert got == {"lanes": [], "read": 0, "cut": False}
    drawn = (await _draw(store, now.recent())).drawn()
    assert drawn[(*RECENT, "empty")]["label"] == "Nothing has run yet"
    assert (*RECENT, "timeline") not in drawn


async def test_runs_lanes_are_the_last_distinct_planes_newest_first(store):
    ps = [await plane(store, name=f"L{i}") for i in range(24)]
    for p in ps:
        await run(store, p)
    await run(store, ps[3])
    got = await collected(store)
    titles = [lane["page"]["title"] for lane in got["lanes"]]
    assert len(titles) == runs.LANES
    assert titles[0] == "L3"
    assert titles[1:] == [f"L{i}" for i in range(23, 4, -1)]
    assert got["cut"] is False


async def test_runs_a_busy_plane_hits_the_budget_with_a_quiet_note(store):
    a, b = await plane(store, name="tick"), await plane(store, name="quiet")
    await run(store, b)
    for _ in range(30):
        await run(store, a)
    got = await collected(store, budget=20, size=7)
    assert [lane["page"]["title"] for lane in got["lanes"]] == ["tick"]
    assert got["cut"] is True and got["read"] >= 20
    shaped = runs.shape(got, 1000.0)
    assert shaped["note"].startswith("Showing 1:")


async def test_runs_a_lane_draws_its_newest_hundred(store):
    p = await plane(store, name="many")
    for _ in range(runs.PER_LANE + 5):
        await ended(store, p, "failed")
    got = await collected(store)
    (lane,) = got["lanes"]
    assert len(lane["runs"]) == runs.PER_LANE
    shaped = runs.shape(got, 1000.0)
    assert shaped["lanes"][0]["items"][0] == [100_000, 200_000, "danger"]
    assert shaped["lanes"][0]["count_label"] == f"{runs.PER_LANE}+ runs"
    assert shaped["note"] == ""


def test_runs_shape_tones_window_and_open_runs():
    got = {
        "lanes": [
            {
                "page": {"id": "a", "title": "A", "icon": "", "href": "/a"},
                "runs": [[900.0, 0.0, ""]],
            },
            {
                "page": {"id": "b", "title": "B", "icon": "", "href": "/b"},
                "runs": [[400.0, 450.0, "killed"]],
            },
        ],
        "read": 2,
        "cut": False,
    }
    shaped = runs.shape(got, 1000.0)
    assert [lane["items"] for lane in shaped["lanes"]] == [
        [[900_000, None, "ok"]],
        [[400_000, 450_000, "warn"]],
    ]
    # From the oldest lane's newest run, a little before, to now.
    assert shaped["end"] == 1_000_000
    assert shaped["start"] < 400_000 < shaped["end"]
    assert shaped["note"] == ""
    assert all("count_label" not in lane for lane in shaped["lanes"])


async def test_runs_and_now_leave_system_planes_out_but_count_their_runs_in_the_budget(store):
    mine = await plane(store, name="mine")
    await do(store, nuspace.plane.add("sys", name="sys", backend="async", system=True))
    await run(store, mine)
    for _ in range(5):
        await run(store, "sys")
    got = await collected(store)
    assert [lane["page"]["title"] for lane in got["lanes"]] == ["mine"]
    assert got["read"] == 6
    # A budget the system plane's runs fill: cut, nothing found.
    got = await collected(store, budget=5, size=5)
    assert got["lanes"] == [] and got["cut"] is True
    # Switch on, the walk takes the system plane as a lane: same budget, same stop.
    got = await collected(store, system=True)
    assert [lane["page"]["title"] for lane in got["lanes"]] == ["sys", "mine"]
    assert got["read"] == 6
    got = await collected(store, system=True, budget=5, size=5)
    assert [lane["page"]["title"] for lane in got["lanes"]] == ["sys"]
    assert got["read"] == 5 and got["cut"] is True
    session = await _draw(store, now.draw())
    assert session.drawn()[(*NOW, "head", "count")] == "1 plane run"
    assert _rows(session) == ["mine"]


async def test_runs_redraw_on_a_new_run_and_not_while_idle(store):
    p = await plane(store, name="P")
    session, task = await _live(store, now.out())
    try:
        await _until(
            lambda: (session.last((*RECENT, "empty")) or {}).get("label") == "Nothing has run yet"
        )
        idle = await _quiet(session, 2.5)
        assert await _quiet(session, 1.0) == idle
        await run(store, p)
        await _until(lambda: session.last((*RECENT, "head", "count")) == "1 plane", timeout=8.0)
        seen = await _quiet(session, 2.5)
        await do(store, Space.info.path.set("/elsewhere"))
        assert await _quiet(session, 1.0) == seen
    finally:
        await _stop(task)


async def test_runs_switch_sets_the_walk_not_a_filter_over_its_lanes(store):
    """On, system planes are lanes from the walk itself: up to the cap, never fewer lanes than off."""
    mine = [await plane(store, name=f"m{i}") for i in range(15)]
    for i in range(10):
        await do(store, nuspace.plane.add(f"s{i}", name=f"s{i}", backend="async", system=True))
    for i in range(15):
        await run(store, mine[i])
        if i < 10:
            await run(store, f"s{i}")
    off = await collected(store)
    assert len(off["lanes"]) == 15
    assert all(lane["page"]["title"].startswith("m") for lane in off["lanes"])
    on = await collected(store, system=True)
    titles = [lane["page"]["title"] for lane in on["lanes"]]
    assert len(titles) == runs.LANES
    assert titles[:2] == ["m14", "m13"] and "s9" in titles
    # The walk itself stops at the cap: run by run, it reads 20 of the 25.
    assert (await collected(store, system=True, size=1))["read"] == runs.LANES
    assert (await collected(store, size=1))["read"] == 25


async def test_runs_flipping_the_switch_walks_again_and_never_flips_it_back(store):
    await run(store, await plane(store, name="mine"))
    await do(store, nuspace.plane.add("sys", name="sys", backend="async", system=True))
    await run(store, "sys")

    class Switched(_Recording):
        on = False

        async def aread(self, path: tuple[str, ...]) -> object:
            return self.on if tuple(path)[-2:] == SWITCH else nu.lang.NULL

    session = Switched()
    task = asyncio.create_task(nu.arun(now.out(), store.ctx.bind(Session, session)))
    await asyncio.sleep(0)
    count = (*RECENT, "head", "count")
    try:
        await _until(lambda: session.last(count) == "1 plane", timeout=8.0)
        session.on = True
        for cb in list(session.notifies[SWITCH].callbacks):
            cb({"value": True})
        await _until(lambda: session.last(count) == "2 planes", timeout=8.0)
        # One switch: Now took it too.
        await _until(lambda: session.last((*NOW, "head", "count")) == "2 plane runs")
        assert [f.payload for f in session.frames if f.ref == SWITCH] == [False]
    finally:
        await _stop(task)


def _lanes(session: _Recording) -> list:
    """The titles of the lanes last shipped to the timeline (a note write carries no lanes)."""
    shipped = [
        f.payload
        for f in session.frames
        if f.ref == (*RECENT, "timeline") and isinstance(f.payload, dict) and "lanes" in f.payload
    ]
    return [lane["title"] for lane in shipped[-1]["lanes"]] if shipped else []


class _Flip(_Recording):
    """A session whose system runs switch reads ``on``, flipped by :meth:`flip`."""

    on = False

    async def aread(self, path: tuple[str, ...]) -> object:
        return self.on if tuple(path)[-2:] == SWITCH else nu.lang.NULL

    def flip(self, on: bool) -> None:
        self.on = on
        for cb in list(self.notifies[SWITCH].callbacks):
            cb({"value": on})


async def test_runs_toggling_the_switch_replaces_the_lanes_every_time(store):
    """On, off, on, off: each walk starts empty, so the lanes, count and note are replaced whole."""
    await run(store, await plane(store, name="mine"))
    await do(store, nuspace.plane.add("sys", name="sys", backend="async", system=True))
    await run(store, "sys")
    session = _Flip()
    task = asyncio.create_task(nu.arun(now.out(), store.ctx.bind(Session, session)))
    await asyncio.sleep(0)
    count = (*RECENT, "head", "count")
    try:
        await _until(lambda: session.last(count) == "1 plane", timeout=8.0)
        assert _lanes(session) == ["mine"]
        for on in (True, False, True, False):
            session.flip(on)
            want = ["sys", "mine"] if on else ["mine"]
            await _until(lambda want=want: _lanes(session) == want, timeout=8.0)
            assert session.last(count) == ("2 planes" if on else "1 plane")
    finally:
        await _stop(task)


async def test_runs_one_built_draw_walks_fresh_each_time(store):
    """The same built term, run again: the walk's plane list does not carry over."""
    await run(store, await plane(store, name="mine"))
    await do(store, nuspace.plane.add("sys", name="sys", backend="async", system=True))
    await run(store, "sys")
    term = now.recent()
    for on in (True, False, True, False):
        session = _Flip()
        session.on = on
        await nu.arun(term, store.ctx.bind(Session, session))
        assert _lanes(session) == (["sys", "mine"] if on else ["mine"]), on


async def test_now_toggling_the_switch_replaces_the_rows_every_time(store):
    await _system_space(store)
    session = _Flip()
    task = asyncio.create_task(nu.arun(now.out(), store.ctx.bind(Session, session)))
    await asyncio.sleep(0)
    count = (*NOW, "head", "count")
    try:
        await _until(lambda: session.last(count) == "3 plane runs")
        for on in (True, False, True, False):
            session.flip(on)
            await _until(
                lambda on=on: session.last(count) == ("15 plane runs" if on else "3 plane runs")
            )
            drawn = session.drawn()
            if on:
                assert len(_rows(session)) == now.ROWS
                assert drawn[(*NOW, "more")] == "+5 more running"
            else:
                assert _rows(session) == ["mine0", "mine1", "mine2"]
                assert (*NOW, "more") not in drawn
    finally:
        await _stop(task)
