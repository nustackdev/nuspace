"""Every pages primitive, against a real on-disk RocksDB.

No workers and no runner here: an op is a tree, so the whole test is "run the
tree, read the store back". Pages are flat, so the interesting property is no
longer depth -- it is that ``parent`` and ``children`` never disagree, which
``test_invariant.py`` walks the whole space for.
"""

from __future__ import annotations

import nu
from nu.lang import EMPTY
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID, ops

from .conftest import SRC, do


ROOT = ROOT_PAGE_ID


def section_keys(page_id):
    """The section dict's own keys, to check them against ``section_order``."""
    return nu.list(Space.pages[page_id].sections.keys())


async def tree(store):
    """Three pages, three levels: root > docs > guides > intro."""
    await do(store, ops.init_space())
    await do(store, ops.add_page(ROOT, page_id="docs", title="Docs"))
    await do(store, ops.add_page("docs", page_id="guides", title="Guides"))
    await do(store, ops.add_page("guides", page_id="intro", title="Intro"))


# --- the root page ----------------------------------------------------------


async def test_init_space_writes_the_root_page_on_a_cold_store(store):
    await do(store, ops.init_space())

    assert await do(store, ops.page_ids()) == [ROOT]
    assert await do(store, ops.title_of(ROOT)) == "Home"
    # The root parents itself, so every `parent` names a page that is there.
    assert await do(store, ops.parent_of(ROOT)) == ROOT
    assert await do(store, ops.children_of(ROOT)) == []


async def test_init_space_twice_does_not_disturb_the_root(store):
    await do(store, ops.init_space())
    await do(store, ops.rename_page(ROOT, "Renamed"))
    await do(store, ops.init_space())

    assert await do(store, ops.title_of(ROOT)) == "Renamed"


async def test_add_page_under_a_parent_that_is_not_there_writes_nothing(store):
    await do(store, ops.add_page("nope", page_id="p_one"))

    assert await do(store, ops.page_ids()) == []


# --- addressing -------------------------------------------------------------


async def test_every_page_is_one_lookup_away_whatever_its_depth(store):
    await tree(store)

    assert await do(store, ops.title_of("intro")) == "Intro"
    assert await do(store, Space.pages["intro"].title) == "Intro"
    assert await do(store, ops.page_ids()) == ["docs", "guides", "intro", ROOT]


async def test_page_exists_answers_for_any_id(store):
    await tree(store)

    assert await do(store, ops.page_exists("intro")) is True
    assert await do(store, ops.page_exists("nope")) is False
    assert await do(store, ops.page_exists(ROOT)) is True


async def test_parent_and_children_read_back_both_ways(store):
    await tree(store)

    assert await do(store, ops.parent_of("guides")) == "docs"
    assert await do(store, ops.children_of("docs")) == ["guides"]
    assert await do(store, ops.parent_of("nope")) is EMPTY
    assert await do(store, ops.children_of("nope")) == []


# --- pages ------------------------------------------------------------------


async def test_add_page_defaults_the_title_to_the_id(store):
    await do(store, ops.init_space())
    await do(store, ops.add_page(ROOT, page_id="p_one"))

    assert await do(store, ops.title_of("p_one")) == "p_one"


async def test_add_page_with_no_id_mints_an_ordered_one(store):
    await do(store, ops.init_space())
    await do(store, ops.add_page(ROOT))
    await do(store, ops.add_page(ROOT))

    ids = await do(store, ops.children_of(ROOT))
    assert len(ids) == 2
    assert all(i.startswith("p_") for i in ids)
    # Minted in creation order, and children are in insertion order.
    assert ids == sorted(ids)


async def test_add_page_appends_to_the_parents_children(store):
    await tree(store)
    await do(store, ops.add_page("docs", page_id="ref", title="Reference"))

    assert await do(store, ops.children_of("docs")) == ["guides", "ref"]


async def test_add_page_run_twice_does_not_double_the_link(store):
    await tree(store)
    await do(store, ops.add_page("docs", page_id="ref"))
    await do(store, ops.add_page("docs", page_id="ref"))

    assert await do(store, ops.children_of("docs")) == ["guides", "ref"]


async def test_rename_page_moves_the_title_and_not_the_id(store):
    await tree(store)
    await do(store, ops.rename_page("intro", "Getting started"))

    assert await do(store, ops.title_of("intro")) == "Getting started"
    assert await do(store, ops.children_of("guides")) == ["intro"]


async def test_rename_page_on_a_missing_page_writes_nothing(store):
    await tree(store)
    await do(store, ops.rename_page("nope", "Nope"))

    assert await do(store, ops.page_exists("nope")) is False


async def test_title_of_is_empty_for_a_page_that_is_not_there(store):
    await tree(store)

    assert await do(store, ops.title_of("nope")) is EMPTY


async def test_remove_page_takes_its_whole_subtree_with_it(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a"))
    await do(store, ops.remove_page("docs"))

    assert await do(store, ops.page_ids()) == [ROOT]
    assert await do(store, ops.page_exists("guides")) is False
    assert await do(store, ops.page_exists("intro")) is False
    assert await do(store, ops.section_ids("guides")) == []


async def test_remove_page_unlinks_it_from_its_parent(store):
    await tree(store)
    await do(store, ops.remove_page("docs"))

    assert await do(store, ops.children_of(ROOT)) == []


async def test_remove_page_leaves_its_siblings(store):
    await tree(store)
    await do(store, ops.add_page("docs", page_id="ref", title="Reference"))
    await do(store, ops.remove_page("ref"))

    assert await do(store, ops.children_of("docs")) == ["guides"]
    assert await do(store, ops.page_exists("guides")) is True


async def test_remove_page_walks_a_wide_subtree_too(store):
    """The worklist is breadth-first, so siblings at every level go as well."""
    await do(store, ops.init_space())
    await do(store, ops.add_page(ROOT, page_id="a"))
    for parent, kid in (("a", "b"), ("a", "c"), ("b", "d"), ("c", "e"), ("d", "f")):
        await do(store, ops.add_page(parent, page_id=kid))
    await do(store, ops.remove_page("a"))

    assert await do(store, ops.page_ids()) == [ROOT]


async def test_remove_page_on_a_missing_page_is_harmless(store):
    await tree(store)
    await do(store, ops.remove_page("nope"))

    assert await do(store, ops.children_of("docs")) == ["guides"]


async def test_remove_page_can_take_the_root(store):
    """Nothing special about the root: it is a row like any other."""
    await tree(store)
    await do(store, ops.remove_page(ROOT))

    assert await do(store, ops.page_ids()) == []


async def test_move_page_relinks_both_sides(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a", name="A"))
    await do(store, ops.move_page("guides", ROOT))

    assert await do(store, ops.children_of(ROOT)) == ["docs", "guides"]
    assert await do(store, ops.children_of("docs")) == []
    assert await do(store, ops.parent_of("guides")) == ROOT
    # Nothing was copied, so the subtree and the sections came along for free.
    assert await do(store, ops.children_of("guides")) == ["intro"]
    assert await do(store, ops.title_of("intro")) == "Intro"
    assert await do(store, ops.section_ids("guides")) == ["s_a"]


async def test_move_page_lands_at_the_index_given(store):
    await tree(store)
    await do(store, ops.add_page(ROOT, page_id="a"))
    await do(store, ops.add_page(ROOT, page_id="b"))
    await do(store, ops.move_page("guides", ROOT, index=1))

    assert await do(store, ops.children_of(ROOT)) == ["docs", "guides", "a", "b"]


async def test_move_page_refuses_to_move_under_itself(store):
    await tree(store)
    await do(store, ops.move_page("docs", "docs"))

    assert await do(store, ops.parent_of("docs")) == ROOT
    assert await do(store, ops.children_of("docs")) == ["guides"]


async def test_move_page_onto_a_parent_that_is_not_there_writes_nothing(store):
    await tree(store)
    await do(store, ops.move_page("guides", "nope"))

    assert await do(store, ops.parent_of("guides")) == "docs"


async def test_reorder_pages_puts_the_children_in_the_order_given(store):
    await tree(store)
    for pid in ("a", "b"):
        await do(store, ops.add_page("docs", page_id=pid))
    await do(store, ops.reorder_pages("docs", ["b", "guides", "a"]))

    assert await do(store, ops.children_of("docs")) == ["b", "guides", "a"]


async def test_reorder_pages_skips_strangers_and_keeps_the_unlisted(store):
    await tree(store)
    await do(store, ops.add_page("docs", page_id="a"))
    await do(store, ops.reorder_pages("docs", ["nope", "a"]))

    assert await do(store, ops.children_of("docs")) == ["a", "guides"]


async def test_reorder_pages_with_nothing_to_do_is_harmless(store):
    await tree(store)
    await do(store, ops.reorder_pages("docs", []))

    assert await do(store, ops.children_of("docs")) == ["guides"]


# --- sections ---------------------------------------------------------------


async def test_add_section_writes_every_field(store):
    await tree(store)
    await do(
        store,
        ops.add_section("guides", SRC, section_id="s_a", name="A", tpl="text", policy="manual"),
    )

    section = Space.pages["guides"].sections["s_a"]
    assert await do(store, ops.snippet_of("guides", "s_a")) == SRC
    assert await do(store, section.name) == "A"
    assert await do(store, section.tpl) == "text"
    assert await do(store, section.policy) == "manual"


async def test_add_section_defaults_the_name_to_the_id_and_the_tpl_to_program(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a"))

    section = Space.pages["guides"].sections["s_a"]
    assert await do(store, section.name) == "s_a"
    assert await do(store, section.tpl) == "program"
    assert await do(store, section.policy) == "always"


async def test_add_section_with_no_id_mints_an_ordered_one(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC))
    await do(store, ops.add_section("guides", SRC))

    ids = await do(store, ops.section_ids("guides"))
    assert len(ids) == 2
    assert all(i.startswith("s_") for i in ids)
    assert ids == sorted(ids)


async def test_add_section_onto_a_page_that_is_not_there_writes_nothing(store):
    await tree(store)
    await do(store, ops.add_section("nope", SRC, section_id="s_a"))

    assert await do(store, ops.section_ids("nope")) == []
    assert await do(store, ops.snippet_of("nope", "s_a")) is EMPTY


async def test_add_section_lands_each_new_section_last(store):
    await tree(store)
    for sid in ("s_a", "s_b", "s_c"):
        await do(store, ops.add_section("guides", SRC, section_id=sid))

    assert await do(store, ops.section_ids("guides")) == ["s_a", "s_b", "s_c"]


async def test_sections_on_two_pages_do_not_see_each_other(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a"))
    await do(store, ops.add_section("docs", SRC, section_id="s_b"))

    assert await do(store, ops.section_ids("guides")) == ["s_a"]
    assert await do(store, ops.section_ids("docs")) == ["s_b"]


async def test_reorder_sections_puts_them_in_the_order_given(store):
    await tree(store)
    for sid in ("s_a", "s_b", "s_c"):
        await do(store, ops.add_section("guides", SRC, section_id=sid))
    await do(store, ops.reorder_sections("guides", ["s_c", "s_a", "s_b"]))

    assert await do(store, ops.section_ids("guides")) == ["s_c", "s_a", "s_b"]


async def test_reorder_sections_skips_strangers_and_keeps_the_unlisted(store):
    await tree(store)
    for sid in ("s_a", "s_b"):
        await do(store, ops.add_section("guides", SRC, section_id=sid))
    await do(store, ops.reorder_sections("guides", ["s_nope", "s_b"]))

    assert await do(store, ops.section_ids("guides")) == ["s_b", "s_a"]


async def test_reorder_sections_with_nothing_to_do_is_a_noop(store):
    await tree(store)
    await do(store, ops.reorder_sections("guides", []))

    assert await do(store, ops.section_ids("guides")) == []


async def test_set_snippet_replaces_the_source(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a"))
    await do(store, ops.set_snippet("guides", "s_a", "edited"))

    assert await do(store, ops.snippet_of("guides", "s_a")) == "edited"


async def test_set_snippet_does_not_conjure_a_section(store):
    await tree(store)
    await do(store, ops.set_snippet("guides", "s_nope", "edited"))

    assert await do(store, ops.section_ids("guides")) == []
    assert await do(store, ops.snippet_of("guides", "s_nope")) is EMPTY


async def test_set_tpl_replaces_the_tpl_and_leaves_the_snippet(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a"))
    await do(store, ops.set_tpl("guides", "s_a", "text"))

    assert await do(store, Space.pages["guides"].sections["s_a"].tpl) == "text"
    assert await do(store, ops.snippet_of("guides", "s_a")) == SRC


async def test_remove_section_drops_the_row_and_the_order_entry(store):
    await tree(store)
    for sid in ("s_a", "s_b"):
        await do(store, ops.add_section("guides", SRC, section_id=sid))
    await do(store, ops.remove_section("guides", "s_a"))

    assert await do(store, ops.section_ids("guides")) == ["s_b"]
    assert await do(store, section_keys("guides")) == ["s_b"]


async def test_remove_section_on_a_missing_section_is_harmless(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a"))
    await do(store, ops.remove_section("guides", "s_nope"))

    assert await do(store, ops.section_ids("guides")) == ["s_a"]


async def test_move_section_carries_every_field_to_the_other_page(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a", name="A", tpl="text"))
    await do(store, ops.move_section("guides", "s_a", "intro"))

    assert await do(store, ops.section_ids("guides")) == []
    assert await do(store, ops.section_ids("intro")) == ["s_a"]
    section = Space.pages["intro"].sections["s_a"]
    assert await do(store, section.name) == "A"
    assert await do(store, section.tpl) == "text"
    assert await do(store, ops.snippet_of("intro", "s_a")) == SRC


async def test_move_section_lands_at_the_index_given(store):
    await tree(store)
    for sid in ("s_a", "s_b"):
        await do(store, ops.add_section("intro", SRC, section_id=sid))
    await do(store, ops.add_section("guides", SRC, section_id="s_c"))
    await do(store, ops.move_section("guides", "s_c", "intro", index=1))

    assert await do(store, ops.section_ids("intro")) == ["s_a", "s_c", "s_b"]


async def test_move_section_onto_a_page_that_is_not_there_writes_nothing(store):
    await tree(store)
    await do(store, ops.add_section("guides", SRC, section_id="s_a"))
    await do(store, ops.move_section("guides", "s_a", "nope"))

    assert await do(store, ops.section_ids("guides")) == ["s_a"]


async def test_move_section_on_a_missing_section_is_harmless(store):
    await tree(store)
    await do(store, ops.move_section("guides", "s_nope", "docs"))

    assert await do(store, ops.section_ids("docs")) == []


async def test_snippet_of_is_empty_for_a_section_that_is_not_there(store):
    await tree(store)

    assert await do(store, ops.snippet_of("guides", "s_nope")) is EMPTY
