"""nav with the real kernel: a plane run per open pane, started on open or restart, stopped on close.

One space for the module: the kernel up with its workers, the web
device's stores beside the core ones, a stand-in session env, and nav
running in the host as the web device runs it. Every test opens its own
tab and planes and polls the store until nav and the kernel have acted.
"""

from __future__ import annotations

import asyncio
import tempfile
import time

import pytest
import pytest_asyncio
from _support.kernel import SET_42, Kernel, _Hold, kernel_open, prog, workers_named
from _support.made import MADE_STORE

import nu
import nuspace
import nuspace.devices.web as web
import nustd.kv
from nuspace.devices.web.nav import BY, nav
from nuspace.devices.web.stores import CONN_STORE, WEB_STORE
from nuspace.kernel import Env
from nuspace.shapes import Space


module_loop = pytest.mark.asyncio(loop_scope="module")

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0

#: Runs until stopped.
FOREVER = prog("return nu.ForeverDo(nu.Delay(0.05))")

#: What the module's kernel calls its workers.
NAME = "nuspace-nav"

#: The tabs' session env, as the kernel resolves it: here it wraps nothing.
ENVS = {"session": lambda sid: Env(label=f"session:{sid}")}


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space():
    data = tempfile.mkdtemp(prefix="nuspace-nav-")
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    stores = nu.With(*(nustd.kv.memory_navigator(tags=(s.root,)) for s in (WEB_STORE, CONN_STORE)))
    init = nustd.kv.atomic(WEB_STORE.init()) >> nustd.kv.atomic(CONN_STORE.init())
    held = nu.let(_Hold(ready, done), lambda _: nu.Noop())
    body = nu.With(MADE_STORE, stores, body=init >> nu.Race(nav(), held))
    task = asyncio.create_task(
        nu.arun(kernel_open(body, data=data, name=NAME, spares=0, envs=ENVS))
    )
    waiting = asyncio.ensure_future(asyncio.shield(ready))
    finished, _ = await asyncio.wait({waiting, task}, timeout=30, return_when="FIRST_COMPLETED")
    if task in finished:
        task.result()
    k = Kernel(await waiting, done, task, data)
    yield k
    await k.close()


async def web_plane(k: Kernel, *progs: str) -> tuple[str, list[str]]:
    p, cells = await k.plane(*progs)
    await k.do(web.add(p))
    return p, cells


async def pane_run(k: Kernel, sid: str, plane: str, *, not_: str = "") -> str:
    """The run nav recorded for a pane, once it is one other than ``not_``."""
    read = web.Conn.connections[sid].panes[plane].plane_run.fallback("")
    return await k.until(lambda: k.read(read), lambda r: r not in ("", not_), SLOW)


async def ended(k: Kernel, run: str) -> dict:
    return await k.until(
        lambda: k.read(Space.exec.plane_runs[run].extract()),
        lambda row: row.get("ended_at") is not None,
        SLOW,
    )


@module_loop
async def test_a_pane_opened_gets_its_own_run_in_its_tab(space):
    k = space
    p, _ = await web_plane(k, FOREVER)
    await k.do(web.open_tab("n1"))
    await k.do(web.open_tab("n2"))
    await k.do(web.set_panes("n1", [p]))
    await k.do(web.set_panes("n2", [p]))
    one, two = await pane_run(k, "n1", p), await pane_run(k, "n2", p)
    assert one != two
    row = await k.read(Space.exec.plane_runs[one].extract())
    assert row["by"] == BY and row["envs"] == [["session", "n1"]]
    await k.do(web.close_tab("n1"))
    await k.do(web.close_tab("n2"))
    await ended(k, one)
    await ended(k, two)


@module_loop
async def test_a_pane_closed_stops_its_run_and_the_tab_keeps_the_rest(space):
    k = space
    a, _ = await web_plane(k, FOREVER)
    b, _ = await web_plane(k, FOREVER)
    await k.do(web.open_tab("c1"))
    await k.do(web.set_panes("c1", [a, b]))
    ra, rb = await pane_run(k, "c1", a), await pane_run(k, "c1", b)
    await k.do(web.set_panes("c1", [b]))
    assert (await ended(k, ra))["exit"] in ("interrupted", "killed")
    still = await k.read(Space.exec.indexes.live.plane_runs.contains(rb))
    assert still is True
    await k.do(web.close_tab("c1"))
    await ended(k, rb)


@module_loop
async def test_a_restart_token_stops_the_run_and_adds_a_fresh_one(space):
    k = space
    p, _ = await web_plane(k, FOREVER)
    await k.do(web.open_tab("r1"))
    await k.do(web.set_panes("r1", [p]))
    first = await pane_run(k, "r1", p)
    await k.do(web.restart_pane("r1", p))
    second = await pane_run(k, "r1", p, not_=first)
    await ended(k, first)
    assert await k.read(Space.exec.indexes.live.plane_runs.contains(second)) is True
    await k.do(web.close_tab("r1"))
    await ended(k, second)


@module_loop
async def test_a_finished_run_stays_finished(space):
    k = space
    p, _ = await web_plane(k, SET_42)
    await k.do(web.open_tab("f1"))
    await k.do(web.set_panes("f1", [p]))
    run = await pane_run(k, "f1", p)
    assert (await ended(k, run))["exit"] == "ok"
    await asyncio.sleep(1.0)
    runs = Space.exec.indexes.history.plane_to_plane_runs[p].runs
    assert await k.read(nu.list(runs.keys())) == [run]
    # A restart asks again.
    await k.do(web.restart_pane("f1", p))
    await pane_run(k, "f1", p, not_=run)
    await k.do(web.close_tab("f1"))


@module_loop
async def test_a_pane_whose_start_fails_waits_for_its_next_restart(space):
    k = space
    p, _ = await web_plane(k, FOREVER)
    q, _ = await web_plane(k, FOREVER)
    await k.do(web.open_tab("x1"))
    await k.do(web.set_panes("x1", [p]))
    run = await pane_run(k, "x1", p)
    await k.do(nuspace.plane.remove(p))
    await ended(k, run)
    # Restarting a removed plane's pane: the add raises Removed, reported, nav goes on.
    await k.do(web.restart_pane("x1", p))
    await k.do(web.set_panes("x1", [p, q]))
    await pane_run(k, "x1", q)
    await k.do(web.close_tab("x1"))


def cell_runs(plane: str, run: str, cell: str):
    node = Space.exec.indexes.history.plane_to_plane_runs[plane].runs[run]
    ids = node.cell_to_cell_runs[cell].ids
    return nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([]))


@module_loop
async def test_a_cell_restart_in_a_live_run_runs_the_cell_again(space):
    k = space
    p, (c, other) = await web_plane(k, FOREVER, FOREVER)
    await k.do(web.open_tab("rc"))
    await k.do(web.set_panes("rc", [p]))
    run = await pane_run(k, "rc", p)
    (old,) = await k.until(lambda: k.read(cell_runs(p, run, c)), lambda ids: len(ids) == 1, SLOW)
    await k.run(web.restart_cell("rc", c))
    _, new = await k.until(lambda: k.read(cell_runs(p, run, c)), lambda ids: len(ids) == 2, SLOW)
    row = Space.exec.cell_runs
    await k.until(
        lambda: k.read(row[old].extract()), lambda r: r.get("exit") == "interrupted", SLOW
    )
    await k.until(lambda: k.read(row[new].started_at), lambda at: at is not None, SLOW)
    # The plane run goes on, the other cell untouched, nav asked for nothing.
    assert await k.read(Space.exec.indexes.live.plane_runs.contains(run)) is True
    assert len(await k.read(cell_runs(p, run, other))) == 1
    assert await k.read(web.Conn.connections["rc"].panes[p].plane_run) == run
    await k.do(web.close_tab("rc"))
    await ended(k, run)


@module_loop
async def test_a_cell_restart_in_a_finished_pane_restarts_the_pane(space):
    k = space
    p, (c,) = await web_plane(k, SET_42)
    await k.do(web.open_tab("rf"))
    await k.do(web.set_panes("rf", [p]))
    first = await pane_run(k, "rf", p)
    await ended(k, first)
    await k.run(web.restart_cell("rf", c))
    second = await pane_run(k, "rf", p, not_=first)
    assert (await ended(k, second))["exit"] == "ok"
    await k.do(web.close_tab("rf"))


@module_loop
async def test_closing_a_pane_right_after_opening_leaves_no_live_run(space):
    """A turn cancelled mid start still stops the run it made."""
    k = space
    p, _ = await web_plane(k, FOREVER)
    await k.do(web.open_tab("fl"))
    for _ in range(3):
        await k.do(web.set_panes("fl", [p]))
        await k.do(web.set_panes("fl", []))
    await k.do(web.close_tab("fl"))
    await asyncio.sleep(1.0)
    runs = Space.exec.indexes.history.plane_to_plane_runs[p].runs
    made = await k.read(nu.If(runs.exists(), nu.list(runs.keys()), nu.Literal([])))
    for run in made:
        row = await ended(k, run)
        assert row["by"] == BY
    live = await k.read(nu.list(Space.exec.indexes.live.plane_runs.keys()))
    assert not set(made) & set(live)


@module_loop
async def test_a_pane_on_a_plane_with_no_view_runs_nothing_until_it_is_on_the_web(space):
    k = space
    p, _ = await k.plane(FOREVER)
    await k.do(web.open_tab("h1"))
    await k.do(web.set_panes("h1", [p]))
    await asyncio.sleep(1.0)
    read = web.Conn.connections["h1"].panes[p].plane_run.fallback("")
    assert await k.read(read) == ""
    # Put on the web while the pane is open: its run starts then.
    await k.do(web.add(p))
    run = await pane_run(k, "h1", p)
    await k.do(web.close_tab("h1"))
    await ended(k, run)


@module_loop
async def test_closing_leaves_no_workers(space):
    """Last in the module: the space closed with nav in it leaves no worker up."""
    k = space
    p, _ = await web_plane(k, FOREVER)
    await k.do(web.open_tab("w1"))
    await k.do(web.set_panes("w1", [p]))
    await pane_run(k, "w1", p)
    await k.close()
    deadline = time.monotonic() + 5
    while workers_named(NAME) and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert workers_named(NAME) == []
