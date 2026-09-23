"""The kernel with real workers, headless: runs start, end, stop, fail and are reaped.

One kernel for the module, in memory, with two spares: every test asks for
its own worker and plane, writes requests through ops, and polls the store
until the kernel has made them true. Reconcile runs against a bare store.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import (
    EXIT_FAILED,
    EXIT_KILLED,
    EXIT_OK,
    EXIT_STOPPED,
    KIND_DOCKER,
    STATUS_DEAD,
    STATUS_UP,
    Space,
)
from nuspace.system.kernel import INIT_BY, open_kernel, reconcile


if TYPE_CHECKING:
    from collections.abc import Callable


# Spawned workers inherit sys.path, so they can unpickle what kernel_envs defines.
sys.path.insert(0, str(Path(__file__).parent))
import kernel_envs


kernel = Space.kernel
module_loop = pytest.mark.asyncio(loop_scope="module")


# --- programs ------------------------------------------------------------------

_HEAD = """
import nu
import nustd.kv
import nuspace

class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()
    s = nustd.kv.StrRef.slot()

def out():
"""


def prog(*lines: str) -> str:
    """A program with ``Tick`` declared, whose ``out`` runs ``lines``."""
    return _HEAD + "".join(f"    {line}\n" for line in lines)


SET_42 = prog("return Tick.n.set(42)")
RAISES = prog('raise ValueError("boom")')
FOREVER = prog('print("built")', 'return nu.print("tick") >> nu.ForeverDo(nu.Delay(0.05))')
READS_TAG = prog('return Tick.s.set(nu.StrAttrRef("test.tag"))')


# --- the harness ------------------------------------------------------------------


class _Hold(ScalarQuery):
    """Hands the host context to ``opened``, then waits for ``done``."""

    def __init__(self, opened: asyncio.Future, done: asyncio.Event) -> None:
        super().__init__()
        self._payload = {"opened": opened, "done": done}

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        opened, done = self._payload["opened"], self._payload["done"]

        async def athunk(rt: object) -> object:
            opened.set_result(rt.ctx)
            await done.wait()

        return athunk


@dataclass
class Kernel:
    """An open kernel: run ops against it, read the store, wait for the kernel."""

    ctx: nu.Context
    done: asyncio.Event
    task: asyncio.Task

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(nustd.kv.Snapshot(term, scope=Space))

    async def until(
        self, term: nu.Nu, pred: Callable[[object], bool], timeout: float = 4.0
    ) -> object:
        """Read ``term`` until ``pred`` holds on it, or fail with the last value."""
        deadline = time.monotonic() + timeout
        while True:
            value = await self.read(term)
            if pred(value):
                return value
            if time.monotonic() > deadline:
                msg = f"timed out waiting, last read: {value!r}"
                raise AssertionError(msg)
            await asyncio.sleep(0.05)

    async def run_row(self, rid: str, pred: Callable[[dict], bool]) -> dict:
        rows = await self.until(ops.runs(), lambda rs: pred(_by_id(rs, rid)))
        return _by_id(rows, rid)

    async def worker_row(self, wid: str, pred: Callable[[dict], bool]) -> dict:
        rows = await self.until(ops.workers(), lambda ws: pred(_by_id(ws, wid)))
        return _by_id(rows, wid)

    async def plane(self, *progs: str) -> tuple[str, list[str]]:
        p = await self.run(ops.add_plane())
        return p, [await self.run(ops.add_cell(p, src)) for src in progs]

    async def close(self) -> None:
        if not self.task.done():
            self.done.set()
            await asyncio.wait_for(self.task, 15)


def _by_id(rows: list[dict], rid: str) -> dict:
    return next((r for r in rows if r["id"] == rid), {})


def _dead(row: dict) -> bool:
    return row.get("status") == STATUS_DEAD


def _up(row: dict) -> bool:
    return row.get("status") == STATUS_UP


def _texts(row: dict, stream: str | None = None) -> list[str]:
    return [text for _, s, text in row["out"] if stream is None or s == stream]


def workers_named(prefix: str) -> list:
    return [p for p in multiprocessing.active_children() if p.name.startswith(prefix)]


async def opened(name: str = "nuspace-test", **kwargs: object) -> Kernel:
    """A kernel open on this loop, held until :meth:`Kernel.close`."""
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    body = nu.Let("test.held", _Hold(ready, done), nu.SetCmd(nu.AnyAttrRef("test.x"), 1))
    task = asyncio.create_task(nu.arun(open_kernel(body, name=name, **kwargs)))
    ctx = await asyncio.wait_for(asyncio.shield(ready), 20)
    return Kernel(ctx, done, task)


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space():
    envs = {"tagged": kernel_envs.tagged, "outer": kernel_envs.outer}
    k = await opened(spares=2, envs=envs, space_envs=["outer"])
    yield k
    await k.close()


# --- runs ---------------------------------------------------------------------------


@module_loop
async def test_a_cell_runs_and_its_state_lands(space):
    p, (c,) = await space.plane(SET_42)
    w = await space.run(ops.worker())
    (r,) = await space.run(ops.up(p, [c], worker=w, by="test"))
    row = await space.run_row(r, _dead)
    assert (row["exit"], row["error"], row["by"]) == (EXIT_OK, "", "test")
    assert row["started"] <= row["ended"]
    assert await space.read(Space.planes[p].cells[c].state.extract()) == {"n": 42}
    assert r not in await space.read(ops.live_runs())


@module_loop
async def test_a_failing_cell_records_why(space):
    p, (c,) = await space.plane(RAISES)
    w = await space.run(ops.worker())
    (r,) = await space.run(ops.up(p, [c], worker=w))
    row = await space.run_row(r, _dead)
    assert row["exit"] == EXIT_FAILED
    assert "boom" in row["error"]
    assert any("boom" in t for t in _texts(row, "stderr"))


@module_loop
async def test_down_stops_a_forever_cell_and_out_flushes_while_up(space):
    p, (c,) = await space.plane(FOREVER)
    w = await space.run(ops.worker())
    (r,) = await space.run(ops.up(p, [c], worker=w))
    row = await space.run_row(r, lambda row: _up(row) and "tick" in _texts(row))
    assert _texts(row, "stdout")[:2] == ["built", "tick"]
    await space.run(ops.down([r]))
    row = await space.run_row(r, _dead)
    assert row["exit"] == EXIT_STOPPED
    assert row["error"] == ""


@module_loop
async def test_reload_by_down_and_up_on_the_same_worker(space):
    p, (c,) = await space.plane(FOREVER)
    w = await space.run(ops.worker())
    (old,) = await space.run(ops.up(p, [c], worker=w))
    await space.run_row(old, _up)
    await space.run(ops.down([old]))
    (new,) = await space.run(ops.up(p, [c], worker=w, by="reload"))
    assert (await space.run_row(old, _dead))["exit"] == EXIT_STOPPED
    assert _up(await space.run_row(new, _up))
    assert (await space.worker_row(w, bool))["status"] == STATUS_UP
    await space.run(ops.kill_worker(w))
    assert (await space.run_row(new, _dead))["exit"] == EXIT_KILLED


@module_loop
async def test_two_runs_share_a_worker_and_idle_gc_follows_the_last(space):
    p, _ = await space.plane(FOREVER, FOREVER)
    w = await space.run(ops.worker())
    ra, rb = await space.run(ops.up_plane(p, worker=w))
    await space.run_row(ra, _up)
    await space.run_row(rb, _up)
    assert sorted(await space.read(ops.live_runs(w))) == sorted([ra, rb])
    await space.run(ops.down([ra]))
    await space.run_row(ra, _dead)
    assert (await space.worker_row(w, bool))["status"] == STATUS_UP
    assert _up(await space.run_row(rb, bool))
    await space.run(ops.down([rb]))
    await space.run_row(rb, _dead)
    worker = await space.worker_row(w, _dead)
    assert worker["error"] == ""
    assert w not in await space.read(ops.active_workers())


@module_loop
async def test_idle_gc_after_a_run_that_returns(space):
    p, (c,) = await space.plane(SET_42)
    w = await space.run(ops.worker())
    await space.run(ops.up(p, [c], worker=w))
    worker = await space.worker_row(w, _dead)
    assert worker["wid"] is not None
    assert worker["started"] <= worker["ended"]


@module_loop
async def test_kill_worker_kills_its_runs(space):
    p, (c,) = await space.plane(FOREVER)
    w = await space.run(ops.worker())
    (r,) = await space.run(ops.up(p, [c], worker=w))
    await space.run_row(r, _up)
    await space.run(ops.kill_worker(w))
    row = await space.run_row(r, _dead)
    assert row["exit"] == EXIT_KILLED
    assert row["error"].startswith("worker exited")
    assert _dead(await space.worker_row(w, _dead))
    assert r not in await space.read(ops.live_runs())


@module_loop
async def test_envs_wrap_and_rewrite_the_program(space):
    p, (a, b) = await space.plane(READS_TAG, READS_TAG)
    w = await space.run(ops.worker())
    (ra,) = await space.run(ops.up(p, [a], worker=w, envs=[ops.env("tagged", "inner")]))
    (rb,) = await space.run(ops.up(p, [b], worker=w))
    assert (await space.run_row(ra, _dead))["exit"] == EXIT_OK
    assert (await space.run_row(rb, _dead))["exit"] == EXIT_OK
    state = Space.planes[p].cells
    assert await space.read(state[a].state["s"]) == "inner"
    assert await space.read(state[b].state["s"]) == "outer"
    assert await space.read(Space.planes[p].state["stamped"]) is True


@module_loop
async def test_an_unknown_env_fails_the_run(space):
    p, (c,) = await space.plane(SET_42)
    w = await space.run(ops.worker())
    (r,) = await space.run(ops.up(p, [c], worker=w, envs=[ops.env("nope")]))
    row = await space.run_row(r, _dead)
    assert row["exit"] == EXIT_FAILED
    assert "nope" in row["error"]


@module_loop
async def test_a_kind_the_kernel_cannot_make(space):
    p, (c,) = await space.plane(SET_42)
    w = await space.run(ops.worker(KIND_DOCKER))
    (r,) = await space.run(ops.up(p, [c], worker=w))
    worker = await space.worker_row(w, _dead)
    assert KIND_DOCKER in worker["error"]
    row = await space.run_row(r, _dead)
    assert row["exit"] == EXIT_FAILED


@module_loop
async def test_a_run_on_a_dead_worker_fails(space):
    p, (c,) = await space.plane(SET_42)
    w = await space.run(ops.worker())
    await space.run(ops.up(p, [c], worker=w))
    await space.worker_row(w, _dead)
    (r,) = await space.run(ops.up(p, [c], worker=w))
    row = await space.run_row(r, _dead)
    assert row["exit"] == EXIT_FAILED
    assert w in row["error"]


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
    w = await first.run(ops.worker())
    (r,) = await first.run(ops.up(p, [c], worker=w))
    await first.run_row(r, _up)
    await first.close()
    again = await opened("nuspace-reopen", path=path, spares=0, init=p)
    try:
        old = await again.run_row(r, _dead)
        assert old["exit"] == EXIT_KILLED
        assert _dead(await again.worker_row(w, bool))
        rows = await again.until(
            ops.runs(plane=p), lambda rs: any(x["by"] == INIT_BY and _up(x) for x in rs)
        )
        (fresh,) = [x for x in rows if x["by"] == INIT_BY]
        assert fresh["worker"] != w
    finally:
        await again.close()
    assert workers_named("nuspace-reopen") == []


async def test_reconcile_marks_leftovers_dead(store):
    w_up, w_dead = await store.run(ops.worker()), await store.run(ops.worker())
    p = await store.run(ops.add_plane())
    c = await store.run(ops.add_cell(p, SET_42))
    r_up, r_done = await store.run(ops.up(p, [c, c], worker=w_up))
    done = kernel.runs[r_done]
    old = kernel.workers[w_dead]
    await store.run(
        atomic(
            done.status.set(STATUS_DEAD)
            >> done.exit.set(EXIT_OK)
            >> kernel.live.del_item(r_done)
            >> old.status.set(STATUS_DEAD)
            >> kernel.active.del_item(w_dead)
            >> kernel.runs[r_up].status.set(STATUS_UP)
        )
    )
    await store.run(reconcile())
    runs = {r["id"]: (r["status"], r["exit"]) for r in await store.read(ops.runs())}
    assert runs == {r_up: (STATUS_DEAD, EXIT_KILLED), r_done: (STATUS_DEAD, EXIT_OK)}
    workers = {w["id"]: w["status"] for w in await store.read(ops.workers())}
    assert workers == {w_up: STATUS_DEAD, w_dead: STATUS_DEAD}
    assert await store.read(ops.live_runs()) == []
    assert await store.read(ops.active_workers()) == []


async def test_reconcile_makes_the_containers(store):
    await store.run(reconcile())
    assert await store.read(nu.List.of(ops.live_runs(), ops.active_workers())) == [[], []]
