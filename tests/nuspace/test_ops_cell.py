"""``nuspace.cell``: each op's writes, the two versions, its raises, the reads."""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
from nuspace.errors import Exists, Missing, Refused, Removed
from nuspace.ops.interactions import Fabrics
from nuspace.shapes import Space


STORES = ("memory", "sqlite")

cells = Space.cells
planes = Space.planes

#: A prog that draws: its built term holds a ui ref. Built with the cell's id offered.
UI_SRC = "import nustd.ui\n\n\ndef out(cell):\n    return nustd.ui.StatRef(cell).set_label('n')\n"


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def listed(store, p="p"):
    return await store.read(nu.list(planes[p].cells.keys()))


async def version(store, p="p"):
    return await store.read(planes[p].version)


@pytest.fixture
async def plane(store):
    await do(
        store, nuspace.plane.add("p", backend="async") >> nuspace.plane.add("q", backend="async")
    )
    return store


async def test_add_writes_the_row_its_place_and_counts_on_the_plane(plane):
    store = plane
    c = await store.made(
        nuspace.atomic(
            nuspace.cell.add(
                "p",
                "def out():\n    return nu.Noop()\n",
                name="Note",
                key="note",
                spec="testing.text",
                meta={"a": 1},
                into=MADE,
            )
        )
    )
    assert c.startswith("c_")
    row = await store.read(cells[c].extract())
    assert {k: row[k] for k in ("name", "key", "version", "plane", "spec", "meta", "fabrics")} == {
        "name": "Note",
        "key": "note",
        "version": 1,
        "plane": "p",
        "spec": "testing.text",
        "meta": {"a": 1},
        "fabrics": [],
    }
    assert await listed(store) == [c]
    assert await store.read(Space.indexes.cell_keys["note"]) == c
    assert await store.read(Space.indexes.spec_cells["testing.text"].ids.last()) == c
    assert await version(store) == 1


async def test_add_works_out_the_fabrics_from_the_prog(plane):
    store = plane
    await do(
        store,
        nuspace.cell.add("p", UI_SRC, id="u") >> nuspace.cell.add("p", "not python (", id="bad"),
    )
    assert await store.read(cells["u"].fabrics) == ["ui"]
    assert await store.read(cells["bad"].fabrics) == []


async def test_add_and_set_prog_store_fabrics_worked_out_already(plane):
    store = plane
    # Given fabrics are stored as they are: the prog is not built.
    await do(store, nuspace.cell.add("p", "s", id="a", fabrics=["ui"]))
    assert await store.read(cells["a"].fabrics) == ["ui"]
    found = Fabrics(UI_SRC, "p", "b")
    await do(store, nuspace.cell.add("p", UI_SRC, id="b", fabrics=found))
    assert await store.read(cells["b"].fabrics) == ["ui"]
    await do(store, nuspace.cell.set_prog("b", UI_SRC, fabrics=[]))
    row = await store.read(cells["b"].extract())
    assert (row["prog"], row["fabrics"], row["version"]) == (UI_SRC, [], 2)
    await do(store, nuspace.cell.remove("b"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.set_prog("b", "s", fabrics=[]))


async def test_keys_take_uppercase_and_keep_case(plane):
    store = plane
    keys = Space.indexes.cell_keys
    await do(
        store,
        nuspace.cell.add("p", "s", id="a", key="Total")
        >> nuspace.cell.add("p", "s", id="b", key=nu.Str("total")),
    )
    assert await store.read(keys.extract()) == {"Total": "a", "total": "b"}
    with pytest.raises(Exists, match="Total"):
        await do(store, nuspace.cell.add("q", "s", key="Total"))
    await do(store, nuspace.cell.set_key("a", "Sum_2"))
    assert await store.read(keys.extract()) == {"Sum_2": "a", "total": "b"}
    with pytest.raises(Refused, match="key chars"):
        nuspace.cell.set_key("a", "sum.2")


async def test_add_places_and_raises(plane):
    store = plane
    await do(store, nuspace.cell.add("p", "s", id="a") >> nuspace.cell.add("p", "s", id="c"))
    await do(
        store, nuspace.cell.add("p", "s", id="b", before="c") >> nuspace.cell.add("q", "s", id="z")
    )
    assert await listed(store) == ["a", "b", "c"]
    with pytest.raises(Exists):
        await do(store, nuspace.cell.add("p", "s", id="a"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell.add("nope", "s"))
    with pytest.raises(Refused, match="not on plane p"):
        await do(store, nuspace.cell.add("p", "s", after="z"))
    await do(store, nuspace.cell.add("p", "s", id="k", key="k"))
    with pytest.raises(Exists, match="cell key k"):
        await do(store, nuspace.cell.add("q", "s", key="k"))
    with pytest.raises(Refused, match="key chars"):
        nuspace.cell.add("p", "s", key="no/slash")
    with pytest.raises(Refused, match="key chars"):
        await do(store, nuspace.cell.add("p", "s", key=nu.Str("Has Space")))
    await do(store, nuspace.plane.remove("q"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.add("q", "s"))


async def test_remove_is_soft_and_frees_the_key(plane):
    store = plane
    await do(store, nuspace.cell.add("p", "s", id="a", key="ka"))
    at = await version(store)
    await do(store, nuspace.cell.remove("a"))
    assert await listed(store) == []
    assert await store.read(cells["a"].removed_by) == "a"
    assert await store.read(cells["a"].key) == "ka"
    assert await store.read(Space.indexes.cell_keys.extract()) == {}
    assert await store.read(nu.list(Space.indexes.removed.keys())) == ["a"]
    assert await version(store) == at + 1
    with pytest.raises(Removed):
        await do(store, nuspace.cell.remove("a"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell.remove("nope"))


async def test_set_key_moves_the_index_entry_and_refuses_a_key_another_cell_holds(plane):
    store = plane
    keys = Space.indexes.cell_keys
    await do(
        store,
        nuspace.cell.add("p", "s", id="a", key="first")
        >> nuspace.cell.add("p", "s", id="b", key="taken"),
    )
    await do(store, nuspace.cell.set_key("a", "second"))
    assert await store.read(keys.extract()) == {"second": "a", "taken": "b"}
    assert await store.read(cells["a"].key) == "second"
    # Setting the key it holds already changes nothing.
    await do(store, nuspace.cell.set_key("a", "second"))
    assert await store.read(keys.extract()) == {"second": "a", "taken": "b"}
    with pytest.raises(Exists, match="taken"):
        await do(store, nuspace.cell.set_key("a", "taken"))
    assert await store.read(keys.extract()) == {"second": "a", "taken": "b"}
    with pytest.raises(Refused, match="empty"):
        nuspace.cell.set_key("a", "")
    await do(store, nuspace.cell.remove_key("a"))
    assert await store.read(cells["a"].key) == ""
    assert await store.read(keys.extract()) == {"taken": "b"}
    with pytest.raises(Missing, match="has no key"):
        await do(store, nuspace.cell.remove_key("a"))


async def test_move_reorders_and_takes_a_cell_to_another_plane(plane):
    store = plane
    await do(
        store,
        nuspace.cell.add("p", "s", id="a")
        >> nuspace.cell.add("p", "s", id="b")
        >> nuspace.cell.add("q", "s", id="x"),
    )
    await do(store, nuspace.cell.move("b", before="a"))
    assert await listed(store) == ["b", "a"]
    await do(store, nuspace.cell.move("b"))
    assert await listed(store) == ["a", "b"]
    p_at, q_at = await version(store), await version(store, "q")
    await do(store, nuspace.cell.move("a", plane="q", before="x"))
    assert await listed(store) == ["b"]
    assert await listed(store, "q") == ["a", "x"]
    assert await store.read(cells["a"].plane) == "q"
    assert (await version(store), await version(store, "q")) == (p_at + 1, q_at + 1)


async def test_move_raises(plane):
    store = plane
    await do(store, nuspace.cell.add("p", "s", id="a") >> nuspace.cell.add("q", "s", id="x"))
    with pytest.raises(Refused, match="not on plane p"):
        await do(store, nuspace.cell.move("a", before="x"))
    with pytest.raises(Refused, match="itself"):
        nuspace.cell.move("a", after="a")
    with pytest.raises(Missing):
        await do(store, nuspace.cell.move("a", plane="nope"))
    await do(store, nuspace.plane.add("r") >> nuspace.plane.remove("r"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.move("a", plane="r"))
    assert await listed(store) == ["a"]


async def test_edits_move_plane_version_and_set_prog_moves_cell_version(plane):
    store = plane
    await do(store, nuspace.cell.add("p", "s", id="a"))
    at = await version(store)
    await do(
        store,
        nuspace.cell.rename("a", "A")
        >> nuspace.cell.set_meta("a", {"m": 1})
        >> nuspace.cell.set_key("a", "ka"),
    )
    assert await version(store) == at + 3
    assert await store.read(cells["a"].version) == 1
    await do(store, nuspace.cell.set_prog("a", UI_SRC))
    row = await store.read(cells["a"].extract())
    assert (row["prog"], row["fabrics"], row["version"], row["name"]) == (UI_SRC, ["ui"], 2, "A")
    assert await version(store) == at + 4
    await do(store, nuspace.cell.remove_key("a"))
    assert await store.read(Space.indexes.cell_keys.extract()) == {}
    with pytest.raises(Missing, match="has no key"):
        await do(store, nuspace.cell.remove_key("a"))
    await do(store, nuspace.cell.remove("a"))
    for op in (
        nuspace.cell.rename("a", "x"),
        nuspace.cell.set_prog("a", "s"),
        nuspace.cell.set_meta("a", {}),
        nuspace.cell.set_key("a", "k"),
    ):
        with pytest.raises(Removed):
            await do(store, op)


async def test_exists_and_title(plane):
    store = plane
    await do(
        store, nuspace.cell.add("p", "s", id="a") >> nuspace.cell.add("p", "s", id="b", name="Bee")
    )
    await do(store, nuspace.cell.remove("b"))
    assert await store.read(
        nu.List.of(
            nuspace.cell.exists("a"),
            nuspace.cell.exists("b"),
            nuspace.cell.exists("b", removed=True),
        )
    ) == [True, False, True]
    assert await store.read(nu.List.of(nuspace.cell.title("a"), nuspace.cell.title("b"))) == [
        "a",
        "Bee",
    ]
    with pytest.raises(Missing):
        await store.read(nuspace.cell.title("nope"))
