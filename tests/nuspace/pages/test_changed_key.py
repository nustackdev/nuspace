"""What a page's sections subscription actually delivers, pinned.

``changed_section_index`` is a measurement, not a guess: these tests record
the real keys the observer hands ``ReactForever`` and assert the section id is
where the runner slices for it, at the root page and three levels down. If the
key shape ever changes this fails loudly instead of the runner silently
reconciling the wrong section.
"""

from __future__ import annotations

from ast import literal_eval

import pytest

import nu
import nu.kv
from nuspace.core.shapes import Space
from nuspace.pages import ops
from nuspace.pages.runner import changed_section_index

from .conftest import SRC, read_state


pytestmark = pytest.mark.timeout(120)


DEEP = ["docs", "guides", "intro"]


def _record(page_path):
    """Append every key the page's sections subscription delivers into state."""
    key = nu.TupleAttrRef("k")
    return nu.ReactForever(
        ops.page_at(page_path).sections.on_change(),
        Space.state.set_item(nu.Str("key.") + nu.ToStr(nu.Len(Space.state)), nu.ToStr(key)),
        changed_key="k",
    )


async def _keys(store, page_path, script):
    """Run ``script`` beside a recorder and give back the keys it saw, in order."""
    tree = nu.With(
        nu.kv.rocksdb_navigator(store),
        body=nu.kv.auto_flow_atomic(
            ops.page_at(page_path).sections.init(nu.Dict.create())
            >> nu.Race(_record(page_path) | script, nu.DelayedDo(nu.Float(3.0), nu.Noop())),
            scope=Space,
        ),
    )
    await nu.arun(tree, nu.Context(), max_parallel=16)
    state = await read_state(store)
    return [literal_eval(v) for k, v in sorted(state.items()) if k.startswith("key.")]


@pytest.mark.parametrize("page_path", [[], ["docs"], DEEP])
async def test_the_section_id_sits_at_the_pinned_index(store, page_path):
    """Add, edit and delete, and read the section id out of every key."""
    index = changed_section_index(page_path)
    script = (
        nu.DelayedDo(0.2, ops.add_section(page_path, SRC, section_id="s_one"))
        >> nu.DelayedDo(0.2, ops.add_section(page_path, SRC, section_id="s_two"))
        >> nu.DelayedDo(0.2, ops.set_snippet(page_path, "s_one", "edited"))
        >> nu.DelayedDo(0.2, ops.remove_section(page_path, "s_two"))
    )
    keys = await _keys(store, page_path, script)

    assert keys, "the subscription delivered nothing at all"
    # Absolute keys are rooted, so every key starts the same way.
    prefix = ("/", "pages", *[seg for pid in page_path for seg in ("pages", pid)], "sections")
    assert {tuple(k[: len(prefix)]) for k in keys} == {prefix}
    assert len(prefix) == index
    # Every key long enough to name a section names one of ours, at that index.
    named = [k[index] for k in keys if len(k) > index]
    assert set(named) == {"s_one", "s_two"}
    # Both row-level and field-level keys occur, and the index works for both.
    assert any(len(k) == index + 1 for k in keys)
    assert any(len(k) > index + 1 for k in keys)


async def test_a_bare_container_key_occurs_and_names_no_section(store):
    """The dict itself changing is reported too, with nothing at the index.

    This is why the live loop guards on length: slicing this one would raise
    IndexError inside the react loop and leave the driver deaf.
    """
    keys = await _keys(store, [], nu.DelayedDo(0.2, ops.add_section([], SRC, section_id="s_one")))

    assert any(len(k) <= changed_section_index([]) for k in keys)
