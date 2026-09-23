"""Plane: a named group of cells, their order and the state they share."""

from __future__ import annotations

import nu
import nustd.kv

from .cell import Cell


__all__ = ["Plane"]


class Plane(nu.Shape):
    """A group of cells. No execution semantics.

    ``order`` sits beside ``cells`` rather than inside a cell, so rearranging
    them is one write that touches no cell. Nesting is not here either: it is
    a relation between planes and lives in ``Space.tree``.

    ``system`` marks a protected plane, eg a service. ``remove_plane`` refuses
    it.

    ``state`` is shared by the plane's cells, shaped by their
    :class:`~nuspace.shapes.state.PlaneState` classes.
    """

    name = nustd.kv.StrRef.slot()
    system = nustd.kv.BoolRef.slot()
    meta = nustd.kv.DictRef.slot(object)
    state = nustd.kv.DictRef.slot(object)
    cells = nustd.kv.ShapesDictRef.slot(Cell)
    order = nustd.kv.ListRef.slot(str)
