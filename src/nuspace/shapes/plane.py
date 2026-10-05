"""Plane: a named, ordered group of cells."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Plane", "PlaneProps"]


class PlaneProps(nu.Shape):
    """What nuspace itself reads off a plane to work. Typed, unlike ``meta``.

    ``system`` marks a protected plane, eg a service or home:
    ``remove_plane`` refuses it, and that is all it means. ``ui`` says the
    shell draws it, and nav brings a routed plane up iff it is set.
    ``made_by`` names the registered Plane it was created from (``""`` for
    none). A record, nothing groups by it. ``backend`` names the backend its
    runs execute on, as registered at open. There is no default: whoever
    makes a plane names one, and a run of a plane with none fails. The one
    run setting a plane holds.
    """

    system = nustd.kv.BoolRef.slot()
    ui = nustd.kv.BoolRef.slot()
    made_by = nustd.kv.StrRef.slot()
    backend = nustd.kv.StrRef.slot()


class Plane(nu.Shape):
    """A group of cells, the runnable thing. How it runs is its ``backend`` prop only.

    ``cells`` is its cell ids, in order: membership and order in one list,
    so rearranging them is one write that touches no cell. The cells
    themselves are in ``Space.cells``, each pointing back here through its
    ``plane``. Nesting is not here either: it is a relation between planes
    and lives in ``Space.tree``.

    ``props`` is what nuspace reads to work (:class:`PlaneProps`). ``meta``
    is free, for anything else, eg a ui plane's ``editable`` and
    ``full_width``.

    The state its cells share is not here: it lives in the state store, at
    ``States.planes[p].state`` (:mod:`nuspace.shapes.states`).
    """

    name = nustd.kv.StrRef.slot()
    props = nustd.kv.ShapeRef.slot(PlaneProps)
    meta = nustd.kv.DictRef.slot(object)
    cells = nustd.kv.ListRef.slot(str)
