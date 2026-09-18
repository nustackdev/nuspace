"""A Space running because a process opened it, and drawing on nothing.

The simplest answer to when and what: every Plane whose ``trigger`` is one
this runtime brings up, and no browser behind any of them. One arm per Plane
either way, so a Plane whose trigger is changed while this is running starts
or stops without anything else moving.

:func:`run_space` is the whole main process runtime as one term. Give it to
``arun`` inside :func:`nuspace.space.open_space` and the Space runs. Drive it
with ``max_parallel=1``: nothing here computes, every branch is an await, and
a larger budget rations the ``Race`` in each arm against a semaphore that
those arms never give back.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.exec import PLANE_ATTR, plane_arm, planes_fold, prop
from nuspace.shapes import DEFAULT_TRIGGER, TRIGGER_BOOT, Space


__all__ = [
    "BOOT_TRIGGERS",
    "run_space",
    "triggered_by",
]


#: What a headless runtime brings up on its own. ``manual`` waits to be asked
#: and ``nav`` is per browser connection, so neither is up because a process
#: opened the Space.
BOOT_TRIGGERS = (TRIGGER_BOOT,)


def triggered_by(
    triggers: tuple[str, ...] = BOOT_TRIGGERS,
    *,
    root: type[nu.Shape] = Space,
) -> nu.Nu:
    """Whether this Plane's ``trigger`` is one of ``triggers``.

    Read against the Plane the fold bound under :data:`PLANE_ATTR`, so one
    term serves every arm, and read per turn, so changing a Plane's trigger
    brings it up or puts it down where it stands.

    Args:
        triggers: the triggers this runtime brings up. Empty brings up
            nothing, which is a runtime that holds the Space open and runs
            none of it.
        root: the Space shape class.
    """
    props = root.planes[nu.StrAttrRef(PLANE_ATTR)].props
    wanted = [nu.Eq(prop(props.trigger, DEFAULT_TRIGGER), nu.Str(t)) for t in triggers]
    if not wanted:
        return nu.Bool(False)
    return wanted[0] if len(wanted) == 1 else nu.Or(*wanted)


def run_space(
    *,
    triggers: tuple[str, ...] = BOOT_TRIGGERS,
    root: type[nu.Shape] = Space,
) -> nu.Nu:
    """The Space running headless, as the one term the main process drives.

    No bracket head: the store, the pool and the sockets come from the
    Context this is run in, which is :func:`nuspace.space.open_space`. Runs
    until cancelled, and the brackets around it reap the fleet on the way out.

    Args:
        triggers: the triggers this runtime brings up.
        root: the Space shape class, which is also the store's tag.

    Returns:
        The tree, already bracketed for atomicity against ``root``.
    """
    return nustd.kv.auto_flow_atomic(
        planes_fold(plane_arm(triggered_by(triggers, root=root), root=root), root=root),
        scope=root,
    )
