"""A text cell: one editable markdown surface over a string in its own state, synced both ways.

What the person wrote lives in the state, not in the prog, so ops reach it
from anywhere and search finds it. The viewer draws it like any other cell.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops


__all__ = ["Doc", "out"]


class Doc(nuspace.CellState):
    """A text cell's state: the markdown it holds."""

    text = nustd.kv.StrRef.slot()


def out() -> nu.Nu:
    """The editor over :attr:`Doc.text`, both ways, for as long as the cell runs."""
    body = nustd.ui.MarkdownRef("text")
    # Brackets placed per step: each read and each keystroke's write is its own.
    return ops.bracketed(
        body.set(Doc.text.fallback(""))
        >> body.set_editable(True)
        >> body.set_placeholder("Write, or press / for cells")
        >> nu.ParallelAsync(
            # This tab typed: keep it. Every other tab on the plane, and every
            # op reading the text, hears it through the store.
            nu.ReactForever(body.on_change(), Doc.text.set(nu.Str(body))),
            # Somebody else typed, or an op set it: show it. The echo back to
            # the author is a no-op, the text is already what it says.
            nu.ReactForever(Doc.text.on_change(), body.set(nu.str(Doc.text))),
        )
    )
