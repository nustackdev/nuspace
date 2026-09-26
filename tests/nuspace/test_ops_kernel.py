"""Kernel ops: records only, no workers. The kernel that acts on them is P3."""

from __future__ import annotations

import pickle

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import (
    KIND_DOCKER,
    KIND_LOCAL,
    STATUS_DEAD,
    STATUS_STARTING,
    STATUS_STOPPING,
    Space,
)


kernel = Space.kernel


async def plane_with(store, n):
    p = await store.run(ops.add_plane())
    cells = [await store.run(ops.add_cell(p, f"src{i}")) for i in range(n)]
    return p, cells


def statuses(rows):
    return {r["id"]: r["status"] for r in rows}


async def test_worker_mints_at_evaluation(store):
    term = ops.worker()
    a, b = await store.run(term), await store.run(term)
    c = await store.run(pickle.loads(pickle.dumps(ops.worker(KIND_DOCKER))))  # noqa: S301
    assert len({a, b, c}) == 3
    assert all(w.startswith("w_") for w in (a, b, c))
    rows = await store.read(ops.workers())
    assert [(r["id"], r["kind"], r["status"]) for r in rows] == [
        (a, KIND_LOCAL, STATUS_STARTING),
        (b, KIND_LOCAL, STATUS_STARTING),
        (c, KIND_DOCKER, STATUS_STARTING),
    ]
    assert rows[0]["wid"] is None
    assert await store.read(ops.active_workers()) == [a, b, c]


async def test_kill_worker(store):
    a, b = await store.run(ops.worker()), await store.run(ops.worker())
    await store.run(nustd.kv.Transaction(kernel.workers[b].status.set(STATUS_DEAD), scope=Space))
    await store.run(ops.kill_worker(a) >> ops.kill_worker(b) >> ops.kill_worker("nope"))
    assert statuses(await store.read(ops.workers())) == {a: STATUS_STOPPING, b: STATUS_DEAD}


async def test_up_writes_a_run_per_cell(store):
    p, (a, b) = await plane_with(store, 2)
    w = await store.run(ops.worker())
    envs = [ops.env("session", "conn-7"), ops.env("lmdb")]
    rids = await store.run(ops.up(p, [b, "ghost", a], worker=w, envs=envs, by="nav"))
    assert len(rids) == 2
    assert all(r.startswith("r_") for r in rids)
    rows = await store.read(ops.runs())
    assert [(r["id"], r["cell"]) for r in rows] == list(zip(rids, [b, a], strict=True))
    assert rows[0] == {
        "id": rids[0],
        "plane": p,
        "cell": b,
        "worker": w,
        "by": "nav",
        "envs": [["session", "conn-7"], ["lmdb"]],
        "status": STATUS_STARTING,
        "exit": "",
        "error": "",
        "started": None,
        "ended": None,
        "out": [],
    }
    assert await store.read(ops.live_runs()) == rids
    assert await store.read(nu.dict(kernel.live.extract())) == dict.fromkeys(rids, w)


async def test_up_mints_at_evaluation(store):
    p, (a,) = await plane_with(store, 1)
    w = await store.run(ops.worker())
    term = ops.up(p, nu.List.of(a), worker=w)
    first, second = await store.run(term), await store.run(term)
    assert len(first) == len(second) == 1
    assert first != second
    assert len(await store.read(ops.runs(cell=a))) == 2


async def test_up_plane_follows_the_order(store):
    p, (a, b, c) = await plane_with(store, 3)
    await store.run(ops.reorder_cells(p, [c, a, b]))
    w = await store.run(ops.worker())
    rids = await store.run(ops.up_plane(p, worker=w, by="init"))
    assert [r["cell"] for r in await store.read(ops.runs())] == [c, a, b]
    assert [r["by"] for r in await store.read(ops.runs())] == ["init"] * 3
    assert await store.run(ops.up_plane("nope", worker=w)) == []
    assert len(rids) == 3


async def test_down_stops_live_runs_only(store):
    p, (a, b) = await plane_with(store, 2)
    w = await store.run(ops.worker())
    r1, r2 = await store.run(ops.up(p, [a, b], worker=w))
    dead = kernel.runs[r2]
    await store.run(
        nustd.kv.Transaction(dead.status.set(STATUS_DEAD) >> kernel.live.del_item(r2), scope=Space)
    )
    await store.run(ops.down([r1, r2, "ghost"]))
    assert statuses(await store.read(ops.runs())) == {r1: STATUS_STOPPING, r2: STATUS_DEAD}
    assert await store.read(ops.runs(status="ghost")) == []


async def test_runs_filters(store):
    p, (a, b) = await plane_with(store, 2)
    q, (c,) = await plane_with(store, 1)
    w1, w2 = await store.run(ops.worker()), await store.run(ops.worker())
    ra, rb = await store.run(ops.up(p, [a, b], worker=w1))
    (rc,) = await store.run(ops.up(q, [c], worker=w2))
    await store.run(ops.down([rb]))

    async def ids(**kw):
        return [r["id"] for r in await store.read(ops.runs(**kw))]

    assert await ids() == [ra, rb, rc]
    assert await ids(plane=p) == [ra, rb]
    assert await ids(plane=p, cell=b) == [rb]
    assert await ids(worker=w2) == [rc]
    assert await ids(status=STATUS_STOPPING) == [rb]
    assert await ids(plane=q, worker=w1) == []
    assert await store.read(ops.live_runs(w1)) == [ra, rb]
    assert await store.read(ops.live_runs(w2)) == [rc]


def test_env_is_plain_data():
    assert ops.env("session", "conn-7") == ["session", "conn-7"]
    assert ops.env("lmdb") == ["lmdb"]


def test_run_attrs():
    assert (ops.PLANE_ATTR, ops.CELL_ATTR, ops.RUN_ATTR) == (
        "nuspace.plane",
        "nuspace.cell",
        "nuspace.run",
    )


async def test_run_records_round_trip_through_sqlite(disk):
    """The codec path: env specs as nested lists, the live index, the active set."""
    p = await disk.run(ops.add_plane())
    c = await disk.run(ops.add_cell(p, "src"))
    w = await disk.run(ops.worker())
    (r,) = await disk.run(ops.up(p, [c], worker=w, envs=[ops.env("session", "c1")]))
    assert (await disk.read(ops.runs()))[0]["envs"] == [["session", "c1"]]
    assert await disk.read(ops.live_runs(w)) == [r]
    assert await disk.read(ops.active_workers()) == [w]
    await disk.run(ops.down([r]) >> ops.kill_worker(w))
    assert (await disk.read(ops.runs()))[0]["status"] == STATUS_STOPPING
    assert (await disk.read(ops.workers()))[0]["status"] == STATUS_STOPPING
