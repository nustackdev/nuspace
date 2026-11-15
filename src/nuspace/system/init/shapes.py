"""init's own state: the plane's key and the boot list, kept in the init plane's state."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.places import at


__all__ = ["KEY", "Boot", "boot_list"]


#: The plane's key. Its id is minted when it is made; code finds it by this.
KEY = "init"


class Boot(nu.Shape):
    """init's state, in the init plane's state.

    ``planes`` is the boot list: the ids of the planes init runs at every
    open, a set (dict of bool, point add and delete). Reach it through the
    plane's place: ``nuspace.at.plane(init.KEY).state(Boot).planes``.
    """

    planes = nustd.kv.DictRef.slot(bool)


def boot_list(*, here: bool = False) -> nu.Nu:
    """The boot list's ref, found by key: one index read. ``here``: the running plane's, no read.

    ``here`` is for init's own cell; every other caller finds the plane by key.
    """
    return (at.plane if here else at.plane(KEY)).state(Boot).planes
