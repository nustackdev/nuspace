"""Cell: a program on a plane."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Cell"]


class Cell(nu.Shape):
    """One cell's row at ``Space.cells[id]``. Structure only.

    Identity: as a plane's. ``key`` is an optional handle, slug chars with
    no ``/``, ``""`` for none, unique among live cells through
    ``Space.indexes.cell_keys`` (a plane and a cell may share one), kept
    after removal. ``name`` is display text only.

    ``prog`` is its source. ``fabrics`` lists the fabrics the prog uses
    (only ``"ui"`` is detected for now), worked out from the prog and
    written in the same commit, so it never goes stale. ``version`` counts
    prog writes: a cell run records the version it ran. ``plane`` is the
    plane listing it in its ``cells``; ``cell.move`` can change it, both
    sides in one commit. ``spec`` names the spec it was made from, ``""``
    for none. ``meta`` is free for programs.

    Lifecycle slots as on :class:`~nuspace.shapes.plane.Plane`: a removed
    cell keeps its row, its runs, its state and its content.

    Its state is in the State store, at ``State.cells[id]``.
    """

    name = nustd.kv.StrRef.slot()
    key = nustd.kv.StrRef.slot()
    prog = nustd.kv.ProgramRef.slot()
    fabrics = nustd.kv.PrimitiveListRef.slot()
    version = nustd.kv.IntRef.slot()
    plane = nustd.kv.StrRef.slot()
    spec = nustd.kv.StrRef.slot()
    meta = nustd.kv.DictRef.slot(object)
    created_at = nustd.kv.FloatRef.slot()
    modified_at = nustd.kv.FloatRef.slot()
    removed_at = nustd.kv.FloatRef.slot()
    removed_by = nustd.kv.StrRef.slot()
