"""The home indexer: id order is creation order, and the pass counts planes and cells added by day.

The pass runs here as the indexer cell's run would, straight against the
store. The reaction wiring with a real kernel is at the end.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import itertools
import socket
import time

import pytest
from _support.kernel import opened
from _support.made import MADE

import nu
import nuspace
import nustd.kv
from nuspace import host, system
from nuspace.devices.web import CONN_STORE, WEB_STORE
from nuspace.devices.web.home import indexer
from nuspace.devices.web.planes import ensure, ensure_indexer
from nuspace.host.layout import data_dir
from nuspace.shapes import Space
from nuspace.system import reactions


STORES = ("memory", "sqlite")

STATE = indexer.index()

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 60.0


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def plane(store, **kwargs) -> str:
    return await store.made(nuspace.atomic(nuspace.plane.add(backend="async", into=MADE, **kwargs)))


async def cell(store, p: str) -> str:
    return await store.made(nuspace.atomic(nuspace.cell.add(p, "x = 1", into=MADE, fabrics=[])))


async def totals(store) -> dict:
    return await store.read(STATE.totals.extract())


async def calendar(store) -> dict:
    got = await store.read(STATE.calendar.extract()) or {}
    return {day: {k: v for k, v in counts.items() if v} for day, counts in got.items()}


def day_of(stamp: float) -> str:
    return datetime.date.fromtimestamp(stamp).isoformat()


async def brute(store) -> tuple[int, int]:
    """Minted planes not system, and minted cells not on a system plane, counted by walking every row."""
    planes = await store.read(nu.list(Space.planes.keys()))
    cells = await store.read(nu.list(Space.cells.keys()))
    minted_planes = 0
    for p in planes:
        if p.startswith("p_"):
            minted_planes += not await store.read(Space.planes[p].system.fallback(False))
    on_system = 0
    for c in cells:
        if not c.startswith("c_"):
            continue
        p = await store.read(Space.cells[c].plane)
        on_system += bool(await store.read(Space.planes[p].system.fallback(False)))
    minted_cells = sum(c.startswith("c_") for c in cells)
    return minted_planes, minted_cells - on_system


# --- The ordering contract ------------------------------------------------------------------


async def test_minted_ids_page_in_mint_order_forward_and_newest_first_back(store):
    planes = [await plane(store, name=f"n{i}") for i in range(6)]
    cells = [await cell(store, planes[0]) for _ in range(6)]
    runs = [
        await store.made(nuspace.atomic(nuspace.plane_run.add(planes[0], into=MADE)))
        for _ in range(6)
    ]
    for rows, minted, prefix in (
        (Space.planes, planes, "p_"),
        (Space.cells, cells, "c_"),
        (Space.exec.plane_runs, runs, "r_"),
    ):
        forward = await store.read(rows.keys(after=prefix, limit=100))
        assert [k for k in forward if k.startswith(prefix)] == minted
        # Paged from a cursor, a page at a time.
        assert await store.read(rows.keys(after=minted[1], limit=2)) == minted[2:4]
        back = await store.read(rows.reversed_keys(before=minted[-1], limit=3))
        assert back == minted[-2:-5:-1]
        newest = await store.read(rows.reversed_keys(limit=100))
        assert [k for k in newest if k.startswith(prefix)] == minted[::-1]


# --- The pass -------------------------------------------------------------------------------


async def test_a_space_never_indexed_reads_counting(store):
    assert await store.read(STATE.cursor.cell.fallback("")) == ""
    await store.run(indexer.catch_up())
    assert await totals(store) == {"planes": 0, "cells": 0, "specs": 0}


async def test_the_first_run_on_an_existing_space_matches_a_brute_count(store):
    await store.run(system.ensure() >> ensure())
    made = [await plane(store) for _ in range(5)]
    for p in made[:3]:
        for _ in range(4):
            await cell(store, p)
    await do(store, nuspace.plane.remove(made[4]))
    await store.run(indexer.catch_up(specs=7))
    got = await totals(store)
    assert (got["planes"], got["cells"]) == await brute(store) == (5, 12)
    assert got["specs"] == 7
    assert await calendar(store) == {day_of(time.time()): {"planes": 5, "cells": 12}}


async def test_fixed_ids_are_skipped(store):
    await do(store, nuspace.plane.add("fixed", backend="async"))
    await do(store, nuspace.cell.add("fixed", "x = 1", id="kept", fabrics=[]))
    minted = await plane(store)
    await store.run(indexer.catch_up())
    got = await totals(store)
    assert (got["planes"], got["cells"]) == (1, 0)
    assert await store.read(STATE.cursor.plane) == minted


async def test_incremental_adds_count_only_what_is_new(store):
    p = await plane(store)
    await cell(store, p)
    await store.run(indexer.catch_up())
    first = await totals(store)
    assert (first["planes"], first["cells"]) == (1, 1)
    q = await plane(store)
    await cell(store, q)
    await cell(store, q)
    await store.run(indexer.catch_up())
    got = await totals(store)
    assert (got["planes"], got["cells"]) == (2, 3)
    # A run with nothing new changes nothing.
    await store.run(indexer.catch_up())
    assert await totals(store) == got


async def test_paged_counts_are_exact(store):
    made = [await plane(store) for _ in range(7)]
    for p in made:
        await cell(store, p)
    await store.run(indexer.catch_up(limit=3))
    got = await totals(store)
    assert (got["planes"], got["cells"]) == (7, 7)
    assert await store.read(STATE.cursor.plane) == made[-1]


async def test_days_bucket_by_local_created_date_across_midnight(store):
    midnight = datetime.datetime.combine(datetime.date(2026, 3, 9), datetime.time()).timestamp()
    stamps = [midnight - 86400 * 2, midnight - 1, midnight + 1, midnight + 2]
    made = [await plane(store) for _ in stamps]
    for p, stamp in zip(made, stamps, strict=True):
        await do(store, Space.planes[p].created_at.set(stamp))
    c = await cell(store, made[0])
    await do(store, Space.cells[c].created_at.set(midnight - 1))
    await store.run(indexer.catch_up())
    assert await calendar(store) == {
        "2026-03-07": {"planes": 1},
        "2026-03-08": {"planes": 1, "cells": 1},
        "2026-03-09": {"planes": 2},
    }
    got = await totals(store)
    assert (got["planes"], got["cells"]) == (4, 1)


async def test_planes_from_specs_are_counted(store):
    made = [await plane(store) for _ in range(3)]
    await do(store, Space.planes[made[0]].spec.set("testing.thing"))
    await store.run(indexer.catch_up())
    later = await plane(store)
    await do(store, Space.planes[later].spec.set("testing.thing"))
    await store.run(indexer.catch_up())
    assert (await totals(store))["from_specs"] == 2


async def test_cells_of_system_planes_are_not_counted(store):
    await store.run(system.ensure())
    p = await plane(store)
    await cell(store, p)
    await store.run(reactions.add(indexer.PLANES_ADDED, p))
    await store.run(indexer.catch_up())
    got = await totals(store)
    assert (got["planes"], got["cells"]) == (1, 1)


async def test_a_page_whose_commit_fails_counts_nothing_and_its_retry_counts_once(store):
    p = await plane(store)
    await cell(store, p)
    crashed = nuspace.atomic(indexer.step() >> nu.Raise(nu.Str("crash before the commit")))
    with pytest.raises(Exception, match="crash before the commit"):
        await store.run(crashed)
    assert await store.read(STATE.cursor.plane.exists()) is False
    assert await calendar(store) == {}
    await store.run(indexer.catch_up())
    await store.run(indexer.catch_up())
    got = await totals(store)
    assert (got["planes"], got["cells"]) == (1, 1)
    assert await calendar(store) == {day_of(time.time()): {"planes": 1, "cells": 1}}


# --- Made at open ---------------------------------------------------------------------------


async def test_ensure_makes_the_indexer_off_the_web_with_two_reactions_once(store):
    await store.run(system.ensure() >> ensure())
    row = await store.read(Space.planes[indexer.PLANE].extract())
    assert row["system"] is True and row["backend"] == indexer.BACKEND
    assert await store.read(nuspace.devices.web.Web.planes.contains(indexer.PLANE)) is False
    with pytest.raises(nuspace.errors.Refused):
        await do(store, nuspace.plane.remove(indexer.PLANE))
    kept = await store.read(STATE.reactions.extract())
    assert set(kept) == {"planes", "cells"}
    listed = reactions.registry().by_plane[indexer.PLANE].ids
    assert set(await store.read(nu.list(listed.keys()))) == set(kept.values())
    # A second open adds nothing.
    await store.run(ensure())
    assert await store.read(STATE.reactions.extract()) == kept
    assert len(await store.read(nu.list(listed.keys()))) == 2


async def test_ensure_without_a_reactions_plane_adds_no_reaction(store):
    await store.run(ensure())
    assert await store.read(Space.planes.contains(indexer.PLANE)) is True
    assert await store.read(STATE.reactions.exists()) is False


def test_the_cell_builds_and_validates():
    namespace: dict = {}
    exec(compile(indexer.PROG, "cell", "exec"), namespace)  # noqa: S102
    nu.validate(nu.compile(namespace["out"]()))


# --- The reactions, with a real kernel ------------------------------------------------------


async def test_planes_and_cells_added_wake_it_and_runs_do_not():
    k = await opened("nuspace-indexer", spares=2)
    try:
        await k.run(system.ensure())
        await k.do(Space.info.opened_at.set(time.time()))
        await k.run(system.start())
        await k.run(ensure_indexer())
        kept = await k.read(STATE.reactions.extract())

        def listening(rows: list) -> bool:
            return all(r in rows for r in kept.values())

        await k.until(lambda: _live_cells(k, reactions.PLANE), listening, SLOW)
        # A reaction is live a moment before its flow listens: add until one gets through.
        deadline = time.monotonic() + SLOW
        for _ in itertools.count():
            p = await k.made(nuspace.plane.add(backend="async", into=MADE))
            try:
                await k.until(lambda: totals_of(k), lambda t: t.get("planes", 0) >= 1, 3.0)
                break
            except AssertionError:
                assert time.monotonic() < deadline
        await k.made(nuspace.cell.add(p, "def out():\n    return None\n", into=MADE))
        await k.until(lambda: totals_of(k), lambda t: t.get("cells", 0) >= 1, SLOW)
        await asyncio.sleep(0.5)
        runs = await _runs(k)
        assert runs and set(runs.values()) <= set(kept.values())
        # A plane run starts and ends: no indexer run for it.
        await k.made(nuspace.plane_run.add(p, into=MADE))
        await asyncio.sleep(1.5)
        assert await _runs(k) == runs
    finally:
        await k.close()


async def test_a_wake_counts_an_existing_space_with_no_add():
    k = await opened("nuspace-indexer-wake", spares=1)
    try:
        await k.run(system.ensure())
        made = [await k.made(nuspace.plane.add(backend="async", into=MADE)) for _ in range(3)]
        await k.made(nuspace.cell.add(made[0], "def out():\n    return None\n", into=MADE))
        # No reactions plane run is up: only the wake can run the indexer.
        await k.run(ensure_indexer())
        assert await totals_of(k) == {}
        await k.run(indexer.wake())
        got = await k.until(lambda: totals_of(k), lambda t: t.get("cells", 0) >= 1, SLOW)
        assert (got["planes"], got["cells"]) == (3, 1)
        assert set((await _runs(k)).values()) == {await k.read(STATE.reactions.planes)}
        # A second wake while its run is live adds none; after, it adds one.
        before = len(await _runs(k))
        await k.run(indexer.wake() >> indexer.wake())
        assert len(await _runs(k)) <= before + 1
    finally:
        await k.close()


# --- At open --------------------------------------------------------------------------------


EVERY_STORE = (*host.CORE, WEB_STORE, CONN_STORE)


async def _on_disk(root, term: nu.Nu) -> object:
    data = data_dir(root)
    navs = [nustd.kv.sqlite_navigator(str(data / s.file), tags=(s.root,)) for s in EVERY_STORE]
    value, _ = await nu.arun(nu.With(*navs, body=term))
    return value


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def test_an_open_counts_an_existing_space_with_no_indexer_state(tmp_path):
    root = tmp_path / "space"
    # A space from before the indexer: made without the web device, so no indexer, no state.
    await nu.arun(host.make_space(root, devices=()))

    def plane_and_cell(made: nu.ObjectRef) -> nu.Nu:
        added = nuspace.atomic(nuspace.plane.add(backend="async", into=made))
        return added >> nuspace.atomic(nuspace.cell.add(nu.Str(made), "x = 1", fabrics=[]))

    for _ in range(2):
        await _on_disk(root, nu.let("", plane_and_cell))
    assert await _on_disk(root, nuspace.atomic(STATE.exists())) is False
    term = host.serve(
        root, open_browser=False, static=None, port=_free_port(), extensions=(), spares=0
    )
    task = asyncio.create_task(nu.arun(term))
    try:
        deadline = time.monotonic() + SLOW
        while True:
            with contextlib.suppress(Exception):  # the host may hold the stores a moment
                got = await _on_disk(root, nuspace.atomic(STATE.totals.extract())) or {}
                if got.get("cells") == 2:
                    break
            assert time.monotonic() < deadline, "timed out waiting for the indexer"
            await asyncio.sleep(0.2)
        assert got["planes"] == 2
        cal = await _on_disk(root, nuspace.atomic(STATE.calendar.extract()))
        assert cal == {day_of(time.time()): {"planes": 2, "cells": 2}}
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, 15)


async def totals_of(k) -> dict:
    return await k.read(STATE.totals.extract()) or {}


async def _live_cells(k, plane_id: str) -> list:
    """Cells with a live cell run in a live run of ``plane_id``."""
    live = Space.exec.indexes.live
    runs = await k.read(_listed(live.plane_to_plane_runs[plane_id].ids))
    found = []
    for r in runs:
        crs = await k.read(_listed(live.plane_run_to_cell_runs[r].ids))
        for cr in crs:
            rec = await k.read(Space.exec.cell_runs[cr].extract())
            if rec.get("started_at") is not None:
                found.append(rec["cell"])
    return found


def _listed(ids) -> nu.Nu:
    return nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([]))


async def _runs(k) -> dict:
    """The indexer's plane runs, each with who asked for it."""
    ids = Space.exec.indexes.history.plane_to_plane_runs[indexer.PLANE].runs
    listed = await k.read(_listed(ids))
    return {r: await k.read(Space.exec.plane_runs[r].by) for r in listed}
