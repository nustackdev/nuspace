"""``nuspace.worker``: the record the kernel writes, its live entries, the raises."""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
from nuspace.errors import Ended, Missing
from nuspace.shapes import EXIT_FAILED, EXIT_OK, Space


STORES = ("memory", "sqlite")

workers = Space.exec.workers
live = Space.exec.indexes.live
history = Space.exec.indexes.history.plane_to_plane_runs


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def made(store, term):
    return await store.made(nuspace.atomic(term))


@pytest.fixture
async def running(store):
    await do(store, nuspace.plane.add("p", backend="mp"))
    r = await made(store, nuspace.plane_run.add("p", into=MADE))
    return store, r


async def test_add_start_end(running):
    store, r = running
    w = await made(store, nuspace.worker.add(r, "mp", into=MADE))
    assert w.startswith("w_")
    assert await store.read(nu.list(history["p"].runs[r].workers.keys())) == [w]
    assert await store.read(nu.list(live.workers.keys())) == [w]
    assert await store.read(nu.list(live.plane_run_to_workers[r].ids.keys())) == [w]
    await do(store, nuspace.worker.start(w, handle={"pid": 42}))
    row = await store.read(workers[w].extract())
    assert (row["backend"], row["plane_run"], row["handle"]) == ("mp", r, {"pid": 42})
    assert "started_at" in row
    await do(store, nuspace.worker.end(w, EXIT_FAILED, "died"))
    row = await store.read(workers[w].extract())
    assert (row["exit"], row["error"]) == (EXIT_FAILED, "died")
    assert await store.read(live.workers.extract()) == {}
    assert await store.read(nu.Not(live.plane_run_to_workers[r].ids)) is True
    with pytest.raises(Ended):
        await do(store, nuspace.worker.end(w, EXIT_OK))
    with pytest.raises(Ended):
        await do(store, nuspace.worker.start(w, handle={}))


async def test_the_last_worker_of_an_ended_plane_run_takes_its_set_along(running):
    store, r = running
    w = await made(store, nuspace.worker.add(r, "mp", into=MADE))
    await do(store, nuspace.plane_run.end(r, EXIT_OK))
    assert await store.read(live.plane_run_to_workers[r].exists()) is True
    await do(store, nuspace.worker.end(w, EXIT_OK))
    assert await store.read(live.plane_run_to_workers[r].exists()) is False


async def test_raises(running):
    store, r = running
    with pytest.raises(Missing):
        await do(store, nuspace.worker.add("nope", "mp"))
    for op in (nuspace.worker.start("nope", handle={}), nuspace.worker.end("nope", EXIT_OK)):
        with pytest.raises(Missing):
            await do(store, op)
    await do(store, nuspace.plane_run.end(r, EXIT_OK))
    with pytest.raises(Ended):
        await do(store, nuspace.worker.add(r, "mp"))
