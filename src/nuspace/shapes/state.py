"""Program declared state: the two bases a cell's shapes say whose they are by.

A program names its state as if it were alone::

    class Tick(CellState):
        n = nustd.kv.IntRef.slot()

    def out():
        return Tick.n.set(Tick.n + 1)

``Tick.n`` resolves bare, at ``("n",)``, under a root shape nobody binds. The
kernel reroots it at load (:mod:`nuspace.shapes.reroot`), so it lands under
the cell that runs it and the store never learns a program's classes. The
base is the whole address: which one a shape subclasses is the only thing
the rerooter asks.
"""

from __future__ import annotations

import nu


__all__ = ["CellState", "PlaneState"]


class CellState(nu.Shape):
    """Base for state owned by one cell. Lands at ``planes[p].cells[c].state``.

    Only the cell's own program writes it. Persistent and shared by every run
    of the cell, so a restart picks up where the last run left off.
    """


class PlaneState(nu.Shape):
    """Base for state shared by a plane's cells. Lands at ``planes[p].state``.

    Where siblings meet: every cell of the plane that declares the same shape
    reads and writes the same slots.
    """
