"""Which Planes are up.

The main process reads the Space and runs what it finds, and hosts none of it:
every Cell is in a worker, and what stays here is one arm per Plane deciding
whether that Plane should be running and putting it where :mod:`nuspace.exec.plane`
says.

Every Plane gets an arm, running or not. A Plane whose ``trigger`` is not one
this runtime brings up sits idle, watching its own props, so the moment
somebody changes the trigger the arm re-enters and the Plane starts. An arm
that is not running costs a parked task and nothing else, which is a great deal
cheaper than the fold re-reading every Plane's props on every write in the
Space.

:func:`run_space` is the whole main process runtime as one term. Give it to
``arun`` inside :func:`nuspace.space.open_space` and the Space runs. Drive it
with ``max_parallel=1``: nothing here computes, every branch is an await, and
a larger budget rations the ``Race`` in each arm against a semaphore that
those arms never give back.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.exec.plane import PLANE_ATTR, run_plane
from nuspace.exec.utils import prop, reenters_on
from nuspace.shapes import DEFAULT_TRIGGER, TRIGGER_BOOT, Space


__all__ = [
    "BOOT_TRIGGERS",
    "plane_arm",
    "planes_fold",
    "run_space",
]


#: What a headless runtime brings up on its own. ``manual`` waits to be asked
#: and ``nav`` is per browser connection, so neither is up because a process
#: opened the Space.
BOOT_TRIGGERS = (TRIGGER_BOOT,)


def planes_fold(arm: nu.Nu, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """One live ``arm`` per Plane in the Space, births and deaths included.

    The subscription is length exact, so this fires when a Plane is added or
    removed and at no other time. A Plane changing is its own arm's business,
    and a Cell changing is two levels down from here.

    Args:
        arm: the body one Plane gets.
        root: the Space shape class.
    """
    # nu.list is load bearing: a keys view is lazy and the atomicity pass
    # brackets the items slot separately, so an undrained view outlives its
    # snapshot and dies reading closed storage.
    return nu.ForEachParReactive(
        nu.list(root.planes.keys()),
        root.planes.on_children_change(),
        arm,
        PLANE_ATTR,
    )


def plane_arm(
    *,
    triggers: tuple[str, ...] = BOOT_TRIGGERS,
    root: type[nu.Shape] = Space,
) -> nu.Nu:
    """One Plane, up if its ``trigger`` says so, re-read whenever its props move.

    The subscription is on ``props`` and nothing wider. A Plane's Cells live
    inside the Plane, so a depth unbounded watch here would restart every Cell
    on the Plane on every keystroke in any one of them.

    Args:
        triggers: the triggers this runtime brings up. A Plane whose trigger
            is not one of them parks.
        root: the Space shape class.
    """
    plane = nu.StrAttrRef(PLANE_ATTR)
    props = root.planes[plane].props
    wanted = [nu.Eq(prop(props.trigger, DEFAULT_TRIGGER), nu.Str(t)) for t in triggers]
    if not wanted:
        up = nu.Bool(False)
    else:
        up = wanted[0] if len(wanted) == 1 else nu.Or(*wanted)
    return reenters_on(props.on_change(), nu.IfDo(up, run_plane(plane, root=root)))


def run_space(
    *,
    triggers: tuple[str, ...] = BOOT_TRIGGERS,
    root: type[nu.Shape] = Space,
) -> nu.Nu:
    """The Space running, as the one term the main process drives.

    No bracket head: the store, the pool and the sockets come from the
    Context this is run in, which is :func:`nuspace.space.open_space`. Runs
    until cancelled, and the brackets around it reap the fleet on the way out.

    The Plane container is made real first. A subscription over a container
    that is not there resolves to INVALID and silently never fires, so the
    fold makes its own precondition true rather than trusting that somebody
    wrote a Plane before this started.

    Args:
        triggers: the triggers this runtime brings up.
        root: the Space shape class, which is also the store's tag.

    Returns:
        The tree, already bracketed for atomicity against ``root``.
    """
    return nustd.kv.auto_flow_atomic(
        root.planes.init(nu.Dict.create())
        >> planes_fold(plane_arm(triggers=triggers, root=root), root=root),
        scope=root,
    )
