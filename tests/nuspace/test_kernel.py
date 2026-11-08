"""The kernel with real workers, headless: plane runs start, end, get interrupted, killed, reaped.

One kernel for the module, on a throwaway space, with two spares: every
test makes its own plane, writes what it wants through ops, and polls the
store until the kernel and the backends have made it true. Error policy
tests open a kernel of their own with a misbehaving backend. Reap is tested
on a bare store and after a real crash of a host process.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import ClassVar

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
    Kernel,
    cell_of,
    ended,
    live,
    only_cell,
    opened,
    texts,
    workers_named,
)
from _support.made import MADE
from _support.probe import PROBE_INIT, Probe

import nu
import nuspace
import nustd.kv
from nu.lang import is_null
from nuspace.kernel import (
    CLOSED,
    LEFT_OVER,
    ORPHAN,
    UNENDED,
    AsyncBackend,
    Backend,
    MpBackend,
    close,
    reap,
)
from nuspace.kernel.backends import PER_PLANE_RUN, provided
from nuspace.kernel.kernel import _release
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, EXIT_OK, Space, State
from nustd.mp_pool import WorkerPool


module_loop = pytest.mark.asyncio(loop_scope="module")

#: The reap module itself: the package's ``reap`` name is the function.
reap_module = importlib.import_module("nuspace.kernel.reap")

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0

_live = Space.exec.indexes.live


class Tick(nu.Shape):
    """The state the test programs keep, read back from the host."""

    n = nustd.kv.IntRef.slot()
    s = nustd.kv.StrRef.slot()


def tick(cell: str) -> nu.Nu:
    return nuspace.at.cell(id=cell).state(Tick)


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space():
    envs = {"tagged": kernel_envs.tagged, "outer": kernel_envs.outer}
    k = await opened(spares=2, envs=envs, space_envs=["outer"])
    yield k
    await k.close()


async def live_cell(space, r: str, cell: str) -> dict:
    """The plane run row once the cell's newest cell run is live."""
    return await space.run_row(r, lambda x: live(cell_of(x, cell)), SLOW)


async def all_live(space, r: str, *cells: str) -> dict:
    return await space.run_row(r, lambda x: all(live(cell_of(x, c)) for c in cells), SLOW)


async def gone_from_live(space, r: str) -> None:
    held = await space.live()
    assert r not in held["plane_runs"]
    assert r not in held["plane_run_to_cell_runs"]
    assert r not in held["plane_run_to_workers"]
    assert r not in held["plane_run_to_failed_cells"]


# --- Plane runs ------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["async", "mp"])
@module_loop
async def test_a_plane_runs_and_ends_when_its_cells_are_done(space, backend):
    p, (a, b) = await space.plane(SET_42, SET_42, backend=backend)
    r = await space.start(p, by="test")
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], row["error"], row["by"], row["backend"]) == (EXIT_OK, "", "test", backend)
    assert [c["cell"] for c in row["cells"]] == [a, b]
    assert all(c["exit"] == EXIT_OK and c["by"] == "test" for c in row["cells"])
    assert all(c["started_at"] <= c["ended_at"] for c in row["cells"])
    assert row["started_at"] <= row["ended_at"]
    for cell in (a, b):
        assert await space.read(tick(cell).n) == 42
    await gone_from_live(space, r)
    # Its workers are records too, ended once the run was.
    assert len(row["workers"]) == (1 if backend == "async" else 2)
    assert {c["worker"] for c in row["cells"]} == {w["id"] for w in row["workers"]}
    for w in row["workers"]:
        assert (w["backend"], w["plane_run"], w["exit"]) == (backend, r, EXIT_OK)
        assert w["handle"]["pid"] > 0
        assert w["id"] not in (await space.live())["workers"]


@module_loop
async def test_a_plane_with_no_cells_ends_at_once(space):
    p, _ = await space.plane()
    r = await space.start(p)
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], row["cells"]) == (EXIT_OK, [])


@module_loop
async def test_a_failing_cell_records_why_and_fails_the_run(space):
    p, _ = await space.plane(RAISES)
    r = await space.start(p)
    row = await space.run_row(r, ended, SLOW)
    cr = only_cell(row)
    assert (row["exit"], cr["exit"]) == (EXIT_FAILED, EXIT_FAILED)
    assert "boom" in cr["error"]
    assert any("boom" in t for t in texts(cr, "stderr"))


@module_loop
async def test_output_lands_on_the_cell_run(space):
    p, (c,) = await space.plane(FOREVER)
    r = await space.start(p)
    row = await space.run_row(r, lambda x: "tick" in texts(cell_of(x, c)), SLOW)
    assert texts(cell_of(row, c), "stdout")[:2] == ["built", "tick"]
    await space.do(nuspace.plane_run.kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_an_unknown_backend_fails_the_run(space):
    p, _ = await space.plane(SET_42, backend="nope")
    r = await space.start(p)
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_FAILED
    assert "nope" in row["error"]
    assert row["cells"] == []
    await gone_from_live(space, r)


@module_loop
async def test_an_unknown_env_fails_the_cell_run(space):
    p, _ = await space.plane(SET_42)
    r = await space.start(p, envs=[["nope"]])
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], only_cell(row)["exit"]) == (EXIT_FAILED, EXIT_FAILED)
    assert "nope" in only_cell(row)["error"]


@module_loop
async def test_envs_wrap_and_rewrite_the_program(space):
    p, (a, b) = await space.plane(READS_TAG, READS_TAG)
    r = await space.start(p, envs=[["tagged", "inner"]])
    assert (await space.run_row(r, ended, SLOW))["exit"] == EXIT_OK
    q, (c,) = await space.plane(READS_TAG)
    r2 = await space.start(q)
    assert (await space.run_row(r2, ended, SLOW))["exit"] == EXIT_OK
    assert await space.read(tick(a).s) == "inner"
    assert await space.read(tick(b).s) == "inner"
    assert await space.read(tick(c).s) == "outer"
    stamped = nuspace.at.plane(id=p).state(kernel_envs.Stamped).stamped
    assert await space.read(stamped) is True


# --- Interrupts and cell runs ------------------------------------------------------------


@module_loop
async def test_cell_interrupt_ends_the_cell_run_and_then_the_plane_run(space):
    p, (c,) = await space.plane(FOREVER)
    r = await space.start(p)
    cr = cell_of(await live_cell(space, r, c), c)["id"]
    await space.do(nuspace.cell_run.interrupt(cr))
    row = await space.run_row(r, ended, SLOW)
    assert (only_cell(row)["exit"], only_cell(row)["error"]) == (EXIT_INTERRUPTED, "")
    # Nobody interrupted the plane run: it ran out of cell runs.
    assert row["exit"] == EXIT_OK


@module_loop
async def test_a_new_cell_run_in_a_live_plane_run_runs_on_its_worker(space):
    """What reload does: interrupt the old cell run and add a new one, in one commit."""
    p, (c,) = await space.plane(FOREVER)
    r = await space.start(p)
    old = cell_of(await live_cell(space, r, c), c)
    assert old["version"] == 1
    await space.do(nuspace.cell.set_prog(c, FOREVER.replace("tick", "tock")))
    await space.do(nuspace.cell_run.interrupt(old["id"]) >> nuspace.cell_run.add(r, c, by="reload"))
    row = await space.run_row(
        r, lambda x: "tock" in texts(cell_of(x, c)) and ended(x["cells"][0]), SLOW
    )
    first, second = row["cells"]
    assert (first["id"], first["exit"]) == (old["id"], EXIT_INTERRUPTED)
    assert (second["by"], second["version"]) == ("reload", 2)
    assert second["worker"] == first["worker"]
    assert not ended(row)
    await space.do(nuspace.plane_run.kill(r))
    row = await space.run_row(r, ended, SLOW)
    assert (row["exit"], cell_of(row, c)["exit"]) == (EXIT_KILLED, EXIT_KILLED)


@module_loop
async def test_a_plane_runs_exit_counts_each_cells_newest_cell_run_only(space):
    """A failed cell run run again and ok: the plane run ends ok, the failure replaced."""
    p, (keep, c) = await space.plane(FOREVER, RAISES)
    r = await space.start(p)
    await space.run_row(r, lambda x: cell_of(x, c).get("exit") == EXIT_FAILED, SLOW)
    assert await space.read(_live.plane_run_to_failed_cells[r].ids.extract()) == {c: True}
    await space.do(nuspace.cell.set_prog(c, SET_42))
    await space.do(nuspace.cell_run.add(r, c))
    await space.run_row(r, lambda x: cell_of(x, c).get("exit") == EXIT_OK, SLOW)
    kept = cell_of(await space.row(r), keep)["id"]
    await space.do(nuspace.cell_run.interrupt(kept))
    row = await space.run_row(r, ended, SLOW)
    assert [y["exit"] for y in row["cells"] if y["cell"] == c] == [EXIT_FAILED, EXIT_OK]
    assert row["exit"] == EXIT_OK


@pytest.mark.parametrize("how", ["interrupt", "stop", "remove"])
@module_loop
async def test_a_failed_cell_fails_the_run_even_when_it_is_interrupted(space, how):
    """Failed wins over interrupted: a policy restarting failed runs must see the failure."""
    p, (keep, c) = await space.plane(FOREVER, RAISES)
    r = await space.start(p)
    await space.run_row(r, lambda x: cell_of(x, c).get("exit") == EXIT_FAILED, SLOW)
    await live_cell(space, r, keep)
    asked = {
        "interrupt": nuspace.plane_run.interrupt(r),
        "stop": nuspace.plane_run.stop(r),
        "remove": nuspace.plane.remove(p),
    }[how]
    await space.do(asked)
    row = await space.run_row(r, ended, SLOW)
    assert (cell_of(row, keep)["exit"], cell_of(row, c)["exit"]) == (EXIT_INTERRUPTED, EXIT_FAILED)
    assert row["exit"] == EXIT_FAILED
    await gone_from_live(space, r)


@module_loop
async def test_a_cell_run_started_before_its_arm_is_born_ends_failed(space):
    """Started by an arm that is gone, nothing runs it: the kernel ends it, the run goes on."""
    p, (keep, c) = await space.plane(FOREVER, SET_42)
    r = await space.start(p)
    await space.run_row(r, lambda x: cell_of(x, c).get("exit") == EXIT_OK, SLOW)
    await live_cell(space, r, keep)
    # One commit: the cell run lands in the live set started already.
    orphan = nuspace.cell_run.add(r, c, into=MADE) >> nuspace.cell_run.start(
        nu.Str(MADE), worker="w_gone"
    )
    await space.do(orphan)
    cr = await space.run(MADE)
    row = await space.run_row(r, lambda x: ended(cell_of(x, c)) and cell_of(x, c)["id"] == cr, SLOW)
    assert (cell_of(row, c)["exit"], cell_of(row, c)["error"]) == (EXIT_FAILED, ORPHAN)
    assert live(cell_of(row, keep))
    assert not ended(row)
    await space.do(nuspace.plane_run.kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_plane_interrupt_ends_every_cell_run(space):
    p, (a, b) = await space.plane(FOREVER, FOREVER)
    r = await space.start(p)
    await all_live(space, r, a, b)
    await space.do(nuspace.plane_run.interrupt(r))
    row = await space.run_row(r, ended, SLOW)
    assert [c["exit"] for c in row["cells"]] == [EXIT_INTERRUPTED, EXIT_INTERRUPTED]
    assert row["exit"] == EXIT_INTERRUPTED


@module_loop
async def test_a_plane_interrupt_spares_cell_runs_added_after_it(space):
    p, (a,) = await space.plane(FOREVER)
    r = await space.start(p)
    old = cell_of(await live_cell(space, r, a), a)["id"]
    # One commit: the interrupt, then a cell run added after it.
    await space.do(nuspace.plane_run.interrupt(r) >> nuspace.cell_run.add(r, a, by="later"))
    row = await space.run_row(
        r,
        lambda x: [c.get("exit") for c in x["cells"] if c["id"] == old] == [EXIT_INTERRUPTED],
        SLOW,
    )
    row = await live_cell(space, r, a)
    fresh = cell_of(row, a)
    assert (fresh["by"], "interrupt_at" in fresh) == ("later", False)
    assert not ended(row)
    await space.do(nuspace.plane_run.kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_a_removed_cell_gets_its_run_interrupted(space):
    p, (a, b) = await space.plane(FOREVER, FOREVER)
    r = await space.start(p)
    await all_live(space, r, a, b)
    await space.do(nuspace.cell.remove(a))
    row = await space.run_row(r, lambda x: ended(cell_of(x, a)), SLOW)
    assert cell_of(row, a)["exit"] == EXIT_INTERRUPTED
    assert live(cell_of(row, b))
    assert not ended(row)
    await space.do(nuspace.plane_run.kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_a_moved_cell_gets_its_run_on_the_old_plane_interrupted(space):
    p, (a, b) = await space.plane(FOREVER, FOREVER)
    q, _ = await space.plane()
    r = await space.start(p)
    await all_live(space, r, a, b)
    await space.do(nuspace.cell.move(a, plane=q))
    row = await space.run_row(r, lambda x: ended(cell_of(x, a)), SLOW)
    assert cell_of(row, a)["exit"] == EXIT_INTERRUPTED
    assert live(cell_of(row, b))
    await space.do(nuspace.plane_run.kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_a_removed_plane_gets_its_run_stopped(space):
    p, (a, b) = await space.plane(FOREVER, FOREVER)
    r = await space.start(p)
    await all_live(space, r, a, b)
    await space.do(nuspace.plane.remove(p))
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_INTERRUPTED
    assert [c["exit"] for c in row["cells"]] == [EXIT_INTERRUPTED, EXIT_INTERRUPTED]
    assert "kill_at" in row


# --- Stop and kill -------------------------------------------------------------------


@module_loop
async def test_plane_stop_interrupts_a_cell_that_listens(space):
    p, (c,) = await space.plane(FOREVER)
    r = await space.start(p)
    await live_cell(space, r, c)
    started = time.monotonic()
    await space.do(nuspace.plane_run.stop(r))
    await space.run(nuspace.bracketed(nuspace.plane_run.wait(r)))
    assert time.monotonic() - started < 5
    row = await space.row(r)
    assert (row["exit"], only_cell(row)["exit"]) == (EXIT_INTERRUPTED, EXIT_INTERRUPTED)


async def blocking(k: Kernel, cell: str) -> None:
    """Wait until a :data:`BLOCKS` cell wrote its state: from there its loop is held."""
    state = State.cells[cell].extract()
    await k.until(lambda: k.read(state), lambda s: not is_null(s) and s.get("n") == 1, SLOW)


@module_loop
async def test_plane_stop_kills_after_the_grace(space):
    p, (c,) = await space.plane(BLOCKS)
    r = await space.start(p)
    await live_cell(space, r, c)
    await blocking(space, c)
    started = time.monotonic()
    await space.do(nuspace.plane_run.stop(r, grace=1.0))
    row = await space.run_row(r, ended, SLOW)
    assert time.monotonic() - started >= 0.9
    assert (row["exit"], only_cell(row)["exit"]) == (EXIT_KILLED, EXIT_KILLED)
    (w,) = row["workers"]
    assert w["exit"] == EXIT_KILLED


@module_loop
async def test_a_kill_at_moved_earlier_restarts_the_wait(space):
    """A stop with a long grace, then a kill: the kill does not wait out the grace."""
    p, (c,) = await space.plane(BLOCKS)
    r = await space.start(p)
    await live_cell(space, r, c)
    await blocking(space, c)
    await space.do(nuspace.plane_run.stop(r, grace=600.0))
    await asyncio.sleep(0.3)
    assert not ended(await space.row(r))
    started = time.monotonic()
    await space.do(nuspace.plane_run.kill(r))
    row = await space.run_row(r, ended, SLOW)
    assert time.monotonic() - started < SLOW
    assert (row["exit"], only_cell(row)["exit"]) == (EXIT_KILLED, EXIT_KILLED)


@pytest.mark.parametrize("backend", ["async", "mp"])
@module_loop
async def test_plane_kill_tears_the_run_down(space, backend):
    p, (a, b) = await space.plane(FOREVER, FOREVER, backend=backend)
    r = await space.start(p)
    row = await all_live(space, r, a, b)
    pids = [w["handle"]["pid"] for w in row["workers"]]
    await space.do(nuspace.plane_run.kill(r))
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_KILLED
    assert [c["exit"] for c in row["cells"]] == [EXIT_KILLED, EXIT_KILLED]
    assert all(w["exit"] == EXIT_KILLED for w in row["workers"])
    await gone_from_live(space, r)
    await _all_gone(pids)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie child counts as gone: reaped by the pool's reader.
    with contextlib.suppress(OSError):
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    return True


async def _all_gone(pids: list[int]) -> None:
    deadline = time.monotonic() + SLOW
    while any(_alive(pid) for pid in pids):
        assert time.monotonic() < deadline, f"still up: {[p for p in pids if _alive(p)]}"
        await asyncio.sleep(0.05)


# --- Crashes -------------------------------------------------------------------------


@module_loop
async def test_mp_a_crash_ends_only_that_cell_run(space):
    p, (steady, crash) = await space.plane(FOREVER, CRASHES, backend="mp")
    r = await space.start(p)
    row = await space.run_row(r, lambda x: ended(cell_of(x, crash)), SLOW)
    gone = cell_of(row, crash)
    assert gone["exit"] == EXIT_FAILED
    assert gone["error"].startswith("Worker exited")
    (dead,) = [w for w in row["workers"] if w["id"] == gone["worker"]]
    assert dead["exit"] == EXIT_FAILED
    row = await live_cell(space, r, steady)
    assert not ended(row)
    assert cell_of(row, steady)["worker"] != gone["worker"]
    await space.do(nuspace.plane_run.kill(r))
    assert (await space.run_row(r, ended, SLOW))["exit"] == EXIT_KILLED


@module_loop
async def test_async_a_crash_ends_every_cell_run(space):
    p, (steady, crash) = await space.plane(FOREVER, CRASHES)
    r = await space.start(p)
    row = await space.run_row(r, ended, SLOW)
    assert row["exit"] == EXIT_FAILED
    for cell in (steady, crash):
        assert cell_of(row, cell)["exit"] == EXIT_FAILED
        assert cell_of(row, cell)["error"].startswith("Worker exited")
    (w,) = row["workers"]
    assert w["exit"] == EXIT_FAILED


_SHARED = """
import nu
import nustd.kv
import nuspace

class Shared(nu.Shape):
    ping = nustd.kv.IntRef.slot()
    pong = nustd.kv.IntRef.slot()

shared = nuspace.at.plane.state(Shared)

def out():
    return nuspace.bracketed({})
"""

#: Wakes on the first ping it hears, and copies what it reads.
LISTENS = _SHARED.format("nu.ReactOnce(shared.ping.on_change(), shared.pong.set(shared.ping))")

#: Pings forever, every tenth of a second, so the listener hears one once it listens.
PINGS = _SHARED.format(
    "nu.ForeverDo(shared.ping.init(0) >> shared.ping.set(shared.ping + 1) >> nu.Delay(0.1))"
)


class Shared(nu.Shape):
    ping = nustd.kv.IntRef.slot()
    pong = nustd.kv.IntRef.slot()


@module_loop
async def test_two_workers_share_the_store_and_hear_each_others_writes(space):
    """Each worker opens the stores itself: a write in one wakes a subscriber in the other."""
    p, (listens, pings) = await space.plane(LISTENS, PINGS, backend="mp")
    r = await space.start(p)
    row = await space.run_row(r, lambda x: ended(cell_of(x, listens)), SLOW)
    heard = cell_of(row, listens)
    assert (heard["exit"], heard["error"]) == (EXIT_OK, "")
    assert heard["worker"] != cell_of(row, pings)["worker"]
    shared = nuspace.at.plane(id=p).state(Shared)
    pong = await space.read(shared.pong)
    assert pong >= 1
    assert await space.read(shared.ping) >= pong
    await space.do(nuspace.plane_run.stop(r))
    row = await space.run_row(r, ended, SLOW)
    assert cell_of(row, pings)["exit"] == EXIT_INTERRUPTED


@module_loop
async def test_closing_leaves_no_workers(space):
    k = await opened("nuspace-closing", spares=1)
    p, (c,) = await k.plane(FOREVER, backend="mp")
    r = await k.start(p)
    await live_cell(k, r, c)
    await k.close()
    deadline = time.monotonic() + 5
    while workers_named("nuspace-closing") and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert workers_named("nuspace-closing") == []


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
    ctx = nu.Context()
    async with nu.Provide(WorkerPool, pool)._aopen(ctx):
        backend = cls()
        await backend.asetup(ctx)
        try:
            yield backend, ctx.fabrics.get(WorkerPool)
        finally:
            await backend.acleanup()


async def _cleaned(pool: WorkerPool, wid: int, want: bool) -> bool:
    deadline = time.monotonic() + SLOW
    while time.monotonic() < deadline:
        if await pool.ateleport(wid, Probe.cleaned) is want:
            return True
        await asyncio.sleep(0.02)
    return False


async def test_placements_and_the_reap_default():
    assert AsyncBackend.placement == PER_PLANE_RUN
    assert MpBackend.placement == "cell_run"
    # Reap does not kill by handle yet: the contract's default does nothing.
    assert await Backend().areap({"pid": 1}) is None

    class Odd(AsyncBackend):
        placement = "per_moon"

    with pytest.raises(ValueError, match="per_moon"):
        provided({"odd": Odd})


@pytest.mark.parametrize("cls", [AsyncBackend, MpBackend])
async def test_launch_hands_back_a_handle_keyed_by_the_minted_id(cls):
    async with _backend(cls) as (backend, pool):
        handle = await backend.alaunch("w_test")
        assert handle["pid"] == pool.status(handle["wid"]).pid
        assert await backend.arun("w_test", "cr", Probe.cleaned.set(True)) == ""
        await backend.astop("w_test")
        assert pool.status(handle["wid"]).state == "exited"
        # Let go twice, or a worker never launched: nothing happens.
        await backend.astop("w_test")
        await backend.akill("w_never")
        with pytest.raises(RuntimeError, match="not up"):
            await backend.arun("w_test", "cr", Probe.cleaned.set(True))


@pytest.mark.parametrize("cls", [AsyncBackend, MpBackend])
async def test_cancelling_a_cell_run_cancels_its_body_on_the_worker(cls):
    async with _backend(cls) as (backend, pool):
        wid = (await backend.alaunch("w"))["wid"]
        arm = asyncio.create_task(backend.arun("w", "c", _TICKS))
        assert await _cleaned(pool, wid, want=False)
        arm.cancel()
        with pytest.raises(asyncio.CancelledError):
            await arm
        # The body's own cleanup ran where it was, and the worker lives on.
        assert await _cleaned(pool, wid, want=True)
        assert pool.status(wid).state != "exited"


@pytest.mark.parametrize("cls", [AsyncBackend, MpBackend])
async def test_a_worker_dying_under_bodies_is_their_loss(cls):
    async with _backend(cls) as (backend, pool):
        wid = (await backend.alaunch("w"))["wid"]
        arms = [
            asyncio.create_task(backend.arun("w", cell, nu.ForeverDo(nu.Delay(0.01))))
            for cell in ("a", "b")
        ]
        await asyncio.sleep(0.3)
        os.kill(pool.status(wid).pid, signal.SIGKILL)
        for arm in arms:
            assert await asyncio.wait_for(arm, SLOW) == "Worker exited: -9"
        with pytest.raises(RuntimeError, match="not up"):
            await backend.arun("w", "c", nu.Noop())


@pytest.mark.parametrize("let_go", ["astop", "akill"])
async def test_a_worker_let_go_is_no_loss(let_go):
    async with _backend(MpBackend) as (backend, _):
        await backend.alaunch("w")
        arm = asyncio.create_task(backend.arun("w", "c", nu.ForeverDo(nu.Delay(0.01))))
        await asyncio.sleep(0.3)
        await getattr(backend, let_go)("w")
        assert await asyncio.wait_for(arm, SLOW) == ""


# --- Error policy -----------------------------------------------------------------------


class _Brittle(AsyncBackend):
    """Lets go as ``async`` does, then raises."""

    async def astop(self, worker: str) -> None:
        await super().astop(worker)
        msg = "stop boom"
        raise RuntimeError(msg)


async def test_a_raising_let_go_is_reported_and_the_folds_go_on(capfd):
    k = await opened("nuspace-brittle", spares=1, backends={"brittle": _Brittle})
    try:
        p, _ = await k.plane(SET_42, backend="brittle")
        r = await k.start(p)
        row = await k.run_row(r, ended, SLOW)
        assert (row["exit"], only_cell(row)["exit"]) == (EXIT_OK, EXIT_OK)
        deadline = time.monotonic() + SLOW
        out = ""
        while time.monotonic() < deadline and "stop boom" not in out:
            out += capfd.readouterr().out
            await asyncio.sleep(0.05)
        # Reported by the arm, or by the let go itself once the arm was cancelled.
        assert "stop boom" in out
        assert f"nuspace kernel plane run {r}: " in out or "nuspace kernel let go of w_" in out
        # Its end stands, and the fold is still up: the next run runs to its end.
        assert (await k.row(r))["exit"] == EXIT_OK
        q, _ = await k.plane(SET_42)
        again = await k.run_row(await k.start(q), ended, SLOW)
        assert (again["exit"], only_cell(again)["exit"]) == (EXIT_OK, EXIT_OK)
    finally:
        await k.close()


class _RunRaises(AsyncBackend):
    """Launches, then raises instead of running a body."""

    async def arun(self, worker: str, cell_run: str, body: nu.Nu) -> str:
        msg = "run boom"
        raise RuntimeError(msg)


class _Unending(AsyncBackend):
    """Says the body ended without running it, so its end is never written."""

    async def arun(self, worker: str, cell_run: str, body: nu.Nu) -> str:
        return ""


class _NoLaunch(MpBackend):
    """Fails to bring any worker up."""

    async def alaunch(self, worker: str) -> dict[str, object]:
        msg = "launch boom"
        raise RuntimeError(msg)


class _NoLaunchShared(_NoLaunch):
    placement = PER_PLANE_RUN


async def test_misbehaving_backends_fail_what_they_hold():
    backends = {
        "raises": _RunRaises,
        "unending": _Unending,
        "nolaunch": _NoLaunch,
        "nolaunch_shared": _NoLaunchShared,
    }
    k = await opened("nuspace-misbehaving", spares=1, backends=backends)
    try:
        p, _ = await k.plane(SET_42, backend="raises")
        row = await k.run_row(await k.start(p), ended, SLOW)
        assert (row["exit"], only_cell(row)["exit"]) == (EXIT_FAILED, EXIT_FAILED)
        assert "run boom" in only_cell(row)["error"]

        p, _ = await k.plane(SET_42, backend="unending")
        row = await k.run_row(await k.start(p), ended, SLOW)
        cr = only_cell(row)
        assert (row["exit"], cr["exit"], cr["error"]) == (EXIT_FAILED, EXIT_FAILED, UNENDED)

        # A worker per cell run that never comes up: the cell run fails, the worker too.
        p, _ = await k.plane(SET_42, backend="nolaunch")
        r = await k.start(p)
        row = await k.run_row(r, ended, SLOW)
        assert (row["exit"], only_cell(row)["exit"]) == (EXIT_FAILED, EXIT_FAILED)
        assert "launch boom" in only_cell(row)["error"]
        (w,) = row["workers"]
        assert (w["exit"], "launch boom" in w["error"]) == (EXIT_FAILED, True)
        await gone_from_live(k, r)

        # The plane run's one worker never comes up: the run fails before any cell run.
        p, _ = await k.plane(SET_42, backend="nolaunch_shared")
        r = await k.start(p)
        row = await k.run_row(r, ended, SLOW)
        assert (row["exit"], row["cells"]) == (EXIT_FAILED, [])
        assert "launch boom" in row["error"]
        assert row["workers"][0]["exit"] == EXIT_FAILED
        await gone_from_live(k, r)
    finally:
        await k.close()


class _Counts(Backend):
    """Records every worker it is asked to let go."""

    placement = PER_PLANE_RUN
    stopped: ClassVar[list[str]] = []

    async def astop(self, worker: str) -> None:
        self.stopped.append(worker)


@pytest.mark.parametrize(("taken", "stopped"), [("w_taken", ["w_taken"]), ("", [])])
async def test_release_lets_go_of_the_worker_the_arm_took(store, taken, stopped):
    """Cancelled between the end's commit and its let go, the live set is empty already."""
    await store.run(nuspace.atomic(nuspace.plane.add("p", backend="counts")))
    r = await store.made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    _Counts.stopped.clear()
    bound = nu.Provide(_Counts, {}, tag="counts", bind_as=Backend)
    release = nu.let(taken, lambda slot: _release(nu.Str(r), nu.Str("counts"), slot))
    await store.run(nu.With(bound, body=release))
    assert _Counts.stopped == stopped


# --- Reap ------------------------------------------------------------------------------


async def test_reap_ends_what_was_live_and_clears_live(store, capfd):
    """A crash simulated in the store: records left live, as a host that died leaves them."""
    await store.run(
        nuspace.atomic(
            nuspace.plane.add("p", backend="async")
            >> nuspace.cell.add("p", SET_42, id="c1", fabrics=[])
            >> nuspace.cell.add("p", SET_42, id="c2", fabrics=[])
        )
    )
    r_live = await store.made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    r_done = await store.made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    await store.run(nuspace.atomic(nuspace.plane_run.end(r_done, EXIT_OK)))
    w = await store.made(nuspace.atomic(nuspace.worker.add(r_live, "async", into=MADE)))
    await store.run(nuspace.atomic(nuspace.worker.start(w, handle={"pid": 1})))
    crs = []
    for c in ("c1", "c2"):
        crs.append(await store.made(nuspace.atomic(nuspace.cell_run.add(r_live, c, into=MADE))))
    await store.run(nuspace.atomic(nuspace.cell_run.start(crs[0], worker=w)))

    await store.run(reap())

    err = capfd.readouterr().err
    assert f"nuspace reap: plane run {r_live} of plane p was left live" in err
    assert f"nuspace reap: worker {w} on async was left live" in err
    rows = Space.exec
    for ref in (rows.plane_runs[r_live], rows.workers[w], *(rows.cell_runs[cr] for cr in crs)):
        rec = await store.read(ref.extract())
        assert (rec["exit"], rec["error"]) == (EXIT_KILLED, LEFT_OVER)
        assert rec["ended_at"] >= rec["created_at"]
    assert (await store.read(rows.plane_runs[r_done].exit)) == EXIT_OK
    assert await store.read(_live.extract()) == {
        "plane_runs": {},
        "plane_to_plane_runs": {},
        "cell_to_cell_runs": {},
        "plane_run_to_cell_runs": {},
        "plane_run_to_failed_cells": {},
        "plane_run_to_workers": {},
        "workers": {},
    }
    # Live is usable again: a new run lands in it.
    r = await store.made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    assert await store.read(nu.list(_live.plane_runs.keys())) == [r]


async def test_reap_on_a_clean_store_writes_nothing_and_says_nothing(store, capfd):
    await store.run(reap())
    assert capfd.readouterr().err == ""
    assert await store.read(nu.Not(_live.plane_runs)) is True


async def test_reap_clears_live_even_when_the_ends_fail(store, capfd):
    """An index naming a run whose row a half written op left inconsistent: live is cleared anyway."""
    await store.run(nuspace.atomic(nuspace.plane.add("p", backend="async")))
    r = await store.made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    # The plane's live set lost the run: plane_run.end's strict delete raises.
    await store.run(nuspace.atomic(_live.plane_to_plane_runs["p"].ids.del_item(r)))
    await store.run(reap())
    assert "could not end the leftovers" in capfd.readouterr().err
    assert await store.read(nu.Not(_live.plane_runs)) is True


async def test_reap_ends_the_leftovers_even_when_the_warnings_fail(store, capfd, monkeypatch):
    await store.run(nuspace.atomic(nuspace.plane.add("p", backend="async")))
    r = await store.made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    monkeypatch.setattr(reap_module, "_warnings", lambda: nu.Raise("list boom"))
    await store.run(reap())
    assert "nuspace reap: could not list the leftovers: " in capfd.readouterr().err
    assert await store.read(Space.exec.plane_runs[r].exit) == EXIT_KILLED
    assert await store.read(nu.Not(_live.plane_runs)) is True


# --- Close ------------------------------------------------------------------------------


async def _live_run(store) -> tuple[str, str, list[str]]:
    """A plane run left live in the store, as a closing host finds it: its worker and two cell runs."""
    await store.run(
        nuspace.atomic(
            nuspace.plane.add("p", backend="async")
            >> nuspace.cell.add("p", SET_42, id="c1", fabrics=[])
            >> nuspace.cell.add("p", SET_42, id="c2", fabrics=[])
        )
    )
    r = await store.made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    w = await store.made(nuspace.atomic(nuspace.worker.add(r, "async", into=MADE)))
    await store.run(nuspace.atomic(nuspace.worker.start(w, handle={"pid": 1})))
    crs = []
    for c in ("c1", "c2"):
        crs.append(await store.made(nuspace.atomic(nuspace.cell_run.add(r, c, into=MADE))))
    await store.run(nuspace.atomic(nuspace.cell_run.start(crs[0], worker=w)))
    return r, w, crs


async def test_close_ends_what_is_live_interrupted_and_skips_what_ended(store, capfd):
    r, w, crs = await _live_run(store)
    # A worker that ended, still listed live: the guarded end skips it.
    gone = await store.made(nuspace.atomic(nuspace.worker.add(r, "async", into=MADE)))
    await store.run(nuspace.atomic(nuspace.worker.end(gone, EXIT_OK)))
    await store.run(nuspace.atomic(_live.workers.set_item(gone, True)))

    await store.run(close())

    assert capfd.readouterr().err == ""
    rows = Space.exec
    for ref in (rows.plane_runs[r], rows.workers[w], *(rows.cell_runs[cr] for cr in crs)):
        rec = await store.read(ref.extract())
        assert (rec["exit"], rec["error"]) == (EXIT_INTERRUPTED, CLOSED)
    assert (await store.read(rows.workers[gone].exit)) == EXIT_OK
    assert await store.read(nu.Not(_live.plane_runs)) is True
    assert await store.read(nu.list(_live.workers.keys())) == [gone]


async def test_close_ends_a_plane_run_whose_cell_failed_failed(store):
    r, _, crs = await _live_run(store)
    await store.run(nuspace.atomic(nuspace.cell_run.end(crs[0], EXIT_FAILED, "boom")))
    await store.run(close())
    rows = Space.exec
    assert (await store.read(rows.plane_runs[r].exit)) == EXIT_FAILED
    assert (await store.read(rows.cell_runs[crs[1]].exit)) == EXIT_INTERRUPTED


async def test_close_reports_a_failed_commit_and_leaves_live_for_the_reap(store, capfd):
    r, w, crs = await _live_run(store)
    # The plane's live set lost the run: plane_run.end's strict delete raises.
    await store.run(nuspace.atomic(_live.plane_to_plane_runs["p"].ids.del_item(r)))
    await store.run(close())
    assert "nuspace close: could not end what was live" in capfd.readouterr().err
    # One commit: nothing of it landed.
    rows = Space.exec
    for ref in (rows.plane_runs[r], rows.workers[w], *(rows.cell_runs[cr] for cr in crs)):
        assert not (await store.read(ref.ended_at.exists()))
    assert await store.read(nu.list(_live.plane_runs.keys())) == [r]
    assert await store.read(nu.list(_live.workers.keys())) == [w]


@module_loop
async def test_a_cell_arm_cancelled_mid_run_leaves_its_worker_to_the_close(tmp_path):
    """A per cell run worker is let go, not ended, when its arm is cancelled with the run live."""
    data = str(tmp_path / "space")
    k = await opened("nuspace-cancelled", data=data, spares=0)
    p, (c,) = await k.plane(FOREVER, backend="mp")
    r = await k.start(p)
    await live_cell(k, r, c)
    # Cancelled without the host's close: the worker stays live, so the reopen reaps it.
    await k.close()
    k = await opened("nuspace-cancelled", data=data, spares=0)
    try:
        row = await k.row(r)
        (w,) = row["workers"]
        assert (w["exit"], w["error"]) == (EXIT_KILLED, LEFT_OVER)
        assert (only_cell(row)["exit"], row["exit"]) == (EXIT_KILLED, EXIT_KILLED)
    finally:
        await k.close()


async def test_reap_after_a_host_crash(tmp_path):
    """A host killed with SIGKILL mid run: its workers die with it, the reopen ends the records."""
    data = str(tmp_path / "space")
    marker = tmp_path / "live.json"
    lib = str(Path(__file__).resolve().parents[1] / "_lib")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([lib, os.environ.get("PYTHONPATH", "")])}
    host = subprocess.Popen(  # noqa: S603 -- our own interpreter and module
        [sys.executable, "-m", "_support.crash_host", data, str(marker)], env=env
    )
    try:
        deadline = time.monotonic() + 60
        while not marker.exists():
            assert host.poll() is None, "the host died before its runs were live"
            assert time.monotonic() < deadline, "the host never got its runs live"
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.2)
        left = json.loads(marker.read_text())
        host.send_signal(signal.SIGKILL)
        host.wait(10)
    finally:
        if host.poll() is None:
            host.kill()
    # mp_pool's parent watch: every worker goes with its host.
    await _all_gone(left["pids"])

    k = await opened("nuspace-reopened", data=data, spares=0)
    try:
        for r in left["runs"]:
            row = await k.row(r)
            assert (row["exit"], row["error"]) == (EXIT_KILLED, LEFT_OVER)
            assert [c["exit"] for c in row["cells"]] == [EXIT_KILLED, EXIT_KILLED]
            assert all(w["exit"] == EXIT_KILLED for w in row["workers"])
        held = await k.live()
        assert held["plane_runs"] == {} and held["workers"] == {}
        # The reopened kernel runs plane runs again.
        p, _ = await k.plane(SET_42)
        assert (await k.run_row(await k.start(p), ended, SLOW))["exit"] == EXIT_OK
    finally:
        await k.close()
