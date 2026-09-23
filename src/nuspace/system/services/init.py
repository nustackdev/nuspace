"""init: pid 1. Brings up the planes its boot list names, once, at open.

The kernel starts this and nothing else. What else runs at boot is data, in
this cell's own state (:class:`Boot`), edited with :func:`boot` and
:func:`unboot` from anywhere. Each plane gets a worker of its own.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import plane_exists, up_plane, worker
from nuspace.ops.utils import atomic
from nuspace.shapes import CellState, Space, reroot

from ..utils import park, snap


__all__ = ["BOOTED", "BY", "CELL", "PLANE", "SHIM", "Boot", "boot", "program", "seed", "unboot"]


#: The plane id, fixed (D31).
PLANE = "init"

#: The one cell on the plane.
CELL = "main"

#: What runs init starts are recorded as ``by``.
BY = "init"

#: The cell's prog: the code lives here, the store holds this (D20).
SHIM = """\
from nuspace.system.services import init


def out():
    return init.program()
"""

#: What the boot list starts as: every other service (nav, supervisor, reload).
#: Seeded by whichever comes first, bootstrap or :func:`boot`, so booting a
#: plane before the first open does not leave the services out.
BOOTED = ("nav", "supervisor", "reload")

_ITEM = "nuspace.init.plane"
_WORKER = "nuspace.init.worker"


class Boot(CellState):
    """init's state: the plane ids to bring up at open, in order."""

    planes = nustd.kv.ListRef.slot(str)


def _here(term: nu.Nu) -> nu.Nu:
    """``term`` with :class:`Boot` landing at init's own cell, for callers anywhere."""
    return reroot(term, PLANE, CELL)


def seed(planes: list[str]) -> nu.Nu:
    """Set init's boot list to ``planes`` if it has none yet. Unbracketed.

    Asks the cell's state for the key: a list that was never written reads
    as there and empty.
    """
    listed = Space.planes[PLANE].cells[CELL].state.contains("planes")
    return nu.IfDo(nu.Not(listed), _here(Boot.planes.set(nu.Literal(list(planes)))))


def boot(plane_id: nu.StrArg) -> nu.Nu:
    """Add a plane to init's boot list. A no-op when it is listed already.

    A store with no list yet gets :data:`BOOTED` first. Takes effect at the
    next open: init reads its list once.
    """
    listed = Boot.planes
    return atomic(
        seed(list(BOOTED))
        >> _here(nu.IfDo(nu.Not(listed.contains(plane_id)), listed.append(plane_id)))
    )


def unboot(plane_id: nu.StrArg) -> nu.Nu:
    """Take a plane off init's boot list. A no-op when it is not listed."""
    listed = Boot.planes
    return atomic(_here(nu.IfDo(listed.contains(plane_id), listed.remove(plane_id))))


def program() -> nu.Nu:
    """Every listed plane that exists, up on a worker of its own. Then parked."""
    plane = nu.StrAttrRef(_ITEM)
    start = nu.Let(_WORKER, worker(), up_plane(plane, worker=nu.StrAttrRef(_WORKER), by=BY))
    return (
        nu.ForEachDo(
            snap(nu.list(Boot.planes)),
            nu.IfDo(snap(plane_exists(plane)), start),
            item=_ITEM,
        )
        >> park()
    )
