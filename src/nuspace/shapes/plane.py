"""Plane: a named group of cells, their order and the state they share."""

from __future__ import annotations

import nu
import nustd.kv

from .cell import Cell


__all__ = ["Plane", "PlaneProps"]


class PlaneProps(nu.Shape):
    """What nuspace itself reads off a plane to work. Typed, unlike ``meta``.

    ``system`` marks a protected plane, eg a service: ``remove_plane``
    refuses it and nav never brings it up. ``ui`` says the shell draws it,
    and ``made_by`` names the app that made it, the sidebar section it is
    listed under.
    """

    system = nustd.kv.BoolRef.slot()
    ui = nustd.kv.BoolRef.slot()
    made_by = nustd.kv.StrRef.slot()


class Plane(nu.Shape):
    """A group of cells. No execution semantics.

    ``order`` sits beside ``cells`` rather than inside a cell, so rearranging
    them is one write that touches no cell. Nesting is not here either: it is
    a relation between planes and lives in ``Space.tree``.

    ``props`` is what nuspace reads to work (:class:`PlaneProps`). ``meta``
    is free, for anything else, eg a ui plane's ``editable`` and
    ``full_width``.

    ``state`` is shared by the plane's cells, shaped by their
    :class:`~nuspace.shapes.state.PlaneState` classes.
    """

    name = nustd.kv.StrRef.slot()
    props = nustd.kv.ShapeRef.slot(PlaneProps)
    meta = nustd.kv.DictRef.slot(object)
    state = nustd.kv.DictRef.slot(object)
    cells = nustd.kv.ShapesDictRef.slot(Cell)
    order = nustd.kv.ListRef.slot(str)
