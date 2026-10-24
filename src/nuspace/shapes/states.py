"""States: the state store, where program declared state lives. Apart from Space.

A space keeps two stores. Space holds what the space is (planes, cells,
nesting, runs); States holds what the programs remember::

    States
      planes          id -> PlaneStates
        <p>
          state       PlaneState shapes, rerooted here
      cells           id -> CellStates
        <c>           CellState shapes, rerooted here
      contents        kind name -> KindContents, every item, by kind and scope

Keyed by the same ids as ``Space.planes`` and ``Space.cells``, and nothing
else: no names, no progs, no run info. ``contents`` is the one exception
to keying by id first: an item is found by its kind, then its scope
(:mod:`nuspace.shapes.contents`). Flat as Space is, so a cell's state
is one lookup away by its id, wherever the cell sits. A plane's own state
sits in ``state`` rather than at the plane's row, so the row can grow
without a state field ever sharing a key. Dropping a plane's state or a
cell's is one delete of its subtree.

``States`` is also this store's tag, as ``Space`` is the other's: a
rerooted chain picks it up and routes to this store's navigator, and a
bracket names it to open a snapshot or a transaction here.
"""

from __future__ import annotations

import nu
import nustd.kv

from .contents import KindContents


__all__ = ["CellStates", "PlaneStates", "States"]


class CellStates(nu.Shape):
    """One cell's state. No slots of its own: the program's ``CellState`` shapes fill it."""


class PlaneStates(nu.Shape):
    """One plane's state, shared by its cells in ``state``."""

    state = nustd.kv.DictRef.slot(object)


class States(nu.Shape):
    """The state store's root: every plane's state and every cell's, by id.

    Written by programs, through their rerooted ``CellState`` and
    ``PlaneState`` slots and their kinds' items, and by the ops that drop a
    plane or cell after its structure.
    """

    planes = nustd.kv.DictRef.slot(PlaneStates)
    cells = nustd.kv.DictRef.slot(CellStates)
    contents = nustd.kv.DictRef.slot(KindContents)
