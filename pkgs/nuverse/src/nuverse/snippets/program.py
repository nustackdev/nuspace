"""The ``program`` snippet: what a fresh code cell starts as.

One key in its own state, then done.
"""

from __future__ import annotations

from nuspace import Snippet


__all__ = ["SNIPPET", "SOURCE"]


SOURCE = """\
import nu
import nustd.kv
import nuspace


class Note(nuspace.CellState):
    hello = nustd.kv.StrRef.slot()


def out():
    # Bare state: the kernel lands it under this cell, whichever it is.
    return Note.hello.set(nu.Str("world"))
"""

SNIPPET = Snippet("program", "Program", SOURCE)
