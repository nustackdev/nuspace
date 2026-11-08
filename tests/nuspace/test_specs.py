"""Specs: the recipe data, and making planes and cells from it with ``nuspace.specs``."""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
import nustd.kv
from nuspace.devices.web.shapes import Web
from nuspace.errors import Exists, Missing
from nuspace.ops.interactions import Fabrics
from nuspace.shapes import ROOT, Space, State
from nuspace.specs import EMPTY_PLANE, CellSpec, PlaneSpec, SpecCells, WebOptions


STORES = ("memory", "sqlite")

planes = Space.planes
specs = nuspace.specs


#: A source that draws: its built term holds a ui ref.
UI_SRC = "import nustd.ui\n\n\ndef out(cell):\n    return nustd.ui.StatRef(cell).set_label('n')\n"


def bracketed_builds(term):
    """The prog builds (``Fabrics``) in ``term``: all of them, and those inside a kv bracket."""
    builds = nu.tree.find(term, lambda n: isinstance(n, Fabrics))
    brackets = nu.tree.find(
        term, lambda n: isinstance(n, (nustd.kv.Transaction, nustd.kv.Snapshot))
    )
    inside = [b for br in brackets for b in nu.tree.find(br, lambda n: isinstance(n, Fabrics))]
    return builds, inside


async def kids(store, p):
    return await store.read(nu.list(planes[p].children.keys()))


async def cell_names(store, p):
    ids = await store.read(nu.list(planes[p].cells.keys()))
    return [await store.read(Space.cells[c].name) for c in ids]


def test_plane_spec_requires_a_backend():
    with pytest.raises(TypeError, match="backend"):
        PlaneSpec("x", "X")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="backend is required"):
        PlaneSpec("x", "X", backend="")


def test_cell_spec_default_is_one_of_its_classes():
    assert CellSpec("x", "X", "").classes == ()
    with pytest.raises(ValueError, match="default_for"):
        CellSpec("x", "X", "", default_for=("prose",))
    with pytest.raises(TypeError, match="tuples"):
        CellSpec("x", "X", "", classes="prose")  # type: ignore[arg-type]


def test_the_empty_plane_shows_on_the_web_and_records_no_spec():
    assert EMPTY_PLANE.web == WebOptions(editable=True, full_width=False, compact=False)
    assert (EMPTY_PLANE.name, EMPTY_PLANE.cells, EMPTY_PLANE.key) == ("", (), "")


async def test_add_plane_makes_the_whole_tree_and_records_each_cells_id(store):
    leaf = PlaneSpec("leaf", "Leaf", cells=(("note", "n"),), backend="mp")
    spec = PlaneSpec(
        "tracker",
        "Tracker",
        icon="list",
        meta={"k": 1},
        cells=(("form", "f"), ("list", "l")),
        children=(leaf,),
        backend="async",
    )
    top = await store.made(specs.add_plane(spec, into=MADE))
    row = await store.read(planes[top].extract())
    assert {k: row[k] for k in ("name", "icon", "spec", "backend", "meta", "parent")} == {
        "name": "Tracker",
        "icon": "lucide:list",
        "spec": "tracker",
        "backend": "async",
        "meta": {"k": 1},
        "parent": ROOT,
    }
    assert await cell_names(store, top) == ["form", "list"]
    (child,) = await kids(store, top)
    assert (await store.read(planes[child].spec), await store.read(planes[child].backend)) == (
        "leaf",
        "mp",
    )
    assert await cell_names(store, child) == ["note"]
    # Siblings find each other by name, in plane state.
    named = await store.read(SpecCells.ids.with_parent(State.planes[top]).extract())
    assert sorted(named) == ["form", "list"]
    assert await store.read(Space.cells[named["form"]].name) == "form"
    assert await store.read(nuspace.at.plane(id=child).state(SpecCells).ids["note"]) is not None
    assert await store.read(Space.indexes.spec_planes["tracker"].ids.last()) == top
    # No web= here: no web row.
    assert await store.read(Web.planes.contains(top)) is False


async def test_add_plane_writes_the_web_row_and_seeds_the_key(store):
    spec = PlaneSpec(
        "meter", "Meter", key="testing_meter", web=WebOptions(compact=True), backend="async"
    )
    p = await store.made(specs.add_plane(spec, id="m1", name="Mine", into=MADE))
    assert p == "m1"
    assert await store.read(planes["m1"].name) == "Mine"
    assert await store.read(Space.indexes.plane_keys["testing_meter"]) == "m1"
    assert await store.read(Web.planes["m1"].extract()) == {
        "editable": True,
        "full_width": False,
        "compact": True,
    }
    with pytest.raises(Exists, match="testing_meter"):
        await store.run(specs.add_plane(spec))


class Kept(nu.Shape):
    """Where a program keeps the plane it made, in State: a kv ``into``."""

    plane = nustd.kv.StrRef.slot()


async def test_add_plane_sets_a_kv_into_in_its_own_commit(store):
    spec = PlaneSpec("t", "T", cells=(("a", "s"),), backend="async")
    into = Kept.plane.with_parent(State.space)
    await store.run(specs.add_plane(spec, into=into))
    top = await store.read(into)
    assert await store.read(planes[top].spec) == "t"
    # The steps after it ran too: the cells' ids are in the plane's state.
    assert list(await store.read(SpecCells.ids.with_parent(State.planes[top]).extract())) == ["a"]


async def test_add_plane_by_registered_name_and_placed(store):
    await store.run(specs.add_plane(EMPTY_PLANE, id="a") >> specs.add_plane(EMPTY_PLANE, id="c"))
    await store.run(specs.add_plane("testing.jobs", id="b", before="c"))
    assert await kids(store, ROOT) == ["a", "b", "c"]
    assert await store.read(planes["b"].spec) == "testing.jobs"
    assert await cell_names(store, "b") == ["list"]
    with pytest.raises(Missing, match="no plane spec"):
        specs.add_plane("testing.nope")


async def test_add_plane_writes_nothing_when_the_space_commit_fails(store):
    spec = PlaneSpec(
        "t",
        "T",
        cells=(("a", "s"),),
        children=(PlaneSpec("k", "K", backend="async"),),
        backend="async",
    )
    with pytest.raises(Missing):
        await store.run(specs.add_plane(spec, parent="nope"))
    assert await kids(store, ROOT) == []
    assert await store.read(Space.cells.extract()) == {}
    assert await store.read(State.planes.extract()) == {}


async def test_add_cell_from_a_spec_or_its_name(store):
    await store.run(nuspace.atomic(nuspace.plane.add("p", backend="async")))
    c = await store.made(nuspace.atomic(specs.add_cell("p", "testing.text", into=MADE)))
    row = await store.read(Space.cells[c].extract())
    assert (row["name"], row["spec"]) == ("text", "testing.text")
    assert await store.read(Space.indexes.spec_cells["testing.text"].ids.last()) == c
    plain = CellSpec("loose", "Loose", "src")
    await store.run(nuspace.atomic(specs.add_cell("p", plain, id="x", before=c)))
    assert await store.read(nu.list(planes["p"].cells.keys())) == ["x", c]
    assert await store.read(Space.cells["x"].spec) == "loose"
    with pytest.raises(Missing, match="no cell spec"):
        specs.add_cell("p", "testing.nope")


async def test_add_plane_works_out_every_cells_fabrics_before_its_brackets(store):
    leaf = PlaneSpec("leaf", "Leaf", cells=(("stat", UI_SRC),), backend="async")
    spec = PlaneSpec(
        "t", "T", cells=(("stat", UI_SRC), ("note", "n")), children=(leaf,), backend="async"
    )
    term = specs.add_plane(spec, into=MADE)
    builds, inside = bracketed_builds(term)
    assert (len(builds), inside) == (3, [])
    top = await store.made(term)
    (child,) = await kids(store, top)
    named = await store.read(SpecCells.ids.with_parent(State.planes[top]).extract())
    assert await store.read(Space.cells[named["stat"]].fabrics) == ["ui"]
    assert await store.read(Space.cells[named["note"]].fabrics) == []
    (leaf_cell,) = await store.read(nu.list(planes[child].cells.keys()))
    assert await store.read(Space.cells[leaf_cell].fabrics) == ["ui"]


async def test_add_cell_works_out_the_fabrics_in_a_step_of_its_own(store):
    await store.run(nuspace.atomic(nuspace.plane.add("p", backend="async")))
    drawn = CellSpec("stat", "Stat", UI_SRC)
    term = nuspace.bracketed(specs.add_cell("p", drawn, into=MADE))
    builds, inside = bracketed_builds(term)
    assert (len(builds), inside) == (1, [])
    c = await store.made(term)
    assert c.startswith("c_")
    assert await store.read(Space.cells[c].fabrics) == ["ui"]
    # Given fabrics: no build at all, stored as given.
    given = specs.add_cell("p", drawn, id="x", fabrics=[])
    assert nu.tree.find(given, lambda n: isinstance(n, Fabrics)) == []
    await store.run(nuspace.atomic(given))
    assert await store.read(Space.cells["x"].fabrics) == []
