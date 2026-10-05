"""The text snippet's search: a text cell is a hit when its text holds the query."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.utils import atomic_state
from nuspace.shapes import Reroot, Space
from nuspace.system import search
from nuspace.system.kernel.body import Rewrites
from nuverse.snippets import SNIPPETS, prose


def _text(plane: str, cell: str, body: str) -> nu.Nu:
    """A text cell holding ``body``, as its program would keep it."""
    kept = atomic_state(ops.cell_state(plane, cell, prose.Doc.text.set(body)))
    return ops.insert_snippet(plane, prose.SNIPPET, cell_id=cell) >> kept


async def _searched(store, *args: object, **kwargs: object) -> str:
    """Search through ``store``. The new search is the newest child of ``SEARCHES``."""
    await store.run(search.search(*args, **kwargs))
    return (await store.read(ops.children(search.SEARCHES)))[-1]


def test_only_text_is_searchable_and_by_its_module_function():
    assert search.searchable(SNIPPETS) == {"text": "nuverse.snippets.prose:search"}
    # The state the search reads is the state the prog keeps.
    assert "class Doc(nuspace.CellState):\n    text = nustd.kv.StrRef.slot()" in prose.SOURCE


async def test_text_search_hits_a_cell_holding_the_query(store):
    await store.run(
        ops.add_plane("p", ui=True, backend="async") >> _text("p", "a", "Water the Basil daily")
    )
    await store.run(ops.insert_snippet("p", prose.SNIPPET, cell_id="empty"))
    got = await store.read(prose.search(nu.Str("basil"), nu.Str("p"), nu.Str("a")))
    assert got == [{"plane": "p", "cell": "a", "excerpt": "Water the Basil daily"}]
    assert await store.read(prose.search(nu.Str("mint"), nu.Str("p"), nu.Str("a"))) == []
    # A text cell nobody typed in yet holds nothing to find.
    assert await store.read(prose.search(nu.Str("basil"), nu.Str("p"), nu.Str("empty"))) == []


async def test_a_search_over_text_cells(store):
    await store.run(
        ops.add_plane("p", name="Herbs", ui=True, backend="async")
        >> _text("p", "a", "Basil likes sun")
        >> _text("p", "b", "Mint spreads")
    )
    searchers = search.searchable(SNIPPETS)
    pid = await _searched(store, "BASIL", ["text"], True, searchers=searchers)
    await store.run(await store.run(_loaded(pid)))
    hits = await store.read(ops.plane_state(pid, search.Search.hits.extract()))
    assert [(h["cell"], h["excerpt"], h["by"]) for h in hits] == [("a", "Basil likes sun", "text")]


def _loaded(plane: str) -> nu.Nu:
    """The search's cell loaded as the kernel loads it."""
    rewrite = Rewrites(Reroot(plane, search.CELL))
    prog = Space.planes[plane].cells[search.CELL].prog
    return nustd.kv.Snapshot(
        prog.load(scope={"plane": plane, "cell": search.CELL}, rewrite=rewrite), scope=Space
    )
