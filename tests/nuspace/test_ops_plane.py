"""``nuspace.plane``: each op's writes, its raises, and the reads that never raise.

Every op is a bare term, run here inside ``nuspace.atomic`` as a caller
would.
"""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nuspace
from nu.lang import is_null
from nuspace.errors import Exists, Missing, Refused, Removed
from nuspace.shapes import ROOT, Space


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

planes = Space.planes
keys = Space.indexes.plane_keys


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def children(store, p=ROOT):
    return await store.read(nu.list(planes[p].children.keys()))


async def test_add_writes_the_row_its_place_under_root_and_its_indexes(store):
    p = await store.made(
        nuspace.atomic(
            nuspace.plane.add(
                name="Notes",
                key="notes",
                icon="lucide:book",
                backend="async",
                spec="testing.plain",
                meta={"tone": "calm"},
                into=MADE,
            )
        )
    )
    assert p.startswith("p_")
    row = await store.read(planes[p].extract())
    assert {k: row[k] for k in ("name", "key", "icon", "parent", "version", "backend", "spec")} == {
        "name": "Notes",
        "key": "notes",
        "icon": "lucide:book",
        "parent": ROOT,
        "version": 0,
        "backend": "async",
        "spec": "testing.plain",
    }
    assert row["system"] is False
    assert row["meta"] == {"tone": "calm"}
    assert row["created_at"] == row["modified_at"]
    assert "removed_at" not in row
    assert await children(store) == [p]
    assert await store.read(keys["notes"]) == p
    assert await store.read(Space.indexes.spec_planes["testing.plain"].ids.last()) == p


async def test_add_places_before_or_after_a_sibling_else_at_the_end(store):
    await do(store, nuspace.plane.add("a") >> nuspace.plane.add("c"))
    await do(store, nuspace.plane.add("b", before="c"))
    await do(store, nuspace.plane.add("d", after="a"))
    assert await children(store) == ["a", "d", "b", "c"]


async def test_add_is_create_only(store):
    await do(store, nuspace.plane.add("a", key="k"))
    with pytest.raises(Exists, match="plane a exists"):
        await do(store, nuspace.plane.add("a"))
    with pytest.raises(Exists, match="plane key k is taken"):
        await do(store, nuspace.plane.add("b", key="k"))
    assert await children(store) == ["a"]


async def test_add_raises_on_a_parent_or_anchor_that_is_not_there(store):
    await do(store, nuspace.plane.add("a") >> nuspace.plane.add("x", parent="a"))
    await do(store, nuspace.plane.remove("a"))
    with pytest.raises(Missing, match="no plane nope"):
        await do(store, nuspace.plane.add("b", parent="nope"))
    with pytest.raises(Removed, match="plane a is removed"):
        await do(store, nuspace.plane.add("b", parent="a"))
    with pytest.raises(Missing):
        await do(store, nuspace.plane.add("b", before="nope"))
    await do(store, nuspace.plane.add("c") >> nuspace.plane.add("y", parent="c"))
    with pytest.raises(Refused, match="plane y is not on plane root"):
        await do(store, nuspace.plane.add("b", after="y"))


def test_add_refuses_bad_literals_at_build():
    with pytest.raises(Refused, match="reserved"):
        nuspace.plane.add(ROOT)
    with pytest.raises(Refused, match="slug"):
        nuspace.plane.add(key="Has Space")
    with pytest.raises(Refused, match="slug"):
        nuspace.plane.add(key="a/b")
    with pytest.raises(Refused, match="icon"):
        nuspace.plane.add(icon="book")
    with pytest.raises(TypeError, match="not both"):
        nuspace.plane.add(before="a", after="b")


async def test_add_refuses_a_key_term_not_in_slug_chars(store):
    with pytest.raises(Refused, match="slug"):
        await do(store, nuspace.plane.add("a", key=nu.Str("Bad Key")))
    await do(store, nuspace.plane.add("a", key=nu.Str("")))
    assert await store.read(planes["a"].key) == ""


async def test_add_mints_at_evaluation(store):
    term = nuspace.atomic(nuspace.plane.add(into=MADE))
    first, second = await store.made(term), await store.made(term)
    assert first != second
    assert await children(store) == [first, second]


async def test_remove_stamps_the_subtree_drops_keys_and_keeps_the_rows(store):
    await do(
        store,
        nuspace.plane.add("a", key="top")
        >> nuspace.plane.add("b", parent="a", key="mid")
        >> nuspace.plane.add("c", parent="b")
        >> nuspace.cell.add("a", "src", id="ca", key="cell-a")
        >> nuspace.cell.add("c", "src", id="cc"),
    )
    await do(store, nuspace.cell.remove("cc"))
    await do(store, nuspace.plane.remove("a"))
    assert await children(store) == []
    for p in ("a", "b", "c"):
        assert await store.read(planes[p].removed_by) == "a"
    assert await store.read(Space.cells["ca"].removed_by) == "a"
    # Removed before by itself: its own stamp stays.
    assert await store.read(Space.cells["cc"].removed_by) == "cc"
    # Rows keep their key, the index lets it go.
    assert await store.read(planes["b"].key) == "mid"
    assert await store.read(keys.extract()) == {}
    assert await store.read(Space.indexes.cell_keys.extract()) == {}
    # Rows below stay listed where they are, for a restore.
    assert await store.read(nu.list(planes["a"].children.keys())) == ["b"]
    assert await store.read(nu.list(Space.indexes.removed.keys())) == ["cc", "a"]
    assert await store.read(nuspace.plane.exists("b")) is False
    assert await store.read(nuspace.plane.exists("b", removed=True)) is True
    # The key is free again.
    await do(store, nuspace.plane.add("d", key="top"))


async def test_remove_raises_on_missing_removed_root_and_system(store):
    await do(store, nuspace.plane.add("a") >> nuspace.plane.add("s", system=True))
    await do(store, nuspace.plane.remove("a"))
    with pytest.raises(Missing):
        await do(store, nuspace.plane.remove("nope"))
    with pytest.raises(Removed):
        await do(store, nuspace.plane.remove("a"))
    with pytest.raises(Refused, match="system"):
        await do(store, nuspace.plane.remove("s"))
    with pytest.raises(Refused, match="root"):
        nuspace.plane.remove(ROOT)
    with pytest.raises(Refused, match="root"):
        await do(store, nuspace.plane.remove(nu.Str(ROOT)))


async def test_move_reorders_among_siblings_and_to_the_end(store):
    await do(store, nuspace.plane.add("a") >> nuspace.plane.add("b") >> nuspace.plane.add("c"))
    await do(store, nuspace.plane.move("c", before="a"))
    assert await children(store) == ["c", "a", "b"]
    await do(store, nuspace.plane.move("c"))
    assert await children(store) == ["a", "b", "c"]
    await do(store, nuspace.plane.move("a", after="b"))
    assert await children(store) == ["b", "a", "c"]


async def test_move_reparents_with_both_sides_in_one_commit(store):
    await do(
        store,
        nuspace.plane.add("a") >> nuspace.plane.add("b") >> nuspace.plane.add("x", parent="b"),
    )
    await do(store, nuspace.plane.move("a", parent="b", before="x"))
    assert await children(store) == ["b"]
    assert await children(store, "b") == ["a", "x"]
    assert await store.read(planes["a"].parent) == "b"


async def test_move_refuses_root_a_cycle_and_a_bad_anchor(store):
    await do(
        store,
        nuspace.plane.add("a")
        >> nuspace.plane.add("b", parent="a")
        >> nuspace.plane.add("c", parent="b")
        >> nuspace.plane.add("d"),
    )
    with pytest.raises(Refused, match="root"):
        nuspace.plane.move(ROOT, parent="a")
    with pytest.raises(Refused, match="under itself"):
        await do(store, nuspace.plane.move("a", parent="c"))
    with pytest.raises(Refused, match="under itself"):
        await do(store, nuspace.plane.move("a", parent="a"))
    with pytest.raises(Refused, match="not on"):
        await do(store, nuspace.plane.move("d", before="b"))
    with pytest.raises(Refused, match="itself"):
        await do(store, nuspace.plane.move("d", before=nu.Str("d")))
    with pytest.raises(Missing):
        await do(store, nuspace.plane.move("d", parent="nope"))
    assert await children(store) == ["a", "d"]


async def test_rename_icon_backend_and_meta_write_the_row(store):
    await do(store, nuspace.plane.add("a", backend="async", meta={"x": 1}))
    before = await store.read(planes["a"].modified_at)
    await do(
        store,
        nuspace.plane.rename("a", "Alpha")
        >> nuspace.plane.set_icon("a", "emoji:🌱")
        >> nuspace.plane.set_backend("a", "mp")
        >> nuspace.plane.set_meta("a", {"y": 2}),
    )
    row = await store.read(planes["a"].extract())
    assert (row["name"], row["icon"], row["backend"], row["meta"]) == (
        "Alpha",
        "emoji:🌱",
        "mp",
        {"x": 1, "y": 2},
    )
    assert row["modified_at"] >= before
    with pytest.raises(Refused, match="root"):
        nuspace.plane.set_backend(ROOT, "mp")
    for op in (
        nuspace.plane.rename("nope", "x"),
        nuspace.plane.set_icon("nope", ""),
        nuspace.plane.set_meta("nope", {}),
    ):
        with pytest.raises(Missing):
            await do(store, op)


async def test_set_key_moves_the_index_entry_and_remove_key_frees_it(store):
    await do(store, nuspace.plane.add("a") >> nuspace.plane.add("b", key="taken"))
    await do(store, nuspace.plane.set_key("a", "first"))
    await do(store, nuspace.plane.set_key("a", "second"))
    await do(store, nuspace.plane.set_key("a", "second"))
    assert await store.read(keys.extract()) == {"second": "a", "taken": "b"}
    with pytest.raises(Exists):
        await do(store, nuspace.plane.set_key("a", "taken"))
    with pytest.raises(Refused, match="empty"):
        nuspace.plane.set_key("a", "")
    await do(store, nuspace.plane.remove_key("a"))
    assert await store.read(planes["a"].key) == ""
    assert await store.read(keys.extract()) == {"taken": "b"}
    with pytest.raises(Missing, match="has no key"):
        await do(store, nuspace.plane.remove_key("a"))


async def test_exists_and_title_read_the_row(store):
    await do(store, nuspace.plane.add("a") >> nuspace.plane.add("b", name="Bee"))
    assert await store.read(
        nu.List.of(nuspace.plane.exists("a"), nuspace.plane.exists("nope"))
    ) == [True, False]
    assert await store.read(nu.List.of(nuspace.plane.title("a"), nuspace.plane.title("b"))) == [
        "a",
        "Bee",
    ]
    with pytest.raises(Missing, match="no plane nope"):
        await store.read(nuspace.plane.title("nope"))


async def test_on_change_fires_on_a_cell_write_and_on_children_change_on_a_child(store):
    await do(store, nuspace.plane.add("a") >> nuspace.cell.add("a", "src", id="c1"))

    async def fired(watch, write):
        """The watch sees ``write``: its first notification ends the race, before the timeout."""
        writer = nu.Delay(0.05) >> nuspace.atomic(write) >> nu.Park()
        await store.run(nu.Timeout(5, nu.Race(nu.ReactOnce(nuspace.atomic(watch)), writer)))

    await fired(nuspace.plane.on_change("a"), nuspace.cell.rename("c1", "x"))
    await fired(nuspace.plane.on_children_change("a"), nuspace.plane.add("k", parent="a"))
    assert is_null(await store.read(planes["k"].removed_at))
