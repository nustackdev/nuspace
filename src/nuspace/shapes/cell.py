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
    """A program. Structure only.

    ``prog`` is python source whose entry point returns a Nu tree. ``version``
    counts its writes: every cell run records the version it ran, so a live
    one running an older prog is told apart without reading source. A cell
    carries no run info: runs, their output and their errors live under
    ``Space.kernel``.

    Its state is not here: it lives in the state store, at
    ``States.planes[p].cells[c]`` (:mod:`nuspace.shapes.states`).

    ``props`` is what nuspace reads to work (:class:`CellProps`). ``meta``
    is free, for anything else.
    """

    name = nustd.kv.StrRef.slot()
    prog = nustd.kv.ProgramRef.slot()
    version = nustd.kv.IntRef.slot()
    props = nustd.kv.ShapeRef.slot(CellProps)
    meta = nustd.kv.DictRef.slot(object)
