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
from nuspace import ops


class Note(nuspace.CellState):
    hello = nustd.kv.StrRef.slot()


def out():
    # Bare state: the kernel lands it under this cell, whichever it is.
    # The write is one commit to the state store, bracketed here.
    return ops.atomic_state(Note.hello.set(nu.Str("world")))
"""

SNIPPET = Snippet("program", "Program", SOURCE)
