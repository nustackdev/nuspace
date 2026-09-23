"""The services with real workers, headless: init, nav, supervisor, reload.

One space for the module, on a store bootstrapped before it opens, the way a
host opens one: the service planes made, a user plane added to init's boot
list, then the kernel started with ``init``. Every test makes its own planes
and polls the store until the services have acted. Bootstrap and the boot
list ops run against a bare store.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest
import pytest_asyncio

import nu
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import (
    EXIT_FAILED,
    EXIT_KILLED,
    EXIT_OK,
    EXIT_STOPPED,
    STATUS_DEAD,
    STATUS_UP,
    Space,
    reroot,
)
from nuspace.system.kernel import Env, store
from nuspace.system.services import (
    ALWAYS,
    BOOTED,
    ON_FAILURE,
    SERVICES,
    boot,
    ensure_system,
    init,
    supervise,
    unboot,
    unsupervise,
)
from nuspace.system.services import nav as nav_service
from nuspace.system.services import supervisor as supervisor_service


sys.path.insert(0, str(Path(__file__).parent))
from test_kernel import SET_42, Kernel, _dead, _up, opened, prog, workers_named


module_loop = pytest.mark.asyncio(loop_scope="module")

#: The attr the test session env binds the connection id under.
SESSION_ATTR = "test.session"

BOOTED_PLANE = "booted"
NAME = "nuspace-services"

READS_SESSION = prog(
    'return Tick.s.set(nu.StrAttrRef("test.session")) >> nu.ForeverDo(nu.Delay(0.05))'
)
RAISES = prog('raise ValueError("boom")')


def version(v: str) -> str:
    return prog(f'return Tick.s.set("{v}") >> nu.ForeverDo(nu.Delay(0.05))')


def session(sid: str) -> Env:
    """What the web device registers, minus the device: the connection bound as an attr."""
    return Env(wrap=lambda body: nu.Let(SESSION_ATTR, nu.Str(sid), body), label=f"session:{sid}")


def boot_list() -> nu.Nu:
    return nu.list(reroot(init.Boot.planes, init.PLANE, init.CELL))


# --- bootstrap, boot list: no workers ----------------------------------------------------


async def test_bootstrap_makes_the_services_and_is_idempotent(store):
    await store.run(ensure_system())
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert set(rows) == {plane for plane, _ in SERVICES}
    for plane, shim in SERVICES:
        assert rows[plane]["system"] is True
        assert rows[plane]["meta"] == {"ui": False}
        assert await store.read(ops.cell_rows(plane)) == [
            {"id": "main", "name": "main", "prog": shim, "meta": {}}
        ]
    assert await store.read(boot_list()) == list(BOOTED)
    # An edited store: a renamed service, a changed boot list. A rerun keeps both.
    await store.run(ops.rename_plane("nav", "navigation") >> unboot("reload"))
    before = await store.read(Space.planes.extract())
    await store.run(ensure_system())
    assert await store.read(Space.planes.extract()) == before
    assert await store.read(boot_list()) == ["nav", "supervisor"]


async def test_boot_and_unboot_are_idempotent(store):
    await store.run(boot("a") >> boot("b") >> boot("a"))
    assert await store.read(boot_list()) == [*BOOTED, "a", "b"]
    await store.run(unboot("a") >> unboot("a") >> unboot("ghost"))
    assert await store.read(boot_list()) == [*BOOTED, "b"]


async def test_supervise_writes_the_policy(store):
    await store.run(supervise("p", "c") >> supervise("p", "d", ALWAYS) >> unsupervise("p", "c"))
    policy = reroot(supervisor_service.Policy.cells, supervisor_service.PLANE, "main")
    assert await store.read(policy.extract()) == {"p/d": "always"}


async def test_unboot_without_a_list(store):
    await store.run(unboot("a"))
    assert await store.read(boot_list()) == []


# --- the space ------------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("services") / "space")
    seed = (
        ensure_system()
        >> ops.add_plane(BOOTED_PLANE)
        >> ops.add_cell(BOOTED_PLANE, SET_42, cell_id="c")
        >> boot(BOOTED_PLANE)
    )
    await nu.arun(nu.With(store(path), body=seed))
    k = await opened(NAME, path=path, spares=2, envs={"session": session}, init=init.PLANE)
    yield k
    await k.close()


#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0


async def runs_of(space: Kernel, plane: str, pred, timeout: float = 4.0) -> list[dict]:
    return await space.until(ops.runs(plane=plane), pred, timeout)


@module_loop
async def test_init_brings_up_its_boot_list(space):
    for plane in BOOTED:
        rows = await runs_of(space, plane, lambda rs: any(_up(r) for r in rs))
        assert [r["by"] for r in rows] == [init.BY]
    (row,) = await runs_of(space, BOOTED_PLANE, lambda rs: rs and _dead(rs[0]))
    assert (row["by"], row["exit"]) == (init.BY, EXIT_OK)
    assert await space.read(Space.planes[BOOTED_PLANE].cells["c"].state["n"]) == 42
    (kernel_run,) = await space.read(ops.runs(plane=init.PLANE))
    assert _up(kernel_run)
    services = {
        r["worker"] for p in (init.PLANE, *BOOTED) for r in await space.read(ops.runs(plane=p))
    }
    assert len(services) == 4


@module_loop
async def test_nav_follows_a_connections_route(space):
    a, _ = await space.plane(READS_SESSION)
    b, _ = await space.plane(READS_SESSION)
    sid = "conn-1"
    route = Space.connections[sid].route
    await space.run(atomic(route.set(a) >> Space.connections[sid].opened.set(time.time())))
    (ra,) = await runs_of(space, a, lambda rs: rs and _up(rs[0]))
    assert (ra["by"], ra["envs"]) == (nav_service.BY, [["session", sid]])
    await space.until(Space.planes[a].cells.extract(), lambda cs: _state(cs) == [sid])

    await space.run(atomic(route.set(b)))
    assert (await space.worker_row(ra["worker"], _dead))["status"] == STATUS_DEAD
    assert (await space.run_row(ra["id"], _dead))["exit"] == EXIT_KILLED
    (rb,) = await runs_of(space, b, lambda rs: rs and _up(rs[0]))
    assert rb["worker"] != ra["worker"]

    await space.run(atomic(Space.connections.del_item(sid)))
    await space.worker_row(rb["worker"], _dead)
    assert (await space.run_row(rb["id"], _dead))["exit"] == EXIT_KILLED


@module_loop
async def test_nav_skips_missing_and_system_planes(space):
    sid = "conn-2"
    await space.run(atomic(Space.connections[sid].route.set("reload")))
    await space.run(atomic(Space.connections[sid].route.set("ghost")))
    p, _ = await space.plane(READS_SESSION)
    await space.run(atomic(Space.connections[sid].route.set(p)))
    await runs_of(space, p, lambda rs: rs and _up(rs[0]))
    reloads = await space.read(ops.runs(plane="reload"))
    assert [r["by"] for r in reloads] == [init.BY]
    await space.run(atomic(Space.connections.del_item(sid)))
    await runs_of(space, p, lambda rs: _dead(rs[0]))


@module_loop
async def test_nav_follows_the_open_planes_cells(space):
    p, _ = await space.plane(READS_SESSION)
    sid = "conn-3"
    await space.run(atomic(Space.connections[sid].route.set(p)))
    (r1,) = await runs_of(space, p, lambda rs: rs and _up(rs[0]))

    c2 = await space.run(ops.add_cell(p, READS_SESSION))
    (r2,) = await space.until(ops.runs(plane=p, cell=c2), lambda rs: rs and _up(rs[0]), SLOW)
    assert (r2["worker"], r2["by"], r2["envs"]) == (
        r1["worker"],
        nav_service.BY,
        [["session", sid]],
    )

    await space.run(ops.remove_cell(p, c2))
    assert (await space.run_row(r2["id"], _dead))["exit"] == EXIT_STOPPED
    assert _up(await space.run_row(r1["id"], _up))

    await space.run(atomic(Space.connections.del_item(sid)))
    assert (await space.run_row(r1["id"], _dead))["exit"] == EXIT_KILLED


@module_loop
async def test_nav_keeps_its_worker_once_an_emptied_plane_gets_a_cell(space):
    p, (c1,) = await space.plane(READS_SESSION)
    sid = "conn-4"
    await space.run(atomic(Space.connections[sid].route.set(p)))
    (r1,) = await runs_of(space, p, lambda rs: rs and _up(rs[0]))

    # The last cell gone, its worker had a run and has none: held, idle GC skips it.
    await space.run(ops.remove_cell(p, c1))
    await space.run_row(r1["id"], _dead)

    c2 = await space.run(ops.add_cell(p, READS_SESSION))
    (r2,) = await space.until(ops.runs(plane=p, cell=c2), lambda rs: rs and _up(rs[0]), SLOW)
    assert r2["worker"] == r1["worker"]

    await space.run(atomic(Space.connections.del_item(sid)))
    assert (await space.run_row(r2["id"], _dead))["exit"] == EXIT_KILLED


@module_loop
async def test_nav_runs_a_cell_that_replaces_the_last_one(space):
    p, (c1,) = await space.plane(READS_SESSION)
    sid = "conn-5"
    await space.run(atomic(Space.connections[sid].route.set(p)))
    (r1,) = await runs_of(space, p, lambda rs: rs and _up(rs[0]))

    # Added right after the removal: its first run may land on the worker
    # idle GC is taking (or beat GC to it), and either way it comes up.
    await space.run(ops.remove_cell(p, c1))
    c2 = await space.run(ops.add_cell(p, READS_SESSION))
    rows = await space.until(ops.runs(plane=p, cell=c2), lambda rs: any(_up(r) for r in rs), SLOW)
    (r2,) = [r for r in rows if _up(r)]
    assert r2["by"] == nav_service.BY
    assert r1["id"] not in [r["id"] for r in rows]

    await space.run(atomic(Space.connections.del_item(sid)))
    assert (await space.run_row(r2["id"], _dead))["exit"] == EXIT_KILLED


def _state(cells: dict) -> list:
    return [c.get("state", {}).get("s") for c in cells.values()]


@module_loop
async def test_supervisor_restarts_with_backoff_until_unsupervised(space):
    p, (c,) = await space.plane(RAISES)
    await space.run(supervise(p, c, ON_FAILURE))
    w = await space.run(ops.worker())
    await space.run(ops.up(p, [c], worker=w, by="test"))
    rows = await runs_of(space, p, lambda rs: len(rs) >= 3 and all(_dead(r) for r in rs))
    await space.run(unsupervise(p, c))
    assert [r["by"] for r in rows[:3]] == ["test", supervisor_service.BY, supervisor_service.BY]
    assert all(r["exit"] == EXIT_FAILED for r in rows)
    first, second = (rows[i + 1]["started"] - rows[i]["ended"] for i in range(2))
    assert first >= 0.25
    assert second >= 0.5
    assert second > first
    # The next wait would be a second: nothing comes after it once unsupervised.
    await asyncio.sleep(1.3)
    assert len(await space.read(ops.runs(plane=p))) == len(rows)


@module_loop
async def test_supervisor_always_restarts_on_a_worker_still_serving(space):
    p, (_, c) = await space.plane(version("keep"), SET_42)
    await space.run(supervise(p, c, ALWAYS))
    w = await space.run(ops.worker())
    await space.run(ops.up_plane(p, worker=w, by="test"))
    # Deadlines, not delays: each wait returns once its condition holds. They
    # are long because a loaded machine stretches backoff and a worker's stop.
    rows = await space.until(ops.runs(plane=p, cell=c), lambda rs: len(rs) >= 3, SLOW)
    await space.run(unsupervise(p, c))
    assert [r["by"] for r in rows[:3]] == ["test", supervisor_service.BY, supervisor_service.BY]
    assert {r["worker"] for r in rows} == {w}
    assert all(r["exit"] == EXIT_OK for r in rows[:2])
    await space.run(ops.kill_worker(w))
    await space.worker_row(w, _dead, SLOW)


@module_loop
async def test_supervisor_leaves_a_stopped_run_alone(space):
    p, (c,) = await space.plane(version("x"))
    await space.run(supervise(p, c, ALWAYS))
    w = await space.run(ops.worker())
    (r,) = await space.run(ops.up(p, [c], worker=w, by="test"))
    await space.run_row(r, _up)
    await space.run(ops.down([r]))
    assert (await space.run_row(r, _dead))["exit"] == EXIT_STOPPED
    await asyncio.sleep(0.6)
    assert [x["id"] for x in await space.read(ops.runs(plane=p))] == [r]
    await space.run(unsupervise(p, c))


@module_loop
async def test_reload_replaces_a_run_when_its_prog_changes(space):
    p, (c,) = await space.plane(version("v1"))
    w = await space.run(ops.worker())
    envs = [ops.env("session", "conn-9")]
    (old,) = await space.run(ops.up(p, [c], worker=w, envs=envs, by="test"))
    await space.run_row(old, _up)
    await space.run(ops.set_prog(p, c, version("v2")))
    rows = await runs_of(space, p, lambda rs: len(rs) == 2 and _up(rs[1]) and _dead(rs[0]))
    assert rows[0]["id"] == old
    assert rows[0]["exit"] == EXIT_STOPPED
    new = rows[1]
    assert (new["worker"], new["by"], new["envs"]) == (w, "test", envs)
    state = Space.planes[p].cells[c].state["s"]
    await space.until(state, lambda s: s == "v2")
    assert (await space.worker_row(w, bool))["status"] == STATUS_UP
    await space.run(ops.kill_worker(w))
    await space.run_row(new["id"], _dead)


@module_loop
async def test_closing_leaves_no_workers(space):
    await space.close()
    deadline = time.monotonic() + 5
    while workers_named(NAME) and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert workers_named(NAME) == []
