"""init's own state: the plane's id and the boot list, kept in the init plane's state."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.places import at


__all__ = ["PLANE", "Boot", "boot_list"]


#: The plane's id, fixed.
PLANE = "init"


class Boot(nu.Shape):
    """init's state, at ``State.planes["init"]``.

    ``planes`` is the boot list: the ids of the planes init runs at every
    open, a set (dict of bool, point add and delete). Reach it through the
    plane's place: ``nuspace.at.plane(id=init.PLANE).state(Boot).planes``.
    """

    planes = nustd.kv.DictRef.slot(bool)


def boot_list() -> nu.Nu:
    """The boot list's ref: ``State.planes["init"]`` read through :class:`Boot`."""
    return at.plane(id=PLANE).state(Boot).planes
