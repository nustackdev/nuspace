"""Cell: a program, the irreducible thing a space holds."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Cell"]


class Cell(nu.Shape):
    """A program and the state it owns. Structure only.

    ``prog`` is python source whose entry point returns a Nu tree. How and
    when it runs is the caller's argument to ``up``, so a cell carries no run
    info: runs, their output and their errors live under ``Space.kernel``.

    ``state`` is the program's own subtree. Its shape comes from the program's
    :class:`~nuspace.shapes.state.CellState` classes, not from here, so it is
    an untyped dict at this level and the rerooted slots resolve under it.
    """

    name = nustd.kv.StrRef.slot()
    prog = nustd.kv.ProgramRef.slot()
    meta = nustd.kv.DictRef.slot(object)
    state = nustd.kv.DictRef.slot(object)
