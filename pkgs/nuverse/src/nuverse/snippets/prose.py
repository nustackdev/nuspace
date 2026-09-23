"""The ``prose`` snippet: a document cell.

One prose surface over a string in its own state, synced both ways. Every
prose cell holds exactly this prog, and that is how the viewer tells one
apart: what the person wrote lives in the state, not here.
"""

from __future__ import annotations

from nuspace import Snippet


__all__ = ["SNIPPET", "SOURCE"]


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
        >> body.set_placeholder(nu.Str("Write, or press / for blocks"))
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

SNIPPET = Snippet("prose", "Text", SOURCE)
