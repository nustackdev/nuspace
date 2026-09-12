"""``parent`` and ``children`` are two spellings of one fact, and agree.

Flat storage buys addressing at a price: the tree is data now, so nothing in
the substrate stops the two sides from drifting. ``ops`` is the only writer
and every structural op fixes both in one tree -- this is what says so out
loud, by walking the whole space after a run of adds, moves and deletes.
"""

from __future__ import annotations

import nu
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID, ROOT_PARENT, ops

from .conftest import SRC, do


async def read_space(store):
    """Every page in the space as ``{id: {"parent": ..., "children": [...]}}``."""
    ids = await do(store, ops.page_ids())
    out = {}
    for page_id in ids:
        out[page_id] = {
            "parent": await do(store, ops.parent_of(page_id)),
            "children": await do(store, ops.children_of(page_id)),
            "sections": await do(store, ops.section_ids(page_id)),
            "keys": await do(store, nu.list(Space.pages[page_id].sections.keys())),
        }
    return out


def assert_consistent(space):
    """Every link is named from both ends, exactly once, and nothing is orphaned."""
    for page_id, row in space.items():
        for child in row["children"]:
            assert child in space, f"{page_id} lists a child {child} that is gone"
            assert space[child]["parent"] == page_id, f"{child} does not point back at {page_id}"
        assert len(set(row["children"])) == len(row["children"]), f"{page_id} has a duplicate child"
        parent = row["parent"]
        # A parent always names a page that is there -- the root names itself.
        assert parent in space, f"{page_id} points at a parent {parent} that is gone"
        if parent == page_id:
            continue
        assert page_id in space[parent]["children"], f"{parent} does not list {page_id}"
    # section_order and the section dict name the same set.
    for page_id, row in space.items():
        assert sorted(row["sections"]) == sorted(row["keys"]), f"{page_id} order/dict disagree"


async def test_a_run_of_adds_moves_and_deletes_leaves_the_two_sides_agreeing(store):
    await do(store, ops.init_space())
    for parent, kid in (
        (ROOT_PAGE_ID, "a"),
        (ROOT_PAGE_ID, "b"),
        ("a", "a1"),
        ("a", "a2"),
        ("a1", "a1x"),
        ("b", "b1"),
    ):
        await do(store, ops.add_page(parent, page_id=kid))
    for page, sid in (("a1", "s_1"), ("a1x", "s_2"), ("b", "s_3")):
        await do(store, ops.add_section(page, SRC, section_id=sid))

    await do(store, ops.move_page("a1", "b"))
    await do(store, ops.move_page("a2", "b1", index=0))
    # Refused, so it must leave the space exactly as it found it.
    await do(store, ops.move_page("b", "b"))
    await do(store, ops.reorder_pages("b", ["b1", "a1"]))
    await do(store, ops.move_section("a1x", "s_2", "b"))
    await do(store, ops.remove_section("b", "s_3"))
    await do(store, ops.remove_page("a1"))

    space = await read_space(store)
    assert_consistent(space)
    assert set(space) == {ROOT_PAGE_ID, "a", "b", "a2", "b1"}
    assert space["b"]["children"] == ["b1"]
    assert space["b"]["sections"] == ["s_2"]
    assert space["a"]["children"] == []


async def test_removing_the_root_leaves_an_empty_and_consistent_space(store):
    await do(store, ops.init_space())
    await do(store, ops.add_page(ROOT_PAGE_ID, page_id="a"))
    await do(store, ops.add_page("a", page_id="b"))
    await do(store, ops.remove_page(ROOT_PAGE_ID))

    space = await read_space(store)
    assert_consistent(space)
    assert space == {}


async def test_a_cold_store_bootstraps_into_a_consistent_space(store):
    await do(store, ops.init_space())

    space = await read_space(store)
    assert_consistent(space)
    assert space[ROOT_PAGE_ID]["parent"] == ROOT_PARENT
