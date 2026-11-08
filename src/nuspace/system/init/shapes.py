"""init's own state: the boot list, kept in the init plane's state."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Boot"]


class Boot(nu.Shape):
    """init's state, at ``State.planes["init"]``.

    ``planes`` is the boot list: the ids of the planes init runs at every
    open, a set (dict of bool, point add and delete). Reach it through the
    plane's place: ``nuspace.at.plane(id=init.PLANE).state(Boot).planes``.
    """

    planes = nustd.kv.DictRef.slot(bool)
