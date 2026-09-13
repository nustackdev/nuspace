"""What a page's sections subscription actually delivers, pinned.

``CHANGED_SECTION_INDEX`` is a measurement, not a guess: these tests record
the real keys the observer hands ``ReactForever`` and assert the section id is
where the runner slices for it. Pages are flat, so the index is a constant --
the same for a top page and one six levels down -- and this is what says so.
"""

from __future__ import annotations

from ast import literal_eval

import pytest

import nu
import nu.kv
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID, ops
from nuspace.pages.runner import CHANGED_SECTION_INDEX
from nuspace.web.pages.session import CHANGED_PAGE_INDEX, SECTIONS_INDEX, SECTIONS_SEGMENT

from .conftest import SRC, do, read_state


pytestmark = pytest.mark.timeout(120)


DEEP = "intro"


async def _seed(store):
    """root > docs > guides > intro, so a deep page is available to subscribe to."""
    await do(store, ops.init_space())
    await do(store, ops.add_page(ROOT_PAGE_ID, page_id="docs"))
    await do(store, ops.add_page("docs", page_id="guides"))
    await do(store, ops.add_page("guides", page_id=DEEP))


def _record(page_id):
    """Append every key the page's sections subscription delivers into state."""
    key = nu.TupleAttrRef("k")
    return nu.ReactForever(
        Space.pages[page_id].sections.on_change(),
        Space.state.set_item(nu.Str("key.") + nu.ToStr(nu.Len(Space.state)), nu.ToStr(key)),
        changed_key="k",
    )


def _record_space():
    """The same recorder, over every page in the space rather than one."""
    key = nu.TupleAttrRef("k")
    return nu.ReactForever(
        Space.pages.on_change(),
        Space.state.set_item(nu.Str("key.") + nu.ToStr(nu.Len(Space.state)), nu.ToStr(key)),
        changed_key="k",
    )


async def _keys(store, page_id, script, recorder=None):
    """Run ``script`` beside a recorder and give back the keys it saw, in order."""
    watch = _record(page_id) if recorder is None else recorder
    tree = nu.With(
        nu.kv.rocksdb_navigator(store),
        body=nu.kv.auto_flow_atomic(
            Space.pages[page_id].sections.init(nu.Dict.create())
            >> nu.Race(watch | script, nu.DelayedDo(nu.Float(3.0), nu.Noop())),
            scope=Space,
        ),
    )
    await nu.arun(tree, nu.Context(), max_parallel=16)
    state = await read_state(store)
    return [literal_eval(v) for k, v in sorted(state.items()) if k.startswith("key.")]


@pytest.mark.parametrize("page_id", [ROOT_PAGE_ID, "docs", DEEP])
async def test_the_section_id_sits_at_the_pinned_index(store, page_id):
    """Add, edit and delete, and read the section id out of every key."""
    await _seed(store)
    script = (
        nu.DelayedDo(0.2, ops.add_section(page_id, SRC, section_id="s_one"))
        >> nu.DelayedDo(0.2, ops.add_section(page_id, SRC, section_id="s_two"))
        >> nu.DelayedDo(0.2, ops.set_snippet(page_id, "s_one", "edited"))
        >> nu.DelayedDo(0.2, ops.remove_section(page_id, "s_two"))
    )
    keys = await _keys(store, page_id, script)

    assert keys, "the subscription delivered nothing at all"
    # Absolute keys are rooted, and a flat page puts the same four entries in
    # front of the section id no matter how deep the page sits in the tree.
    prefix = ("/", "pages", page_id, "sections")
    assert {tuple(k[: len(prefix)]) for k in keys} == {prefix}
    assert len(prefix) == CHANGED_SECTION_INDEX
    # Every key long enough to name a section names one of ours, at that index.
    named = [k[CHANGED_SECTION_INDEX] for k in keys if len(k) > CHANGED_SECTION_INDEX]
    assert set(named) == {"s_one", "s_two"}
    # Both row-level and field-level keys occur, and the index works for both.
    assert any(len(k) == CHANGED_SECTION_INDEX + 1 for k in keys)
    assert any(len(k) > CHANGED_SECTION_INDEX + 1 for k in keys)


async def test_a_bare_container_key_occurs_and_names_no_section(store):
    """The dict itself changing is reported too, with nothing at the index.

    This is why the live loop guards on length: slicing this one would raise
    IndexError inside the react loop and leave the driver deaf.
    """
    await _seed(store)
    script = nu.DelayedDo(0.2, ops.add_section(ROOT_PAGE_ID, SRC, section_id="s_one"))
    keys = await _keys(store, ROOT_PAGE_ID, script)

    assert any(len(k) <= CHANGED_SECTION_INDEX for k in keys)


async def test_the_space_wide_subscription_carries_both_ids(store):
    """One subscription over every page tells you the page as well as the section.

    This is what lets the per-connection supervisor hold a single stable
    subscription and decide membership off the event rather than by a read.
    """
    await _seed(store)
    script = (
        nu.DelayedDo(0.2, ops.add_section("docs", SRC, section_id="s_docs"))
        >> nu.DelayedDo(0.2, ops.add_section(DEEP, SRC, section_id="s_deep"))
        >> nu.DelayedDo(0.2, ops.rename_page("docs", "Docs"))
    )
    keys = await _keys(store, ROOT_PAGE_ID, script, recorder=_record_space())

    sections = [
        k for k in keys if len(k) > CHANGED_SECTION_INDEX and k[SECTIONS_INDEX] == SECTIONS_SEGMENT
    ]
    assert sections, "nothing named a section at all"
    pairs = {(k[CHANGED_PAGE_INDEX], k[CHANGED_SECTION_INDEX]) for k in sections}
    assert pairs == {("docs", "s_docs"), (DEEP, "s_deep")}
    # And a page slot that is not sections fires on the same subscription,
    # which is why the guard tests the segment rather than only the length.
    assert any(len(k) > SECTIONS_INDEX and k[SECTIONS_INDEX] != SECTIONS_SEGMENT for k in keys)
