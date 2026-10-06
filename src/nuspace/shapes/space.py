"""Space: the world. What you open."""

from __future__ import annotations

import nu
import nustd.kv

from .cell import Cell
from .connection import Connection
from .kernel import Kernel
from .plane import Plane


__all__ = ["RECENTS_CAP", "Space", "SpaceInfo", "SpaceSettings", "SpaceState"]


#: How many plane ids ``SpaceState.recents`` keeps.
RECENTS_CAP = 20


class SpaceInfo(nu.Shape):
    """What the host says about the space it opened. Written once per open.

    ``path`` is the space directory, ``""`` for a throwaway one. ``opened``
    is when this open started, in seconds since the epoch. ``versions`` maps
    a package name (``nuspace``, and ``nuverse`` when installed) to its
    installed version.
    """

    path = nustd.kv.StrRef.slot()
    opened = nustd.kv.FloatRef.slot()
    versions = nustd.kv.DictRef.slot(str)


class SpaceState(nu.Shape):
    """Space wide state: things about the space as a whole, not one plane.

    ``recents`` is the plane ids opened in a tab, newest first, deduped and
    capped at :data:`RECENTS_CAP`, written whole (D24) by the web device.
    ``info`` is written by the host at open.
    """

    recents = nustd.kv.PrimitiveListRef.slot()
    info = nustd.kv.ShapeRef.slot(SpaceInfo)


class SpaceSettings(nu.Shape):
    """The space's own settings, written from the settings plane. Unset reads as off.

    ``telemetry`` is whether the space may share anonymous usage data.
    Nothing reads it yet: it is wired to telemetry once there is some.

    Space level only: what belongs to one device or browser, eg its theme,
    stays there and never lands in the store.
    """

    telemetry = nustd.kv.BoolRef.slot()


class Space(nu.Shape):
    """Planes, their cells, the top level, the kernel's records, device and space state.

    ``planes`` and ``cells`` are flat, so a plane or a cell is one lookup
    away by its id alone. A plane lists its cell ids in order, a cell names
    its plane. Nesting is on the planes too: a plane lists its children and
    names its parent. ``top`` lists the planes with no parent, in order.

    One writer per subtree: people, cells and services write ``planes``,
    ``cells`` and ``top`` through ops, the ops write intents into ``kernel`` and the
    kernel and the backends its effects, the web device writes
    ``connections`` and ``state.recents``, the host writes ``state.info``,
    the settings plane writes ``settings``.

    ``pinned`` is the plane ids pinned to the top of the sidebar, in order,
    written through the pin ops. A pin is a shortcut: the plane stays where
    it hangs.

    ``Space`` is also the store's tag. kv refs find their navigator by root
    shape class, so the store is bound under this class. Program state is
    not here: it lives in the other store, under
    :class:`~nuspace.shapes.states.States`.
    """

    planes = nustd.kv.DictRef.slot(Plane)
    cells = nustd.kv.DictRef.slot(Cell)
    top = nustd.kv.ListRef.slot(str)
    kernel = nustd.kv.ShapeRef.slot(Kernel)
    connections = nustd.kv.DictRef.slot(Connection)
    state = nustd.kv.ShapeRef.slot(SpaceState)
    settings = nustd.kv.ShapeRef.slot(SpaceSettings)
    pinned = nustd.kv.ListRef.slot(str)
