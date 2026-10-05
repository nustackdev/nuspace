"""A program cell: one key in its own state, then done."""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import ops


__all__ = ["Note", "out"]


class Note(nuspace.CellState):
    """The program cell's state."""

    hello = nustd.kv.StrRef.slot()


def out() -> nu.Nu:
    """Write its one key."""
    # Bare state: the kernel lands it under this cell, whichever it is.
    # The write is one commit to the state store, bracketed here.
    return ops.atomic_state(Note.hello.set(nu.Str("world")))
