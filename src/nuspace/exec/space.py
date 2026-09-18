"""Folding the Planes in a Space.

The main process reads the Space and runs what it finds, and hosts none of
it: every Cell is in a worker, and what stays here is one arm per Plane
putting that Plane where :mod:`nuspace.exec.plane` says.

Every Plane gets an arm, running or not. Whether a Plane should be up is a
driver's call and arrives as a predicate, so an arm whose answer is no sits
idle watching its own props, and the moment somebody changes them the arm
re-enters and the Plane starts. An arm that is not running costs a parked
task and nothing else, which is a great deal cheaper than the fold re-reading
every Plane's props on every write in the Space.

Both of these are combinators. Nothing here runs on its own and nothing here
decides anything: a driver picks the predicate and drives the fold.
:mod:`nuspace.drivers.headless` is the one that answers with ``trigger``.
"""

from __future__ import annotations

import nu
from nuspace.exec.plane import PLANE_ATTR, run_plane
from nuspace.exec.utils import reenters_on
from nuspace.shapes import Space


__all__ = [
    "plane_arm",
    "planes_fold",
]


def planes_fold(arm: nu.Nu, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """One live ``arm`` per Plane in the Space, births and deaths included.

    The subscription is length exact, so this fires when a Plane is added or
    removed and at no other time. A Plane changing is its own arm's business,
    and a Cell changing is two levels down from here.

    The Plane container is made real first. A subscription over a container
    that is not there resolves to INVALID and silently never fires, so the
    fold makes its own precondition true rather than trusting that somebody
    wrote a Plane before this started.

    Args:
        arm: the body one Plane gets.
        root: the Space shape class.
    """
    # nu.list is load bearing: a keys view is lazy and the atomicity pass
    # brackets the items slot separately, so an undrained view outlives its
    # snapshot and dies reading closed storage.
    return root.planes.init(nu.Dict.create()) >> nu.ForEachParReactive(
        nu.list(root.planes.keys()),
        root.planes.on_children_change(),
        arm,
        PLANE_ATTR,
    )


def plane_arm(up: nu.Nu, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """One Plane, running while ``up`` says so, re-read whenever its props move.

    The subscription is on ``props`` and nothing wider. A Plane's Cells live
    inside the Plane, so a depth unbounded watch here would restart every Cell
    on the Plane on every keystroke in any one of them.

    Args:
        up: whether this Plane should be running, as a term read per turn
            against the Plane the fold bound under :data:`PLANE_ATTR`. False
            parks the arm, which keeps it watching for the answer to change.
        root: the Space shape class.
    """
    plane = nu.StrAttrRef(PLANE_ATTR)
    props = root.planes[plane].props
    return reenters_on(props.on_change(), nu.IfDo(up, run_plane(plane, root=root)))
