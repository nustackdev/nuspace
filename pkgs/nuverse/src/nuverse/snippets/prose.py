"""The ``text`` snippet: a text editor cell.

One prose surface over a string in its own state, synced both ways. What the
person wrote lives in the state, not in the prog. The viewer draws it like any
other cell. Registered under :data:`~nuspace.TEXT`, it is the space's text
snippet, so typing into an empty line starts one.

Searchable (:func:`search`): a text cell is a hit when its text holds the
query, ignoring case.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import TEXT, Snippet, ops
from nuspace.system.search import excerpt, matches


__all__ = ["SNIPPET", "SOURCE", "Doc", "search"]


class Doc(nuspace.CellState):
    """The text cell's state, as :data:`SOURCE` declares it: read by :func:`search`."""

    text = nustd.kv.StrRef.slot()


SOURCE = """\
import nu
import nustd.kv
import nustd.ui
import nuspace


class Doc(nuspace.CellState):
    text = nustd.kv.StrRef.slot()


def out():
    body = nustd.ui.ProseRef("text")
    held = nu.If(Doc.text.exists(), nu.ToStr(Doc.text), nu.Str(""))
    return (
        body.set(held)
        >> body.set_placeholder(nu.Str("Write, or press / for cells"))
        >> nu.ParallelAsync(
            # This tab typed: keep it. Every other tab on the plane hears it
            # through the store.
            nu.ReactForever(body.on_change(), Doc.text.set(nu.Str(body))),
            # Somebody else typed: show it. The echo back to the author is a
            # no-op, the text is already what it says.
            nu.ReactForever(Doc.text.on_change(), body.set(nu.ToStr(Doc.text))),
        )
    )
"""


def search(query: nu.StrArg, plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """One text cell searched: ``[{plane, cell, excerpt}]`` when its text holds ``query``, else ``[]``."""
    held = ops.cell_state(plane, cell, nu.If(Doc.text.exists(), nu.ToStr(Doc.text), nu.Str("")))

    def found(text: nu.ObjectRef) -> nu.Nu:
        hit = nu.List.of(nu.Dict.of(plane=plane, cell=cell, excerpt=excerpt(text, query)))
        return nu.If(matches(text, query), hit, nu.List.of())

    return nu.let(held, found)


SNIPPET = Snippet(TEXT, "Text", SOURCE, search=search)
