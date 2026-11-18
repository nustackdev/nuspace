"""nav with the real kernel: a plane run per open pane, started on open or restart, stopped on close.

One space for the module: the kernel up with its workers, the web
device's stores beside the core ones, a stand-in session env, and nav
running in the host as the web device runs it. Every test opens its own
tab and planes and polls the store until nav and the kernel have acted.
"""

from __future__ import annotations

import asyncio
import socket
import tempfile
import time

import pytest
import pytest_asyncio
from _support.kernel import (
    RAISES,
    SET_42,
    Kernel,
    _Hold,
    init_stores,
    kernel_open,
    navigators,
    prog,
    workers_named,
)
from _support.made import MADE_STORE

import nu
import nuspace
import nuspace.web as web
import nustd.kv
import nustd.mp_pool
from nuspace import kernel
from nuspace.kernel import CLOSED, LEFT_OVER, Env
from nuspace.kernel.kernel import loop
from nuspace.shapes import EXIT_FAILED, Space
from nuspace.space.local import binding
from nuspace.space.local.session import AddressFile
from nuspace.web.env import session_env
from nuspace.web.nav import BY, nav
from nuspace.web.stores import CONN_STORE, WEB_STORE


module_loop = pytest.mark.asyncio(loop_scope="module")

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0

#: Runs until stopped.
FOREVER = prog("return nu.ForeverDo(nu.Delay(0.05))")

#: What the module's kernel calls its workers.
NAME = "nuspace-nav"


def _dead_address() -> str:
    """``host:port`` nobody listens on."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{s.getsockname()[1]}"


#: The tabs' session env, as the kernel resolves it: here it wraps nothing.
#: Beside it, the real one with no web: at an address nobody answers, and
#: through local's address file with no file written.
ENVS = {
    "session": lambda sid: Env(label=f"session:{sid}"),
    "deadweb": session_env(lambda: _DEAD),
    "noweb": session_env(AddressFile(f"{tempfile.gettempdir()}/nuspace-nav-none/session.addr")),
}

_DEAD = _dead_address()


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
async def test_a_failed_plane_waits_for_its_restart_and_never_loops(space):
    k = space
    p, _ = await web_plane(k, RAISES)
    await k.do(web.open_tab("e1"))
    await k.do(web.set_panes("e1", [p]))
    run = await pane_run(k, "e1", p)
    assert (await ended(k, run))["exit"] == EXIT_FAILED
    await asyncio.sleep(1.0)
    runs = Space.exec.indexes.history.plane_to_plane_runs[p].runs
    assert await k.read(nu.list(runs.keys())) == [run]
    await k.do(web.restart_pane("e1", p))
    await pane_run(k, "e1", p, not_=run)
    await k.do(web.close_tab("e1"))


@module_loop
@pytest.mark.parametrize(
    ("env", "said"),
    [("deadweb", f"No web answers at {_DEAD}"), ("noweb", "No web runs on this space")],
    ids=["web-gone", "no-address"],
)
async def test_a_session_cell_run_with_no_web_fails_and_the_kernel_goes_on(space, env, said):
    k = space
    p, (c,) = await k.plane(SET_42)
    run = await k.start(p, envs=[[env, "t1"]])
    assert (await ended(k, run))["exit"] == EXIT_FAILED
    rows = await k.read(Space.exec.cell_runs.extract())
    (row,) = [r for r in rows.values() if r["plane_run"] == run and r["cell"] == c]
    assert row["exit"] == EXIT_FAILED
    assert said in row["error"]
    # The kernel is untouched: the next run, outside a session, runs.
    again = await k.start(p)
    assert (await ended(k, again))["exit"] == "ok"


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


# --- nav across kernels ------------------------------------------------------------------
#
# nav in one context with the stores, and a kernel in a task of its own on the
# same files, started and stopped under it, as local runs them in two processes.


class _Up:
    """A kernel on the stores at ``data``, run in a task of its own until :meth:`down`."""

    def __init__(self, data: str, term: nu.Nu, name: str) -> None:
        loop_ = asyncio.get_running_loop()
        self.ready, self.done = loop_.create_future(), asyncio.Event()
        pool = nustd.mp_pool.pool(name=name, init=navigators(data), spares=0, grace=2.0)
        held = nu.let(_Hold(self.ready, self.done), lambda _: nu.Noop())
        body = nu.Race(term, nu.With(MADE_STORE, body=held))
        opened = nu.With(navigators(data), pool, kernel.bound(envs=ENVS), body=body)
        self.task = asyncio.create_task(nu.arun(opened))

    async def up(self) -> None:
        waiting = asyncio.ensure_future(asyncio.shield(self.ready))
        finished, _ = await asyncio.wait(
            {waiting, self.task}, timeout=30, return_when="FIRST_COMPLETED"
        )
        if self.task in finished:
            self.task.result()

    async def down(self) -> None:
        self.done.set()
        await asyncio.wait_for(self.task, 15)


async def _nav_alone(data: str) -> Kernel:
    """nav and the stores at ``data``, no kernel: run ops through it as through a kernel."""
    loop_ = asyncio.get_running_loop()
    ready, done = loop_.create_future(), asyncio.Event()
    mem = nu.With(*(nustd.kv.memory_navigator(tags=(s.root,)) for s in (WEB_STORE, CONN_STORE)))
    init = init_stores() >> nustd.kv.atomic(WEB_STORE.init()) >> nustd.kv.atomic(CONN_STORE.init())
    held = nu.let(_Hold(ready, done), lambda _: nu.Noop())
    body = nu.With(MADE_STORE, mem, body=init >> nu.Race(nav(), held))
    task = asyncio.create_task(nu.arun(nu.With(binding.served(data), navigators(data), body=body)))
    waiting = asyncio.ensure_future(asyncio.shield(ready))
    finished, _ = await asyncio.wait({waiting, task}, timeout=30, return_when="FIRST_COMPLETED")
    if task in finished:
        task.result()
    return Kernel(await waiting, done, task, data)


async def _started(k: Kernel, run: str) -> None:
    started = Space.exec.plane_runs[run].started_at.exists()
    await k.until(lambda: k.read(started), bool, SLOW)


async def _asks_again(tmp_path, first: nu.Nu, why: str) -> None:
    """A pane's run ended by kernel ``first`` going away, as ``why``: nav asks again, the next kernel starts it."""
    data = str(tmp_path / "data")
    (tmp_path / "data" / "store").mkdir(parents=True)
    k = await _nav_alone(data)
    try:
        p, _ = await web_plane(k, FOREVER)
        await k.do(web.open_tab("k1"))
        await k.do(web.set_panes("k1", [p]))
        run = await pane_run(k, "k1", p)
        one = _Up(data, first, f"{NAME}-one")
        await one.up()
        await _started(k, run)
        await one.down()
        if why == LEFT_OVER:
            # A crash ends nothing: the run is left started, for the next kernel's reap.
            assert not await k.read(Space.exec.plane_runs[run].ended_at.exists())
        else:
            assert (await ended(k, run))["error"] == why
        two = _Up(data, kernel.driver(), f"{NAME}-two")
        await two.up()
        try:
            assert (await ended(k, run))["error"] == why
            again = await pane_run(k, "k1", p, not_=run)
            await _started(k, again)
            assert await k.read(Space.exec.plane_runs[again].by) == BY
            await k.do(web.close_tab("k1"))
            await ended(k, again)
        finally:
            await two.down()
    finally:
        await k.close()


async def test_nav_asks_again_after_a_kernel_close(tmp_path):
    await _asks_again(tmp_path, kernel.driver(), CLOSED)


async def test_nav_asks_again_after_a_reap(tmp_path):
    # Reap and the loop, no close: going down is a crash.
    await _asks_again(tmp_path, kernel.reap() >> loop(), LEFT_OVER)
