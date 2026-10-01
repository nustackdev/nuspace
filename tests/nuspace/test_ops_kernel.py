"""Kernel ops: intents on records only, no kernel. The kernel that acts on them is test_kernel."""

from __future__ import annotations

import pytest

import nu
from nu.lang import wire
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import Space


kernel = Space.kernel


async def plane_with(store, n, backend="async", **kw):
    p = await store.run(ops.add_plane(backend=backend, **kw))
    cells = [await store.run(ops.add_cell(p, f"src{i}")) for i in range(n)]
    return p, cells


async def test_plane_run_writes_a_run_with_a_cell_run_for_each_cell(store):
    p, (a, b) = await plane_with(store, 2)
    await store.run(ops.reorder_cells(p, [b, a]))
    envs = [ops.env("session", "conn-7"), ops.env("lmdb")]
    r = await store.run(ops.plane_run(p, by="nav", envs=envs))
    assert r.startswith("r_")
    row = await store.read(ops.run(r))
    assert {k: row[k] for k in ("plane", "backend", "by", "envs", "termination_requested")} == {
        "plane": p,
        "backend": "async",
        "by": "nav",
        "envs": [["session", "conn-7"], ["lmdb"]],
        "termination_requested": False,
    }
    # Effects are the kernel's: nothing started, nothing ended.
    assert (row["started_at"], row["terminated_at"], row["exit"]) == (None, None, "")
    assert sorted(c["cell"] for c in row["cells"]) == sorted([a, b])
    assert all(c["by"] == "nav" and c["version"] == 1 for c in row["cells"])
    assert all(c["interrupt_requested"] is False and c["worker"] == "" for c in row["cells"])
    assert sorted(row["cells_running"]) == sorted(c["id"] for c in row["cells"])
    assert [x["id"] for x in await store.read(ops.runs())] == [r]
    assert [x["id"] for x in await store.read(ops.runs(plane=p))] == [r]
    assert await store.read(ops.runs(plane="other")) == []


async def test_plane_run_takes_the_planes_backend(store):
    p, _ = await plane_with(store, 1, backend="mp")
    r = await store.run(ops.plane_run(p))
    assert (await store.read(ops.run(r)))["backend"] == "mp"
    (row,) = [x for x in await store.read(ops.plane_rows()) if x["id"] == p]
    assert row["props"]["backend"] == "mp"


async def test_plane_run_mints_at_evaluation(store):
    p, _ = await plane_with(store, 1)
    term = ops.plane_run(p)
    first, second = await store.run(term), await store.run(term)
    again = await store.run(wire.loads(wire.dumps(ops.plane_run(p))))
    assert len({first, second, again}) == 3
    assert await store.run(ops.plane_run("nope")) == ""


async def test_cell_run_needs_a_live_run_and_a_cell(store):
    p, (a,) = await plane_with(store, 1)
    r = await store.run(ops.plane_run(p))
    cr = await store.run(ops.cell_run(r, a, by="reload"))
    assert cr.startswith("cr_")
    assert await store.run(ops.cell_run(r, "ghost")) == ""
    assert await store.run(ops.cell_run("r_ghost", a)) == ""
    live = await store.read(ops.cell_runs(r, live=True))
    assert cr in [c["id"] for c in live]
    (mine,) = [c for c in live if c["id"] == cr]
    assert (mine["cell"], mine["by"]) == (a, "reload")
    await store.run(atomic(kernel.running.discard(r)))
    assert await store.run(ops.cell_run(r, a)) == ""


async def test_latest_is_each_cells_newest_cell_run(store):
    p, (a, b) = await plane_with(store, 2)
    r = await store.run(ops.plane_run(p))
    row = await store.read(ops.run(r))
    first = {c["cell"]: c["id"] for c in row["cells"]}
    assert row["latest"] == first
    await store.run(ops.cell_run(r, a))
    again = await store.run(ops.cell_run(r, a))
    assert (await store.read(ops.run(r)))["latest"] == {a: again, b: first[b]}
    assert await store.read(nu.List.of(ops.latest(r, a), ops.latest(r, b))) == [again, first[b]]
    assert await store.read(ops.latest(r, "ghost")) == ""
    assert await store.read(ops.latest("r_ghost", a)) == ""


async def test_set_prog_bumps_the_version_a_cell_run_records(store):
    p, (a,) = await plane_with(store, 1)
    await store.run(ops.set_prog(p, a, "v2") >> ops.set_prog(p, a, "v3"))
    assert await store.read(Space.planes[p].cells[a].version) == 3
    r = await store.run(ops.plane_run(p))
    (cr,) = (await store.read(ops.run(r)))["cells"]
    assert cr["version"] == 3


async def test_interrupts_and_kill_write_intents_on_live_runs_only(store):
    p, _ = await plane_with(store, 2)
    r = await store.run(ops.plane_run(p))
    ca, cb = (await store.read(ops.run(r)))["cells_running"]
    await store.run(ops.cell_interrupt(r, ca) >> ops.cell_interrupt(r, "ghost"))
    flags = {c["id"]: c["interrupt_requested"] for c in (await store.read(ops.run(r)))["cells"]}
    assert flags == {ca: True, cb: False}
    await store.run(ops.plane_interrupt(r))
    assert all(c["interrupt_requested"] for c in (await store.read(ops.run(r)))["cells"])
    await store.run(ops.plane_kill(r))
    assert (await store.read(ops.run(r)))["termination_requested"] is True
    # A run out of running is not live: nothing more is asked of it.
    q = await store.run(ops.plane_run(p))
    await store.run(atomic(kernel.running.discard(q)))
    await store.run(ops.plane_kill(q))
    assert (await store.read(ops.run(q)))["termination_requested"] is False


async def test_remove_cell_interrupts_its_live_cell_runs(store):
    p, (a, b) = await plane_with(store, 2)
    r = await store.run(ops.plane_run(p))
    await store.run(ops.remove_cell(p, a))
    flags = {c["cell"]: c["interrupt_requested"] for c in (await store.read(ops.run(r)))["cells"]}
    assert flags == {a: True, b: False}


async def test_remove_plane_kills_its_live_runs(store):
    p, _ = await plane_with(store, 1)
    q, _ = await plane_with(store, 1)
    rp, rq = await store.run(ops.plane_run(p)), await store.run(ops.plane_run(q))
    assert await store.run(ops.remove_plane(p)) is True
    assert (await store.read(ops.run(rp)))["termination_requested"] is True
    assert (await store.read(ops.run(rq)))["termination_requested"] is False


def test_env_is_plain_data():
    assert ops.env("session", "conn-7") == ["session", "conn-7"]
    assert ops.env("lmdb") == ["lmdb"]


@pytest.mark.parametrize("name", ["plane", "cell", "run", "cell_run"])
def test_here_reads_its_frame(name):
    assert nu.run(nu.Frame(ops.Here, getattr(ops.Here, name), **{name: "x"}))[0] == "x"


async def test_run_records_round_trip_through_sqlite(disk):
    """The codec path: env specs as nested lists, the live sets."""
    p = await disk.run(ops.add_plane(backend="async"))
    await disk.run(ops.add_cell(p, "src"))
    r = await disk.run(ops.plane_run(p, envs=[ops.env("session", "c1")]))
    row = await disk.read(ops.run(r))
    assert row["envs"] == [["session", "c1"]]
    assert len(row["cells_running"]) == 1
    assert [x["id"] for x in await disk.read(ops.runs())] == [r]
    await disk.run(ops.plane_interrupt(r) >> ops.plane_kill(r))
    row = await disk.read(ops.run(r))
    assert row["termination_requested"] is True
    assert row["cells"][0]["interrupt_requested"] is True
    assert await disk.read(nu.List.of(ops.workers())) == [[]]
