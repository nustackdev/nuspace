"""States: the state store, where program declared state lives. Apart from Space.

A space keeps two stores. Space holds what the space is (planes, cells,
tree, runs); States holds what the programs remember::

    States
      planes          id -> PlaneStates
        <p>
          state       PlaneState shapes, rerooted here
          cells       id -> CellStates
            <c>       CellState shapes, rerooted here

Keyed by the same plane and cell ids as ``Space.planes``, and nothing else:
no names, no progs, no run info. A plane's own state sits in ``state``
beside ``cells`` rather than next to the cell ids, so a state field and a
cell id never share a key. Dropping a plane's states or a cell's is one
delete of its subtree.

``States`` is also this store's tag, as ``Space`` is the other's: a
rerooted chain picks it up and routes to this store's navigator, and a
bracket names it to open a snapshot or a transaction here.
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["CellStates", "PlaneStates", "States"]


class CellStates(nu.Shape):
    """One cell's state. No slots of its own: the program's ``CellState`` shapes fill it."""


class PlaneStates(nu.Shape):
    """One plane's state: shared by its cells in ``state``, each cell's own under ``cells``."""

    state = nustd.kv.DictRef.slot(object)
    cells = nustd.kv.ShapesDictRef.slot(CellStates)


class States(nu.Shape):
    """The state store's root: every plane's state, by plane id.

    Written by programs, through their rerooted ``CellState`` and
    ``PlaneState`` slots, and by the ops that drop or move a plane or cell
    after its structure.
    """

    planes = nustd.kv.ShapesDictRef.slot(PlaneStates)
