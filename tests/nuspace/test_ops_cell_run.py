"""``nuspace.cell_run``: the record, history and live entries, the failed cells set, the raises."""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
from nuspace.errors import Ended, Missing, Refused, Removed
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_OK, Space


STORES = ("memory", "sqlite")

cell_runs = Space.exec.cell_runs
live = Space.exec.indexes.live
history = Space.exec.indexes.history.plane_to_plane_runs


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def made(store, term):
    return await store.made(nuspace.atomic(term))


@pytest.fixture
async def running(store):
    """A plane ``p`` with cells ``c1``, ``c2``, a cell ``q1`` on another plane, and a live run of ``p``."""
    await do(
        store,
        nuspace.plane.add("p", backend="async")
        >> nuspace.plane.add("q", backend="async")
        >> nuspace.cell.add("p", "s", id="c1")
        >> nuspace.cell.add("p", "s", id="c2")
        >> nuspace.cell.add("q", "s", id="q1"),
    )
    r = await made(store, nuspace.plane_run.add("p", into=MADE))
    return store, r


async def test_add_writes_the_record_its_history_and_live_entries(running):
    store, r = running
    await do(store, nuspace.cell.set_prog("c1", "s2"))
    cr = await made(store, nuspace.cell_run.add(r, "c1", by="reload", into=MADE))
    assert cr.startswith("cr_")
    row = await store.read(cell_runs[cr].extract())
    assert {k: row[k] for k in ("plane_run", "cell", "version", "by", "worker", "out")} == {
        "plane_run": r,
        "cell": "c1",
        "version": 2,
        "by": "reload",
        "worker": "",
        "out": [],
    }
    ids = history["p"].runs[r].cell_to_cell_runs["c1"].ids
    assert await store.read(ids.last()) == cr
    assert await store.read(nu.list(live.cell_to_cell_runs["c1"].ids.keys())) == [cr]
    assert await store.read(nu.list(live.plane_run_to_cell_runs[r].ids.keys())) == [cr]


async def test_add_raises(running):
    store, r = running
    with pytest.raises(Refused, match="not on plane run"):
        await do(store, nuspace.cell_run.add(r, "q1"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell_run.add(r, "nope"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell_run.add("nope", "c1"))
    await do(store, nuspace.cell.remove("c2"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell_run.add(r, "c2"))
    await do(store, nuspace.plane_run.end(r, EXIT_OK))
    with pytest.raises(Ended):
        await do(store, nuspace.cell_run.add(r, "c1"))


async def test_start_interrupt_end(running):
    store, r = running
    cr = await made(store, nuspace.cell_run.add(r, "c1", into=MADE))
    await do(store, nuspace.cell_run.start(cr, worker="w1") >> nuspace.cell_run.interrupt(cr))
    row = await store.read(cell_runs[cr].extract())
    assert row["worker"] == "w1"
    assert row["interrupt_at"] >= row["started_at"]
    await do(store, nuspace.cell_run.end(cr, EXIT_INTERRUPTED))
    assert await store.read(cell_runs[cr].exit) == EXIT_INTERRUPTED
    assert await store.read(live.cell_to_cell_runs["c1"].ids.extract()) == {}
    assert await store.read(nu.Not(live.plane_run_to_cell_runs[r].ids)) is True
    # Interrupting an ended run harms nothing; ending or starting it again is a driver bug.
    await do(store, nuspace.cell_run.interrupt(cr))
    with pytest.raises(Ended):
        await do(store, nuspace.cell_run.end(cr, EXIT_OK))
    with pytest.raises(Ended):
        await do(store, nuspace.cell_run.start(cr, worker="w2"))
    for op in (nuspace.cell_run.interrupt("nope"), nuspace.cell_run.end("nope", EXIT_OK)):
        with pytest.raises(Missing):
            await do(store, op)


async def test_a_failed_end_counts_only_for_the_cells_newest_run(running):
    store, r = running
    failed = live.plane_run_to_failed_cells[r].ids
    old = await made(store, nuspace.cell_run.add(r, "c1", into=MADE))
    new = await made(store, nuspace.cell_run.add(r, "c1", into=MADE))
    # Replaced by a newer run: its failure does not count.
    await do(store, nuspace.cell_run.end(old, EXIT_FAILED, "boom"))
    assert await store.read(failed.extract()) == {}
    await do(store, nuspace.cell_run.end(new, EXIT_FAILED, "boom"))
    assert await store.read(failed.extract()) == {"c1": True}
    # A new run of the cell replaces the failed one.
    await do(store, nuspace.cell_run.add(r, "c1"))
    assert await store.read(failed.extract()) == {}


async def test_the_last_end_in_an_ended_plane_run_drops_its_live_set(running):
    store, r = running
    first = await made(store, nuspace.cell_run.add(r, "c1", into=MADE))
    last = await made(store, nuspace.cell_run.add(r, "c2", into=MADE))
    await do(store, nuspace.plane_run.end(r, EXIT_INTERRUPTED))
    held = live.plane_run_to_cell_runs[r]
    await do(store, nuspace.cell_run.end(first, EXIT_INTERRUPTED))
    assert await store.read(held.ids.extract()) == {last: True}
    await do(store, nuspace.cell_run.end(last, EXIT_INTERRUPTED))
    assert await store.read(held.exists()) is False


def test_end_refuses_an_unknown_exit_at_build():
    with pytest.raises(Refused):
        nuspace.cell_run.end("cr", "maybe")
