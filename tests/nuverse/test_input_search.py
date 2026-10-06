"""The input snippets' search: an input cell is a hit when its value is the query."""

from __future__ import annotations

import datetime

import pytest

import nu
from nuspace import ops
from nuspace.system import search
from nuverse.snippets import SNIPPETS, date, number, select, slider, switch, text_input


@pytest.mark.parametrize(
    ("kind", "value", "hits", "misses", "excerpt"),
    [
        (text_input, "Basil", ["basil", "  BASIL "], ["bas", "basil leaf"], "price: Basil"),
        (select, "Two", ["two"], ["tw", "three"], "price: Two"),
        (number, 42.0, ["42", "42.0", " 42 "], ["4", "abc", ""], "price: 42"),
        (slider, 7.5, ["7.5"], ["7", "75"], "price: 7.5"),
        (switch, True, ["on", "TRUE", "yes"], ["off", "no", "maybe"], "price: on"),
        (switch, False, ["off", "false", "no"], ["on", "yes"], "price: off"),
        (
            date,
            datetime.date(2026, 10, 6),
            ["2026-10-06"],
            ["2026-10", "06/10/2026"],
            "price: 2026-10-06",
        ),
    ],
    ids=lambda v: getattr(v, "__name__", None),
)
async def test_an_input_hits_on_its_value_only(store, kind, value, hits, misses, excerpt):
    await store.run(
        ops.add_plane("p", ui=True, backend="async")
        >> ops.insert_snippet("p", kind.SNIPPET, cell_id="c")
        >> ops.rename_cell("c", "price")
        >> kind.set_value("c", value)
    )
    for query in hits:
        assert await store.read(kind.search(nu.Str(query), nu.Str("c"))) == [{"excerpt": excerpt}]
    for query in misses:
        assert await store.read(kind.search(nu.Str(query), nu.Str("c"))) == []


@pytest.mark.parametrize("kind", [text_input, select, number, slider, switch, date])
async def test_an_input_never_set_is_nothing_to_find(store, kind):
    await store.run(
        ops.add_plane("p", ui=True, backend="async")
        >> ops.insert_snippet("p", kind.SNIPPET, cell_id="c")
    )
    for query in ("", "0", "off", "false"):
        assert await store.read(kind.search(nu.Str(query), nu.Str("c"))) == []


def test_every_input_is_searchable():
    names = set(search.searchable(SNIPPETS))
    assert {"text_input", "number", "slider", "switch", "select", "date"} <= names


async def test_a_search_finds_an_input_by_its_value(store):
    from tests.nuverse.test_text_search import _loaded, _searched

    await store.run(
        ops.add_plane("p", name="Budget", ui=True, backend="async")
        >> ops.insert_snippet("p", number.SNIPPET, cell_id="n")
        >> ops.rename_cell("n", "limit")
        >> number.set_value("n", 250)
        >> ops.insert_snippet("p", number.SNIPPET, cell_id="m")
        >> number.set_value("m", 25)
    )
    pid = await _searched(store, "250", ["number"], False, searchers=search.searchable(SNIPPETS))
    (cell,) = await store.read(ops.cells(pid))
    await store.run(await store.run(_loaded(pid, cell)))
    hits = await store.read(ops.plane_state(pid, search.Search.hits.extract()))
    assert [(h["cell"], h["excerpt"], h["by"]) for h in hits] == [("n", "limit: 250", "number")]
