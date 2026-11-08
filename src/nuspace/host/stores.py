"""The stores' fixed containers, made real once at open.

A container never written is absent, and reading one (its length, its
keys, whether it holds an id) raises. The top level of both stores is fixed
by their root shapes, so each container there is created up front, before
anything reads it. ``init`` writes only where one is missing, so this is
safe on every open of an existing space. A plane's or a cell's own
containers are made with the row, by the op that adds it.
"""

from __future__ import annotations

import nu
from nuspace.shapes import Space, States

from .utils import atomic, atomic_state


__all__ = ["init_stores"]


def _space() -> nu.Nu:
    """Space's top level: structure, devices, the space's own state, the kernel's indexes."""
    return (
        Space.planes.init(nu.Dict.create())
        >> Space.cells.init(nu.Dict.create())
        >> Space.top.init(nu.List.create())
        >> Space.pinned.init(nu.List.create())
        >> Space.connections.init(nu.Dict.create())
        >> Space.state.recents.init(nu.List.create())
        >> Space.state.made.init(nu.Dict.create())
        >> Space.kernel.runs.init(nu.Dict.create())
        >> Space.kernel.running.init(nu.Set.create())
        >> Space.kernel.workers.init(nu.Dict.create())
        >> Space.kernel.workers_running.init(nu.Set.create())
        >> Space.kernel.planes_running.init(nu.Dict.create())
    )


def _states() -> nu.Nu:
    """States' top level: every plane's state, every cell's, every kind's items."""
    return (
        States.planes.init(nu.Dict.create())
        >> States.cells.init(nu.Dict.create())
        >> States.contents.init(nu.Dict.create())
    )


def init_stores() -> nu.Nu:
    """Every fixed top level container of both stores, made where missing. Two commits, Space first."""
    return atomic(_space()) >> atomic_state(_states())
