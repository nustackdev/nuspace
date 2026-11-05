"""reactions: the ops against a bare store, then reactions firing planes on real workers.

The ops run against the in memory store: the reaction cell, its source, its
key. The space is one for the module, bootstrapped the way a host opens one,
so init brings the reactions plane up at boot, with no cells. Every test
makes its own target plane and watches its own state, and polls the store
until the reactions have acted.

A reaction is an event flow: it runs its plane once per change notified,
never on enable, with no re-checks. A burst of changes merges in
:func:`reactions.up_plane`.
"""

from __future__ import annotations

import asyncio
import itertools
import time

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


async def enabled(store, change: str, plane: str, **kwargs: str) -> str:
    """Enable a reaction through ``store``, and its cell: :func:`reactions.reaction_of` them."""
    await store.run(enable_react(change, plane, **kwargs))
    return await store.read(reactions.reaction_of(change, plane))


NAME = "nuspace-reactions"

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 20.0

#: A target that runs to completion, long enough to land changes while it runs.
WORKS = prog("return nu.Delay(1.0) >> ops.atomic_state(Tick.n.set(1))")


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
    await store.run(ensure_system() >> ops.add_plane("chat", backend="async"))
    cid = await enabled(store, on("chat"), "chat")
    assert cid.startswith("react_")
    assert await enabled(store, on("chat"), "chat") == cid
    assert await store.read(ops.cells(reactions.PLANE)) == [cid]
    source = await store.read(ops.prog(cid))
    assert "PLANE = 'chat'" in source
    assert on("chat") in source
    assert "up_plane(PLANE)" in source
    # An event flow, every fire under the services policy.
    assert "nu.ReactLatest(" in source
    assert "restarting(" in source
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
    await store.run(ensure_system() >> ops.add_plane("chat", backend="async"))
    with pytest.raises(ConstructionError) as err:
        await store.run(enable_react(change, "chat", imports=imports))
    assert err.value.diagnostic is not None
    assert await store.read(ops.cells(reactions.PLANE)) == []
    assert await store.read(index()) == {}
    assert await store.read(reactions.live_run()) == ""


async def test_enable_takes_imports(store):
    await store.run(ensure_system() >> ops.add_plane("chat", backend="async"))
    cid = await enabled(store, on("chat"), "chat", imports="import json")
    assert "\nimport json\n" in await store.read(ops.prog(cid))


async def test_disable_removes_the_reaction_and_its_key(store):
    await store.run(ensure_system() >> ops.add_plane("chat", backend="async"))
    cid = await enabled(store, on("chat"), "chat")
    other = await enabled(store, on("chat", "other"), "chat")
    await store.run(disable_react(on("chat"), "chat") >> disable_react(on("chat"), "chat"))
    assert await store.read(ops.cells(reactions.PLANE)) == [other]
    assert list((await store.read(index())).values()) == [other]
    assert await store.read(reactions.reaction_of(on("chat"), "chat")) == ""
    again = await enabled(store, on("chat"), "chat")
    assert again not in ("", cid)


# --- The space ------------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("reactions") / "space")
    await nu.arun(nu.With(store(path), body=ops.init_stores() >> ensure_system()))
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


def all_ended(rows: list[dict]) -> bool:
    return all(ended(r) for r in rows)


async def settled(space: Kernel, plane: str, quiet: float = 1.5) -> list[dict]:
    """The plane's runs by reactions once they settle: all ended, none new for ``quiet`` seconds."""
    deadline = time.monotonic() + SLOW
    rows = mine(await space.read(history(plane)))
    while True:
        await asyncio.sleep(quiet)
        now = mine(await space.read(history(plane)))
        if len(now) == len(rows) and all_ended(now):
            return now
        if time.monotonic() > deadline:
            msg = f"reaction runs never settled: {now!r}"
            raise AssertionError(msg)
        rows = now


async def reacting(space: Kernel, change: str, plane: str) -> str:
    """Enable a reaction and wait for its cell run to be live, its subscription bound."""
    cid = await enabled(space, change, plane)
    rid = await space.until(reactions.live_run(), bool, SLOW)
    await space.run_row(rid, lambda r: live(_cell(r, cid)), SLOW)
    # The cell run is live a moment before its subscription binds.
    await asyncio.sleep(0.3)
    return cid


@module_loop
async def test_the_plane_boots_with_no_cells_and_comes_up_on_enable(space):
    """init runs the plane at boot, and the run ends at once: no cells.

    Unless a test before this one enabled a reaction before init reached the
    plane: then it was up already, and init left it alone.
    """
    assert reactions.PLANE in BOOTED

    def booted(rows: list[dict]) -> bool:
        by_init = [r for r in rows if r["by"] == init.BY]
        return any(ended(r) for r in by_init) or (not by_init and bool(mine(rows)))

    rows = await space.until(history(reactions.PLANE), booted, SLOW)
    for row in rows:
        if row["by"] == init.BY:
            assert (row["exit"], row["cells"]) == (EXIT_OK, [])
    if not mine(rows):
        assert await space.read(reactions.live_run()) == ""
    p, _ = await space.plane(WORKS)
    await reacting(space, on(p), p)
    rid = await space.read(reactions.live_run())
    assert (await space.read(ops.run(rid)))["by"] == reactions.BY


@module_loop
async def test_enabling_does_not_run_the_plane(space):
    p, _ = await space.plane(WORKS)
    await reacting(space, on(p), p)
    await asyncio.sleep(1.5)
    assert await space.read(history(p)) == []


@module_loop
async def test_a_change_runs_the_plane_once(space):
    p, (c,) = await space.plane(WORKS)
    await reacting(space, on(p), p)
    await space.run(bump(p, 1))
    rows = await fired(space, p, lambda rs: len(rs) == 1 and all_ended(rs))
    assert rows[0]["exit"] == EXIT_OK
    assert (await space.read(States.cells[c].extract()))["n"] == 1
    await asyncio.sleep(2.0)
    assert len(await space.read(history(p))) == 1


@module_loop
async def test_a_burst_merges(space):
    """A burst of changes while idle: one run for the first, at most one after it."""
    p, _ = await space.plane(WORKS)
    await reacting(space, on(p), p)
    for n in range(1, 13):
        await space.run(bump(p, n))
    rows = await fired(space, p, lambda rs: len(rs) >= 1 and all_ended(rs))
    rows = await settled(space, p)
    assert 1 <= len(rows) <= 2, rows
    assert no_overlap(rows), rows


def no_overlap(rows: list[dict]) -> bool:
    spans = sorted((r["started_at"], r["terminated_at"]) for r in rows)
    return all(a[1] <= b[0] for a, b in itertools.pairwise(spans))


@module_loop
@pytest.mark.parametrize("changes", [1, 12])
async def test_changes_during_a_live_run_fire_after_it(space, changes):
    """Changes landing mid run: one run follows it, never two at once."""
    p, _ = await space.plane(WORKS)
    await reacting(space, on(p), p)
    base = len(mine(await space.read(history(p))))
    await space.run(bump(p, 1))
    rows = await fired(space, p, lambda rs: len(rs) == base + 1 and rs[-1]["started_at"])
    mid = rows[-1]
    for n in range(changes):
        await space.run(bump(p, 100 + n))
        await asyncio.sleep(0.02)
    rows = await fired(space, p, lambda rs: len(rs) >= base + 2 and all_ended(rs))
    await asyncio.sleep(2.0)
    rows = mine(await space.read(history(p)))
    assert all_ended(rows)
    assert no_overlap(rows), rows
    (ended_mid,) = [r for r in rows if r["id"] == mid["id"]]
    after = [r for r in rows if r["started_at"] >= ended_mid["terminated_at"]]
    assert len(after) == 1, rows
    assert len(rows) == base + 2


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
    _, (c,) = await space.plane(prog("return ops.atomic_state(Tick.n.set(0))"))
    p, _ = await space.plane(WORKS)
    await reacting(space, f'States.cells.on_descendants_change("{c}", "n")', p)
    base = len(mine(await space.read(history(p))))
    at = time.time()
    await space.run(atomic_state(ops.cell_state(c, Tick.n.set(5))))
    # At least one run after the write: a late start up fire or a split
    # notification may add one, which the contract makes harmless.
    rows = await fired(space, p, lambda rs: len(rs) > base and all_ended(rs))
    assert rows[-1]["started_at"] >= at
    assert rows[-1]["exit"] == EXIT_OK


@module_loop
async def test_disable_stops_the_fires_and_removes_the_cell(space):
    p, _ = await space.plane(WORKS)
    cid = await reacting(space, on(p), p)
    base = len(await space.read(history(p)))
    rid = await space.read(reactions.live_run())
    await space.run(disable_react(on(p), p))
    assert cid not in await space.read(ops.cells(reactions.PLANE))
    assert await space.read(reactions.reaction_of(on(p), p)) == ""
    row = await space.run_row(rid, lambda r: ended(_cell(r, cid)), SLOW)
    assert _cell(row, cid)["exit"] == EXIT_INTERRUPTED
    await space.run(bump(p, 2))
    await asyncio.sleep(2.0)
    assert len(await space.read(history(p))) == base


async def test_a_reaction_comes_back_at_the_next_open(tmp_path):
    """A reaction outlives its open: init runs it at boot, and the next change fires.

    A change made while the space was closed is not one: event flows are best
    effort, and no run comes of it.
    """
    path = str(tmp_path / "space")
    seed = (
        ops.init_stores()
        >> ensure_system()
        >> ops.add_plane("chat", ui=True, backend="async")
        >> ops.add_cell("chat", WORKS)
    )
    await nu.arun(nu.With(store(path), body=seed))
    k = await opened(f"{NAME}-reopen", path=path, spares=1, init=init.PLANE)
    try:
        cid = await reacting(k, on("chat"), "chat")
    finally:
        await k.close()
    await nu.arun(nu.With(store(path), body=bump("chat", 1)))
    k = await opened(f"{NAME}-reopen", path=path, spares=1, init=init.PLANE)
    try:
        # The reactions plane came back at boot, by init, with the reaction in it.
        rid = await k.until(reactions.live_run(), bool, SLOW)
        row = await k.run_row(rid, lambda r: live(_cell(r, cid)), SLOW)
        assert row["by"] == init.BY
        await asyncio.sleep(0.3)
        assert mine(await k.read(history("chat"))) == []
        await k.run(bump("chat", 2))
        rows = await fired(k, "chat", lambda rs: len(rs) == 1 and all_ended(rs))
        assert rows[0]["exit"] == EXIT_OK
    finally:
        await k.close()
