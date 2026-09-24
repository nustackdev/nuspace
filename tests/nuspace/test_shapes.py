"""Layer zero: program declared state lands under its cell and plane.

The spike first: a ``CellState`` and a ``PlaneState`` shape, rerooted, read
and written through the real kv stack and watched through it. Then what the
rerooter must leave alone, and the class form surviving a pickle, since that
is how it reaches a worker.
"""

from __future__ import annotations

import pickle

import pytest

import nu
import nustd.kv
import nustd.ui
from nu.core.flows.react import React
from nuspace.shapes import (
    ROOT,
    STATUSES,
    CellState,
    PlaneState,
    Reroot,
    Space,
    reroot,
)


class Tick(CellState):
    n = nustd.kv.IntRef.slot()


class Note(nu.Shape):
    text = nustd.kv.StrRef.slot()


class Draft(CellState):
    note = nustd.kv.ShapeRef.slot(Note)
    tags = nustd.kv.ListRef.slot(str)


class Chat(PlaneState):
    title = nustd.kv.StrRef.slot()


class Movies(nu.Shape):
    """Another store, tagged apart from Space. Must never be rerooted."""

    count = nustd.kv.IntRef.slot()


class Page(nu.Shape):
    inp = nustd.ui.InputRef.slot()


def cell_state(plane: str, cell: str) -> nustd.kv.DictRef:
    return Space.planes[plane].cells[cell].state


def bump() -> nu.Nu:
    return nu.IfDo(Tick.n.missing(), Tick.n.set(0)) >> Tick.n.set(Tick.n + 1)


def _store(tmp_path):
    """A Space on disk, and the two calls that write it and read it back."""
    path = str(tmp_path / "space")

    async def write(term):
        await nu.arun(
            nu.With(
                nustd.kv.rocksdb_navigator(path, tags=(Space,)),
                body=nustd.kv.auto_flow_atomic(term, scope=Space),
            )
        )

    async def read(term):
        value, _ = await nu.arun(
            nu.With(
                nustd.kv.rocksdb_navigator(path, tags=(Space,)),
                body=nustd.kv.Snapshot(term, scope=Space),
            )
        )
        return value

    return write, read


# --- the spike ---------------------------------------------------------------


async def test_cell_state_persists_under_the_cell(tmp_path):
    write, read = _store(tmp_path)
    await write(reroot(bump() >> bump(), "p", "c"))
    await write(reroot(bump(), "p", "c"))
    assert await read(cell_state("p", "c")["n"]) == 3
    assert await read(reroot(Tick.n, "p", "c")) == 3


async def test_cells_do_not_share_cell_state(tmp_path):
    write, read = _store(tmp_path)
    await write(reroot(bump(), "p", "a") >> reroot(bump() >> bump(), "p", "b"))
    assert await read(nu.List.of(cell_state("p", "a")["n"], cell_state("p", "b")["n"])) == [1, 2]


async def test_nested_slots_resolve_under_cell_state(tmp_path):
    write, read = _store(tmp_path)
    await write(reroot(Draft.note.text.set("hi") >> Draft.tags.append("x"), "p", "c"))
    got = reroot(nu.List.of(Draft.note.text, nu.list(Draft.tags)), "p", "c")
    assert await read(got) == ["hi", ["x"]]


async def test_plane_state_is_shared_by_the_planes_cells(tmp_path):
    write, read = _store(tmp_path)
    await write(reroot(Chat.title.set("ideas"), "p", "a"))
    assert await read(reroot(Chat.title, "p", "b")) == "ideas"
    assert await read(Space.planes["p"].state["title"]) == "ideas"


def watched(watch: nu.Nu, change: nu.Nu, plane: str = "p", cell: str = "c") -> nu.Nu:
    """``watch`` and a later ``change`` racing on one store, bounded.

    Both rerooted under ``plane``. The change waits a beat so the watch has
    subscribed first; the timeout turns a watch that never fires into a
    failed read rather than a hung test.
    """
    return nu.Timeout(
        2.0,
        nu.Gather(
            reroot(watch, plane, cell),
            nu.Delay(0.05) >> reroot(change, plane, cell),
        ),
    )


async def test_on_change_fires_on_a_rerooted_cell_ref(tmp_path):
    write, read = _store(tmp_path)
    seen = Space.planes["p"].name
    await write(watched(React(Tick.n.on_change(), seen.set("fired")), bump()))
    assert await read(nu.List.of(seen, cell_state("p", "c")["n"])) == ["fired", 1]


async def test_on_change_fires_on_a_rerooted_plane_ref(tmp_path):
    write, read = _store(tmp_path)
    seen = Space.planes["p"].name
    await write(watched(React(Chat.title.on_change(), seen.set(Chat.title)), Chat.title.set("t")))
    assert await read(seen) == "t"


@pytest.mark.parametrize(("target", "expected"), [("d", "quiet"), ("c", "wrong")])
async def test_a_cell_does_not_hear_its_siblings_cell_state(tmp_path, target, expected):
    """Cell ``c`` listens while ``target`` bumps; only its own bump is heard.

    The ``c`` case is the control: it proves the listener would have fired.
    """
    write, read = _store(tmp_path)
    seen = Space.planes["p"].name
    heard = React(Tick.n.on_change(), seen.set("wrong"))
    other = nu.Delay(0.05) >> reroot(bump(), "p", target)
    await write(nu.Timeout(0.3, reroot(heard, "p", "c"), on_timeout=seen.set("quiet")) | other)
    assert await read(seen) == expected


# --- run time ids -------------------------------------------------------------


async def test_plane_and_cell_can_be_attrs_bound_at_run_time(tmp_path):
    write, read = _store(tmp_path)
    plane, cell = nu.StrAttrRef("plane"), nu.StrAttrRef("cell")
    bind = nu.SetCmd(plane, nu.Str("p")) >> nu.SetCmd(cell, nu.Str("c"))
    await write(bind >> reroot(bump() >> Chat.title.set("t"), plane, cell))
    assert await read(nu.List.of(cell_state("p", "c")["n"], Space.planes["p"].state["title"])) == [
        1,
        "t",
    ]


async def test_the_class_form_survives_a_pickle(tmp_path):
    write, read = _store(tmp_path)
    plane, cell = nu.StrAttrRef("plane"), nu.StrAttrRef("cell")
    rewrite = pickle.loads(pickle.dumps(Reroot(plane, cell)))  # noqa: S301
    bind = nu.SetCmd(plane, nu.Str("p")) >> nu.SetCmd(cell, nu.Str("c"))
    await write(bind >> rewrite(bump()))
    assert await read(cell_state("p", "c")["n"]) == 1


async def test_a_rerooted_term_survives_a_pickle(tmp_path):
    """What actually crosses to a worker: the term, already rewritten."""
    write, read = _store(tmp_path)
    plane = nu.StrAttrRef("plane")
    term = pickle.loads(pickle.dumps(reroot(bump(), plane, "c")))  # noqa: S301
    await write(nu.SetCmd(plane, nu.Str("p")) >> term)
    assert await read(cell_state("p", "c")["n"]) == 1


# --- what is left alone --------------------------------------------------------


def test_foreign_chains_come_back_as_the_same_object():
    for term in (
        Movies.count.set(Movies.count + 1),
        Space.planes["p"].name.set("x"),
        Page.inp.set("hi"),
        Space.planes[Movies.count].name,
    ):
        assert reroot(term, "p", "c") is term


async def test_foreign_store_stays_where_it_is(tmp_path):
    """A program touching its own db and its own state: only the state moves."""
    write, read = _store(tmp_path)
    movies = str(tmp_path / "movies")
    moved = reroot(Movies.count.set(7) >> Tick.n.set(Movies.count), "p", "c")
    term = nu.With(
        nustd.kv.rocksdb_navigator(movies, tags=(Movies,)),
        body=nustd.kv.auto_flow_atomic(moved, scope=Movies),
    )
    await write(term)
    assert await read(cell_state("p", "c")["n"]) == 7
    value, _ = await nu.arun(
        nu.With(
            nustd.kv.rocksdb_navigator(movies, tags=(Movies,)),
            body=nustd.kv.Snapshot(Movies.count, scope=Movies),
        )
    )
    assert value == 7


def test_constants():
    assert ROOT == "root"
    assert STATUSES == ("starting", "up", "stopping", "dead")
