"""reactions: the ops against a bare store, then reactions firing planes on real workers.

The ops run against the in memory store: the reaction cell, its source, its
key. The space is one for the module, bootstrapped the way a host opens one,
so init brings the reactions plane up at boot, with no cells. Every test
makes its own target plane and watches its own state, and polls the store
until the reactions have acted.
"""

from __future__ import annotations

import asyncio
import itertools

import pytest
import pytest_asyncio
from _support.kernel import Kernel, ended, history, live, opened, prog

import nu
import nustd.kv
from nu.prog import ConstructionError
from nuspace import ops
from nuspace.ops.utils import atomic_state
from nuspace.shapes import EXIT_INTERRUPTED, EXIT_OK, CellState, PlaneState, Space, States
from nuspace.system.kernel import store
from nuspace.system.services import (
    BOOTED,
    disable_react,
    enable_react,
    ensure_system,
    init,
    reactions,
)


module_loop = pytest.mark.asyncio(loop_scope="module")

NAME = "nuspace-reactions"

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0

#: A target that runs to completion, long enough to land changes while it runs.
WORKS = prog("return nu.Delay(1.0) >> Tick.n.set(1)")


class Inbox(PlaneState):
    """A watched leaf, in the target plane's own state."""

    count = nustd.kv.IntRef.slot()
    other = nustd.kv.IntRef.slot()


class Tick(CellState):
    """A watched leaf, in a cell's own state."""

    n = nustd.kv.IntRef.slot()


def on(plane: str, key: str = "count") -> str:
    """The change a reaction waits on: a key of the plane's state, as source."""
    return f'States.planes["{plane}"].state["{key}"].on_change()'


def bump(plane: str, n: int, key: str = "count") -> nu.Nu:
    return atomic_state(ops.plane_state(plane, getattr(Inbox, key).set(n)))


def index() -> nu.Nu:
    cells = ops.plane_state(reactions.PLANE, reactions.Registry.cells)
    return nu.If(cells.exists(), cells.extract(), nu.Literal({}))


# --- The ops: no workers ------------------------------------------------------------------


async def test_bootstrap_makes_the_plane_with_no_cells(store):
    await store.run(ensure_system())
    row = Space.planes[reactions.PLANE]
    assert await store.read(row.name) == reactions.PLANE
    assert await store.read(row.props.extract()) == {
        "system": True,
        "ui": False,
        "made_by": "",
        "backend": "async",
    }
    assert await store.read(ops.cells(reactions.PLANE)) == []


async def test_enable_writes_the_change_as_source_and_is_idempotent(store):
    await store.run(ensure_system() >> ops.add_plane("chat"))
    cid = await store.run(enable_react(on("chat"), "chat"))
    assert cid.startswith("react_")
    assert await store.run(enable_react(on("chat"), "chat")) == cid
    assert await store.read(ops.cells(reactions.PLANE)) == [cid]
    source = await store.read(ops.prog(reactions.PLANE, cid))
    assert "PLANE = 'chat'" in source
    assert on("chat") in source
    assert "up_plane(PLANE)" in source
    assert list((await store.read(index())).values()) == [cid]
    assert await store.read(reactions.reaction_of(on("chat"), "chat")) == cid
    # No kernel here: the run it asked for is written, by react.
    rid = await store.read(reactions.live_run())
    assert (await store.read(ops.run(rid)))["by"] == reactions.BY


@pytest.mark.parametrize(
    ("change", "imports"),
    [
        ('States.planes["chat"].state["count"].on_change(', ""),
        (on("chat"), "import no_such_module"),
        ("undefined_name.on_change()", ""),
    ],
)
async def test_enable_refuses_source_that_does_not_load(store, change, imports):
    await store.run(ensure_system() >> ops.add_plane("chat"))
    with pytest.raises(ConstructionError) as err:
        await store.run(enable_react(change, "chat", imports=imports))
    assert err.value.diagnostic is not None
    assert await store.read(ops.cells(reactions.PLANE)) == []
    assert await store.read(index()) == {}
    assert await store.read(reactions.live_run()) == ""


async def test_enable_takes_imports(store):
    await store.run(ensure_system() >> ops.add_plane("chat"))
    cid = await store.run(enable_react(on("chat"), "chat", imports="import json"))
    assert "\nimport json\n" in await store.read(ops.prog(reactions.PLANE, cid))


async def test_disable_removes_the_reaction_and_its_key(store):
    await store.run(ensure_system() >> ops.add_plane("chat"))
    cid = await store.run(enable_react(on("chat"), "chat"))
    other = await store.run(enable_react(on("chat", "other"), "chat"))
    await store.run(disable_react(on("chat"), "chat") >> disable_react(on("chat"), "chat"))
    assert await store.read(ops.cells(reactions.PLANE)) == [other]
    assert list((await store.read(index())).values()) == [other]
    assert await store.read(reactions.reaction_of(on("chat"), "chat")) == ""
    again = await store.run(enable_react(on("chat"), "chat"))
    assert again not in ("", cid)


# --- The space ------------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("reactions") / "space")
    await nu.arun(nu.With(store(path), body=ensure_system()))
    k = await opened(NAME, path=path, spares=2, init=init.PLANE)
    yield k
    await k.close()


def mine(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["by"] == reactions.BY]


async def fired(space: Kernel, plane: str, pred, timeout: float = SLOW) -> list[dict]:
    """The plane's runs by reactions, oldest first, read until ``pred`` holds on them."""
    return mine(await space.until(history(plane), lambda rs: pred(mine(rs)), timeout))


def _cell(row: dict, cell: str) -> dict:
    found = [c for c in row.get("cells", []) if c["cell"] == cell]
    return found[-1] if found else {}


async def reacting(space: Kernel, change: str, plane: str) -> str:
    """Enable a reaction, wait for its cell run to be live, and for its first fire to end."""
    before = len(mine(await space.read(history(plane))))
    cid = await space.run(enable_react(change, plane))
    rid = await space.until(reactions.live_run(), bool, SLOW)
    await space.run_row(rid, lambda r: live(_cell(r, cid)), SLOW)
    await fired(space, plane, lambda rs: len(rs) > before and all(ended(r) for r in rs))
    return cid


def all_ended(rows: list[dict]) -> bool:
    return all(ended(r) for r in rows)


@module_loop
async def test_the_plane_boots_with_no_cells_and_comes_up_on_enable(space):
    assert reactions.PLANE in BOOTED
    (row,) = await space.until(history(reactions.PLANE), lambda rs: rs and ended(rs[0]), SLOW)
    assert (row["by"], row["exit"], row["cells"]) == (init.BY, EXIT_OK, [])
    assert await space.read(reactions.live_run()) == ""
    p, _ = await space.plane(WORKS)
    await reacting(space, on(p), p)
    rid = await space.read(reactions.live_run())
    assert (await space.read(ops.run(rid)))["by"] == reactions.BY


@module_loop
async def test_a_change_runs_the_plane_once(space):
    p, (c,) = await space.plane(WORKS)
    await reacting(space, on(p), p)
    (first,) = mine(await space.read(history(p)))
    await asyncio.sleep(1.0)
    assert len(await space.read(history(p))) == 1
    await space.run(bump(p, 1))
    rows = await fired(space, p, lambda rs: len(rs) == 2 and all_ended(rs))
    assert rows[1]["exit"] == EXIT_OK
    assert rows[0]["id"] == first["id"]
    assert (await space.read(States.planes[p].cells[c].extract()))["n"] == 1
    await asyncio.sleep(1.5)
    assert len(await space.read(history(p))) == 2


def no_overlap(rows: list[dict]) -> bool:
    spans = sorted((r["started_at"], r["terminated_at"]) for r in rows)
    return all(a[1] <= b[0] for a, b in itertools.pairwise(spans))


@module_loop
@pytest.mark.parametrize("changes", [1, 12])
async def test_changes_during_a_live_run_fire_after_it(space, changes):
    """Changes landing mid run: at least one run follows it, never two at once.

    Notifications queued while a reaction waits may give a few serial runs:
    accepted, so the count is not pinned.
    """
    p, _ = await space.plane(WORKS)
    await reacting(space, on(p), p)
    await space.run(bump(p, 1))
    (_, mid) = await fired(space, p, lambda rs: len(rs) == 2 and rs[1]["started_at"])
    for n in range(changes):
        await space.run(bump(p, 100 + n))
        await asyncio.sleep(0.02)
    rows = await fired(space, p, lambda rs: len(rs) >= 3 and all_ended(rs))
    await asyncio.sleep(2.0)
    rows = mine(await space.read(history(p)))
    assert all_ended(rows)
    assert no_overlap(rows), rows
    (ended_mid,) = [r for r in rows if r["id"] == mid["id"]]
    after = [r for r in rows if r["started_at"] >= ended_mid["terminated_at"]]
    assert after
    assert len(rows) <= 3 + changes


@module_loop
async def test_never_two_runs_at_once(space):
    """Two reactions on one plane, changes landing on both, runs never overlap."""
    p, _ = await space.plane(WORKS)
    await reacting(space, on(p), p)
    await reacting(space, on(p, "other"), p)
    for n in range(1, 7):
        await space.run(bump(p, n) >> bump(p, n, "other"))
        await asyncio.sleep(0.3)
    await fired(space, p, lambda rs: len(rs) >= 4 and all_ended(rs))
    await asyncio.sleep(2.5)
    rows = await space.read(history(p))
    assert all(r["by"] == reactions.BY for r in rows)
    assert all_ended(rows)
    assert no_overlap(rows), rows


@module_loop
async def test_a_cell_state_change_fires(space):
    q, (c,) = await space.plane(prog("return Tick.n.set(0)"))
    p, _ = await space.plane(WORKS)
    await reacting(space, f'States.planes["{q}"].cells.on_descendants_change("{c}", "n")', p)
    await space.run(atomic_state(ops.cell_state(q, c, Tick.n.set(5))))
    await fired(space, p, lambda rs: len(rs) == 2 and all_ended(rs))


@module_loop
async def test_disable_stops_the_fires_and_removes_the_cell(space):
    p, _ = await space.plane(WORKS)
    cid = await reacting(space, on(p), p)
    rid = await space.read(reactions.live_run())
    await space.run(disable_react(on(p), p))
    assert cid not in await space.read(ops.cells(reactions.PLANE))
    assert await space.read(reactions.reaction_of(on(p), p)) == ""
    row = await space.run_row(rid, lambda r: ended(_cell(r, cid)), SLOW)
    assert _cell(row, cid)["exit"] == EXIT_INTERRUPTED
    await space.run(bump(p, 2))
    await asyncio.sleep(2.0)
    assert len(await space.read(history(p))) == 1


async def test_a_change_while_the_space_was_closed_fires_at_the_next_open(tmp_path):
    """Each reaction fires as it starts: what landed between two opens is handled."""
    path = str(tmp_path / "space")
    seed = ensure_system() >> ops.add_plane("chat", ui=True) >> ops.add_cell("chat", WORKS)
    await nu.arun(nu.With(store(path), body=seed))
    k = await opened(f"{NAME}-reopen", path=path, spares=1, init=init.PLANE)
    try:
        await reacting(k, on("chat"), "chat")
    finally:
        await k.close()
    await nu.arun(nu.With(store(path), body=bump("chat", 1)))
    k = await opened(f"{NAME}-reopen", path=path, spares=1, init=init.PLANE)
    try:
        rows = await fired(k, "chat", lambda rs: len(rs) == 2 and all_ended(rs))
        assert rows[1]["exit"] == EXIT_OK
        # The reactions plane came back at boot, by init, with the reaction in it.
        row = await k.run_row(await k.until(reactions.live_run(), bool, SLOW), bool)
        assert row["by"] == init.BY
    finally:
        await k.close()
