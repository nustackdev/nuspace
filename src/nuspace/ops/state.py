"""State ops: reach a sibling's state, wipe state.

A program names its state bare and the kernel lands it under the cell
running it. :func:`sibling` lands it under another cell of the same plane
instead, so two cells meet without either knowing the store's layout.
"""

from __future__ import annotations

import nu
from nuspace.shapes import CellState, PlaneState, Space, reroot_base

from .kernel import PLANE_ATTR
from .read import cell_exists, plane_exists
from .utils import atomic


__all__ = ["CellState", "PlaneState", "clear_state", "sibling"]


def sibling(cell_id: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` with its ``CellState`` chains landing under a sibling cell.

    The sibling is ``cell_id`` in the plane of the run evaluating this: the
    plane is read from :data:`~nuspace.ops.kernel.PLANE_ATTR`, which the
    kernel binds inside every run. Rerooted here, the chains no longer root
    at ``CellState``, so the kernel's own reroot leaves them alone.
    ``PlaneState`` chains are untouched and land at the shared plane state.

    Args:
        cell_id: The sibling's id. Ids, not names: names are not unique.
        term: What to read or write there, eg ``Tick.n``.
    """
    plane = nu.StrAttrRef(PLANE_ATTR)
    return reroot_base(term, CellState, Space.planes[plane].cells[cell_id].state)


def clear_state(plane_id: nu.StrArg, cell_id: nu.StrArg | None = None) -> nu.Nu:
    """Wipe a cell's state, or the plane's shared state when ``cell_id`` is None.

    A person's op, not a step in a restart: a cell coming back is meant to
    find what it left. A no-op when the plane or cell is missing.
    """
    plane = Space.planes[plane_id]
    if cell_id is None:
        return atomic(nu.IfDo(plane_exists(plane_id), plane.state.clear()))
    return atomic(nu.IfDo(cell_exists(plane_id, cell_id), plane.cells[cell_id].state.clear()))
