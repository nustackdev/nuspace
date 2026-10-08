"""The services with real workers, headless: init, nav, supervisor, reload.

One space for the module, on a store bootstrapped before it opens, the way a
host opens one: the service planes made, a user plane added to init's boot
list, then the kernel started with ``init``. Every test makes its own planes
and polls the store until the services have acted. Bootstrap and the boot
list ops run against a bare store.
"""

from __future__ import annotations

import asyncio
import time

import pytest
import pytest_asyncio
from _support import kernel_envs
from _support.kernel import (
    RAISES,
    SET_42,
    Kernel,
    cell_of,
    ended,
    history,
    live,
    opened,
    prog,
    workers_named,
)
from _support.made import MADE

import nu
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_OK, Space, States, reroot
from nuspace.system.kernel import INIT_BY, store
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
from nuspace.system.services import reactions as reactions_service
from nuspace.system.services import reload as reload_service
from nuspace.system.services import supervisor as supervisor_service


module_loop = pytest.mark.asyncio(loop_scope="module")

BOOTED_PLANE = "booted"

#: The booted services that stay up: all but reactions, which has no cells of its own.
LIVE_BOOTED = [p for p in BOOTED if p != "reactions"]
NAME = "nuspace-services"

READS_SESSION = prog(
    "from _support.kernel_envs import Connection",
    "return ops.atomic_state(Tick.s.set(Connection.sid)) >> nu.ForeverDo(nu.Delay(0.05))",
)
#: Fails, but only after long enough for the supervisor to have seen it live.
FAILS_LATE = prog('return nu.Delay(0.6) >> nu.Raise(nu.Str("boom"))')


def version(v: str) -> str:
    return prog(f'return ops.atomic_state(Tick.s.set("{v}")) >> nu.ForeverDo(nu.Delay(0.05))')


def boot_list() -> nu.Nu:
    return nu.list(reroot(init.Boot.planes, init.PLANE, init.CELL))


# --- bootstrap, boot list: no workers ----------------------------------------------------


async def test_bootstrap_makes_the_services_and_is_idempotent(store):
    await store.run(ensure_system())
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert set(rows) == {plane for plane, _, _ in SERVICES} | {reactions_service.PLANE}
    for plane, cell, shim in SERVICES:
        assert rows[plane]["props"] == {
            "system": True,
            "ui": False,
            "made_by": "",
            "backend": "mp",
        }
        assert rows[plane]["meta"] == {}
        assert await store.read(ops.cell_rows(plane)) == [
            {
                "id": cell,
                "name": "main",
                "prog": shim,
                "props": {"made_by": "", "has_ui": False},
                "meta": {},
            }
        ]
    assert await store.read(boot_list()) == list(BOOTED)
    # An edited store: a renamed service, a changed boot list. A rerun keeps both.
    await store.run(ops.rename_plane("nav", "navigation") >> unboot("reload"))
    before = await store.read(Space.planes.extract())
    await store.run(ensure_system())
    assert await store.read(Space.planes.extract()) == before
    assert await store.read(boot_list()) == [p for p in BOOTED if p != "reload"]


async def test_boot_and_unboot_are_idempotent(store):
    await store.run(boot("a") >> boot("b") >> boot("a"))
    assert await store.read(boot_list()) == [*BOOTED, "a", "b"]
    await store.run(unboot("a") >> unboot("a") >> unboot("ghost"))
    assert await store.read(boot_list()) == [*BOOTED, "b"]


async def test_supervise_writes_the_policy_per_plane(store):
    await store.run(supervise("p") >> supervise("q", ALWAYS) >> unsupervise("p"))
    planes = reroot(
        supervisor_service.Policy.planes, supervisor_service.PLANE, supervisor_service.CELL
    )
    assert await store.read(planes.extract()) == {"q": "always"}
    assert await store.read(supervisor_service.policy_of("q")) == ALWAYS
    assert await store.read(supervisor_service.policy_of("p")) == ""
    assert await store.read(supervisor_service.run_of("q")) == ""
    # Nothing to stop: unsupervising a plane never supervised is a no-op.
    await store.run(unsupervise("ghost"))


async def test_supervise_sets_and_clears_a_fixed_delay(store):
    delays = reroot(
        supervisor_service.Policy.delays, supervisor_service.PLANE, supervisor_service.CELL
    )
    await store.run(supervise("p", ALWAYS, delay=2) >> supervise("q", delay=0.5))
    assert await store.read(delays.extract()) == {"p": 2.0, "q": 0.5}
    assert await store.read(supervisor_service.delay_of("p")) == 2.0
    assert await store.read(supervisor_service.policy_of("p")) == ALWAYS
    # Supervised again with no delay backs off, unsupervised drops both.
    await store.run(supervise("p", ALWAYS) >> unsupervise("q"))
    assert await store.read(delays.extract()) == {}
    assert await store.read(supervisor_service.delay_of("p")) == -1.0
    assert await store.read(supervisor_service.policy_of("q")) == ""


async def test_unboot_without_a_list(store):
    await store.run(unboot("a"))
    assert await store.read(boot_list()) == []


# --- The space ------------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("services") / "space")
    seed = (
        ensure_system()
        >> ops.add_plane(BOOTED_PLANE, backend="async")
        >> ops.add_cell(BOOTED_PLANE, SET_42, cell_id="c")
        >> boot(BOOTED_PLANE)
    )
    await nu.arun(nu.With(store(path), body=seed))
    k = await opened(
        NAME, path=path, spares=2, envs={"session": kernel_envs.session}, init=init.PLANE
    )
    yield k
    await k.close()


#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0


async def runs_of(space: Kernel, plane: str, pred, timeout: float = SLOW) -> list[dict]:
    """Every plane run of a plane ever, read until ``pred`` holds on them. Test only: O(n)."""
    return await space.until(history(plane), pred, timeout)


def only(rows: list[dict]) -> dict:
    (row,) = rows
    return row


def first_cell(row: dict) -> dict:
    return row["cells"][0] if row.get("cells") else {}


async def open_tab(space: Kernel, sid: str, *routes: str) -> None:
    conn = Space.connections[sid]
    await space.run(atomic(conn.routes.set(list(routes)) >> conn.opened.set(time.time())))


async def close_tab(space: Kernel, sid: str) -> None:
    await space.run(atomic(Space.connections.del_item(sid)))


async def pane(space: Kernel, sid: str, plane: str) -> dict:
    """The live run nav made for a tab's pane, once its first cell run is live."""
    rid = await space.until(nav_service.pane_run(sid, plane), bool, SLOW)
    return await space.run_row(rid, lambda r: live(first_cell(r)), SLOW)


@module_loop
async def test_init_brings_up_its_boot_list(space):
    for plane in LIVE_BOOTED:
        row = only(await runs_of(space, plane, lambda rs: rs and live(first_cell(rs[0]))))
        assert row["by"] == init.BY
    # The reactions plane has no cells until a reaction is enabled: its run ends at once.
    row = only(await runs_of(space, reactions_service.PLANE, lambda rs: rs and ended(rs[0])))
    assert (row["by"], row["exit"], row["cells"]) == (init.BY, EXIT_OK, [])
    row = only(await runs_of(space, BOOTED_PLANE, lambda rs: rs and ended(rs[0])))
    assert (row["by"], row["exit"]) == (init.BY, EXIT_OK)
    assert await space.read(States.cells["c"].extract()) == {"n": 42}
    kernel_run = only(await space.read(ops.runs(plane=init.PLANE)))
    assert kernel_run["by"] == INIT_BY
    workers = {
        w for p in (init.PLANE, *LIVE_BOOTED) for w in only(await space.read(history(p)))["workers"]
    }
    assert len(workers) == 1 + len(LIVE_BOOTED)


@module_loop
async def test_nav_runs_each_open_plane_in_its_own_run(space):
    a, (ca,) = await space.plane(READS_SESSION)
    b, _ = await space.plane(READS_SESSION)
    sid = "conn-1"
    await open_tab(space, sid, a, b)
    ra, rb = await pane(space, sid, a), await pane(space, sid, b)
    assert (ra["by"], ra["envs"]) == (nav_service.BY, [["session", sid]])
    assert (rb["by"], rb["envs"]) == (nav_service.BY, [["session", sid]])
    assert ra["workers"] != rb["workers"]
    await space.until(States.cells[ca].extract(), lambda s: s.get("s") == sid)

    # Closing a stops only its run: b keeps going.
    await open_tab(space, sid, b)
    row = await space.run_row(ra["id"], ended, SLOW)
    assert row["exit"] == EXIT_INTERRUPTED
    await space.until(nav_service.pane_run(sid, a), lambda x: x == "")
    assert not ended(await space.read(ops.run(rb["id"])))

    await close_tab(space, sid)
    assert (await space.run_row(rb["id"], ended, SLOW))["exit"] == EXIT_INTERRUPTED
    await space.until(nav_service.pane_run(sid, b), lambda x: x == "")


@module_loop
async def test_nav_stops_every_open_planes_run_when_the_connection_goes(space):
    a, _ = await space.plane(READS_SESSION)
    b, _ = await space.plane(READS_SESSION, backend="mp")
    sid = "conn-both"
    await open_tab(space, sid, a, b)
    ra, rb = await pane(space, sid, a), await pane(space, sid, b)
    assert rb["backend"] == "mp"
    await close_tab(space, sid)
    for r in (ra, rb):
        row = await space.run_row(r["id"], ended, SLOW)
        assert row["exit"] == EXIT_INTERRUPTED
        for w in row["workers"]:
            assert (await space.worker_row(w, timeout=SLOW))["exit"] == EXIT_OK


@module_loop
async def test_nav_skips_missing_and_system_planes(space):
    sid = "conn-2"
    await open_tab(space, sid, "reload")
    await open_tab(space, sid, "ghost")
    p, _ = await space.plane(READS_SESSION)
    await open_tab(space, sid, p)
    await pane(space, sid, p)
    assert [r["by"] for r in await space.read(history("reload"))] == [init.BY]
    await close_tab(space, sid)
    await runs_of(space, p, lambda rs: ended(rs[0]))


@module_loop
async def test_nav_brings_up_a_system_ui_plane_and_never_a_service(space):
    """``system`` only protects: a system ui plane (home) comes up, a service never does."""
    sid = "conn-system-ui"
    p = await space.made(ops.add_plane(system=True, ui=True, backend="async", into=MADE))
    await space.run(ops.add_cell(p, READS_SESSION))
    await open_tab(space, sid, "reload", p)
    await pane(space, sid, p)
    assert [r["by"] for r in await space.read(history("reload"))] == [init.BY]
    await close_tab(space, sid)
    await runs_of(space, p, lambda rs: ended(rs[0]))


@module_loop
async def test_nav_waits_for_a_routed_plane_not_written_yet(space):
    """A new plane is selected before its create lands: nav waits, not gives up."""
    sid = "conn-early"
    await open_tab(space, sid, "early")
    # Past a tick, so nav has seen the routes and found no plane behind it.
    await asyncio.sleep(1.5)
    await space.run(ops.add_plane("early", ui=True, backend="async"))
    await space.run(ops.add_cell("early", READS_SESSION))
    await pane(space, sid, "early")
    await close_tab(space, sid)
    await runs_of(space, "early", lambda rs: all(ended(r) for r in rs))


@module_loop
async def test_nav_follows_the_open_planes_cells(space):
    p, (c1,) = await space.plane(READS_SESSION)
    sid = "conn-3"
    await open_tab(space, sid, p)
    r = (await pane(space, sid, p))["id"]

    c2 = await space.made(ops.add_cell(p, READS_SESSION, into=MADE))
    row = await space.run_row(r, lambda x: live(cell_of(x, c2)), SLOW)
    new = cell_of(row, c2)
    assert new["by"] == nav_service.BY
    assert new["worker"] == cell_of(row, c1)["worker"]

    await space.run(ops.remove_cell(c2))
    row = await space.run_row(r, lambda x: ended(cell_of(x, c2)), SLOW)
    assert cell_of(row, c2)["exit"] == EXIT_INTERRUPTED
    assert live(cell_of(row, c1))
    assert not ended(row)

    await close_tab(space, sid)
    assert (await space.run_row(r, ended, SLOW))["exit"] == EXIT_INTERRUPTED


@module_loop
async def test_nav_runs_the_plane_again_once_its_run_ended_and_a_cell_changed(space):
    p, (c,) = await space.plane(SET_42)
    sid = "conn-4"
    await open_tab(space, sid, p)
    first = await space.until(nav_service.pane_run(sid, p), bool, SLOW)
    assert (await space.run_row(first, ended, SLOW))["exit"] == EXIT_OK
    await space.run(ops.set_prog(c, prog("return ops.atomic_state(Tick.n.set(7))")))
    again = await space.until(nav_service.pane_run(sid, p), lambda x: x not in ("", first), SLOW)
    assert (await space.run_row(again, ended, SLOW))["exit"] == EXIT_OK
    assert (await space.read(States.cells[c].extract()))["n"] == 7
    await close_tab(space, sid)


async def supervised(space: Kernel, plane: str, pred, timeout: float = SLOW) -> list[dict]:
    """The plane's runs by the supervisor, oldest first, read until ``pred`` holds on them."""

    def mine(rows: list[dict]) -> list[dict]:
        return [r for r in rows if r["by"] == supervisor_service.BY]

    return mine(await space.until(history(plane), lambda rs: pred(mine(rs)), timeout))


def gaps(rows: list[dict]) -> list[float]:
    """The waits between one run ending and the next starting."""
    return [rows[i + 1]["started_at"] - rows[i]["terminated_at"] for i in range(len(rows) - 1)]


@module_loop
async def test_supervisor_restarts_a_failed_plane_with_backoff_until_unsupervised(space):
    p, _ = await space.plane(FAILS_LATE)
    await space.run(supervise(p, ON_FAILURE))
    rows = await supervised(space, p, lambda rs: len(rs) >= 3 and all(ended(r) for r in rs[:3]))
    await space.run(unsupervise(p))
    assert all(r["exit"] == EXIT_FAILED for r in rows[:3])
    assert all(first_cell(r)["by"] == supervisor_service.BY for r in rows[:3])
    first, second = gaps(rows[:3])
    assert first >= 0.25
    assert second >= 0.5
    assert second > first
    # Unsupervised: its run stopped, nothing after it.
    await runs_of(space, p, lambda rs: all(ended(r) for r in rs))
    count = len(await space.read(history(p)))
    await asyncio.sleep(1.3)
    assert len(await space.read(history(p))) == count
    assert await space.read(supervisor_service.run_of(p)) == ""


@module_loop
async def test_supervisor_always_with_a_delay_is_periodic(space):
    delay = 0.6
    p, _ = await space.plane(prog("return nu.Delay(0.5) >> ops.atomic_state(Tick.n.set(42))"))
    await space.run(supervise(p, ALWAYS, delay=delay))
    rows = await supervised(space, p, lambda rs: len(rs) >= 3 and all(ended(r) for r in rs[:3]))
    await space.run(unsupervise(p))
    assert all(r["exit"] == EXIT_OK for r in rows[:3])
    # The fixed wait every time, where the backoff would be 0.25s after an ok exit.
    assert all(delay <= gap < delay + 2.0 for gap in gaps(rows[:3])), gaps(rows[:3])


@module_loop
async def test_supervisor_on_failure_leaves_an_ok_plane_down_until_supervised_again(space):
    p, _ = await space.plane(SET_42)
    await space.run(supervise(p, ON_FAILURE))
    (row,) = await supervised(space, p, lambda rs: len(rs) == 1 and ended(rs[0]))
    assert row["exit"] == EXIT_OK
    await asyncio.sleep(0.8)
    assert [r["id"] for r in await space.read(history(p))] == [row["id"]]
    # Always restarts after ok: supervising it again brings it up, and again.
    await space.run(supervise(p, ALWAYS))
    rows = await supervised(space, p, lambda rs: len(rs) >= 3)
    await space.run(unsupervise(p))
    assert all(r["exit"] == EXIT_OK for r in rows[:2])


@module_loop
async def test_supervisor_leaves_an_interrupted_run_alone(space):
    p, _ = await space.plane(version("x"))
    await space.run(supervise(p, ALWAYS))
    (row,) = await supervised(space, p, lambda rs: len(rs) == 1 and live(first_cell(rs[0])))
    await space.run(ops.plane_interrupt(row["id"]))
    assert (await space.run_row(row["id"], ended, SLOW))["exit"] == EXIT_INTERRUPTED
    await asyncio.sleep(0.8)
    assert [x["id"] for x in await space.read(history(p))] == [row["id"]]
    await space.run(unsupervise(p))


@module_loop
async def test_supervisor_ignores_runs_by_others(space):
    """Another run of the plane failing is not restarted, and its own run is left as it is."""
    p, _ = await space.plane(version("x"))
    await space.run(supervise(p, ON_FAILURE))
    (mine,) = await supervised(space, p, lambda rs: len(rs) == 1 and live(first_cell(rs[0])))
    theirs = await space.made(ops.plane_run(p, by="test", envs=[ops.env("nope")], into=MADE))
    assert (await space.run_row(theirs, ended, SLOW))["exit"] == EXIT_FAILED
    killed = await space.made(ops.plane_run(p, by="test", into=MADE))
    await space.run(ops.plane_kill(killed))
    await space.run_row(killed, ended, SLOW)
    await asyncio.sleep(0.8)
    rows = await space.read(history(p))
    assert [r["id"] for r in rows] == [mine["id"], theirs, killed]
    assert not ended(rows[0])
    assert await space.read(supervisor_service.run_of(p)) == mine["id"]
    await space.run(unsupervise(p))


@module_loop
async def test_unsupervise_stops_its_run(space):
    p, _ = await space.plane(version("x"))
    await space.run(supervise(p, ALWAYS))
    (row,) = await supervised(space, p, lambda rs: len(rs) == 1 and live(first_cell(rs[0])))
    await space.run(unsupervise(p))
    assert (await space.read(ops.run(row["id"])))["exit"] == EXIT_INTERRUPTED
    await asyncio.sleep(0.8)
    assert [x["id"] for x in await space.read(history(p))] == [row["id"]]


@module_loop
async def test_supervisor_leaves_a_failed_cell_in_a_live_run(space):
    """Plane level: a cell failing while its run goes on is not restarted."""
    p, (_, bad) = await space.plane(version("x"), RAISES)
    await space.run(supervise(p, ON_FAILURE))
    (row,) = await supervised(
        space, p, lambda rs: len(rs) == 1 and cell_of(rs[0], bad).get("exit") == EXIT_FAILED
    )
    await asyncio.sleep(0.8)
    row = await space.read(ops.run(row["id"]))
    assert not ended(row)
    assert len([c for c in row["cells"] if c["cell"] == bad]) == 1
    await space.run(unsupervise(p))


@module_loop
async def test_reload_replaces_a_cell_run_when_its_prog_changes(space):
    p, (c,) = await space.plane(version("v1"))
    envs = [ops.env("session", "conn-9")]
    r = await space.made(ops.plane_run(p, envs=envs, by="test", into=MADE))
    old = first_cell(await space.run_row(r, lambda x: live(first_cell(x)), SLOW))
    await space.run(ops.set_prog(c, version("v2")))

    def replaced(x: dict) -> bool:
        # The old body sees its interrupt on its own time: wait for its end too.
        return len(x["cells"]) == 2 and ended(x["cells"][0]) and live(x["cells"][1])

    row = await space.run_row(r, replaced, SLOW)
    gone, new = row["cells"]
    assert (gone["id"], gone["exit"]) == (old["id"], EXIT_INTERRUPTED)
    assert (new["by"], new["version"], new["worker"]) == (reload_service.BY, 2, old["worker"])
    assert (row["by"], row["envs"]) == ("test", envs)
    assert not ended(row)
    await space.until(States.cells[c].extract(), lambda s: s.get("s") == "v2")
    await space.run(ops.plane_kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_reload_runs_again_a_cell_whose_run_ended_when_its_prog_changes(space):
    """A cell that drew once and returned, in a run kept live by another, is run again on an edit."""
    p, (keeps, once) = await space.plane(version("v1"), SET_42)
    r = await space.made(ops.plane_run(p, by="test", into=MADE))
    await space.run_row(r, lambda x: ended(cell_of(x, once)) and live(cell_of(x, keeps)), SLOW)
    await space.run(ops.set_prog(once, prog("return ops.atomic_state(Tick.n.set(7))")))
    row = await space.run_row(r, lambda x: ended(cell_of(x, once)) and len(x["cells"]) == 3, SLOW)
    again = cell_of(row, once)
    assert (again["by"], again["version"], again["exit"]) == (reload_service.BY, 2, EXIT_OK)
    assert [c["cell"] for c in row["cells"]].count(keeps) == 1
    assert (await space.read(States.cells[once].extract()))["n"] == 7
    await space.run(ops.plane_kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_closing_leaves_no_workers(space):
    await space.close()
    deadline = time.monotonic() + 5
    while workers_named(NAME) and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert workers_named(NAME) == []
