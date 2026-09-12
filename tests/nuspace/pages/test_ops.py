"""Every pages primitive, against a real on-disk RocksDB.

No workers and no runner here: an op is a tree, so the whole test is "run the
tree, read the store back". The nesting is deliberately two and three levels
deep, because a flat page tree would not exercise the addressing at all.
"""

from __future__ import annotations

import pytest

from nu.lang import EMPTY
from nuspace.core.shapes import Space
from nuspace.pages import ORDER_STEP, ops

from .conftest import SRC, Route, do


DOCS = ["docs"]
GUIDES = ["docs", "guides"]
INTRO = ["docs", "guides", "intro"]


async def tree(store):
    """A three-deep page tree: docs > guides > intro."""
    await do(store, ops.add_page([], page_id="docs", title="Docs"))
    await do(store, ops.add_page(DOCS, page_id="guides", title="Guides"))
    await do(store, ops.add_page(GUIDES, page_id="intro", title="Intro"))


# --- addressing -------------------------------------------------------------


async def test_page_at_walks_one_link_per_segment(store):
    await tree(store)

    assert await do(store, ops.page_at([]).title) is EMPTY
    assert await do(store, ops.page_at(INTRO).title) == "Intro"
    assert (
        await do(store, Space.pages.pages["docs"].pages["guides"].pages["intro"].title) == "Intro"
    )


async def test_page_ids_answers_at_every_level(store):
    await tree(store)

    assert await do(store, ops.page_ids([])) == ["docs"]
    assert await do(store, ops.page_ids(DOCS)) == ["guides"]
    assert await do(store, ops.page_ids(GUIDES)) == ["intro"]
    assert await do(store, ops.page_ids(INTRO)) == []


async def test_page_exists_at_depth_and_for_the_root(store):
    await tree(store)

    assert await do(store, ops.page_exists(INTRO)) is True
    assert await do(store, ops.page_exists(["docs", "nope"])) is False
    # The root page is the space itself, so there is nothing to look up.
    assert await do(store, ops.page_exists([])) is True


# --- pages ------------------------------------------------------------------


async def test_add_page_defaults_the_title_to_the_id(store):
    await do(store, ops.add_page([], page_id="p_one"))

    assert await do(store, ops.title_of(["p_one"])) == "p_one"


async def test_add_page_with_no_id_mints_an_ordered_one(store):
    await do(store, ops.add_page([]))
    await do(store, ops.add_page([]))

    ids = await do(store, ops.page_ids([]))
    assert len(ids) == 2
    assert all(i.startswith("p_") for i in ids)
    # Minted in creation order, and the store lists them sorted by key.
    assert ids == sorted(ids)


async def test_rename_page_moves_the_title_and_not_the_id(store):
    await tree(store)
    await do(store, ops.rename_page(INTRO, "Getting started"))

    assert await do(store, ops.title_of(INTRO)) == "Getting started"
    assert await do(store, ops.page_ids(GUIDES)) == ["intro"]


async def test_title_of_is_empty_for_a_page_that_is_not_there(store):
    await tree(store)

    assert await do(store, ops.title_of(["docs", "nope"])) is EMPTY


async def test_titles_maps_child_id_to_title(store):
    await tree(store)
    await do(store, ops.add_page(DOCS, page_id="ref", title="Reference"))

    assert await do(store, ops.titles(DOCS)) == {"guides": "Guides", "ref": "Reference"}


async def test_remove_page_takes_its_whole_subtree_with_it(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.remove_page(DOCS))

    assert await do(store, ops.page_ids([])) == []
    assert await do(store, ops.page_exists(GUIDES)) is False
    assert await do(store, ops.title_of(INTRO)) is EMPTY
    assert await do(store, ops.section_ids(GUIDES)) == []


async def test_remove_page_leaves_its_siblings(store):
    await tree(store)
    await do(store, ops.add_page(DOCS, page_id="ref", title="Reference"))
    await do(store, ops.remove_page(["docs", "ref"]))

    assert await do(store, ops.page_ids(DOCS)) == ["guides"]


async def test_remove_page_on_a_missing_page_is_harmless(store):
    await tree(store)
    await do(store, ops.remove_page(["docs", "nope"]))

    assert await do(store, ops.page_ids(DOCS)) == ["guides"]


async def test_remove_page_refuses_the_root(store):
    with pytest.raises(ValueError, match="root page has no parent"):
        ops.remove_page([])


async def test_move_page_carries_the_subtree_and_the_sections(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a", name="A"))
    await do(store, ops.move_page(GUIDES, []))

    assert await do(store, ops.page_ids([])) == ["docs", "guides"]
    assert await do(store, ops.page_ids(DOCS)) == []
    assert await do(store, ops.title_of(["guides"])) == "Guides"
    assert await do(store, ops.page_ids(["guides"])) == ["intro"]
    assert await do(store, ops.title_of(["guides", "intro"])) == "Intro"
    assert await do(store, ops.section_ids(["guides"])) == ["s_a"]


async def test_move_page_can_rekey_on_the_way(store):
    await tree(store)
    await do(store, ops.move_page(GUIDES, [], page_id="howto"))

    assert await do(store, ops.title_of(["howto"])) == "Guides"


async def test_move_page_refuses_to_move_under_itself(store):
    with pytest.raises(ValueError, match="its own descendant"):
        ops.move_page(DOCS, GUIDES)
    with pytest.raises(ValueError, match="its own descendant"):
        ops.move_page(DOCS, DOCS)


# --- sections ---------------------------------------------------------------


async def test_add_section_writes_every_field(store):
    await tree(store)
    await do(
        store,
        ops.add_section(GUIDES, SRC, section_id="s_a", name="A", tpl="text", policy="manual"),
    )

    section = Space.pages.pages["docs"].pages["guides"].sections["s_a"]
    assert await do(store, ops.snippet_of(GUIDES, "s_a")) == SRC
    assert await do(store, section.name) == "A"
    assert await do(store, section.tpl) == "text"
    assert await do(store, section.policy) == "manual"


async def test_add_section_defaults_the_name_to_the_id_and_the_tpl_to_program(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))

    section = Space.pages.pages["docs"].pages["guides"].sections["s_a"]
    assert await do(store, section.name) == "s_a"
    assert await do(store, section.tpl) == "program"
    assert await do(store, section.policy) == "always"


async def test_add_section_with_no_id_mints_an_ordered_one(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC))
    await do(store, ops.add_section(GUIDES, SRC))

    ids = await do(store, ops.section_ids(GUIDES))
    assert len(ids) == 2
    assert all(i.startswith("s_") for i in ids)
    assert ids == sorted(ids)


async def test_add_section_lands_each_new_section_last(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_b"))
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_c"))

    assert await do(store, ops.section_order(GUIDES)) == {
        "s_a": 0,
        "s_b": ORDER_STEP,
        "s_c": 2 * ORDER_STEP,
    }


async def test_sections_on_two_pages_do_not_see_each_other(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.add_section(DOCS, SRC, section_id="s_b"))

    assert await do(store, ops.section_ids(GUIDES)) == ["s_a"]
    assert await do(store, ops.section_ids(DOCS)) == ["s_b"]


async def test_reorder_sections_renormalises_to_index_times_step(store):
    await tree(store)
    for sid in ("s_a", "s_b", "s_c"):
        await do(store, ops.add_section(GUIDES, SRC, section_id=sid))
    await do(store, ops.reorder_sections(GUIDES, ["s_c", "s_a", "s_b"]))

    assert await do(store, ops.section_order(GUIDES)) == {
        "s_c": 0,
        "s_a": ORDER_STEP,
        "s_b": 2 * ORDER_STEP,
    }


async def test_reorder_sections_skips_ids_that_are_not_on_the_page(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.reorder_sections(GUIDES, ["s_nope", "s_a"]))

    assert await do(store, ops.section_ids(GUIDES)) == ["s_a"]
    assert await do(store, ops.section_order(GUIDES)) == {"s_a": ORDER_STEP}


async def test_reorder_sections_with_nothing_to_do_is_a_noop(store):
    await tree(store)
    await do(store, ops.reorder_sections(GUIDES, []))

    assert await do(store, ops.section_ids(GUIDES)) == []


async def test_set_snippet_replaces_the_source(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.set_snippet(GUIDES, "s_a", "edited"))

    assert await do(store, ops.snippet_of(GUIDES, "s_a")) == "edited"


async def test_set_tpl_replaces_the_tpl_and_leaves_the_snippet(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.set_tpl(GUIDES, "s_a", "text"))

    section = Space.pages.pages["docs"].pages["guides"].sections["s_a"]
    assert await do(store, section.tpl) == "text"
    assert await do(store, ops.snippet_of(GUIDES, "s_a")) == SRC


async def test_remove_section_drops_the_row_and_leaves_the_others(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_b"))
    await do(store, ops.remove_section(GUIDES, "s_a"))

    assert await do(store, ops.section_ids(GUIDES)) == ["s_b"]


async def test_remove_section_on_a_missing_section_is_harmless(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a"))
    await do(store, ops.remove_section(GUIDES, "s_nope"))

    assert await do(store, ops.section_ids(GUIDES)) == ["s_a"]


async def test_move_section_carries_every_field_to_the_other_page(store):
    await tree(store)
    await do(store, ops.add_section(GUIDES, SRC, section_id="s_a", name="A", tpl="text"))
    await do(store, ops.move_section(GUIDES, "s_a", INTRO))

    assert await do(store, ops.section_ids(GUIDES)) == []
    assert await do(store, ops.section_ids(INTRO)) == ["s_a"]
    section = Space.pages.pages["docs"].pages["guides"].pages["intro"].sections["s_a"]
    assert await do(store, section.name) == "A"
    assert await do(store, section.tpl) == "text"
    assert await do(store, ops.snippet_of(INTRO, "s_a")) == SRC


async def test_move_section_on_a_missing_section_is_harmless(store):
    await tree(store)
    await do(store, ops.move_section(GUIDES, "s_nope", DOCS))

    assert await do(store, ops.section_ids(DOCS)) == []


async def test_snippet_of_is_empty_for_a_section_that_is_not_there(store):
    await tree(store)

    assert await do(store, ops.snippet_of(GUIDES, "s_nope")) is EMPTY


# --- a path that is runtime data --------------------------------------------


async def test_title_of_takes_a_path_read_out_of_another_fabric(store):
    """The browser case: the route arrives as data, with no python in the loop."""
    await tree(store)
    data = {}
    await do(store, Route.path.set(["docs", "guides", "intro"]), data=data)

    assert await do(store, ops.title_of(Route.path), data=data) == "Intro"


async def test_rename_page_takes_a_path_read_out_of_another_fabric(store):
    await tree(store)
    data = {}
    await do(store, Route.path.set(["docs", "guides"]), data=data)
    await do(store, ops.rename_page(Route.path, "Renamed"), data=data)

    assert await do(store, ops.title_of(GUIDES)) == "Renamed"
