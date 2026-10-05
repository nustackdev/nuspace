"""State ops: reach another cell's or plane's state, wipe state.

A program names its state bare and the kernel lands it in the States
store, under the cell running it. :func:`sibling` lands it under another
cell of the same plane instead, so two cells meet without either knowing
the store's layout. :func:`cell_state` and :func:`plane_state` land it under
any plane's, for a reader that is not on that plane (eg a search).
:func:`bracketed` lands a whole term under the running cell and brackets it,
for an author who wants the brackets placed for them.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.shapes import CellState, PlaneState, Space, States, reroot, reroot_base

from .kernel import Here
from .read import cell_exists, plane_exists
from .utils import atomic_state


__all__ = [
    "CellState",
    "PlaneState",
    "bracketed",
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
    kernel holds in a frame around every run. Rerooted here, the chains no longer root
    at ``CellState``, so the kernel's own reroot leaves them alone.
    ``PlaneState`` chains are untouched and land at the shared plane state.

    Bare, like any state read: it routes to the States store, so the
    bracket its caller puts around it names :class:`~nuspace.shapes.States`
    (eg :func:`~.utils.atomic_state`, :func:`~.utils.snapshot`).

    Args:
        cell_id: The sibling's id. Ids, not names: names are not unique.
        term: What to read or write there, eg ``Tick.n``.
    """
    return cell_state(Here.plane, cell_id, term)


def cell_state(plane_id: nu.StrArg, cell_id: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` with its ``CellState`` chains landing under any plane's cell.

    :func:`sibling` for a cell on another plane. Bare, and routed to the
    States store, as :func:`sibling` is: its caller brackets it.

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
    reroot leaves them alone. Bare, and routed to the States store: its
    caller brackets it.

    Args:
        plane_id: The plane.
        term: What to read or write there, eg ``Search.hits``.
    """
    return reroot_base(term, PlaneState, States.planes[plane_id].state)


def bracketed(term: nu.Nu) -> nu.Nu:
    """``term`` landed under the running cell, with a bracket placed around each store access.

    The hands-off way to follow the bracket rule (see :mod:`nuspace.ops.utils`):
    an author wraps a cell's whole ``out()`` in it and writes the rest bare.
    Its state chains are rerooted under the running cell first, through
    :class:`~nuspace.ops.kernel.Here` as :func:`sibling` does, so they belong to
    States before the brackets are placed; the kernel's own reroot then leaves
    them alone. Then one pass per store, Space and then States, puts a
    snapshot around each Flow branch that reads and a transaction around each
    one that writes. Brackets already in the term, an op's own included, are
    kept and looked into, never doubled.

    Each branch of a Flow is bracketed on its own, so a loop, a wait or a
    subscription gets a bracket per step and never one around itself. A
    wrapper that is not a Flow (eg ``Frame``, ``let``, ``With``, ``TryCatch``,
    ``Timeout``) and reads a store outside its Flow branches gets one bracket
    around all of it, so one that holds a loop, a wait or an ``Eval`` holds
    that bracket for as long as they run. Code shaped like that brackets by
    hand, with :func:`~.utils.atomic_state` and :func:`~.utils.snapshot`.

    Only inside a cell run, where :class:`~nuspace.ops.kernel.Here` is held.

    Args:
        term: What the cell runs, eg the body of ``out()``.
    """
    landed = reroot(term, Here.plane, Here.cell)
    return nustd.kv.auto_flow_atomic(nustd.kv.auto_flow_atomic(landed, scope=Space), scope=States)


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
    return nu.IfDo(
        cell_exists(plane_id, cell_id).not_().and_(States.planes.contains(plane_id)),
        nu.IfDo(cells.contains(cell_id), cells.del_item(cell_id)),
    )


def drop_plane_state(plane_id: nu.StrArg) -> nu.Nu:
    """A plane gone from Space, its state and all its cells' deleted. No bracket.

    Leaves a plane that is there alone, as :func:`drop_cell_state` does a
    cell. One delete of the plane's subtree.
    """
    planes = States.planes
    return nu.IfDo(
        plane_exists(plane_id).not_().and_(planes.contains(plane_id)), planes.del_item(plane_id)
    )
