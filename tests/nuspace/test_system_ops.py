"""The system planes against a bare store: made at open, their ops, what they raise.

No kernel: what the ops write is read back. The drivers run in
``test_system_planes``.
"""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
from nu.prog import ConstructionError
from nuspace import system
from nuspace.errors import Exists, Missing, Refused, Removed
from nuspace.shapes import Space, State
from nuspace.shapes.plane import RESERVED
from nuspace.system import init, reactions, reload, supervisor


STORES = ("memory", "sqlite")


async def made_plane(store, **kwargs) -> str:
    return await store.made(nuspace.atomic(nuspace.plane.add(backend="async", into=MADE, **kwargs)))


# --- the set ------------------------------------------------------------------------


async def test_ensure_makes_every_system_plane_once(store):
    await store.run(system.ensure())
    planes = {p: await store.read(Space.planes[p].extract()) for p, _, _ in system.PLANES}
    assert all(row["system"] for row in planes.values())
    assert {p: row["backend"] for p, row in planes.items()} == {
        init.PLANE: "mp",
        supervisor.PLANE: "mp",
        reload.PLANE: "mp",
        reactions.PLANE: "async",
    }
    assert await store.read(nu.list(Space.planes[init.PLANE].cells.keys())) == [init.CELL]
    assert await store.read(nu.list(Space.planes[reactions.PLANE].cells.keys())) == [reactions.PARK]
    assert await store.read(Space.cells[reactions.PARK].prog) == reactions.plane.PARK_PROG
    assert await store.read(nu.list(init.boot_list().keys())) == sorted(init.BOOTED)
    # Idempotent, and an edited boot list is left as it is.
    await store.run(nuspace.atomic(init.unboot(reload.PLANE)))
    await store.run(system.ensure())
    assert await store.read(nu.list(Space.planes[init.PLANE].cells.keys())) == [init.CELL]
    assert reload.PLANE not in await store.read(nu.list(init.boot_list().keys()))


async def test_start_asks_for_one_init_run(store):
    await store.run(system.ensure())
    await store.run(system.start())
    await store.run(system.start())
    live = await store.read(Space.exec.indexes.live.plane_to_plane_runs[init.PLANE].ids.extract())
    (run,) = live
    assert await store.read(Space.exec.plane_runs[run].by) == system.planes.BY


async def test_a_system_plane_cannot_be_removed(store):
    await store.run(system.ensure())
    with pytest.raises(Refused):
        await store.run(nuspace.atomic(nuspace.plane.remove(supervisor.PLANE)))


async def test_a_system_plane_id_is_reserved(store):
    for pid in RESERVED:
        with pytest.raises(Refused, match="reserved"):
            nuspace.plane.add(pid, backend="async")
        with pytest.raises(Refused, match="reserved"):
            await store.run(nuspace.atomic(nuspace.plane.add(nu.Str(pid), backend="async")))
    assert {p for p, _, _ in system.PLANES} <= RESERVED
    await store.run(nuspace.atomic(nuspace.plane.add(init.PLANE, backend="mp", system=True)))
    await store.run(nuspace.atomic(nuspace.plane.add(nu.Str("x"), backend="mp")))


async def test_ensure_refuses_a_system_id_held_by_something_else(store):
    # A store from before the ids were reserved: written past the check.
    await store.run(nuspace.atomic(nuspace.plane.add("reload", backend="mp", system=nu.Bool(True))))
    await store.run(nuspace.atomic(Space.planes["reload"].system.set(False)))
    with pytest.raises(Refused, match="not system"):
        await store.run(system.ensure())


async def test_ensure_refuses_a_system_cell_id_on_another_plane(store):
    p = await made_plane(store)
    await store.run(
        nuspace.atomic(nuspace.cell.add(p, reactions.plane.PARK_PROG, id=init.CELL, fabrics=[]))
    )
    with pytest.raises(Refused, match="another plane"):
        await store.run(system.ensure())


# --- init -----------------------------------------------------------------------------


async def test_boot_and_unboot(store):
    p = await made_plane(store)
    await store.run(nuspace.atomic(init.boot(p)))
    assert await store.read(init.boot_list()[p]) is True
    with pytest.raises(Exists):
        await store.run(nuspace.atomic(init.boot(p)))
    await store.run(nuspace.atomic(init.boot(p, exists_ok=True)))
    await store.run(nuspace.atomic(init.unboot(p)))
    assert await store.read(init.boot_list()[p].exists()) is False
    with pytest.raises(Missing):
        await store.run(nuspace.atomic(init.unboot(p)))
    await store.run(nuspace.atomic(init.unboot(p, missing_ok=True)))


async def test_boot_refuses_a_missing_or_removed_plane(store):
    with pytest.raises(Missing):
        await store.run(nuspace.atomic(init.boot("nope")))
    p = await made_plane(store)
    await store.run(nuspace.atomic(nuspace.plane.remove(p)))
    with pytest.raises(Removed):
        await store.run(nuspace.atomic(init.boot(p)))


# --- supervisor -----------------------------------------------------------------------


async def test_supervise_and_unsupervise(store):
    p = await made_plane(store)
    row = supervisor.supervised()[p]
    await store.run(nuspace.atomic(supervisor.supervise(p, policy=supervisor.ON_FAILURE)))
    assert await store.read(row.extract()) == {"policy": supervisor.ON_FAILURE}
    with pytest.raises(Exists):
        await store.run(nuspace.atomic(supervisor.supervise(p, policy=supervisor.ALWAYS)))
    await store.run(
        nuspace.atomic(supervisor.supervise(p, policy=supervisor.ALWAYS, delay=2.5, exists_ok=True))
    )
    assert await store.read(row.extract()) == {"policy": supervisor.ALWAYS, "delay": 2.5}
    # Back to the backoff: the delay goes.
    await store.run(
        nuspace.atomic(supervisor.supervise(p, policy=supervisor.ON_FAILURE, exists_ok=True))
    )
    assert await store.read(row.extract()) == {"policy": supervisor.ON_FAILURE}
    await store.run(nuspace.atomic(supervisor.unsupervise(p)))
    assert await store.read(row.exists()) is False
    with pytest.raises(Missing):
        await store.run(nuspace.atomic(supervisor.unsupervise(p)))
    await store.run(nuspace.atomic(supervisor.unsupervise(p, missing_ok=True)))


async def test_supervise_forgets_a_run_that_is_over(store):
    """A plane its policy left down comes up again: supervising it asks for it to run."""
    p = await made_plane(store)
    run = await store.made(nuspace.atomic(nuspace.plane_run.add(p, into=MADE)))
    row = supervisor.supervised()[p]
    await store.run(
        nuspace.atomic(supervisor.supervise(p, policy=supervisor.ON_FAILURE) >> row.run.set(run))
    )
    await store.run(
        nuspace.atomic(supervisor.supervise(p, policy=supervisor.ON_FAILURE, exists_ok=True))
    )
    assert await store.read(row.run) == run
    await store.run(nuspace.atomic(nuspace.plane_run.end(run, "ok")))
    await store.run(
        nuspace.atomic(supervisor.supervise(p, policy=supervisor.ON_FAILURE, exists_ok=True))
    )
    assert await store.read(row.run.exists()) is False


async def test_supervise_refuses(store):
    with pytest.raises(Missing):
        await store.run(nuspace.atomic(supervisor.supervise("nope", policy=supervisor.ON_FAILURE)))
    p = await made_plane(store)
    with pytest.raises(Refused):
        supervisor.supervise(p, policy="sometimes")
    with pytest.raises(Refused):
        supervisor.supervise(p, policy=supervisor.ON_FAILURE, delay=-1.0)
    with pytest.raises(Refused):
        await store.run(nuspace.atomic(supervisor.supervise(p, policy=nu.Str("sometimes"))))
    await store.run(nuspace.atomic(nuspace.plane.remove(p)))
    with pytest.raises(Removed):
        await store.run(nuspace.atomic(supervisor.supervise(p, policy=supervisor.ON_FAILURE)))


# --- reactions ------------------------------------------------------------------------


CHANGE = 'nuspace.at.plane(id="watched").state(Box).body.on_change()'
IMPORTS = ("from _support.contents import Note as Box",)


async def test_add_writes_a_reaction_cell_and_where_it_is_kept(store):
    await store.run(system.ensure())
    p = await made_plane(store)
    r = await store.made(reactions.add(CHANGE, p, imports=IMPORTS, into=MADE))
    cell = await store.read(Space.cells[r].extract())
    assert (cell["plane"], cell["name"], cell["fabrics"]) == (reactions.PLANE, p, [])
    assert f"react(\n        {CHANGE},\n        PLANE,\n        REACTION,\n    )" in cell["prog"]
    assert "nuspace.utils" not in cell["prog"]
    assert f"PLANE = {p!r}" in cell["prog"]
    assert f"REACTION = {r!r}" in cell["prog"]
    assert IMPORTS[0] in cell["prog"]
    assert await store.read(nu.list(Space.planes[reactions.PLANE].cells.keys())) == [
        reactions.PARK,
        r,
    ]
    assert await store.read(State.cells[r].extract()) == {"plane": p}
    assert await store.read(reactions.registry().by_plane[p].ids.extract()) == {r: True}
    # Additive: the same pair twice is two reactions.
    again = await store.made(reactions.add(CHANGE, p, imports=IMPORTS, into=MADE))
    assert again != r
    assert set(await store.read(reactions.registry().by_plane[p].ids.extract())) == {r, again}


@pytest.mark.parametrize(
    ("change", "imports"),
    [("not python (", ()), (CHANGE, ()), (CHANGE, ("from nowhere import Box",))],
)
async def test_add_refuses_source_that_does_not_load_and_writes_nothing(store, change, imports):
    await store.run(system.ensure())
    p = await made_plane(store)
    with pytest.raises(ConstructionError):
        await store.run(reactions.add(change, p, imports=imports))
    assert await store.read(nu.list(Space.planes[reactions.PLANE].cells.keys())) == [reactions.PARK]
    assert await store.read(reactions.registry().by_plane[p].exists()) is False


async def test_add_refuses_a_missing_or_removed_plane(store):
    await store.run(system.ensure())
    with pytest.raises(Missing):
        await store.run(reactions.add(CHANGE, "nope", imports=IMPORTS))
    p = await made_plane(store)
    await store.run(nuspace.atomic(nuspace.plane.remove(p)))
    with pytest.raises(Removed):
        await store.run(reactions.add(CHANGE, p, imports=IMPORTS))
    assert await store.read(nu.list(Space.planes[reactions.PLANE].cells.keys())) == [reactions.PARK]


async def test_remove_takes_the_cell_and_its_entry(store):
    await store.run(system.ensure())
    p = await made_plane(store)
    r = await store.made(reactions.add(CHANGE, p, imports=IMPORTS, into=MADE))
    await store.run(reactions.remove(r))
    assert await store.read(Space.cells[r].removed_at.exists()) is True
    assert await store.read(reactions.registry().by_plane[p].ids.extract()) == {}
    with pytest.raises(Missing):
        await store.run(reactions.remove(r))
    with pytest.raises(Missing):
        await store.run(reactions.remove("nope"))
    with pytest.raises(Missing):
        await store.run(reactions.remove(reactions.PARK))


async def test_clear_removes_every_reaction_of_a_plane(store):
    await store.run(system.ensure())
    p, other = await made_plane(store), await made_plane(store)
    mine = [await store.made(reactions.add(CHANGE, p, imports=IMPORTS, into=MADE)) for _ in "ab"]
    kept = await store.made(reactions.add(CHANGE, other, imports=IMPORTS, into=MADE))
    # An entry naming no live reaction, as a crash between commits leaves: dropped.
    await store.run(nuspace.atomic(reactions.registry().by_plane[p].ids.set_item("gone", True)))
    await store.run(reactions.clear(p))
    assert all([await store.read(Space.cells[r].removed_at.exists()) for r in mine])
    assert await store.read(reactions.registry().by_plane[p].ids.extract()) == {}
    assert await store.read(Space.cells[kept].removed_at.exists()) is False
    # None is fine.
    await store.run(reactions.clear(p))
    await store.run(reactions.clear("never"))
