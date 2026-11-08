"""nav with real workers, headless. init, supervisor and reload: test_system_planes.

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
    SET_42,
    Kernel,
    cell_of,
    ended,
    history,
    live,
    opened,
    prog,
    texts,
    workers_named,
)
from _support.made import MADE

import nu
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import EXIT_INTERRUPTED, EXIT_OK, Space, States
from nuspace.system.kernel import store
from nuspace.system.services import (
    BOOTED,
    boot,
    ensure_system,
    init,
)
from nuspace.system.services import nav as nav_service


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


# --- The space ------------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("services") / "space")
    seed = (
        ops.init_stores()
        >> ensure_system()
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
    """The live run nav made for a tab's pane, once its first cell run is live.

    The pane's run is read again on every poll: a plane whose row lands
    before its cells may get an empty run first, which ends at once, and nav
    runs the plane again when the cells come.
    """
    deadline = time.monotonic() + SLOW
    row: dict = {}
    while True:
        rid = await space.read(nav_service.pane_run(sid, plane))
        row = await space.read(ops.run(rid)) if rid else {}
        if live(first_cell(row)):
            return row
        if time.monotonic() > deadline:
            msg = f"no live pane for {sid}/{plane}, last run: {row!r}"
            raise AssertionError(msg)
        await asyncio.sleep(0.05)


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
async def test_nav_closing_a_route_right_after_opening_leaves_no_live_run(space):
    """A turn cancelled mid start still stops the run it made."""
    p, _ = await space.plane(READS_SESSION)
    sid = "conn-flicker"
    for _ in range(3):
        await open_tab(space, sid, p)
        await open_tab(space, sid)
    await close_tab(space, sid)
    await asyncio.sleep(1.0)
    rows = await runs_of(space, p, lambda rs: all(ended(r) for r in rs))
    assert all(r["by"] == nav_service.BY for r in rows)
    assert await space.read(nav_service.pane_run(sid, p)) == ""


@module_loop
async def test_nav_reports_and_restarts_a_raising_arm_and_its_siblings_keep_going(space):
    """A connection whose arm raises is reported on nav's stdout and tried again; others run on."""
    good, _ = await space.plane(READS_SESSION)
    await open_tab(space, "conn-good", good)
    r = (await pane(space, "conn-good", good))["id"]
    # A route that cannot be an id at all: the connection's arm raises on it.
    await space.run(atomic(Space.connections["conn-bad"].routes.set([["x"]])))

    def reported(rows: list[dict]) -> bool:
        out = texts(cell_of(only(rows), nav_service.CELL), "stdout")
        return any(line.startswith("nuspace nav conn-bad: ") for line in out)

    await space.until(history(nav_service.PLANE), reported, SLOW)
    # The sibling's run is untouched, and a new pane still comes up.
    assert not ended(await space.read(ops.run(r)))
    other, _ = await space.plane(READS_SESSION)
    await open_tab(space, "conn-good", good, other)
    await pane(space, "conn-good", other)
    # Fixed, the raising arm comes back on its own after its delay.
    await open_tab(space, "conn-bad", other)
    await pane(space, "conn-bad", other)
    await close_tab(space, "conn-bad")
    await close_tab(space, "conn-good")
    await runs_of(space, other, lambda rs: all(ended(x) for x in rs))


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


@module_loop
async def test_nav_runs_the_plane_again_once_when_a_cell_came_during_its_run(space):
    """The cells are read as the run starts: one added while it runs reruns it after."""
    p, _ = await space.plane(prog("return nu.Delay(0.8) >> ops.atomic_state(Tick.n.set(1))"))
    sid = "conn-mid"
    await open_tab(space, sid, p)
    first = await space.until(nav_service.pane_run(sid, p), bool, SLOW)
    await space.run(ops.add_cell(p, SET_42))
    assert (await space.run_row(first, ended, SLOW))["exit"] == EXIT_OK
    again = await space.until(nav_service.pane_run(sid, p), lambda x: x not in ("", first), SLOW)
    assert (await space.run_row(again, ended, SLOW))["exit"] == EXIT_OK
    await asyncio.sleep(1.0)
    assert await space.read(nav_service.pane_run(sid, p)) == again
    await close_tab(space, sid)


@module_loop
async def test_nav_restart_stops_the_panes_run_and_makes_a_new_one(space):
    p, _ = await space.plane(READS_SESSION)
    sid = "conn-restart"
    await open_tab(space, sid, p)
    first = (await pane(space, sid, p))["id"]
    await space.run(nav_service.restart(sid, p))
    assert (await space.run_row(first, ended, SLOW))["exit"] == EXIT_INTERRUPTED
    again = await space.until(nav_service.pane_run(sid, p), lambda x: x not in ("", first), SLOW)
    assert not ended(await space.read(ops.run(again)))
    await close_tab(space, sid)
    assert (await space.run_row(again, ended, SLOW))["exit"] == EXIT_INTERRUPTED


@module_loop
async def test_nav_restart_cell_runs_it_again_in_the_live_run(space):
    p, (c1, c2) = await space.plane(READS_SESSION, READS_SESSION)
    sid = "conn-restart-cell"
    await open_tab(space, sid, p)
    r = (await pane(space, sid, p))["id"]
    old = cell_of(await space.run_row(r, lambda x: live(cell_of(x, c1)), SLOW), c1)
    await space.run(nav_service.restart_cell(sid, c1))
    row = await space.run_row(r, lambda x: cell_of(x, c1)["id"] != old["id"], SLOW)
    assert cell_of(row, c1)["by"] == nav_service.RESTART_BY
    assert live(cell_of(row, c2))
    assert not ended(row)
    assert await space.read(nav_service.pane_run(sid, p)) == r
    await close_tab(space, sid)


@module_loop
async def test_nav_restart_cell_runs_the_plane_again_once_its_run_ended(space):
    p, (c,) = await space.plane(SET_42)
    sid = "conn-restart-over"
    await open_tab(space, sid, p)
    first = await space.until(nav_service.pane_run(sid, p), bool, SLOW)
    assert (await space.run_row(first, ended, SLOW))["exit"] == EXIT_OK
    await space.run(nav_service.restart_cell(sid, c))
    again = await space.until(nav_service.pane_run(sid, p), lambda x: x not in ("", first), SLOW)
    assert (await space.run_row(again, ended, SLOW))["exit"] == EXIT_OK
    await close_tab(space, sid)


@module_loop
async def test_closing_leaves_no_workers(space):
    await space.close()
    deadline = time.monotonic() + 5
    while workers_named(NAME) and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert workers_named(NAME) == []
