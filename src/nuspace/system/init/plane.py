"""init: pid 1. Runs the planes its boot list names, once, at open.

The kernel starts this and nothing else. What else runs at boot is data, in
this cell's own state (:class:`Boot`), edited with :func:`boot` and
:func:`unboot` from anywhere. Each plane gets a plane run of its own,
``by`` init, on the backend the plane names, unless it is live already:
something may bring a plane up before init reaches it (``enable_react``
starts the reactions plane when it finds it down), and a second run would
run its cells twice. The check and the start are one commit.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops.kernel import add_plane_run
from nuspace.ops.utils import MintId, atomic, atomic_state, listed
from nuspace.shapes import CellState, Space, reroot

from ..utils import snap


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
CELL = "init_main"

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
    """Set init's boot list to ``planes`` if it has none yet. Unbracketed."""
    return _here(Boot.planes.init(list(planes)))


def boot(plane_id: nu.StrArg) -> nu.Nu:
    """Add a plane to init's boot list. A no-op when it is listed already.

    A store with no list yet gets :data:`BOOTED` first. Takes effect at the
    next open: init reads its list once.
    """
    planes = Boot.planes
    return atomic_state(
        seed(list(BOOTED))
        >> _here(nu.IfDo(planes.contains(plane_id).not_(), planes.append(plane_id)))
    )


def unboot(plane_id: nu.StrArg) -> nu.Nu:
    """Take a plane off init's boot list. A no-op when it is not listed, or there is no list yet.

    The list is written by the first :func:`boot` or open, so a store that
    had neither has none to take from.
    """
    planes = Boot.planes
    return atomic_state(_here(nu.IfDo(planes.exists(), planes.remove(plane_id, missing_ok=True))))


def booted() -> nu.List:
    """The boot list, from anywhere. Bare read, ``[]`` when there is none."""
    return nu.list(_here(listed(Boot.planes)))


def program() -> nu.Nu:
    """Every listed plane that exists and is down, run. Then parked: pid 1 never returns."""
    running = Space.kernel.planes_running

    def up(at: nu.Attr) -> nu.Nu:
        plane = nu.Str(at)
        # A plane's entry is there only while it has live runs. No run is
        # written for a plane that does not exist.
        down = running.contains(plane).not_()
        return nu.let(
            MintId("r"), lambda rid: atomic(nu.IfDo(down, add_plane_run(nu.Str(rid), plane, by=BY)))
        )

    return nu.ForEachDo(snap(nu.list(Boot.planes)), up) >> nu.Park()
