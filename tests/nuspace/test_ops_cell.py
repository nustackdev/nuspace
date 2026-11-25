"""``nuspace.cell``: each op's writes, the two versions, its raises, the reads."""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
from nuspace.errors import Exists, Missing, Refused, Removed
from nuspace.ops.interactions import Fabrics
from nuspace.shapes import ROOT, Space


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


async def test_add_takes_only_key_chars_ids(plane):
    store = plane
    for bad in ("a b", "a/b", "a.b", ""):
        with pytest.raises(Refused, match="cell ids are key chars"):
            nuspace.cell.add("p", "s", id=bad)
    with pytest.raises(Refused, match="cell ids are key chars"):
        await do(store, nuspace.cell.add("p", "s", id=nu.Str("a b"), fabrics=[]))
    await do(store, nuspace.cell.add("p", "s", id="My-cell_2", fabrics=[]))
    assert await listed(store) == ["My-cell_2"]


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


async def unstamped(store, *rows):
    """Zero ``modified_at`` on each row, so a test sees which ones an op stamps."""
    await do(store, nu.Sequential(*(r.modified_at.set(0.0) for r in rows)))


async def stamped(store, *rows):
    return [await store.read(r.modified_at) > 0 for r in rows]


async def test_move_reorders_within_the_plane(plane):
    store = plane
    await do(
        store,
        nuspace.cell.add("p", "s", id="a")
        >> nuspace.cell.add("p", "s", id="b")
        >> nuspace.cell.add("p", "s", id="c"),
    )
    await do(store, nuspace.cell.move("c", before="a"))
    assert await listed(store) == ["c", "a", "b"]
    await do(store, nuspace.cell.move("c"))
    assert await listed(store) == ["a", "b", "c"]
    await do(store, nuspace.cell.move("a", after="b"))
    assert await listed(store) == ["b", "a", "c"]
    assert await store.read(cells["a"].plane) == "p"


async def test_move_stamps_the_plane_once_and_not_the_cell(plane):
    store = plane
    await do(store, nuspace.cell.add("p", "s", id="a") >> nuspace.cell.add("p", "s", id="b"))
    await unstamped(store, cells["a"], planes["p"], planes["q"])
    at, q_at = await version(store), await version(store, "q")
    await do(store, nuspace.cell.move("a", after="b"))
    assert await stamped(store, cells["a"], planes["p"], planes["q"]) == [False, True, False]
    assert (await version(store), await version(store, "q")) == (at + 1, q_at)
    assert await store.read(cells["a"].version) == 1


async def test_move_is_allowed_on_a_system_plane(plane):
    store = plane
    await do(
        store,
        nuspace.plane.add("sys", backend="async", system=True)
        >> nuspace.cell.add("sys", "s", id="a")
        >> nuspace.cell.add("sys", "s", id="b"),
    )
    await do(store, nuspace.cell.move("b", before="a"))
    assert await listed(store, "sys") == ["b", "a"]


async def test_move_raises(plane):
    store = plane
    await do(store, nuspace.cell.add("p", "s", id="a") >> nuspace.cell.add("q", "s", id="x"))
    with pytest.raises(Refused, match="not on plane p"):
        await do(store, nuspace.cell.move("a", before="x"))
    with pytest.raises(Refused, match="itself"):
        nuspace.cell.move("a", after="a")
    with pytest.raises(Refused, match="itself"):
        await do(store, nuspace.cell.move("a", after=nu.Str("a")))
    with pytest.raises(Missing):
        await do(store, nuspace.cell.move("nope"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell.move("a", before="nope"))
    await do(store, nuspace.cell.add("p", "s", id="b") >> nuspace.cell.remove("b"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.move("b"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.move("a", before="b"))
    with pytest.raises(TypeError):
        nuspace.cell.move("a", before="x", after="x")
    assert await listed(store) == ["a"]


async def test_transfer_takes_a_cell_to_another_plane_in_one_commit(plane):
    store = plane
    await do(
        store,
        nuspace.cell.add("p", "s", id="a", key="ka")
        >> nuspace.cell.add("p", "s", id="b")
        >> nuspace.cell.add("q", "s", id="x")
        >> nuspace.cell.add("q", "s", id="y"),
    )
    await do(store, nuspace.cell.transfer("a", "q", before="y"))
    assert await listed(store) == ["b"]
    assert await listed(store, "q") == ["x", "a", "y"]
    assert await store.read(cells["a"].plane) == "q"
    await do(store, nuspace.cell.transfer("b", "q"))
    assert await listed(store) == []
    assert await listed(store, "q") == ["x", "a", "y", "b"]


async def test_transfer_stamps_the_cell_and_both_planes(plane):
    store = plane
    await do(
        store,
        nuspace.plane.add("r", backend="async")
        >> nuspace.cell.add("p", "s", id="a", key="ka", spec="testing.plain"),
    )
    before = await store.read(cells["a"].extract())
    await unstamped(store, cells["a"], planes["p"], planes["q"], planes["r"])
    at = [await version(store, p) for p in "pqr"]
    await do(store, nuspace.cell.transfer("a", "q"))
    rows = [cells["a"], planes["p"], planes["q"], planes["r"]]
    assert await stamped(store, *rows) == [True, True, True, False]
    assert [await version(store, p) for p in "pqr"] == [at[0] + 1, at[1] + 1, at[2]]
    after = await store.read(cells["a"].extract())
    for k in ("version", "fabrics", "spec", "key", "prog", "name"):
        assert after[k] == before[k], k


async def test_transfer_raises(plane):
    store = plane
    await do(
        store,
        nuspace.plane.add("sys", backend="async", system=True)
        >> nuspace.cell.add("p", "s", id="a")
        >> nuspace.cell.add("p", "s", id="b")
        >> nuspace.cell.add("q", "s", id="x")
        >> nuspace.cell.add("sys", "s", id="z"),
    )
    with pytest.raises(Refused, match="on plane p already"):
        await do(store, nuspace.cell.transfer("a", "p"))
    with pytest.raises(Refused, match="plane sys is a system plane"):
        await do(store, nuspace.cell.transfer("a", "sys"))
    with pytest.raises(Refused, match="plane root is a system plane"):
        await do(store, nuspace.cell.transfer("a", ROOT))
    with pytest.raises(Refused, match="plane sys is a system plane"):
        await do(store, nuspace.cell.transfer("z", "q"))
    with pytest.raises(Refused, match="not on plane q"):
        await do(store, nuspace.cell.transfer("a", "q", before="b"))
    with pytest.raises(Refused, match="itself"):
        nuspace.cell.transfer("a", "q", after="a")
    with pytest.raises(Missing):
        await do(store, nuspace.cell.transfer("a", "nope"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell.transfer("nope", "q"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell.transfer("a", "q", before="nope"))
    await do(store, nuspace.plane.add("r") >> nuspace.plane.remove("r"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.transfer("a", "r"))
    await do(store, nuspace.cell.remove("b"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.transfer("b", "q"))
    with pytest.raises(TypeError):
        nuspace.cell.transfer("a", "q", before="x", after="x")
    assert await listed(store) == ["a"]
    assert await listed(store, "q") == ["x"]
    assert await listed(store, "sys") == ["z"]


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


async def test_add_and_remove_stamp_the_plane_and_no_bystander(plane):
    store = plane
    await unstamped(store, planes["p"], planes["q"])
    await do(store, nuspace.cell.add("p", "s", id="a"))
    assert await stamped(store, planes["p"], planes["q"]) == [True, False]
    await unstamped(store, planes["p"], cells["a"])
    await do(store, nuspace.cell.remove("a"))
    assert await stamped(store, planes["p"], planes["q"]) == [True, False]


async def test_restore_takes_back_the_remove_and_lands_last(plane):
    store = plane
    await do(
        store,
        nuspace.cell.add("p", "s", id="a", key="ka")
        >> nuspace.cell.add("p", "s", id="b")
        >> nuspace.cell.add("p", "s", id="c"),
    )
    await do(store, nuspace.cell.remove("a"))
    at = await version(store)
    born = await store.read(cells["a"].version)
    await do(store, nuspace.cell.restore("a"))
    assert await listed(store) == ["b", "c", "a"]
    assert await store.read(cells["a"].removed_at.exists()) is False
    assert await store.read(cells["a"].removed_by.exists()) is False
    assert await store.read(Space.indexes.cell_keys.extract()) == {"ka": "a"}
    assert await store.read(nu.list(Space.indexes.removed.keys())) == []
    assert await store.read(nuspace.cell.exists("a")) is True
    # Its own version moves, so reload runs it again in a live plane run.
    assert await store.read(cells["a"].version) == born + 1
    assert await version(store) == at + 1


async def test_restore_refuses_what_is_not_removed_by_itself(plane):
    store = plane
    await do(store, nuspace.cell.add("p", "s", id="a") >> nuspace.cell.add("q", "s", id="b"))
    with pytest.raises(Missing):
        await do(store, nuspace.cell.restore("nope"))
    with pytest.raises(Refused, match="not removed"):
        await do(store, nuspace.cell.restore("a"))
    # Went with its plane: the plane is what comes back.
    await do(store, nuspace.plane.remove("q"))
    with pytest.raises(Refused, match="went with q"):
        await do(store, nuspace.cell.restore("b"))


async def test_restore_refuses_a_removed_plane_or_a_taken_key(plane):
    store = plane
    await do(
        store,
        nuspace.cell.add("p", "s", id="a", key="k") >> nuspace.cell.add("q", "s", id="b"),
    )
    await do(store, nuspace.cell.remove("a"))
    await do(store, nuspace.cell.add("p", "s", id="other", key="k"))
    with pytest.raises(Exists, match="taken"):
        await do(store, nuspace.cell.restore("a"))
    assert await store.read(cells["a"].removed_by) == "a"
    assert await listed(store) == ["other"]
    await do(store, nuspace.cell.remove("b") >> nuspace.plane.remove("q"))
    with pytest.raises(Removed):
        await do(store, nuspace.cell.restore("b"))
