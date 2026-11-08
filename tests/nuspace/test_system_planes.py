"""The system planes' drivers with real workers, headless: init, supervisor, reload, reactions.

One space for the module, opened the way a host opens one: the kernel up,
the system planes made, ``opened_at`` stamped, a user plane booted, then
init's run asked for. init brings up the rest. Every test makes its own
planes and polls the store until the drivers have acted.
"""

from __future__ import annotations

import asyncio
import itertools
import tempfile
import time

import pytest
import pytest_asyncio
from _support.kernel import RAISES, SET_42, Kernel, cell_of, ended, live, opened, prog
from _support.made import MADE

import nu
import nuspace
from nuspace import system
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, EXIT_OK, Space, State
from nuspace.system import init, reactions, reload, supervisor


module_loop = pytest.mark.asyncio(loop_scope="module")

NAME = "nuspace-system"

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0

#: Fails, but only after long enough for the supervisor to have seen it live.
FAILS_LATE = prog('return nu.Delay(0.6) >> nu.Raise(nu.Str("boom"))')


def version(v: str) -> str:
    """Writes ``v`` to its state, then runs until stopped."""
    set_v = f'nuspace.atomic(nuspace.here(Tick).s.set("{v}"))'
    return prog(f"return {set_v} >> nu.ForeverDo(nu.Delay(0.05))")


async def open_space(name: str, *, data: str | None = None) -> Kernel:
    """A kernel open the way a host opens one: system planes made, ``opened_at`` stamped, init asked for."""
    k = await opened(name, data=data, spares=2)
    await k.run(system.ensure())
    await k.do(Space.info.opened_at.set(time.time()))
    await k.run(system.start())
    return k


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space():
    k = await opened(NAME, spares=2)
    await k.run(system.ensure())
    booted, _ = await k.plane(SET_42)
    await k.do(Space.info.opened_at.set(time.time()))
    await k.do(init.boot(booted))
    await k.run(system.start())
    k.booted = booted
    yield k
    await k.close()


async def runs_of(k: Kernel, plane: str) -> list[dict]:
    """Every plane run of a plane, oldest first, as :meth:`Kernel.row` reads it. Test only."""
    ids = Space.exec.indexes.history.plane_to_plane_runs[plane].runs
    listed = await k.read(nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([])))
    return [await k.row(r) for r in listed]


async def until_runs(k: Kernel, plane: str, pred, timeout: float = SLOW) -> list[dict]:
    return await k.until(lambda: runs_of(k, plane), pred, timeout)


def first_cell(row: dict) -> dict:
    return row["cells"][0] if row.get("cells") else {}


def gaps(rows: list[dict]) -> list[float]:
    """The waits between one run ending and the next being asked for."""
    return [rows[i + 1]["created_at"] - rows[i]["ended_at"] for i in range(len(rows) - 1)]


# --- init ---------------------------------------------------------------------------


@module_loop
async def test_init_runs_its_boot_list_once_per_open(space):
    (own,) = await until_runs(space, init.PLANE, lambda rs: rs and live(first_cell(rs[0])))
    assert own["by"] == system.planes.BY
    for plane in (supervisor.PLANE, reload.PLANE, reactions.PLANE):
        (row,) = await until_runs(space, plane, lambda rs: rs and live(first_cell(rs[0])))
        assert row["by"] == init.BY
    # The reactions plane stays up with no reaction: its park cell never ends.
    assert [c["cell"] for c in row["cells"]] == [reactions.PARK]
    (row,) = await until_runs(space, space.booted, lambda rs: rs and ended(rs[0]))
    assert (row["by"], row["exit"]) == (init.BY, EXIT_OK)
    assert await space.read(State.cells[first_cell(row)["cell"]].extract()) == {"n": 42}
    # Ended in this open, so not run again.
    await asyncio.sleep(0.6)
    assert len(await runs_of(space, space.booted)) == 1


@module_loop
async def test_init_runs_a_plane_booted_mid_open_once(space):
    p, _ = await space.plane(SET_42)
    await space.do(init.boot(p))
    (row,) = await until_runs(space, p, lambda rs: rs and ended(rs[0]))
    assert row["by"] == init.BY
    # Another list change: a plane that ran in this open stays down.
    q, _ = await space.plane(SET_42)
    await space.do(init.boot(q))
    await until_runs(space, q, lambda rs: rs and ended(rs[0]))
    assert len(await runs_of(space, p)) == 1


@module_loop
async def test_a_plane_booted_and_supervised_gets_one_run(space):
    """init leaves a supervised plane to the supervisor: one run in the open, not two."""
    p, _ = await space.plane(version("x"))
    await space.do(supervisor.supervise(p, policy=supervisor.ALWAYS) >> init.boot(p))
    (row,) = await until_runs(space, p, lambda rs: len(rs) == 1 and live(first_cell(rs[0])))
    assert row["by"] == supervisor.BY
    await asyncio.sleep(0.8)
    assert len(await runs_of(space, p)) == 1
    await space.do(supervisor.unsupervise(p) >> init.unboot(p))
    await space.do(nuspace.plane_run.kill(row["id"]))


# --- supervisor -------------------------------------------------------------------------


@module_loop
async def test_supervisor_restarts_a_failed_plane_with_backoff(space):
    p, _ = await space.plane(FAILS_LATE)
    await space.do(supervisor.supervise(p, policy=supervisor.ON_FAILURE))
    rows = await until_runs(space, p, lambda rs: len(rs) >= 3 and all(ended(r) for r in rs[:3]))
    await space.do(supervisor.unsupervise(p))
    assert all((r["by"], r["exit"]) == (supervisor.BY, EXIT_FAILED) for r in rows[:3])
    # Lower bounds only: load stretches a wait but never shortens one.
    first, second = gaps(rows[:3])
    assert first >= supervisor.BACKOFF_START
    assert second >= 2 * supervisor.BACKOFF_START
    # Unsupervised: a run going is left alone, nothing starts after it.
    rows = await until_runs(space, p, lambda rs: all(ended(r) for r in rs))
    await asyncio.sleep(1.0)
    assert len(await runs_of(space, p)) == len(rows)


@module_loop
async def test_supervisor_on_failure_leaves_an_ok_plane_down(space):
    p, _ = await space.plane(SET_42)
    await space.do(supervisor.supervise(p, policy=supervisor.ON_FAILURE))
    (row,) = await until_runs(space, p, lambda rs: len(rs) == 1 and ended(rs[0]))
    assert row["exit"] == EXIT_OK
    await asyncio.sleep(0.8)
    assert len(await runs_of(space, p)) == 1
    # Always restarts after ok, with the fixed delay.
    await space.do(supervisor.supervise(p, policy=supervisor.ALWAYS, delay=0.4, exists_ok=True))
    rows = await until_runs(space, p, lambda rs: len(rs) >= 3 and all(ended(r) for r in rs[:3]))
    await space.do(supervisor.unsupervise(p))
    assert all(r["exit"] == EXIT_OK for r in rows[:3])
    assert gaps(rows[1:3])[0] >= 0.4


@module_loop
async def test_supervisor_leaves_runs_of_others_and_asked_ends_alone(space):
    p, _ = await space.plane(version("x"))
    await space.do(supervisor.supervise(p, policy=supervisor.ALWAYS))
    (mine,) = await until_runs(space, p, lambda rs: len(rs) == 1 and live(first_cell(rs[0])))
    theirs = await space.made(nuspace.plane_run.add(p, by="test", into=MADE))
    await space.do(nuspace.plane_run.kill(theirs))
    await space.run_row(theirs, ended, SLOW)
    await space.do(nuspace.plane_run.interrupt(mine["id"]))
    assert (await space.run_row(mine["id"], ended, SLOW))["exit"] == EXIT_INTERRUPTED
    await asyncio.sleep(0.8)
    assert [r["id"] for r in await runs_of(space, p)] == [mine["id"], theirs]
    await space.do(supervisor.unsupervise(p))


@module_loop
async def test_supervisor_runs_a_plane_again_after_a_new_open(space):
    """A remembered run from an earlier open, ended killed by reap, is no reason to stay down."""
    p, _ = await space.plane(version("x"))
    old = await space.made(nuspace.plane_run.add(p, by=supervisor.BY, into=MADE))
    await space.do(nuspace.plane_run.kill(old))
    assert (await space.run_row(old, ended, SLOW))["exit"] == EXIT_KILLED
    await space.do(Space.info.opened_at.set(time.time()))
    row = supervisor.supervised()[p]
    await space.do(supervisor.supervise(p, policy=supervisor.ON_FAILURE) >> row.run.set(old))
    rows = await until_runs(space, p, lambda rs: len(rs) == 2 and live(first_cell(rs[1])))
    assert rows[1]["by"] == supervisor.BY
    assert await space.read(row.run) == rows[1]["id"]
    await space.do(supervisor.unsupervise(p))
    await space.do(nuspace.plane_run.kill(rows[1]["id"]))


@module_loop
async def test_supervisor_leaves_a_failed_cell_in_a_live_run(space):
    """Plane level: a cell failing while its plane run goes on is not restarted."""
    p, (_, bad) = await space.plane(version("x"), RAISES)
    await space.do(supervisor.supervise(p, policy=supervisor.ON_FAILURE))

    def failed(rs: list[dict]) -> bool:
        return len(rs) == 1 and cell_of(rs[0], bad).get("exit") == EXIT_FAILED

    (row,) = await until_runs(space, p, failed)
    await asyncio.sleep(0.8)
    row = await space.row(row["id"])
    assert not ended(row)
    assert [c["cell"] for c in row["cells"]].count(bad) == 1
    assert len(await runs_of(space, p)) == 1
    await space.do(supervisor.unsupervise(p))
    await space.do(nuspace.plane_run.kill(row["id"]))


# --- reload ---------------------------------------------------------------------------


@module_loop
async def test_reload_reruns_a_rewritten_cell_and_runs_a_new_one(space):
    p, (c,) = await space.plane(version("v1"))
    r = await space.made(nuspace.plane_run.add(p, by="test", into=MADE))
    old = first_cell(await space.run_row(r, lambda x: live(first_cell(x)), SLOW))
    await space.do(nuspace.cell.set_prog(c, version("v2"), fabrics=[]))

    def replaced(x: dict) -> bool:
        return len(x["cells"]) == 2 and ended(x["cells"][0]) and live(x["cells"][1])

    row = await space.run_row(r, replaced, SLOW)
    gone, new = row["cells"]
    assert (gone["id"], gone["exit"]) == (old["id"], EXIT_INTERRUPTED)
    assert (new["by"], new["version"]) == (reload.BY, 2)
    await space.until(lambda: space.read(State.cells[c].extract()), lambda s: s.get("s") == "v2")
    added = await space.made(nuspace.cell.add(p, SET_42, fabrics=[], into=MADE))
    row = await space.run_row(r, lambda x: ended(cell_of(x, added)), SLOW)
    assert (cell_of(row, added)["by"], cell_of(row, added)["exit"]) == (reload.BY, EXIT_OK)
    assert [x["cell"] for x in row["cells"]].count(c) == 2
    await space.do(nuspace.plane_run.kill(r))
    await space.run_row(r, ended, SLOW)


@module_loop
async def test_reload_runs_again_a_cell_whose_run_ended_when_its_prog_changes(space):
    """A cell that drew and returned, in a run kept live by another, runs again on an edit."""
    p, (keeps, once) = await space.plane(version("v1"), SET_42)
    r = await space.made(nuspace.plane_run.add(p, by="test", into=MADE))
    await space.run_row(r, lambda x: ended(cell_of(x, once)) and live(cell_of(x, keeps)), SLOW)
    seven = prog("return nuspace.atomic(nuspace.here(Tick).n.set(7))")
    await space.do(nuspace.cell.set_prog(once, seven, fabrics=[]))
    row = await space.run_row(r, lambda x: len(x["cells"]) == 3 and ended(cell_of(x, once)), SLOW)
    again = cell_of(row, once)
    assert (again["by"], again["version"], again["exit"]) == (reload.BY, 2, EXIT_OK)
    assert [c["cell"] for c in row["cells"]].count(keeps) == 1
    assert (await space.read(State.cells[once].extract()))["n"] == 7
    await space.do(nuspace.plane_run.kill(r))
    await space.run_row(r, ended, SLOW)


# --- reactions ------------------------------------------------------------------------


WATCHED = "watched"
IMPORTS = ("from _support.contents import Note as Box",)

#: Runs to completion, long enough to land changes while it runs.
WORKS = prog("return nu.Delay(0.6) >> nuspace.atomic(nuspace.here(Tick).n.set(1))")


def change_of(watched: str = WATCHED) -> str:
    """The change a reaction waits on, as source: the body of a watched plane's state."""
    return f'nuspace.at.plane(id="{watched}").state(Box).body.on_change()'


CHANGE = change_of()


def box(watched: str = WATCHED):
    from _support.contents import Note

    return nuspace.at.plane(id=watched).state(Note)


async def reacting(k: Kernel, watched: str, plane: str) -> str:
    """A reaction on ``watched`` that runs ``plane``, once its cell runs: its id."""
    r = await k.made(reactions.add(change_of(watched), plane, imports=IMPORTS, into=MADE))
    rows = await until_runs(k, reactions.PLANE, lambda rs: any(not ended(x) for x in rs))
    (host,) = [x for x in rows if not ended(x)]
    await k.run_row(host["id"], lambda x: live(cell_of(x, r)), SLOW)
    return r


def no_overlap(rows: list[dict]) -> bool:
    """No two of the plane runs were up at once."""
    spans = sorted((r["started_at"], r["ended_at"]) for r in rows)
    return all(a[1] <= b[0] for a, b in itertools.pairwise(spans))


def all_ended(rows: list[dict]) -> bool:
    return bool(rows) and all(ended(r) for r in rows)


@module_loop
async def test_a_reaction_runs_its_plane_on_each_change_until_removed(space):
    p, _ = await space.plane(SET_42)
    r = await space.made(reactions.add(CHANGE, p, imports=IMPORTS, into=MADE))
    (host,) = [x for x in await runs_of(space, reactions.PLANE) if not ended(x)]
    await space.run_row(host["id"], lambda x: live(cell_of(x, r)), SLOW)
    assert cell_of(await space.row(host["id"]), r)["by"] == reload.BY
    await asyncio.sleep(0.3)
    assert await runs_of(space, p) == []
    await space.do(box().body.set("one"))
    (row,) = await until_runs(space, p, lambda rs: len(rs) == 1 and ended(rs[0]))
    assert (row["by"], row["exit"]) == (r, EXIT_OK)
    await space.do(box().body.set("two"))
    await until_runs(space, p, lambda rs: len(rs) == 2 and ended(rs[1]))
    await space.run(reactions.remove(r))
    await space.run_row(host["id"], lambda x: ended(cell_of(x, r)), SLOW)
    await space.do(box().body.set("three"))
    await asyncio.sleep(0.8)
    assert len(await runs_of(space, p)) == 2


@module_loop
async def test_a_burst_merges(space):
    """A burst of changes while idle: one run for the first, at most one after it."""
    p, _ = await space.plane(WORKS)
    await reacting(space, "burst", p)
    for n in range(12):
        await space.do(box("burst").body.set(str(n)))
    await until_runs(space, p, all_ended)
    await asyncio.sleep(1.5)
    rows = await runs_of(space, p)
    assert 1 <= len(rows) <= 2, rows
    assert all_ended(rows)
    assert no_overlap(rows), rows


@module_loop
@pytest.mark.parametrize("changes", [1, 12])
async def test_changes_during_a_live_run_fire_after_it(space, changes):
    """Changes landing mid run: one run follows it, never two at once."""
    watched = f"during{changes}"
    p, _ = await space.plane(WORKS)
    r = await reacting(space, watched, p)
    await space.do(box(watched).body.set("first"))
    await until_runs(space, p, lambda rs: len(rs) == 1 and live(rs[0]))
    for n in range(changes):
        await space.do(box(watched).body.set(f"mid {n}"))
        await asyncio.sleep(0.02)
    await until_runs(space, p, lambda rs: len(rs) >= 2 and all_ended(rs))
    await asyncio.sleep(1.5)
    rows = await runs_of(space, p)
    assert len(rows) == 2, rows
    assert all(x["by"] == r for x in rows)
    assert rows[1]["started_at"] >= rows[0]["ended_at"]


@module_loop
async def test_never_two_runs_of_one_reaction_at_once(space):
    """Two reactions on one plane, changes landing on both: each one's runs never overlap."""
    p, _ = await space.plane(WORKS)
    one, two = await reacting(space, "one", p), await reacting(space, "two", p)
    for n in range(6):
        await space.do(box("one").body.set(str(n)) >> box("two").body.set(str(n)))
        await asyncio.sleep(0.3)
    await until_runs(space, p, lambda rs: len(rs) >= 4 and all_ended(rs))
    await asyncio.sleep(1.5)
    rows = await runs_of(space, p)
    assert all_ended(rows)
    assert {x["by"] for x in rows} == {one, two}
    for r in (one, two):
        mine = [x for x in rows if x["by"] == r]
        assert no_overlap(mine), mine
        # What it checks is the run it asked for last: one point read, no scan.
        assert await space.read(State.cells[r].extract()) == {"plane": p, "run": mine[-1]["id"]}


@module_loop
async def test_a_run_by_someone_else_does_not_hold_a_reaction_back(space):
    p, _ = await space.plane(version("x"))
    r = await reacting(space, "theirs", p)
    theirs = await space.made(nuspace.plane_run.add(p, by="test", into=MADE))
    await space.run_row(theirs, lambda x: live(first_cell(x)), SLOW)
    await space.do(box("theirs").body.set("go"))
    rows = await until_runs(space, p, lambda rs: len(rs) == 2 and live(first_cell(rs[1])))
    assert rows[1]["by"] == r
    assert not ended(await space.row(theirs))
    await space.run(reactions.remove(r))
    for x in rows:
        await space.do(nuspace.plane_run.kill(x["id"]))


async def test_a_reaction_comes_back_at_the_next_open():
    """A reaction outlives its open: init boots the reactions plane, and the next change fires.

    A change made while the space was closed is not one: event flows are
    best effort, and no run comes of it.
    """
    data = tempfile.mkdtemp(prefix="nuspace-reopen-")
    name = f"{NAME}-reopen"
    k = await open_space(name, data=data)
    try:
        p, _ = await k.plane(SET_42)
        r = await reacting(k, "reopen", p)
    finally:
        await k.close()
    k = await open_space(name, data=data)
    try:
        # The reactions plane came back at boot, by init, with the reaction in it.
        host = await until_runs(k, reactions.PLANE, lambda rs: any(live(x) for x in rs))
        (row,) = [x for x in host if live(x)]
        assert row["by"] == init.BY
        await k.run_row(row["id"], lambda x: live(cell_of(x, r)), SLOW)
        await asyncio.sleep(0.3)
        assert await runs_of(k, p) == []
        await k.do(box("reopen").body.set("again"))
        (fired,) = await until_runs(k, p, lambda rs: len(rs) == 1 and ended(rs[0]))
        assert (fired["by"], fired["exit"]) == (r, EXIT_OK)
    finally:
        await k.close()
