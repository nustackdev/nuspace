"""State ops: reach another cell's or plane's state, wipe state.

A program names its state bare and the kernel lands it in the States
store, under the cell running it. :func:`sibling` lands it under another
cell of the same plane instead, so two cells meet without either knowing
the store's layout. :func:`cell_state` and :func:`plane_state` land it under
any plane's, for a reader that is not on that plane (eg a search).
"""

from __future__ import annotations

import nu
from nuspace.shapes import CellState, PlaneState, States, reroot_base

from .kernel import Here
from .read import cell_exists, plane_exists
from .utils import atomic_state


__all__ = [
    "CellState",
    "PlaneState",
    "cell_state",
    "clear_state",
    "drop_cell_state",
    "drop_plane_state",
    "plane_state",
    "sibling",
]


def sibling(cell_id: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` with its ``CellState`` chains landing under a sibling cell.

    The sibling is ``cell_id`` in the plane of the run evaluating this: the
    plane is read from :attr:`~nuspace.ops.kernel.Here.plane`, which the
    kernel declares inside every run. Rerooted here, the chains no longer root
    at ``CellState``, so the kernel's own reroot leaves them alone.
    ``PlaneState`` chains are untouched and land at the shared plane state.

    Bare, like any state read: it routes to the States store, so the
    bracket around it names :class:`~nuspace.shapes.States` (the kernel's
    own pass does, inside a run).

    Args:
        cell_id: The sibling's id. Ids, not names: names are not unique.
        term: What to read or write there, eg ``Tick.n``.
    """
    return cell_state(Here.plane, cell_id, term)


def cell_state(plane_id: nu.StrArg, cell_id: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` with its ``CellState`` chains landing under any plane's cell.

    :func:`sibling` for a cell on another plane. Bare, and routed to the
    States store, as :func:`sibling` is.

    Args:
        plane_id: The cell's plane.
        cell_id: The cell.
        term: What to read or write there, eg ``Doc.text``.
    """
    return reroot_base(term, CellState, States.planes[plane_id].cells[cell_id])


def plane_state(plane_id: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` with its ``PlaneState`` chains landing under any plane's shared state.

    What a plane's own cells reach bare, reached from outside it: by an op
    that seeds a plane's state, or a cell showing another plane's. Rerooted
    here, the chains no longer root at ``PlaneState``, so the kernel's own
    reroot leaves them alone. Bare, and routed to the States store.

    Args:
        plane_id: The plane.
        term: What to read or write there, eg ``Search.hits``.
    """
    return reroot_base(term, PlaneState, States.planes[plane_id].state)


def clear_state(plane_id: nu.StrArg, cell_id: nu.StrArg | None = None) -> nu.Nu:
    """Wipe a cell's state, or the plane's shared state when ``cell_id`` is None.

    A person's op, not a step in a restart: a cell coming back is meant to
    find what it left. A no-op when the plane or cell is missing. One commit
    on the States store: whether the plane or cell is there is read from a
    Space snapshot.
    """
    plane = States.planes[plane_id]
    if cell_id is None:
        wipe = nu.IfDo(plane.contains("state"), plane.state.clear())
        there = plane_exists(plane_id)
    else:
        wipe = nu.IfDo(plane.cells.contains(cell_id), plane.cells.del_item(cell_id))
        there = cell_exists(plane_id, cell_id)
    # Asked first: a write under a plane the store holds nothing for makes its row, empty.
    return atomic_state(nu.IfDo(there, nu.IfDo(States.planes.contains(plane_id), wipe)))


def drop_cell_state(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A cell gone from Space, its state deleted. No bracket: run it in :func:`atomic_state`.

    Asks Space first and leaves the state of a cell that is there, so run
    after the commit that removed it, a cell given the same id again in
    between keeps what it has. One delete of the cell's subtree.
    """
    cells = States.planes[plane_id].cells
    gone = nu.Not(cell_exists(plane_id, cell_id))
    held = nu.IfDo(cells.contains(cell_id), cells.del_item(cell_id))
    return nu.IfDo(nu.And(gone, States.planes.contains(plane_id)), held)


def drop_plane_state(plane_id: nu.StrArg) -> nu.Nu:
    """A plane gone from Space, its state and all its cells' deleted. No bracket.

    Leaves a plane that is there alone, as :func:`drop_cell_state` does a
    cell. One delete of the plane's subtree.
    """
    planes = States.planes
    gone = nu.Not(plane_exists(plane_id))
    return nu.IfDo(nu.And(gone, planes.contains(plane_id)), planes.del_item(plane_id))
