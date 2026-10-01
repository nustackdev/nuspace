"""init: pid 1. Runs the planes its boot list names, once, at open.

The kernel starts this and nothing else. What else runs at boot is data, in
this cell's own state (:class:`Boot`), edited with :func:`boot` and
:func:`unboot` from anywhere. Each plane gets a plane run of its own,
``by`` init, on the backend the plane names.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import plane_exists, plane_run
from nuspace.ops.utils import atomic_state
from nuspace.shapes import CellState, States, reroot

from ..utils import park, snap


__all__ = [
    "BOOTED",
    "BY",
    "CELL",
    "PLANE",
    "SHIM",
    "Boot",
    "boot",
    "booted",
    "program",
    "seed",
    "unboot",
]


#: The plane id, fixed (D31).
PLANE = "init"

#: The one cell on the plane.
CELL = "main"

#: What plane runs init starts are recorded as ``by``.
BY = "init"

#: The cell's prog: the code lives here, the store holds this (D20).
SHIM = """\
from nuspace.system.services import init


def out():
    return init.program()
"""

#: What the boot list starts as: every other service (nav, supervisor, reload, reactions).
#: Seeded by whichever comes first, bootstrap or :func:`boot`, so booting a
#: plane before the first open does not leave the services out.
BOOTED = ("nav", "supervisor", "reload", "reactions")


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
    listed = States.planes[PLANE].cells[CELL].contains("planes")
    return nu.IfDo(listed.not_(), _here(Boot.planes.set(list(planes))))


def boot(plane_id: nu.StrArg) -> nu.Nu:
    """Add a plane to init's boot list. A no-op when it is listed already.

    A store with no list yet gets :data:`BOOTED` first. Takes effect at the
    next open: init reads its list once.
    """
    listed = Boot.planes
    return atomic_state(
        seed(list(BOOTED))
        >> _here(nu.IfDo(listed.contains(plane_id).not_(), listed.append(plane_id)))
    )


def unboot(plane_id: nu.StrArg) -> nu.Nu:
    """Take a plane off init's boot list. A no-op when it is not listed."""
    return atomic_state(_here(Boot.planes.remove(plane_id, missing_ok=True)))


def booted() -> nu.List:
    """The boot list, from anywhere. Bare read, ``[]`` when there is none."""
    return nu.list(_here(Boot.planes))


def program() -> nu.Nu:
    """Every listed plane that exists, run. Then parked."""

    def up(at: nu.Attr) -> nu.Nu:
        plane = nu.Str(at)
        return nu.IfDo(snap(plane_exists(plane)), plane_run(plane, by=BY))

    return nu.ForEachDo(snap(nu.list(Boot.planes)), up) >> park()
