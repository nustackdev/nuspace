"""The kernel with real workers, headless: plane runs start, end, get interrupted, killed, reaped.

One kernel for the module, on a throwaway store, with two spares: every test makes
its own plane, writes intents through ops, and polls the store until the kernel
and the backends have made them true. Reconcile runs against a bare store.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time

import pytest
import pytest_asyncio
from _support import kernel_envs
from _support.kernel import (
    BLOCKS,
    CRASHES,
    FOREVER,
    RAISES,
    READS_TAG,
    SET_42,
    cell_of,
    ended,
    live,
    only_cell,
    opened,
    texts,
    worker,
    workers_named,
)
from _support.probe import PROBE_INIT, Probe

import nu
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, EXIT_OK, Space, States
from nuspace.system.backends import AsyncBackend, Backend, MpBackend
from nuspace.system.kernel import INIT_BY, reconcile
from nustd.mp_pool import WorkerPool


kernel = Space.kernel
module_loop = pytest.mark.asyncio(loop_scope="module")

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space():
    envs = {"tagged": kernel_envs.tagged, "outer": kernel_envs.outer}
    k = await opened(spares=2, envs=envs, space_envs=["outer"])
    yield k
    await k.close()


async def live_cell(space, rid: str, cell: str) -> dict:
    """The run row once the cell's newest cell run is live."""
    return await space.run_row(rid, lambda r: live(cell_of(r, cell)), SLOW)


# --- Plane runs ------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["async", "mp"])
@module_loop
async def test_a_plane_runs_and_ends_when_its_cells_are_done(space, backend):
    p, (a, b) = await space.plane(SET_42, SET_42, backend=backend)
    r = await space.run(ops.plane_run(p, by="test"))
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], row["error"], row["by"], row["backend"]) == (EXIT_OK, "", "test", backend)
    assert [c["cell"] for c in row["cells"]] == [a, b]
    assert all(c["exit"] == EXIT_OK and c["by"] == "test" for c in row["cells"])
    assert all(c["started_at"] <= c["terminated_at"] for c in row["cells"])
    assert row["started_at"] <= row["terminated_at"]
    assert row["cells_running"] == []
    for cell in (a, b):
        assert await space.read(States.planes[p].cells[cell].extract()) == {"n": 42}
    assert r not in [x["id"] for x in await space.read(ops.runs())]
    # Its workers are records too, ended once the run was.
    assert len(row["workers"]) == (1 if backend == "async" else 2)
    assert {c["worker"] for c in row["cells"]} <= set(row["workers"])
    for w in row["workers"]:
        rec = await space.worker_row(w)
        assert (rec["backend"], rec["run"], rec["exit"]) == (backend, r, EXIT_OK)
        assert rec["handle"] != ""
    assert not set(row["workers"]) & {w["id"] for w in await space.read(ops.workers())}


@module_loop
async def test_a_plane_with_no_cells_ends_at_once(space):
    p, _ = await space.plane()
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], row["cells"]) == (EXIT_OK, [])


@module_loop
async def test_plane_run_on_a_missing_plane(space):
    assert await space.run(ops.plane_run("ghost")) == ""


@module_loop
async def test_a_failing_cell_records_why(space):
    p, _ = await space.plane(RAISES)
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, ended, SLOW)
    cr = only_cell(row)
    assert (row["exit"], cr["exit"]) == (EXIT_FAILED, EXIT_FAILED)
    assert "boom" in cr["error"]
    assert any("boom" in t for t in texts(cr, "stderr"))


@module_loop
async def test_an_unknown_backend_fails_the_run(space):
    p, _ = await space.plane(SET_42, backend="nope")
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_FAILED
    assert "nope" in row["error"]
    assert only_cell(row)["exit"] == EXIT_FAILED


@module_loop
async def test_a_plane_naming_no_backend_fails_the_run(space):
    # add_plane refuses an empty backend, so a row with none is written by hand.
    p, _ = await space.plane(SET_42, backend="mp")
    await space.run(atomic(Space.planes[p].props.backend.set("")))
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], row["backend"]) == (EXIT_FAILED, "")
    assert "names no backend" in row["error"]
    assert only_cell(row)["exit"] == EXIT_FAILED


@module_loop
async def test_an_unknown_env_fails_the_cell_run(space):
    p, _ = await space.plane(SET_42)
    r = await space.run(ops.plane_run(p, envs=[ops.env("nope")]))
    row = await space.run_row(r, ended, SLOW)
    assert only_cell(row)["exit"] == EXIT_FAILED
    assert "nope" in only_cell(row)["error"]


@module_loop
async def test_envs_wrap_and_rewrite_the_program(space):
    p, (a, b) = await space.plane(READS_TAG, READS_TAG)
    r = await space.run(ops.plane_run(p, envs=[ops.env("tagged", "inner")]))
    assert (await space.run_row(r, ended, SLOW))["exit"] == EXIT_OK
    q, (c,) = await space.plane(READS_TAG)
    r2 = await space.run(ops.plane_run(q))
    assert (await space.run_row(r2, ended, SLOW))["exit"] == EXIT_OK
    cells = States.planes[p].cells
    assert await space.read(cells[a].extract()) == {"s": "inner"}
    assert await space.read(cells[b].extract()) == {"s": "inner"}
    assert await space.read(States.planes[q].cells[c].extract()) == {"s": "outer"}
    assert await space.read(States.planes[p].state["stamped"]) is True


# --- Interrupt and cell runs -------------------------------------------------------------


@module_loop
async def test_cell_interrupt_ends_the_cell_run_and_then_the_plane_run(space):
    p, (c,) = await space.plane(FOREVER)
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, lambda x: "tick" in texts(cell_of(x, c)), SLOW)
    cr = cell_of(row, c)
    assert texts(cr, "stdout")[:2] == ["built", "tick"]
    assert cr["id"] in [x["id"] for x in await space.read(ops.cell_runs(r, live=True))]
    await space.run(ops.cell_interrupt(r, cr["id"]))
    row = await space.run_row(r, ended, SLOW)
    assert (only_cell(row)["exit"], only_cell(row)["error"]) == (EXIT_INTERRUPTED, "")
    assert only_cell(row)["interrupt_requested"] is True
    assert row["exit"] == EXIT_INTERRUPTED


@module_loop
async def test_cell_run_reruns_a_cell_in_the_live_plane_run(space):
    """A reload: interrupt the old cell run and run the cell anew, in one commit, same worker."""
    p, (c,) = await space.plane(FOREVER)
    r = await space.run(ops.plane_run(p))
    old = cell_of(await live_cell(space, r, c), c)
    assert old["version"] == 1
    await space.run(ops.set_prog(p, c, FOREVER.replace("tick", "tock")))
    await space.run(
        atomic(
            ops.kernel.interrupt(r, old["id"])
            >> ops.kernel.add_cell_run(r, c, "cr_test_new", by="reload")
        )
    )
    row = await space.run_row(
        r, lambda x: "tock" in texts(cell_of(x, c)) and ended(x["cells"][0]), SLOW
    )
    first, second = row["cells"]
    assert (first["id"], first["exit"]) == (old["id"], EXIT_INTERRUPTED)
    assert (second["id"], second["by"], second["version"]) == ("cr_test_new", "reload", 2)
    assert second["worker"] == first["worker"]
    assert not ended(row)
    # cell_run is the same thing as one op, yielding its id.
    third = await space.run(ops.cell_run(r, c, by="test"))
    assert third.startswith("cr_")
    await space.run_row(r, lambda x: any(live(y) for y in x["cells"] if y["id"] == third), SLOW)
    assert await space.run(ops.cell_run(r, "ghost")) == ""
    await space.run(ops.plane_kill(r))
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_KILLED
    assert await space.run(ops.cell_run(r, c)) == ""


@module_loop
async def test_a_plane_runs_exit_counts_each_cells_newest_cell_run_only(space):
    """A failed cell run run again and ok: the plane run ends ok, the failure superseded."""
    p, (keep, c) = await space.plane(FOREVER, RAISES)
    r = await space.run(ops.plane_run(p))
    await space.run_row(r, lambda x: cell_of(x, c).get("exit") == EXIT_FAILED, SLOW)
    await space.run(ops.set_prog(p, c, SET_42))
    again = await space.run(ops.cell_run(r, c))
    await space.run_row(r, lambda x: ended(cell_of(x, c)) and cell_of(x, c)["id"] == again, SLOW)
    await space.run(ops.cell_interrupt(r, cell_of(await space.read(ops.run(r)), keep)["id"]))
    row = await space.run_row(r, ended, SLOW)
    assert [y["exit"] for y in row["cells"] if y["cell"] == c] == [EXIT_FAILED, EXIT_OK]
    assert row["latest"] == {keep: cell_of(row, keep)["id"], c: again}
    assert row["exit"] == EXIT_OK


@module_loop
async def test_plane_interrupt_ends_every_cell_run(space):
    p, (a, b) = await space.plane(FOREVER, FOREVER)
    r = await space.run(ops.plane_run(p))
    await space.run_row(r, lambda x: live(cell_of(x, a)) and live(cell_of(x, b)), SLOW)
    await space.run(ops.plane_interrupt(r))
    row = await space.run_row(r, ended, SLOW)
    assert [c["exit"] for c in row["cells"]] == [EXIT_INTERRUPTED, EXIT_INTERRUPTED]
    assert row["exit"] == EXIT_INTERRUPTED


# --- Stop and kill -------------------------------------------------------------------


@module_loop
async def test_plane_stop_interrupts_a_cell_that_listens(space):
    p, (c,) = await space.plane(FOREVER)
    r = await space.run(ops.plane_run(p))
    await live_cell(space, r, c)
    started = time.monotonic()
    await space.run(ops.plane_stop(r))
    assert time.monotonic() - started < 5
    row = await space.read(ops.run(r))
    assert ended(row)
    assert (row["exit"], only_cell(row)["exit"], row["termination_requested"]) == (
        EXIT_INTERRUPTED,
        EXIT_INTERRUPTED,
        False,
    )


@module_loop
async def test_plane_stop_kills_after_the_grace(space):
    p, (c,) = await space.plane(BLOCKS)
    r = await space.run(ops.plane_run(p))
    await live_cell(space, r, c)
    # Past the program's first step: from here its loop is held.
    await asyncio.sleep(0.5)
    started = time.monotonic()
    await space.run(ops.plane_stop(r, grace=1.0))
    assert time.monotonic() - started >= 1.0
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], only_cell(row)["exit"]) == (EXIT_KILLED, EXIT_KILLED)
    assert row["termination_requested"] is True
    (w,) = row["workers"]
    assert (await space.worker_row(w))["exit"] == EXIT_KILLED


@pytest.mark.parametrize("backend", ["async", "mp"])
@module_loop
async def test_plane_kill_tears_the_run_down(space, backend):
    p, (a, b) = await space.plane(FOREVER, FOREVER, backend=backend)
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, lambda x: live(cell_of(x, a)) and live(cell_of(x, b)), SLOW)
    workers = row["workers"]
    assert set(workers) <= {w["id"] for w in await space.read(ops.workers())}
    await space.run(ops.plane_kill(r))
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_KILLED
    assert [c["exit"] for c in row["cells"]] == [EXIT_KILLED, EXIT_KILLED]
    for w in workers:
        assert (await space.worker_row(w))["exit"] == EXIT_KILLED
    assert not set(workers) & {w["id"] for w in await space.read(ops.workers())}


# --- Crashes -------------------------------------------------------------------------


@module_loop
async def test_mp_a_crash_ends_only_that_cell_run(space):
    p, (steady, crash) = await space.plane(FOREVER, CRASHES, backend="mp")
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, lambda x: ended(cell_of(x, crash)), SLOW)
    gone = cell_of(row, crash)
    assert gone["exit"] == EXIT_FAILED
    assert gone["error"].startswith("Worker exited")
    assert (await space.worker_row(gone["worker"]))["exit"] == EXIT_FAILED
    row = await live_cell(space, r, steady)
    assert not ended(row)
    assert cell_of(row, steady)["worker"] != gone["worker"]
    await space.run(ops.plane_kill(r))
    assert (await space.run_row(r, ended, SLOW))["exit"] == EXIT_KILLED


@module_loop
async def test_async_a_crash_ends_every_cell_run(space):
    p, (steady, crash) = await space.plane(FOREVER, CRASHES)
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_FAILED
    for cell in (steady, crash):
        assert cell_of(row, cell)["exit"] == EXIT_FAILED
        assert cell_of(row, cell)["error"].startswith("Worker exited")
    (w,) = row["workers"]
    assert (await space.worker_row(w))["exit"] == EXIT_FAILED


# --- Backends -------------------------------------------------------------------------

#: Ticks until cancelled, and marks ``cleaned`` on the way out. The mark lives
#: in the worker's mem store, where a later read finds it.
_TICKS = nu.TryCatch(
    Probe.cleaned.set(False) >> nu.ForeverDo(nu.Delay(0.01)),
    finally_=Probe.cleaned.set(True),
)


@contextlib.asynccontextmanager
async def _backend(cls: type[Backend]):
    """A bare backend over a bare pool, no store: bodies here are plain Nu."""
    pool = {"name": "nuspace-test-backend", "init": PROBE_INIT}
    async with nu.Provide(WorkerPool, pool)._aopen(nu.Context()) as ctx:
        backend = cls()
        await backend.asetup(ctx)
        try:
            yield backend, ctx.get(WorkerPool)
        finally:
            await backend.acleanup()


async def _cleaned(pool: WorkerPool, wid: int, want: bool) -> bool:
    deadline = time.monotonic() + SLOW
    while time.monotonic() < deadline:
        if await pool.ateleport(wid, Probe.cleaned) is want:
            return True
        await asyncio.sleep(0.02)
    return False


@pytest.mark.parametrize("cls", [AsyncBackend, MpBackend])
async def test_cancelling_a_cell_run_cancels_its_body_on_the_worker(cls):
    async with _backend(cls) as (backend, pool):
        await backend.astart("r")
        await backend.aplace("r", "c")
        wid = backend._holding("r", "c").wid
        arm = asyncio.create_task(backend.arun("r", "c", _TICKS, {}))
        assert await _cleaned(pool, wid, want=False)
        arm.cancel()
        with pytest.raises(asyncio.CancelledError):
            await arm
        # The body's own cleanup ran where it was, and the worker lives on.
        assert await _cleaned(pool, wid, want=True)
        assert pool.alive(wid)


@pytest.mark.parametrize(("cls", "shared"), [(AsyncBackend, True), (MpBackend, False)])
async def test_a_worker_dying_under_a_body_is_its_loss(cls, shared):
    async with _backend(cls) as (backend, pool):
        await backend.astart("r")
        for cell in ("a", "b"):
            await backend.aplace("r", cell)
        arms = {
            cell: asyncio.create_task(backend.arun("r", cell, nu.ForeverDo(nu.Delay(0.01)), {}))
            for cell in ("a", "b")
        }
        await asyncio.sleep(0.3)
        os.kill(pool._workers[backend._holding("r", "a").wid].proc.pid, signal.SIGKILL)
        assert await asyncio.wait_for(arms["a"], SLOW) == "Worker exited: -9"
        assert backend._holding("r", "a") is None
        if shared:
            assert await asyncio.wait_for(arms["b"], SLOW) == "Worker exited: -9"
        else:
            await asyncio.sleep(0.3)
            assert not arms["b"].done()
            arms["b"].cancel()


@pytest.mark.parametrize("cls", [AsyncBackend, MpBackend])
async def test_a_worker_let_go_is_no_loss(cls):
    async with _backend(cls) as (backend, _):
        await backend.astart("r")
        await backend.aplace("r", "c")
        arm = asyncio.create_task(backend.arun("r", "c", nu.ForeverDo(nu.Delay(0.01)), {}))
        await asyncio.sleep(0.3)
        await backend.akill("r")
        assert await asyncio.wait_for(arm, SLOW) == ""


# --- Shared store --------------------------------------------------------------------

_SHARED = """
import nu
import nustd.kv
import nuspace

class Shared(nuspace.PlaneState):
    ping = nustd.kv.IntRef.slot()
    pong = nustd.kv.IntRef.slot()

def out():
    return {}
"""

#: Wakes on the first ping it hears, and copies what it reads.
LISTENS = _SHARED.format("nu.React(Shared.ping.on_change(), Shared.pong.set(Shared.ping))")

#: Pings forever, every tenth of a second, so the listener hears one once it listens.
PINGS = _SHARED.format(
    "nu.ForeverDo(nu.IfDo(Shared.ping.missing(), Shared.ping.set(0))"
    " >> Shared.ping.set(Shared.ping + 1) >> nu.Delay(0.1))"
)


@module_loop
async def test_two_workers_share_the_store_and_hear_each_others_writes(space):
    """Each worker opens the store itself: a write in one wakes a subscriber in the other."""
    p, (listens, pings) = await space.plane(LISTENS, PINGS, backend="mp")
    r = await space.run(ops.plane_run(p))
    row = await space.run_row(r, lambda x: ended(cell_of(x, listens)), SLOW)
    heard = cell_of(row, listens)
    assert (heard["exit"], heard["error"]) == (EXIT_OK, "")
    assert heard["worker"] != cell_of(row, pings)["worker"]
    shared = States.planes[p].state
    pong = await space.read(shared["pong"])
    assert pong >= 1
    assert await space.read(shared["ping"]) >= pong
    await space.run(ops.plane_stop(r))
    assert cell_of(await space.read(ops.run(r)), pings)["exit"] == EXIT_INTERRUPTED


@module_loop
async def test_live_reads_walk_the_indexes(space):
    p, (c,) = await space.plane(FOREVER)
    r = await space.run(ops.plane_run(p, by="test"))
    await live_cell(space, r, c)
    (row,) = await space.read(ops.runs(plane=p))
    assert (row["id"], row["by"], row["plane"]) == (r, "test", p)
    assert len(row["cells_running"]) == 1
    (w,) = row["workers"]
    (rec,) = [x for x in await space.read(ops.workers()) if x["id"] == w]
    assert (rec["run"], rec["plane"], rec["backend"]) == (r, p, "async")
    await space.run(ops.plane_stop(r))
    assert await space.read(ops.runs(plane=p)) == []


@module_loop
async def test_closing_leaves_no_workers(space):
    await space.close()
    deadline = time.monotonic() + 5
    while workers_named("nuspace-test") and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert workers_named("nuspace-test") == []


# --- reconcile ------------------------------------------------------------------------


async def test_reopen_reconciles_then_starts_init(tmp_path):
    """Workers die with the host, so a reopen finds its records lying, fixes them, starts init."""
    path = str(tmp_path / "space")
    first = await opened("nuspace-reopen", path=path, spares=0)
    p, (c,) = await first.plane(FOREVER)
    r = await first.run(ops.plane_run(p))
    row = await live_cell(first, r, c)
    (w,) = row["workers"]
    await first.close()
    again = await opened("nuspace-reopen", path=path, spares=0, init=p)
    try:
        old = await again.run_row(r, ended)
        assert (old["exit"], only_cell(old)["exit"]) == (EXIT_KILLED, EXIT_KILLED)
        assert (await again.worker_row(w))["terminated_at"] is not None
        rows = await again.until(
            ops.runs(plane=p), lambda rs: any(x["by"] == INIT_BY for x in rs), SLOW
        )
        (fresh,) = [x for x in rows if x["by"] == INIT_BY]
        assert fresh["id"] != r
    finally:
        await again.close()
    assert workers_named("nuspace-reopen") == []


async def test_reconcile_ends_what_was_live(store):
    p = await store.run(ops.add_plane(backend="async"))
    c = await store.run(ops.add_cell(p, SET_42))
    r_live = await store.run(ops.plane_run(p))
    r_done = await store.run(ops.plane_run(p))
    await store.run(atomic(kernel.running.discard(r_done) >> kernel.runs[r_done].exit.set("ok")))
    w = "w_test"
    await store.run(atomic(kernel.workers[w].run.set(r_live) >> kernel.workers_running.add(w)))
    await store.run(reconcile())
    live_row = await store.read(ops.run(r_live))
    assert (live_row["exit"], only_cell(live_row)["exit"]) == (EXIT_KILLED, EXIT_KILLED)
    assert live_row["cells_running"] == []
    assert (await store.read(ops.run(r_done)))["exit"] == "ok"
    assert (await store.read(worker(w)))["exit"] == EXIT_KILLED
    assert await store.read(ops.runs()) == []
    assert await store.read(ops.workers()) == []
    del c


async def test_reconcile_makes_the_containers(store):
    await store.run(reconcile())
    assert await store.read(nu.List.of(ops.runs(), ops.workers())) == [[], []]
