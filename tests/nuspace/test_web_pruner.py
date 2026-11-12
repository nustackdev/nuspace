"""The desk pruner: removed planes come off every desk, desks stay, a bulk removal is one pass.

The pass runs here as the pruner cell's run would, straight against the
store. The reaction wiring, with a real host and no browser, is at the end.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import time
from typing import TYPE_CHECKING

import pytest

import nu
import nuspace
import nuspace.web as web
from nu.lang import ScalarQuery
from nuspace import host, system
from nuspace.errors import Refused
from nuspace.shapes import Space
from nuspace.system import reactions
from nuspace.web.desks import pruner
from nuspace.web.desks.model import item_problem, items_of
from nuspace.web.planes import ensure, ensure_pruner


if TYPE_CHECKING:
    from collections.abc import Callable


STORES = ("memory", "sqlite")

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 60.0


async def do(store, term):
    return await store.run(nuspace.atomic(term))


def link(plane: str, **params: str) -> dict:
    return {"plane": plane, "params": params}


def _recent(held: dict, recent: str | None) -> dict:
    return held if recent is None else {**held, "recent": link(recent)}


def item(plane: str, item_id: str, recent: str | None = None) -> dict:
    """A plane item."""
    return _recent({"id": item_id, "kind": "plane", "original": link(plane)}, recent)


def pane(plane: str, share: float = 1, recent: str | None = None) -> dict:
    return _recent({"share": share, "original": link(plane)}, recent)


def strip(item_id: str, *columns: list[dict]) -> dict:
    width = 600
    return {
        "id": item_id,
        "kind": "strip",
        "columns": [{"width": width, "panes": list(c)} for c in columns],
    }


def desk(*items: dict, name: str = "Desk") -> dict:
    return {"name": name, "items": list(items)}


def shown(held: dict) -> list:
    """A desk's items as plane ids: a plane item its original, a strip its columns' originals."""
    out = []
    for i in held["items"]:
        if i["kind"] == "plane":
            out.append(i["original"]["plane"])
        else:
            out.append([[p["original"]["plane"] for p in c["panes"]] for c in i["columns"]])
    return out


async def planes(store, *ids: str, parent: str | None = None) -> None:
    for p in ids:
        kwargs = {"parent": parent} if parent else {}
        await do(store, nuspace.plane.add(p, backend="async", **kwargs))


def made(desk_id: str, held: dict) -> nu.Nu:
    """A desk stored as the browser's create would: the desk, then its items."""
    return web.desks.create_desk(held["name"], id=desk_id) >> web.desks.write_items(
        desk_id, items_of(held["items"])
    )


def _read_desks() -> nu.Nu:
    from nuspace.web.desks.model import DesksView

    return DesksView(web.Web.desks.extract())


def stored(held: dict) -> dict:
    """A desk as it is stored: its name and its entries, no ids in them."""
    entries = {i["id"]: {k: v for k, v in i.items() if k != "id"} for i in held["items"]}
    return {"name": held["name"], "entries": entries}


async def desks(store) -> dict:
    return await store.read(_read_desks()) or {}


async def prune(store) -> None:
    await store.run(pruner.catch_up())


# --- The pass -------------------------------------------------------------------------------


async def test_a_removed_plane_comes_off_both_desks_it_sits_on_and_both_desks_stay(store):
    await planes(store, "x", "b", "c", "e", "d", "r")
    await planes(store, "y", parent="x")
    # All x: left empty, and kept.
    await do(store, made("deska001", desk(item("x", "aaaaaa"), item("y", "bbbbbb"))))
    two = desk(
        # Navigated to x: the recent drops, it shows b again.
        item("b", "cccccc", recent="x"),
        # Navigated away from x: it goes all the same, its original is x.
        item("x", "dddddd", recent="r"),
        # Its x column empties and goes; y leaves c and e, scaled back to sum 1.
        strip("eeeeee", [pane("x")], [pane("y", 0.2), pane("c", 0.3), pane("e", 0.5)], [pane("d")]),
        # Down to one pane, which keeps its recent: a plane item in its place, its id kept.
        strip("ffffff", [pane("x")], [pane("d", recent="r")]),
        # A pane navigated to x falls back to its original.
        strip("gggggg", [pane("c", recent="y")], [pane("e")]),
        # Every pane gone: the strip goes.
        strip("hhhhhh", [pane("x", 0.5), pane("y", 0.5)]),
    )
    await do(store, made("deskb002", two))
    # No removed plane on it: never written.
    untouched = desk(item("c", "iiiiii"), strip("jjjjjj", [pane("c")], [pane("d")]))
    await do(store, made("deskc003", untouched))

    await do(store, nuspace.plane.remove("x"))  # y is below x: removed with it
    assert await store.read(pruner.pending()) is True
    await prune(store)

    held = await desks(store)
    assert set(held) == {"deska001", "deskb002", "deskc003"}
    assert held["deska001"] == desk()
    assert held["deskc003"] == untouched
    items = held["deskb002"]["items"]
    assert items[0] == item("b", "cccccc")
    assert shown(held["deskb002"]) == ["b", [["c", "e"], ["d"]], "d", [["c"], ["e"]]]
    kept = items[1]["columns"]
    assert [c["width"] for c in kept] == [c["width"] for c in two["items"][2]["columns"][1:]]
    assert [p["share"] for p in kept[0]["panes"]] == pytest.approx([0.375, 0.625])
    assert items[2] == item("d", "ffffff", recent="r")
    assert items[3] == strip("gggggg", [pane("c")], [pane("e")])
    assert all(
        item_problem({k: v for k, v in i.items() if k != "id"}) == ""
        for d in held.values()
        for i in d["items"]
    )
    assert await store.read(pruner.pending()) is False


async def test_a_bulk_removal_is_one_pass(store):
    await planes(store, "p1", "p2", "p3", "p4", "p5")
    await do(store, made("deska001", desk(item("p1", "aaaaaa"), item("p4", "bbbbbb"))))
    bulk = desk(strip("cccccc", [pane("p2", 0.5), pane("p5", 0.5)], [pane("p3")], [pane("p4")]))
    await do(store, made("deskb002", bulk))
    for p in ("p1", "p2", "p3"):
        await do(store, nuspace.plane.remove(p))
    await do(store, pruner.step())
    held = await desks(store)
    assert shown(held["deska001"]) == ["p4"]
    assert shown(held["deskb002"]) == [[["p5"], ["p4"]]]
    assert held["deskb002"]["items"][0]["columns"][0]["panes"][0]["share"] == pytest.approx(1)
    assert await store.read(pruner.pending()) is False


async def test_a_system_plane_is_never_pruned(store):
    await store.run(ensure())
    home = await store.read(web.Web.roles["home"])
    await planes(store, "b")
    kept = desk(item(home, "aaaaaa"), strip("bbbbbb", [pane("b")], [pane("ghost")]))
    await do(store, made("deska001", kept))
    with pytest.raises(Refused, match="system plane"):
        await do(store, nuspace.plane.remove(home))
    assert await store.read(pruner.pending()) is False
    await prune(store)
    # A plane id with no row is left too: only a removed plane is pruned.
    assert (await desks(store))["deska001"] == kept


async def test_an_item_off_the_shape_is_left_as_it_is(store):
    await planes(store, "a", "b")
    await do(store, made("deska001", desk(item("b", "aaaaaa"))))
    old = {"kind": "plane", "plane": "a"}
    await do(store, web.Web.desks["deska001"].entries.set_item("bbbbbb", old))
    await do(store, nuspace.plane.remove("a"))
    assert await store.read(pruner.pending()) is False
    await prune(store)
    assert await store.read(web.Web.desks["deska001"].entries["bbbbbb"].extract()) == old


async def test_nothing_to_prune_writes_nothing(store):
    await planes(store, "a", "b")
    await do(store, made("deska001", desk(item("a", "aaaaaa"), item("b", "bbbbbb"))))
    assert await store.read(pruner.pending()) is False
    await prune(store)
    assert set(await desks(store)) == {"deska001"}


def test_the_plan_is_plain_python():
    two = stored(desk(strip("aaaaaa", [pane("a", 0.25), pane("b", 0.75)], [pane("c")])))

    def change(*sets: dict, deletes: tuple = ()) -> dict:
        written = {i["id"]: {k: v for k, v in i.items() if k != "id"} for i in sets}
        return {"sets": written, "deletes": list(deletes)}

    assert pruner.plan({"d1": two}, ["b"]) == {
        "d1": change(strip("aaaaaa", [pane("a", 1.0)], [pane("c")])),
    }
    assert pruner.plan({"d1": two}, ["a", "b"]) == {"d1": change(item("c", "aaaaaa"))}
    assert pruner.plan({"d1": two}, ["a", "b", "c"]) == {"d1": change(deletes=("aaaaaa",))}
    assert pruner.plan({"d1": two}, []) == {}
    navigated = stored(desk(item("a", "bbbbbb", recent="z"), item("c", "cccccc")))
    assert pruner.plan({"d1": navigated}, ["z"]) == {"d1": change(item("a", "bbbbbb"))}
    # Panes falling back to their original can show one plane twice: the later one goes.
    back = stored(
        desk(strip("aaaaaa", [pane("a", recent="r")], [pane("b")], [pane("a", recent="s")]))
    )
    assert pruner.plan({"d1": back}, ["s"]) == {
        "d1": change(strip("aaaaaa", [pane("a", recent="r")], [pane("b")], [pane("a")])),
    }
    assert pruner.plan({"d1": back}, ["r", "s"]) == {
        "d1": change(strip("aaaaaa", [pane("a")], [pane("b")])),
    }
    # Off the shape: never written, never deleted.
    off = {"name": "x", "entries": {"aaaaaa": {"kind": "plane", "plane": "a"}}}
    assert pruner.plan({"d1": off}, ["a"]) == {}


# --- Made at open ---------------------------------------------------------------------------


async def test_ensure_makes_the_pruner_off_the_web_with_one_reaction_once(store):
    await store.run(system.ensure() >> ensure())
    row = await store.read(Space.planes[pruner.PLANE].extract())
    assert row["system"] is True and row["backend"] == pruner.BACKEND
    assert await store.read(web.Web.planes.contains(pruner.PLANE)) is False
    with pytest.raises(Refused):
        await do(store, nuspace.plane.remove(pruner.PLANE))
    kept = await store.read(pruner.pruner().reaction)
    listed = reactions.registry().by_plane[pruner.PLANE].ids
    assert await store.read(nu.list(listed.keys())) == [kept]
    await store.run(ensure_pruner())
    assert await store.read(pruner.pruner().reaction) == kept
    assert len(await store.read(nu.list(listed.keys()))) == 1


async def test_ensure_without_a_reactions_plane_adds_no_reaction(store):
    await store.run(ensure())
    assert await store.read(Space.planes.contains(pruner.PLANE)) is True
    assert await store.read(pruner.pruner().reaction.exists()) is False


def test_a_user_plane_cannot_take_the_pruner_id():
    with pytest.raises(Refused, match="reserved"):
        nuspace.plane.add(pruner.PLANE)


def test_the_cell_builds_and_validates():
    namespace: dict = {}
    exec(compile(pruner.PROG, "cell", "exec"), namespace)  # noqa: S102
    nu.validate(nu.compile(namespace["out"]()))


# --- The reaction, in a served space with no browser -----------------------------------------


class _Hold(ScalarQuery):
    """Hands the host's context to the test, then waits for ``done``."""

    def __init__(self, opened: asyncio.Future, done: asyncio.Event) -> None:
        super().__init__()
        self._payload = {"opened": opened, "done": done}

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        opened, done = self._payload["opened"], self._payload["done"]

        async def athunk(rt: object) -> object:
            opened.set_result(rt.ctx)
            await done.wait()

        return athunk


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _listed(ids) -> nu.Nu:
    return nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([]))


class Served:
    """A space served with the web device and no tab: ops and reads against its stores."""

    def __init__(self, ctx: nu.Context) -> None:
        self.ctx = ctx

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(nuspace.atomic(term))

    async def do(self, term: nu.Nu) -> object:
        return await self.run(nuspace.atomic(term))

    async def until(self, read, pred, timeout: float = SLOW) -> object:
        deadline = time.monotonic() + timeout
        while True:
            value = await read()
            if pred(value):
                return value
            assert time.monotonic() < deadline, f"timed out, last read: {value!r}"
            await asyncio.sleep(0.05)

    async def runs(self) -> list:
        """The pruner's plane runs, in start order."""
        ids = Space.exec.indexes.history.plane_to_plane_runs[pruner.PLANE].runs
        return await self.read(_listed(ids))

    async def live_runs(self) -> list:
        ids = Space.exec.indexes.live.plane_to_plane_runs[pruner.PLANE].ids
        return await self.read(_listed(ids))

    async def desks(self) -> dict:
        return await self.read(_read_desks()) or {}


async def test_a_removal_prunes_with_no_browser_and_a_bulk_removal_is_one_run(tmp_path):
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    hold = nu.let(_Hold(ready, done), lambda _: nu.Noop())
    term = host.open_space(
        tmp_path / "space",
        open_browser=False,
        static=None,
        port=_free_port(),
        extensions=(),
        spares=0,
        body=hold,
    )
    task = asyncio.create_task(nu.arun(term))
    try:
        waiting = asyncio.ensure_future(asyncio.shield(ready))
        finished, _ = await asyncio.wait(
            {waiting, task}, timeout=SLOW, return_when="FIRST_COMPLETED"
        )
        if task in finished:
            task.result()
        s = Served(await waiting)
        for p in ("p1", "p2", "p3", "p4", "p5"):
            await s.do(nuspace.plane.add(p, backend="async"))

        # The run the open asks for (wake) ends first, so a prune past here is the reaction's.
        await s.until(s.runs, lambda r: len(r) >= 1)
        await s.until(s.live_runs, lambda r: r == [])
        # A reaction is live a moment before its flow listens: remove until one gets through.
        deadline = time.monotonic() + SLOW
        for i in range(1000):
            probe, mine = f"probe{i}", f"probe{i:03d}"
            await s.do(nuspace.plane.add(probe, backend="async"))
            await s.do(made(mine, desk(item(probe, "aaaaaa"), item("p5", "bbbbbb"))))
            await s.do(nuspace.plane.remove(probe))
            with contextlib.suppress(AssertionError):
                await s.until(s.desks, lambda d, m=mine: shown(d[m]) == ["p5"], 3.0)
                break
            assert time.monotonic() < deadline, "the pruner never woke"
        await s.until(s.live_runs, lambda r: r == [])
        before = len(await s.runs())

        await s.do(made("deska001", desk(item("p1", "aaaaaa"), item("p4", "bbbbbb"))))
        bulk = desk(strip("cccccc", [pane("p2", 0.5), pane("p5", 0.5)], [pane("p3")], [pane("p4")]))
        await s.do(made("deskb002", bulk))
        for p in ("p1", "p2", "p3"):
            await s.do(nuspace.plane.remove(p))
        held = await s.until(s.desks, lambda d: shown(d["deska001"]) == ["p4"])
        assert shown(held["deskb002"]) == [[["p5"], ["p4"]]]
        await asyncio.sleep(pruner.SETTLE + 1.0)
        await s.until(s.live_runs, lambda r: r == [])
        assert len(await s.runs()) == before + 1
    finally:
        done.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, 15)
