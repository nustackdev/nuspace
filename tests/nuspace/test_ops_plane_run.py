"""``nuspace.plane_run``: the record, its lifecycle slots, the live indexes, and the raises.

No kernel here: the ops only write what is asked and what was observed.
The kernel that acts on them has its own tests.
"""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
from nuspace.errors import Ended, Missing, Refused, Removed
from nuspace.shapes import EXIT_FAILED, EXIT_KILLED, EXIT_OK, ROOT, Space


STORES = ("memory", "sqlite")

runs = Space.exec.plane_runs
live = Space.exec.indexes.live
history = Space.exec.indexes.history.plane_to_plane_runs


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def run_of(store, plane="p", **kw):
    return await store.made(nuspace.atomic(nuspace.plane_run.add(plane, into=MADE, **kw)))


@pytest.fixture
async def plane(store):
    await do(store, nuspace.plane.add("p", backend="async") >> nuspace.cell.add("p", "s", id="c1"))
    return store


async def test_add_writes_the_record_its_history_node_and_live_entries(plane):
    store = plane
    r = await run_of(store, by="nav", envs=[["session", "s1"]])
    assert r.startswith("r_")
    row = await store.read(runs[r].extract())
    assert {k: row[k] for k in ("plane", "backend", "by", "envs")} == {
        "plane": "p",
        "backend": "async",
        "by": "nav",
        "envs": [["session", "s1"]],
    }
    assert "created_at" in row
    assert all(k not in row for k in ("started_at", "ended_at", "exit"))
    assert await store.read(history["p"].runs.last()) == r
    assert await store.read(nu.list(live.plane_runs.keys())) == [r]
    assert await store.read(nu.list(live.plane_to_plane_runs["p"].ids.keys())) == [r]
    # Its own live sets are there, empty, so an empty check is one seek.
    assert await store.read(nu.Not(live.plane_run_to_cell_runs[r].ids)) is True
    assert await store.read(nuspace.plane_run.any_live("p")) is True
    # Nothing else: the kernel adds the cell runs.
    assert await store.read(Space.exec.cell_runs.extract()) == {}


async def test_add_raises_on_a_plane_that_cannot_run(plane):
    store = plane
    with pytest.raises(Missing):
        await do(store, nuspace.plane_run.add("nope"))
    with pytest.raises(Refused, match="no backend"):
        await do(store, nuspace.plane_run.add(ROOT))
    await do(store, nuspace.plane.add("gone", backend="async") >> nuspace.plane.remove("gone"))
    with pytest.raises(Removed):
        await do(store, nuspace.plane_run.add("gone"))


async def test_start_writes_started_at_once(plane):
    store = plane
    r = await run_of(store)
    await do(store, nuspace.plane_run.start(r))
    first = await store.read(runs[r].started_at)
    await do(store, nuspace.plane_run.start(r))
    assert await store.read(runs[r].started_at) == first
    with pytest.raises(Missing):
        await do(store, nuspace.plane_run.start("nope"))


async def test_interrupt_kill_and_stop_write_their_times(plane):
    store = plane
    r = await run_of(store)
    await do(store, nuspace.plane_run.interrupt(r))
    asked = await store.read(runs[r].interrupt_at)
    await do(store, nuspace.plane_run.stop(r, grace=30.0))
    row = await store.read(runs[r].extract())
    assert row["interrupt_at"] >= asked
    assert row["kill_at"] == pytest.approx(row["interrupt_at"] + 30.0)
    # An earlier kill_at wins.
    await do(store, nuspace.plane_run.kill(r))
    killed = await store.read(runs[r].kill_at)
    assert killed < row["kill_at"]
    await do(store, nuspace.plane_run.stop(r, grace=60.0))
    assert await store.read(runs[r].kill_at) == killed
    for op in (nuspace.plane_run.interrupt, nuspace.plane_run.kill, nuspace.plane_run.stop):
        with pytest.raises(Missing):
            await do(store, op("nope"))


async def test_asks_on_an_ended_run_are_no_ops(plane):
    store = plane
    r = await run_of(store)
    await do(store, nuspace.plane_run.end(r, EXIT_OK))
    await do(
        store,
        nuspace.plane_run.interrupt(r) >> nuspace.plane_run.kill(r) >> nuspace.plane_run.stop(r),
    )
    row = await store.read(runs[r].extract())
    assert all(k not in row for k in ("interrupt_at", "kill_at"))


async def test_end_takes_it_out_of_live_once(plane):
    store = plane
    r = await run_of(store)
    await do(store, nuspace.plane_run.end(r, EXIT_KILLED, "torn down"))
    row = await store.read(runs[r].extract())
    assert (row["exit"], row["error"]) == (EXIT_KILLED, "torn down")
    assert "ended_at" in row
    assert await store.read(live.plane_runs.extract()) == {}
    assert await store.read(live.plane_to_plane_runs["p"].ids.extract()) == {}
    assert await store.read(live.plane_run_to_failed_cells[r].exists()) is False
    assert await store.read(live.plane_run_to_cell_runs[r].exists()) is False
    assert await store.read(nuspace.plane_run.any_live("p")) is False
    with pytest.raises(Ended):
        await do(store, nuspace.plane_run.end(r, EXIT_OK))
    with pytest.raises(Ended):
        await do(store, nuspace.plane_run.start(r))


async def test_end_ok_is_written_failed_when_a_cells_last_run_failed(plane):
    store = plane
    r = await run_of(store)
    cr = await store.made(nuspace.atomic(nuspace.cell_run.add(r, "c1", into=MADE)))
    await do(store, nuspace.cell_run.end(cr, EXIT_FAILED, "boom"))
    await do(store, nuspace.plane_run.end(r, EXIT_OK))
    assert await store.read(runs[r].exit) == EXIT_FAILED


async def test_end_refuses_an_unknown_exit(plane):
    store = plane
    r = await run_of(store)
    with pytest.raises(Refused, match="exit"):
        nuspace.plane_run.end(r, "fine")
    with pytest.raises(Refused, match="exit"):
        await do(store, nuspace.plane_run.end(r, nu.Str("fine")))
    with pytest.raises(Missing):
        await do(store, nuspace.plane_run.end("nope", EXIT_OK))


async def test_any_live_raises_on_a_missing_plane_and_reads_false_on_one_never_run(plane):
    store = plane
    assert await store.read(nuspace.plane_run.any_live("p")) is False
    with pytest.raises(Missing):
        await store.read(nuspace.plane_run.any_live("nope"))


async def test_wait_returns_once_the_run_ended(plane):
    store = plane
    r = await run_of(store)
    ender = nu.Delay(0.05) >> nuspace.atomic(nuspace.plane_run.end(r, EXIT_OK))
    await store.run(
        nu.Timeout(
            5,
            nuspace.bracketed(nuspace.plane_run.wait(r)) | ender,
        )
    )
    # Already ended: at once.
    await store.run(nu.Timeout(5, nuspace.bracketed(nuspace.plane_run.wait(r))))
    with pytest.raises(Missing):
        await store.run(nuspace.bracketed(nuspace.plane_run.wait("nope")))


async def test_on_live_change_fires_on_add(plane):
    store = plane
    writer = nu.Delay(0.05) >> nuspace.atomic(nuspace.plane_run.add("p")) >> nu.Park()
    for watch in (nuspace.plane_run.on_live_change(), nuspace.plane_run.on_live_change(plane="p")):
        await store.run(nu.Timeout(5, nu.Race(nu.ReactOnce(nuspace.atomic(watch)), writer)))
