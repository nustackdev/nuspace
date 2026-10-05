"""The text snippet's search: a text cell is a hit when its text holds the query."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system import search
from nuspace.system.kernel.body import Rewrites
from nuverse.snippets import SNIPPETS, prose


def _text(plane: str, cell: str, body: str) -> nu.Nu:
    """A text cell holding ``body``, set the way any program sets it."""
    return ops.insert_snippet(plane, prose.SNIPPET, cell_id=cell) >> prose.set_text(cell, body)


async def _searched(store, *args: object, **kwargs: object) -> str:
    """Search through ``store``. The new search is the newest child of ``SEARCHES``."""
    await store.run(search.search(*args, **kwargs))
    return (await store.read(ops.children(search.SEARCHES)))[-1]


def test_text_is_searchable_by_a_module_function():
    assert search.searchable(SNIPPETS) == {"text": "nuverse.snippets.prose.ops:search"}


async def test_text_search_hits_a_cell_holding_the_query(store):
    await store.run(
        ops.add_plane("p", ui=True, backend="async") >> _text("p", "a", "Water the Basil daily")
    )
    await store.run(ops.insert_snippet("p", prose.SNIPPET, cell_id="empty"))
    got = await store.read(prose.search(nu.Str("basil"), nu.Str("a")))
    assert got == [{"excerpt": "Water the Basil daily"}]
    assert await store.read(prose.search(nu.Str("mint"), nu.Str("a"))) == []
    # A text cell nobody typed in yet holds nothing to find.
    assert await store.read(prose.search(nu.Str("basil"), nu.Str("empty"))) == []


async def test_a_search_over_text_cells(store):
    await store.run(
        ops.add_plane("p", name="Herbs", ui=True, backend="async")
        >> _text("p", "a", "Basil likes sun")
        >> _text("p", "b", "Mint spreads")
    )
    searchers = search.searchable(SNIPPETS)
    pid = await _searched(store, "BASIL", ["text"], True, searchers=searchers)
    (cell,) = await store.read(ops.cells(pid))
    await store.run(await store.run(_loaded(pid, cell)))
    hits = await store.read(ops.plane_state(pid, search.Search.hits.extract()))
    assert [(h["cell"], h["excerpt"], h["by"]) for h in hits] == [("a", "Basil likes sun", "text")]


def _loaded(plane: str, cell: str) -> nu.Nu:
    """The search's cell loaded as the kernel loads it."""
    rewrite = Rewrites(Reroot(plane, cell))
    prog = Space.cells[cell].prog
    return nustd.kv.Snapshot(
        prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite), scope=Space
    )
