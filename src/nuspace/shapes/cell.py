"""Cell: a program, the irreducible thing a space holds."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Cell", "CellProps"]


class CellProps(nu.Shape):
    """What nuspace itself reads off a cell to work. Typed, unlike ``meta``.

    ``made_by`` names the snippet the cell was made from (``""`` for none).
    A cell without one is not of any snippet's type.

    ``has_ui`` says whether the cell's program draws: its constructed tree
    holds a ui ref. Worked out whenever the prog is written, never by hand.
    Unwritten on cells older than it, which read as maybe drawing.
    """

    made_by = nustd.kv.StrRef.slot()
    has_ui = nustd.kv.BoolRef.slot()


class Cell(nu.Shape):
    """A program and the state it owns. Structure only.

    ``prog`` is python source whose entry point returns a Nu tree. How and
    when it runs is the caller's argument to ``up``, so a cell carries no run
    info: runs, their output and their errors live under ``Space.kernel``.

    ``state`` is the program's own subtree. Its shape comes from the program's
    :class:`~nuspace.shapes.state.CellState` classes, not from here, so it is
    an untyped dict at this level and the rerooted slots resolve under it.

    ``props`` is what nuspace reads to work (:class:`CellProps`). ``meta``
    is free, for anything else.
    """

    name = nustd.kv.StrRef.slot()
    prog = nustd.kv.ProgramRef.slot()
    props = nustd.kv.ShapeRef.slot(CellProps)
    meta = nustd.kv.DictRef.slot(object)
    state = nustd.kv.DictRef.slot(object)
