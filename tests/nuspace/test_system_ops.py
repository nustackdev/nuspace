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


async def keyed(store, key: str) -> str:
    """The id of the plane holding ``key``."""
    return await store.read(nuspace.plane.keyed(key))


async def cells_of(store, key: str) -> list[str]:
    """The cell ids of the plane holding ``key``, in order."""
    return await store.read(nu.list(Space.planes[nuspace.plane.keyed(key)].cells.keys()))


async def park(store) -> str:
    """The reactions plane's park cell: its first."""
    return (await cells_of(store, reactions.KEY))[0]


# --- the set ------------------------------------------------------------------------


async def test_ensure_makes_every_system_plane_once(store):
    await store.run(system.ensure())
    ids = {key: await keyed(store, key) for key, *_ in system.PLANES}
    # Minted ids, like any plane's: code finds them by key.
    assert all(pid.startswith("p_") for pid in ids.values())
    planes = {key: await store.read(Space.planes[pid].extract()) for key, pid in ids.items()}
    assert all(row["system"] for row in planes.values())
    assert {key: row["key"] for key, row in planes.items()} == {key: key for key in ids}
    assert {key: row["name"] for key, row in planes.items()} == {
        init.KEY: "Init",
        supervisor.KEY: "Supervisor",
        reload.KEY: "Reload",
        reactions.KEY: "Reactions",
    }
    assert {key: row["backend"] for key, row in planes.items()} == {
        init.KEY: "mp",
        supervisor.KEY: "mp",
        reload.KEY: "mp",
        reactions.KEY: "async",
    }
    (main,) = await cells_of(store, init.KEY)
    assert main.startswith("c_") and await store.read(Space.cells[main].name) == "main"
    assert await store.read(Space.cells[await park(store)].prog) == reactions.plane.PARK_PROG
    booted = {ids[key] for key in init.BOOTED}
    assert set(await store.read(nu.list(init.boot_list().keys()))) == booted
    # Idempotent, and an edited boot list is left as it is.
    await store.run(nuspace.atomic(init.unboot(ids[reload.KEY])))
    await store.run(system.ensure())
    assert {key: await keyed(store, key) for key, *_ in system.PLANES} == ids
    assert await cells_of(store, init.KEY) == [main]
    assert ids[reload.KEY] not in await store.read(nu.list(init.boot_list().keys()))


async def test_start_asks_for_one_init_run(store):
    await store.run(system.ensure())
    await store.run(system.start())
    await store.run(system.start())
    plane = nuspace.plane.keyed(init.KEY)
    live = await store.read(Space.exec.indexes.live.plane_to_plane_runs[plane].ids.extract())
    (run,) = live
    assert await store.read(Space.exec.plane_runs[run].by) == system.planes.BY


async def test_a_system_plane_cannot_be_removed(store):
    await store.run(system.ensure())
    with pytest.raises(Refused):
        await store.run(nuspace.atomic(nuspace.plane.remove(await keyed(store, supervisor.KEY))))


async def test_a_system_plane_key_is_reserved(store):
    assert {key for key, *_ in system.PLANES} <= RESERVED
    p = await made_plane(store)
    for key in RESERVED:
        with pytest.raises(Refused, match="reserved"):
            nuspace.plane.add(key=key, backend="async")
        with pytest.raises(Refused, match="reserved"):
            await store.run(nuspace.atomic(nuspace.plane.add(key=nu.Str(key), backend="async")))
        with pytest.raises(Refused, match="reserved"):
            await store.run(nuspace.atomic(nuspace.plane.set_key(p, key)))
    # The names are plain ids now, the keys are what is held.
    await store.run(nuspace.atomic(nuspace.plane.add("init", backend="mp")))
    await store.run(nuspace.atomic(nuspace.plane.add(key="init", backend="mp", system=True)))


# --- init -----------------------------------------------------------------------------


async def test_boot_and_unboot(store):
    await store.run(system.ensure())
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
    await store.run(system.ensure())
    with pytest.raises(Missing):
        await store.run(nuspace.atomic(init.boot("nope")))
    p = await made_plane(store)
    await store.run(nuspace.atomic(nuspace.plane.remove(p)))
    with pytest.raises(Removed):
        await store.run(nuspace.atomic(init.boot(p)))


# --- supervisor -----------------------------------------------------------------------


async def test_supervise_and_unsupervise(store):
    await store.run(system.ensure())
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
    await store.run(system.ensure())
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
    await store.run(system.ensure())
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
    assert (cell["plane"], cell["name"], cell["fabrics"]) == (
        await keyed(store, reactions.KEY),
        p,
        [],
    )
    assert f"react(\n        {CHANGE},\n        PLANE,\n        REACTION,\n    )" in cell["prog"]
    assert "nuspace.utils" not in cell["prog"]
    assert f"PLANE = {p!r}" in cell["prog"]
    assert f"REACTION = {r!r}" in cell["prog"]
    assert IMPORTS[0] in cell["prog"]
    assert await cells_of(store, reactions.KEY) == [await park(store), r]
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
    assert await cells_of(store, reactions.KEY) == [await park(store)]
    assert await store.read(reactions.registry().by_plane[p].exists()) is False


async def test_add_refuses_a_missing_or_removed_plane(store):
    await store.run(system.ensure())
    with pytest.raises(Missing):
        await store.run(reactions.add(CHANGE, "nope", imports=IMPORTS))
    p = await made_plane(store)
    await store.run(nuspace.atomic(nuspace.plane.remove(p)))
    with pytest.raises(Removed):
        await store.run(reactions.add(CHANGE, p, imports=IMPORTS))
    assert await cells_of(store, reactions.KEY) == [await park(store)]


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
        await store.run(reactions.remove(await park(store)))


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
